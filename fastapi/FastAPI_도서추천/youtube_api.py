# youtube_api.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
from html import unescape
import os, requests, logging

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="YouTube Proxy API")

# 개발 중엔 * 로 두고, 운영에선 8081 등 필요한 출처만 허용하세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# 환경변수에서 API 키 읽기 (예: setx YOUTUBE_API_KEY "AIza..."):
YOUTUBE_API_KEY = "AIzaSyDtsdmz204NoNAFBam4S3Fe_gNR4Sy_7Ko"

Y_SEARCH = "https://www.googleapis.com/youtube/v3/search"
Y_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
TIMEOUT = 10


def require_key():
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="Missing YOUTUBE_API_KEY")


def fetch_video_stats(video_ids: List[str]) -> dict:
    """videoId 리스트로 조회수/좋아요/댓글 수 가져오기"""
    if not video_ids:
        return {}
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "statistics",
        "id": ",".join(video_ids),
    }
    try:
        r = requests.get(Y_VIDEOS, params=params, timeout=TIMEOUT)
        r.raise_for_status()
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

    # 1) 검색
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "type": "video",
        "q": q,
        "maxResults": max_results,
        "safeSearch": safe,
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        r = requests.get(Y_SEARCH, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        payload = r.json()
    except requests.RequestException as e:
        log.error("YouTube API error: %s", e)
        raise HTTPException(status_code=502, detail=f"YouTube upstream error: {e}")

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
        thumb = (thumbs.get("medium") or thumbs.get("default") or thumbs.get("high") or {}).get("url")

        raw_title = sn.get("title") or ""
        raw_channel = sn.get("channelTitle") or ""

        items.append({
            "videoId": vid,
            "title": unescape(raw_title),               # ← "&quot;" 등 디코딩
            "channelTitle": unescape(raw_channel),      # (옵션) 채널명도 디코딩
            "publishedAt": sn.get("publishedAt"),
            "thumbnail": thumb,
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
        })

    # 3) 통계 붙이기
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
