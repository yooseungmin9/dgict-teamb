# youtube_api.py (패치 버전: quotaExceeded 시에도 페이지가 뜨도록 fallback 추가)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
from html import unescape
import os, requests, logging

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="YouTube Proxy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# 🔐 환경변수 우선
# _YT_FALLBACK = "AIzaSyDtsdmz204NoNAFBam4S3Fe_gNR4Sy_7Ko"
# _YT_FALLBACK = "AIzaSyAvBT58ksxCS_E0nehgiy5fMJbtXnePghk"
# _YT_FALLBACK = "AIzaSyBtxipDV9KVMm5j87yNiVMvriFSTZzJyeo"
_YT_FALLBACK = "AIzaSyB-_o4aPDlCDY_xwaTjbPKd-bkozHEOYO4"
# _YT_FALLBACK = "AIzaSyDeKCDQL_eGrxCBMJvH4aCA_FOunlWPLVY"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", _YT_FALLBACK).strip()

Y_SEARCH = "https://www.googleapis.com/youtube/v3/search"
Y_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
TIMEOUT = 10


def require_key():
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="Missing YOUTUBE_API_KEY")


def _extract_google_error_detail(resp: requests.Response) -> Dict[str, Any]:
    try:
        j = resp.json()
    except Exception:
        return {"message": resp.text, "status_code": resp.status_code}
    detail: Dict[str, Any] = {"status_code": resp.status_code, "error": j.get("error", {})}
    err = j.get("error") or {}
    if isinstance(err, dict):
        detail["code"] = err.get("code")
        detail["message"] = err.get("message")
        errors = err.get("errors")
        if isinstance(errors, list) and errors:
            detail["reason"] = errors[0].get("reason")
            detail["domain"] = errors[0].get("domain")
    return detail


def _fallback_items(q: str) -> Dict[str, Any]:
    """API 실패(특히 quotaExceeded) 시에도 페이지가 깨지지 않도록 반환할 안전한 더미 데이터."""
    demo = [
        {
            "videoId": "dQw4w9WgXcQ",
            "title": f"[DEMO] '{q}' 관련 예시 영상 #1",
            "channelTitle": "Demo Channel",
            "publishedAt": "2020-01-01T00:00:00Z",
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "statistics": {"viewCount": "0", "likeCount": "0", "commentCount": "0"},
        },
        {
            "videoId": "3GwjfUFyY6M",
            "title": f"[DEMO] '{q}' 관련 예시 영상 #2",
            "channelTitle": "Demo Channel 2",
            "publishedAt": "2020-01-02T00:00:00Z",
            "thumbnail": "https://i.ytimg.com/vi/3GwjfUFyY6M/mqdefault.jpg",
            "url": "https://www.youtube.com/watch?v=3GwjfUFyY6M",
            "statistics": {"viewCount": "0", "likeCount": "0", "commentCount": "0"},
        },
    ]
    return {
        "count": len(demo),
        "items": demo,
        "nextPageToken": None,
        "prevPageToken": None,
        "fallback": True,                # ← 프론트에서 “데모입니다” 같은 안내에 사용 가능
        "fallback_reason": "quotaExceeded or upstream error",
    }


def fetch_video_stats(video_ids: List[str]) -> dict:
    if not video_ids:
        return {}
    params = {"key": YOUTUBE_API_KEY, "part": "statistics", "id": ",".join(video_ids)}
    try:
        r = requests.get(Y_VIDEOS, params=params, timeout=TIMEOUT)
        if not r.ok:
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


@app.get("/youtube/search")
def youtube_search(
    q: str = Query(..., min_length=1, description="검색어"),
    max_results: int = Query(8, ge=1, le=50),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    safe: str = Query("moderate", regex="^(none|moderate|strict)$"),
    _raw: int = 0,
    allow_fallback: int = Query(1, description="API 실패 시 데모 데이터 반환(1=on,0=off)"),
) -> Dict[str, Any]:
    """
    YouTube Data API v3 proxy.
    - API 실패해도 페이지가 떠야 하므로, 기본값(allow_fallback=1)에서는 데모 데이터를 반환.
    """
    require_key()

    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "type": "video",
        "q": q,
        "maxResults": max_results,
        "safeSearch": safe,
        # 쿼터 절약용 fields를 쓰고 싶으면 아래 주석 해제
        # "fields": "items(id/videoId,snippet(title,channelTitle,publishedAt,thumbnails/medium/url)),nextPageToken,prevPageToken",
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        r = requests.get(Y_SEARCH, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        log.error("YouTube API network error: %s", e)
        # 네트워크 장애일 때도 페이지가 떠야 한다면 fallback
        if allow_fallback:
            return _fallback_items(q)
        raise HTTPException(status_code=502, detail=f"YouTube upstream network error: {e}")

    if not r.ok:
        # 4xx/5xx 원문 파싱
        detail = _extract_google_error_detail(r)
        reason = str(detail.get("reason"))
        # 🔸 quotaExceeded 등일 때는 200 + fallback
        if allow_fallback and r.status_code == 403 and reason == "quotaExceeded":
            log.warning("quotaExceeded detected; serving fallback items.")
            return _fallback_items(q)
        # 그 외에는 있는 그대로 던짐
        raise HTTPException(status_code=r.status_code, detail=detail)

    payload = r.json()

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
        thumb = (
            (thumbs.get("medium") or {}).get("url")
            or (thumbs.get("high") or {}).get("url")
            or (thumbs.get("default") or {}).get("url")
        )
        items.append({
            "videoId": vid,
            "title": unescape(sn.get("title") or ""),
            "channelTitle": unescape(sn.get("channelTitle") or ""),
            "publishedAt": sn.get("publishedAt"),
            "thumbnail": thumb,
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
        })

    stats = fetch_video_stats(video_ids)
    for it in items:
        it["statistics"] = stats.get(it["videoId"], {})

    out: Dict[str, Any] = {
        "count": len(items),
        "items": items,
        "nextPageToken": payload.get("nextPageToken"),
        "prevPageToken": payload.get("prevPageToken"),
        "fallback": False,
    }
    if _raw == 1:
        out["_raw"] = payload
    return out
