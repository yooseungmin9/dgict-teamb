# app.py (FastAPI 최종본)
from __future__ import annotations

import os, re
from collections import Counter, defaultdict
from typing import Optional
from random import randint
from dotenv import load_dotenv

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from konlpy.tag import Okt

# 1. 환경 변수 로드 및 DB 연결
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["test123"]
col_video = db["youtube_db2"]
col_comments = db["youtube_comments"]

# 2. FastAPI 초기화
app = FastAPI(title="YouTube Opinion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 간단 토크나이저
okt = Okt()
STOPWORDS = {
    "그리고", "하지만", "영상", "정말", "그냥", "진짜",
    "하면", "해서", "하는", "에서", "으로", "이다",
    "것", "거", "저", "나", "너", "우리", "너무", "이런"
}

def tokenize(text: str) -> list[str]:
    tokens = okt.nouns(text or "")
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

# 4. 헬스체크
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

# 5. /videos — 영상 목록 조회
@app.get("/videos")
def get_videos(
    category: Optional[str] = Query(None, description="카테고리 필터"),
    sort_by: Optional[str] = Query("latest", description="정렬 기준: views/comments/latest"),
) -> list[dict]:
    query = {}
    if category:
        query["category"] = category

    sort_map = {
        "views": ("view_count", -1),
        "comments": ("comment_count", -1),
        "latest": ("published_at", -1),
    }
    sort_field, sort_dir = sort_map.get(sort_by, ("published_at", -1))

    docs = (
        col_video.find(query, {"_id": 0, "video_id": 1, "title": 1, "thumbnail_url": 1, "category": 1})
        .sort(sort_field, sort_dir)
        .limit(20)
    )

    return [
        {
            "video_id": d.get("video_id"),
            "title": d.get("title", ""),
            "thumbnail": d.get("thumbnail_url", ""),
            "category": d.get("category", ""),
        }
        for d in docs
    ]

# 6. /videos/{video_id} — 단일 영상 상세
@app.get("/videos/{video_id}")
def get_video_detail(video_id: str) -> dict:
    doc = col_video.find_one({"video_id": video_id})
    if not doc:
        return {"error": "Video not found"}

    return {
        "video_id": doc.get("video_id"),
        "title": doc.get("title", ""),
        "category": doc.get("category", ""),
        "published_at": doc.get("published_at", ""),
        "views": int(doc.get("view_count", 0) or 0),
        "comments": int(doc.get("comment_count", 0) or 0),
        "thumbnail": doc.get("thumbnail_url", ""),
        "video_url": f"https://www.youtube.com/embed/{doc.get('video_id','')}",
    }

# 7. /analysis/{video_id} — 댓글 기반 감정 분석
@app.get("/analysis/{video_id}")
def get_analysis(
    video_id: str,
    limit: Optional[int] = Query(None, ge=1, description="집계할 댓글 수. None=전체"),
    topn: int = Query(100, ge=5, le=300, description="워드클라우드 상위 단어 수"),
) -> dict:
    vdoc = col_video.find_one({"video_id": video_id}) or {}

    q = {"video_id": video_id}
    cursor = col_comments.find(q, {"_id": 0, "text": 1, "emotion": 1})
    if limit is not None:
        cursor = cursor.limit(int(limit))
    cmts = list(cursor)

    if not cmts and vdoc.get("comments"):
        cmts = vdoc["comments"][: (limit or len(vdoc["comments"]))]

    id2label = {
        0: "공포(Fear)", 1: "놀람(Surprise)", 2: "분노(Anger)",
        3: "슬픔(Sadness)", 4: "중립(Neutral)", 5: "행복(Happiness)", 6: "혐오(Disgust)"
    }
    emo_alias = {v: v for v in id2label.values()}
    emo_alias.update({
        "Fear": "공포(Fear)", "Surprise": "놀람(Surprise)", "Anger": "분노(Anger)",
        "Sadness": "슬픔(Sadness)", "Neutral": "중립(Neutral)",
        "Happiness": "행복(Happiness)", "Disgust": "혐오(Disgust)"
    })

    emo_counter = Counter({lbl: 0 for lbl in id2label.values()})
    word_counter = Counter()
    samples: list[dict] = []

    for c in cmts:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        emo_raw = (c.get("emotion") or "").strip()
        emo = emo_alias.get(emo_raw)
        if emo:
            emo_counter[emo] += 1
        tokens = tokenize(text)
        if tokens:
            word_counter.update(tokens)
        if len(samples) < 3:
            samples.append({"text": text, "emotion": emo or "Unknown"})

    emo_groups = defaultdict(list)
    for c in cmts:
        text = (c.get("text") or "").strip()
        emo_raw = (c.get("emotion") or "").strip()
        emo = emo_alias.get(emo_raw, "미분류(Unknown)")
        if text:
            emo_groups[emo].append(text)

    emo_samples = {}
    for emo, texts in emo_groups.items():
        candidates = [c for c in cmts if c.get("emotion") == emo and c.get("text")]
        if candidates:
            best = max(candidates, key=lambda c: c.get("emotion_scores", {}).get(emo, 0))
            emo_samples[emo] = best["text"]

    total_comments = len(cmts)
    if total_comments > 0 and sum(emo_counter.values()) > 0:
        top_emo, top_cnt = emo_counter.most_common(1)[0]
        summary_lines = [f"이 영상 댓글 {total_comments}개 중 '{top_emo}' 감정이 {top_cnt}건으로 가장 많음", ""]
    else:
        summary_lines = ["댓글이 없어 분석할 수 없습니다."]

    for emo, rep in emo_samples.items():
        summary_lines.append(f"({emo})")
        summary_lines.append(rep)
        summary_lines.append("")

    summary = "\n".join(summary_lines).strip()
    wc_pairs = [{"text": w, "count": int(cnt)} for w, cnt in word_counter.most_common(topn)]
    if not wc_pairs:
        wc_pairs = [{"text": "댓글없음", "count": 1}]

    return {
        "video_id": video_id,
        "total_comments_used": total_comments,
        "sentiment": dict(emo_counter),
        "wordcloud": wc_pairs,
        "summary": summary,
        "samples_by_emotion": emo_samples
    }

# 8. /youtube/results — 대시보드용 요약 엔드포인트
@app.get("/youtube/results")
def get_random_youtube_video() -> dict:
    try:
        count = col_video.count_documents({})
        if count == 0:
            return {"error": "no_data"}

        v = (
            col_video.find({}, {"_id": 0, "video_id": 1, "title": 1, "thumbnail_url": 1})
            .skip(randint(0, count - 1))
            .limit(1)[0]
        )
        vid = v.get("video_id")
        if not vid:
            return {"error": "missing_video_id"}

        result = get_analysis(vid, limit=200, topn=80)
        full_summary = result.get("summary", "").strip()
        lines = [l.strip() for l in full_summary.splitlines() if l.strip()]

        head = lines[0] if lines else ""

        def is_header(s: str) -> bool:
            return s.startswith("(") and s.endswith(")")

        body = next((l for l in lines[1:] if not is_header(l) and "감정이" not in l), "")
        short_summary = head if not body else f"{head}\n\n{body}"
        if len(short_summary) > 180:
            short_summary = short_summary[:180].rstrip() + " ..."

        return {
            "video_id": vid,
            "title": v.get("title", ""),
            "thumbnail_url": v.get("thumbnail_url", ""),
            "summary": short_summary,
            "wordcloud": result.get("wordcloud"),
            "sentiment": result.get("sentiment"),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"{type(e).__name__}: {e}"}
