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
        "http://localhost:8080",  # ✅ 대시보드 주소 추가
        "http://127.0.0.1:8080",
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
def get_videos(
    category: Optional[str] = Query(None, description="카테고리 필터"),
    sort_by: Optional[str] = Query("latest", description="정렬 기준: views/comments/latest"),
) -> list[dict]:
    """
    유튜브 영상 리스트 (카테고리+정렬)
    - ?category=증권&sort_by=views
    """
    # 1️⃣ 필터 조건
    query = {}
    if category:
        query["category"] = category

    # 2️⃣ 정렬 기준 매핑
    sort_map = {
        "views": ("view_count", -1),       # 조회수순
        "comments": ("comment_count", -1), # 댓글순
        "latest": ("published_at", -1),    # 최신순
    }
    sort_field, sort_dir = sort_map.get(sort_by, ("published_at", -1))

    # 3️⃣ MongoDB 쿼리
    docs = (
        col_video.find(query, {"_id": 0, "video_id": 1, "title": 1, "thumbnail_url": 1, "category": 1})
        .sort(sort_field, sort_dir)
        .limit(20)
    )

    # 4️⃣ 반환 구조
    return [
        {
            "video_id": d.get("video_id"),
            "title": d.get("title", ""),
            "thumbnail": d.get("thumbnail_url", ""),
            "category": d.get("category", ""),
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
    if limit is not None:
        cursor = cursor.limit(int(limit))
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

    # 4) 결과 구성 — 감정별 대표 댓글 포함
    from collections import defaultdict

    # 감정별 댓글 그룹
    emo_groups = defaultdict(list)
    for c in cmts:
        text = (c.get("text") or "").strip()
        emo_raw = (c.get("emotion") or "").strip()
        emo = emo_alias.get(emo_raw, "미분류(Unknown)")
        if text:
            emo_groups[emo].append(text)

    # 감정별 대표 댓글 1개씩
    emo_samples = {emo: texts[0] for emo, texts in emo_groups.items() if texts}

    # 요약 1줄 생성
    total_comments = len(cmts)
    if total_comments > 0 and sum(emo_counter.values()) > 0:
        top_emo, top_cnt = emo_counter.most_common(1)[0]
        summary_lines = [f"이 영상 댓글 {total_comments}개 중 '{top_emo}' 감정이 {top_cnt}건으로 가장 많음", ""]
    else:
        summary_lines = ["댓글이 없어 분석할 수 없습니다."]

    # 감정별 대표 댓글 추가
    for emo, rep in emo_samples.items():
        summary_lines.append(f"({emo})")
        summary_lines.append(rep)
        summary_lines.append("")

    summary = "\n".join(summary_lines).strip()

    # 워드클라우드 생성
    wc_pairs = [{"text": w, "count": int(cnt)} for w, cnt in word_counter.most_common(topn)]
    if not wc_pairs:
        wc_pairs = [{"text": "댓글없음", "count": 1}]

    # 최종 반환
    return {
        "video_id": video_id,
        "total_comments_used": total_comments,
        "sentiment": dict(emo_counter),
        "wordcloud": wc_pairs,
        "summary": summary,  # ✅ 감정별 요약 문단
        "samples_by_emotion": emo_samples  # ✅ 새 필드 추가
    }


# ✅ app.py 내 패치: /youtube/results 만 교체
from random import randint

@app.get("/youtube/results")
def get_random_youtube_video() -> dict:
    """대시보드용: 랜덤 1개 영상 + 경량 분석 포함."""
    try:
        # 1) 영상 개수 확인
        count = col_video.count_documents({})
        if count == 0:
            return {"error": "no_data"}

        # 2) 랜덤 1건 조회 (_id 제외, 필요한 필드만)
        v = (
            col_video.find(
                {}, {"_id": 0, "video_id": 1, "title": 1, "thumbnail_url": 1}
            )
            .skip(randint(0, count - 1))
            .limit(1)[0]
        )
        vid = v.get("video_id")
        if not vid:
            return {"error": "missing_video_id"}

        # 3) 경량 분석 호출: 무한 조회 방지 (속도 안정)
        #    get_analysis는 이미 'if limit is not None: cursor.limit(int(limit))' 로 안전
        result = get_analysis(vid, limit=200, topn=80)

        # 4) 합쳐서 반환
        return {
            "video_id": vid,
            "title": v.get("title", ""),
            "thumbnail_url": v.get("thumbnail_url", ""),
            "summary": result.get("summary"),
            "wordcloud": result.get("wordcloud"),
            "sentiment": result.get("sentiment"),
        }

    except Exception as e:
        # 디버깅 편의용 로그 + 에러 메시지 반환(대시보드에서 처리)
        import traceback
        traceback.print_exc()
        return {"error": f"{type(e).__name__}: {e}"}



# ✅ 참고: get_analysis 내부 limit 처리(이미 반영되어 있으면 그대로 두세요)
# cursor = col_comments.find(q, {"_id": 0, "text": 1, "emotion": 1})
# if limit is not None:
#     cursor = cursor.limit(int(limit))
