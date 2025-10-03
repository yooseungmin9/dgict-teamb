# youtube_api.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
from html import unescape
import os, requests, logging

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="YouTube Proxy API")

# 개발 중엔 * 로 두고, 운영에선 필요한 출처만 허용하세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# 🔐 환경변수 → 하드코딩 순으로 읽기(하드코딩은 지양)
_YT_FALLBACK = "AIzaSyDtsdmz204NoNAFBam4S3Fe_gNR4Sy_7Ko"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", _YT_FALLBACK).strip()

Y_SEARCH = "https://www.googleapis.com/youtube/v3/search"
Y_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
TIMEOUT = 10


def require_key():
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="Missing YOUTUBE_API_KEY")


def _extract_google_error_detail(resp: requests.Response) -> Dict[str, Any]:
    """Google API 에러 바디에서 핵심 정보를 뽑아 사람이 읽기 쉽게 가공"""
    try:
        j = resp.json()
    except Exception:
        return {"message": resp.text}

    detail: Dict[str, Any] = {
        "status_code": resp.status_code,
        "error": j.get("error", {}),
    }
    # 흔히 보는 필드들(reason/code/message) 평탄화
    err = j.get("error") or {}
    if isinstance(err, dict):
        detail["code"] = err.get("code")
        detail["message"] = err.get("message")
        errors = err.get("errors")
        if isinstance(errors, list) and errors:
            # 첫 번째 이유(reason)만 빼서 같이 보여줌
            detail["reason"] = errors[0].get("reason")
            detail["domain"] = errors[0].get("domain")
    return detail


def fetch_video_stats(video_ids: List[str]) -> dict:
    """videoId 리스트로 조회수/좋아요/댓글 수 가져오기"""
    if not video_ids:
        return {}
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "statistics",
        "id": ",".join(video_ids),
        # 쿼터 절약을 위해 fields 사용 가능(여기선 통계 전체가 필요해서 생략)
        # "fields": "items(id,statistics(viewCount,likeCount,commentCount))",
    }
    try:
        r = requests.get(Y_VIDEOS, params=params, timeout=TIMEOUT)
        if not r.ok:
            # 4xx/5xx를 그대로 기록
            log.error("YouTube stats API error: %s | body=%s", r.status_code, r.text)
            return {}
        payload = r.json()
    except requests.RequestException as e:
        log.error("YouTube stats API error: %s", e)
        return {}

    stats = {}
    for it in payload.get("items", []):
        vid = it.get("id")
        stat = it.get("statistics", {}) or {}
        stats[vid] = {
            "viewCount": stat.get("viewCount"),
            "likeCount": stat.get("likeCount"),
            "commentCount": stat.get("commentCount"),
        }
    return stats


@app.get("/healthz")
def healthz():
    return {"ok": True, "has_key": bool(YOUTUBE_API_KEY)}


@app.get("/healthz/youtube")
def healthz_youtube():
    """
    유튜브 API 실제 호출 헬스체크.
    - 초소량 요청(maxResults=1, fields로 최소 응답)을 날려 200/403 등 상태와 reason을 그대로 보여줌.
    """
    require_key()
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "type": "video",
        "q": "ping",             # 무해한 테스트 키워드
        "maxResults": 1,
        "safeSearch": "none",
        "fields": "items(id/videoId),nextPageToken",  # 쿼터 절약
    }
    try:
        r = requests.get(Y_SEARCH, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        # 네트워크/타임아웃 등 진짜 연결 실패만 502
        raise HTTPException(status_code=502, detail=f"Network error to YouTube: {e}")

    if r.ok:
        data = r.json()
        return {
            "ok": True,
            "status": r.status_code,
            "sample": data.get("items", []),
            "note": "YouTube Data API reachable and responding.",
        }

    # 4xx/5xx — 에러 이유(body) 그대로 출력
    detail = _extract_google_error_detail(r)
    raise HTTPException(status_code=r.status_code, detail=detail)


@app.get("/youtube/search")
def youtube_search(
    q: str = Query(..., min_length=1, description="검색어"),
    max_results: int = Query(8, ge=1, le=50),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    safe: str = Query("moderate", regex="^(none|moderate|strict)$"),
    _raw: int = 0,  # 디버그용: 원본 응답 포함 여부
) -> Dict[str, Any]:
    """
    YouTube Data API v3 proxy.
    - q: 검색어
    - max_results: 1~50
    - pageToken: 다음 페이지 토큰
    - safe: none|moderate|strict (검색 안전 필터)
    """
    require_key()

    # 1) 검색 (쿼터 절약: fields 지정 가능 — 썸네일/타이틀/채널 위주)
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "type": "video",
        "q": q,
        "maxResults": max_results,
        "safeSearch": safe,
        # "fields": "items(id/videoId,snippet(title,channelTitle,publishedAt,thumbnails/medium/url)),nextPageToken,prevPageToken",
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        r = requests.get(Y_SEARCH, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        # 네트워크성 오류만 502
        log.error("YouTube API network error: %s", e)
        raise HTTPException(status_code=502, detail=f"YouTube upstream network error: {e}")

    if not r.ok:
        # 🔴 중요한 변화: 4xx는 4xx 그대로 노출 (스프링에서 원인 분류 쉬움)
        detail = _extract_google_error_detail(r)
        log.error("YouTube API returned error: %s | detail=%s", r.status_code, detail)
        raise HTTPException(status_code=r.status_code, detail=detail)

    payload = r.json()

    # 2) 검색 결과 파싱 + 타이틀 HTML 엔티티 디코딩
    items: List[Dict[str, Any]] = []
    video_ids: List[str] = []
    for it in payload.get("items", []):
        idp = it.get("id", {}) or {}
        if idp.get("kind") != "youtube#video":
            continue
        vid = idp.get("videoId")
        video_ids.append(vid)
        sn = it.get("snippet", {}) or {}
        thumbs = sn.get("thumbnails") or {}
        # 썸네일 우선순위 선택
        thumb = (
            (thumbs.get("medium") or {}).get("url")
            or (thumbs.get("high") or {}).get("url")
            or (thumbs.get("default") or {}).get("url")
        )

        raw_title = sn.get("title") or ""
        raw_channel = sn.get("channelTitle") or ""

        items.append({
            "videoId": vid,
            "title": unescape(raw_title),
            "channelTitle": unescape(raw_channel),
            "publishedAt": sn.get("publishedAt"),
            "thumbnail": thumb,
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
        })

    # 3) 통계 붙이기 (실패해도 본문은 제공)
    stats = fetch_video_stats(video_ids)
    for it in items:
        it["statistics"] = stats.get(it["videoId"], {})

    out: Dict[str, Any] = {
        "count": len(items),
        "items": items,
        "nextPageToken": payload.get("nextPageToken"),
        "prevPageToken": payload.get("prevPageToken"),
    }
    if _raw == 1:
        out["_raw"] = payload
    return out
