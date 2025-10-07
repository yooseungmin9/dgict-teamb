# app.py (FastAPI 최종본)
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient


# ------------------
# FastAPI 초기화
# ------------------
app = FastAPI(title="YouTube Opinion API")

# CORS: 프론트는 8081
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------
# MongoDB 연결
# ------------------
# 주의: 실제 배포 시 환경변수로 교체 권장
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["test123"]
col_video = db["youtube_db2"]
col_comments = db["youtube_comments"]

# ------------------
# 간단 토크나이저
# ------------------
from konlpy.tag import Okt

okt = Okt()

# 불용어 확장 (필요에 따라 계속 추가 가능)
STOPWORDS = {
    "그리고", "하지만", "영상", "정말", "그냥", "진짜",
    "하면", "해서", "하는", "에서", "으로", "이다",
    "것", "거", "저", "나", "너", "우리", "너무", "이런"
}

def tokenize(text: str) -> list[str]:
    """Okt 명사 추출 기반 토큰화 + 불용어 제거"""
    tokens = okt.nouns(text or "")
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

# ------------------
# API 라우트
# ------------------
@app.get("/health")
def health() -> dict:
    """헬스체크."""
    return {"status": "ok"}


@app.get("/videos")
def get_videos() -> list[dict]:
    """유튜브 영상 리스트(썸네일 포함) 반환."""
    docs = col_video.find({}, {"video_id": 1, "title": 1, "thumbnail_url": 1, "_id": 0})
    return [
        {
            "video_id": d.get("video_id"),
            "title": d.get("title", ""),
            "thumbnail": d.get("thumbnail_url", ""),
        }
        for d in docs
    ]


@app.get("/videos/{video_id}")
def get_video_detail(video_id: str) -> dict:
    """특정 영상 메타정보 반환."""
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


@app.get("/analysis/{video_id}")
def get_analysis(
    video_id: str,
    limit: Optional[int] = Query(None, ge=1, description="집계할 댓글 수. None=전체"),
    topn: int = Query(100, ge=5, le=300, description="워드클라우드 상위 단어 수"),
) -> dict:
    """
    특정 영상 댓글 기반 분석 결과 반환.
    - 댓글 소스 우선순위: youtube_comments 컬렉션 → video.comments 배열 fallback
    - 항상 7개 감정 키 존재하도록 0으로 초기화
    - 데이터 없을 때도 wordcloud/summary 안전값 보장
    """
    vdoc = col_video.find_one({"video_id": video_id}) or {}

    # 1) 댓글 로딩
    q = {"video_id": video_id}
    cursor = col_comments.find(q, {"_id": 0, "text": 1, "emotion": 1})
    if limit:
        cursor = cursor.limit(limit)
    cmts = list(cursor)

    # fallback: video 문서 내 comments 배열 사용
    if not cmts and vdoc.get("comments"):
        cmts = vdoc["comments"][: (limit or len(vdoc["comments"]))]

    # 2) 감정 매핑 (7 클래스)
    id2label = {
        0: "공포(Fear)",
        1: "놀람(Surprise)",
        2: "분노(Anger)",
        3: "슬픔(Sadness)",
        4: "중립(Neutral)",
        5: "행복(Happiness)",
        6: "혐오(Disgust)",
    }
    emo_alias = {v: v for v in id2label.values()}
    emo_alias.update(
        {
            "Fear": "공포(Fear)",
            "공포": "공포(Fear)",
            "Surprise": "놀람(Surprise)",
            "놀람": "놀람(Surprise)",
            "Anger": "분노(Anger)",
            "분노": "분노(Anger)",
            "Sadness": "슬픔(Sadness)",
            "슬픔": "슬픔(Sadness)",
            "Neutral": "중립(Neutral)",
            "중립": "중립(Neutral)",
            "Happiness": "행복(Happiness)",
            "기쁨": "행복(Happiness)",
            "Joy": "행복(Happiness)",
            "Disgust": "혐오(Disgust)",
            "혐오": "혐오(Disgust)",
        }
    )

    # 3) 집계
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

    # 4) 결과 구성
    wc_pairs = [{"text": w, "count": int(cnt)} for w, cnt in word_counter.most_common(topn)]
    if not wc_pairs:
        wc_pairs = [{"text": "댓글없음", "count": 1}]

    total_comments = len(cmts)
    if total_comments > 0 and sum(emo_counter.values()) > 0:
        top_emo, top_cnt = emo_counter.most_common(1)[0]
        summary = f"이 영상 댓글 {total_comments}개 중 '{top_emo}' 감정이 {top_cnt}건으로 가장 많음"
    elif total_comments == 0:
        summary = "댓글이 없어 분석할 수 없습니다."
    else:
        summary = "분석 결과가 충분하지 않습니다."

    return {
        "video_id": video_id,
        "total_comments_used": total_comments,
        "sentiment": dict(emo_counter),
        "wordcloud": wc_pairs,
        "summary": summary,
        "comments": samples,
    }
