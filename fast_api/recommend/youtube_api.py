# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
from html import unescape
import os, requests, logging
from dotenv import load_dotenv

# 0) .env 로드 (없으면 조용히 패스)
load_dotenv()

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="YouTube Proxy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # 기존 동작 유지 (필요하면 ENV로 빼도 OK)
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# 1) 환경변수
YOUTUBE_API_KEY = (os.getenv("YOUTUBE_API_KEY") or "").strip()
Y_SEARCH = "https://www.googleapis.com/youtube/v3/search"
Y_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
TIMEOUT = int(os.getenv("YOUTUBE_TIMEOUT", "10"))  # 선택: 기본 10초

# 2) 유틸
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
        "fallback": True,
        "fallback_reason": "quotaExceeded or missing_key or upstream error",
    }

def fetch_video_stats(video_ids: List[str]) -> dict:
    # 키가 없으면 통계 호출 생략 (빈 dict)
    if not video_ids or not YOUTUBE_API_KEY:
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

# 3) 엔드포인트

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
    allow_fallback: int = Query(1, description="API 실패/무키 시 데모 데이터 반환(1=on,0=off)"),
) -> Dict[str, Any]:

    # 키가 없으면: allow_fallback=1 이면 데모 반환, 아니면 500
    if not YOUTUBE_API_KEY:
        if allow_fallback:
            return _fallback_items(q)
        raise HTTPException(status_code=500, detail="Missing YOUTUBE_API_KEY")

    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "type": "video",
        "q": q,
        "maxResults": max_results,
        "safeSearch": safe,
        # 필요 시 쿼터 절약:
        # "fields": "items(id/videoId,snippet(title,channelTitle,publishedAt,thumbnails/medium/url)),nextPageToken,prevPageToken",
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        r = requests.get(Y_SEARCH, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        log.error("YouTube API network error: %s", e)
        if allow_fallback:
            return _fallback_items(q)
        raise HTTPException(status_code=502, detail=f"YouTube upstream network error: {e}")

    if not r.ok:
        detail = _extract_google_error_detail(r)
        reason = str(detail.get("reason"))
        if allow_fallback and r.status_code == 403 and reason == "quotaExceeded":
            log.warning("quotaExceeded detected; serving fallback items.")
            return _fallback_items(q)
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
