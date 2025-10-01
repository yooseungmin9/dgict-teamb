# api/routers/sentiment_service.py
# [입문자용] 기존 sentiment_api.py를 APIRouter로 변환
from fastapi import APIRouter, Query
from typing import Dict
from datetime import datetime, timedelta
from pymongo import MongoClient

router = APIRouter()

# [상수] 실제 연결 값 고정 (환경변수 없이 상수로)
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/?retryWrites=true&w=majority"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

def get_collection():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME][COLL_NAME]

@router.get("/sentiment")
def get_sentiment(days: int = Query(7, ge=1, le=90)) -> Dict:
    """
    최근 N일 간 카테고리별 감성 집계
    요구 필드: news_date(YYYYMMDD), category, sentiment("긍정/중립/부정")
    """
    col = get_collection()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    pipeline = [
        {"$match": {"news_date": {"$gte": since}}},
        {"$group": {"_id": {"cat": "$category", "sent": "$sentiment_score"}, "count": {"$sum": 1}}},
    ]
    cursor = col.aggregate(pipeline)

    result = {}
    for row in cursor:
        cat = row["_id"]["cat"]
        sent = row["_id"]["sent"]
        cnt  = row["count"]
        if cat not in result:
            result[cat] = {"긍정": 0, "중립": 0, "부정": 0}
        # 없는 라벨이 오더라도 KeyError 방지
        if sent not in result[cat]:
            result[cat][sent] = 0
        result[cat][sent] += cnt

    return {
        "data": result,
        "meta": {
            "days": days,
            "last_refreshed": datetime.now().isoformat(),
            "total_docs": sum(sum(v.values()) for v in result.values())
        }
    }

# === 간단 테스트 ===
# curl "http://127.0.0.1:8000/api/sentiment?days=7"
