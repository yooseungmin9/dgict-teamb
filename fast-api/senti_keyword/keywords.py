# keywords.py  (백엔드)  — 안전한 집계 파이프라인 + 파일명 충돌 없음
# 사용법: main.py에서  app.include_router(keywords_router)
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, time
from pymongo import MongoClient

# === Mongo 접속 정보 ===
MONGO_URI   = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME     = "test123"
COLL_NAME   = "shared_articles"
FIELD_KEYWORDS = "keywords"  # 문서 내부 필드명(배열)

keywords_router = APIRouter(prefix="/keywords", tags=["keywords"])  # 이름 충돌 방지

def day_range_utc(d):
    return datetime.combine(d, time.min), datetime.combine(d, time.max)

def top_keywords_for_date(target_date, top_n: int = 3):
    start_dt, end_dt = day_range_utc(target_date)
    pipeline = [
        # 1) 날짜 변환 및 기간 필터
        {"$addFields": {"dt": {"$dateFromString": {"dateString": "$published_at"}}}},
        {"$match": {"dt": {"$gte": start_dt, "$lte": end_dt}}},

        # 2) 키워드 배열 존재/유효성
        {"$match": {FIELD_KEYWORDS: {"$exists": True, "$ne": None}}},

        # 3) 펼치기
        {"$unwind": f"${FIELD_KEYWORDS}"},

        # 4) 정규화(소문자 + trim)
        {"$addFields": {"kw_norm": {"$toLower": f"${FIELD_KEYWORDS}"}}},
        {"$addFields": {"kw_norm": {"$trim": {"input": "$kw_norm"}}}},

        # 5) 빈 문자열 제거
        {"$match": {"kw_norm": {"$ne": ""}}},

        # (선택) 불용어 제외 예시:
        # {"$match": {"kw_norm": {"$nin": ["일부","기존"]}}},

        # 6) 집계
        {"$group": {"_id": "$kw_norm", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": int(top_n)},

        # 7) 출력 정리 (주의: "$_id"에 점(.) 없어야 함)
        {"$project": {"_id": 0, "keyword": "$_id", "count": 1}}
    ]

    cli = MongoClient(MONGO_URI)
    rows = list(cli[DB_NAME][COLL_NAME].aggregate(pipeline, allowDiskUse=True))
    cli.close()
    return rows  # [{"keyword":"...", "count":N}, ...]

@keywords_router.get("/top")
def keywords_top(top_n: int = Query(3, ge=1, le=20)):
    """
    오늘/어제 키워드 TOP-N
    반환:
    {
      "today":     [{"keyword":"...", "count":N}, ...],
      "yesterday": [{"keyword":"...", "count":M}, ...]
    }
    """
    try:
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        return {
            "today":     top_keywords_for_date(today, top_n),
            "yesterday": top_keywords_for_date(yesterday, top_n),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"키워드 집계 실패: {e}")

# [간단 테스트]
# uvicorn main:app --reload --port 8000
# 브라우저/터미널: http://127.0.0.1:8000/keywords/top?top_n=3