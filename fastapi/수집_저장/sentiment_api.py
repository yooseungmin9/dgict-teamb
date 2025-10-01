# sentiment_api.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Dict

MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "test123"
COLL_NAME = "shared_articles"

app = FastAPI(title="EcoNews Sentiment API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_collection():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME][COLL_NAME]


@app.get("/sentiment")
def get_sentiment(days: int = Query(7, ge=1, le=90)) -> Dict:
    """
    최근 N일 간 카테고리별 감성 집계
    (이미 DB에 저장된 category, sentiment 필드를 활용)
    """
    col = get_collection()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    # MongoDB aggregation
    pipeline = [
        {"$match": {"news_date": {"$gte": since}}},
        {"$group": {
            "_id": {"cat": "$category", "sent": "$sentiment"},
            "count": {"$sum": 1}
        }}
    ]

    cursor = col.aggregate(pipeline)

    # 결과를 {카테고리: {긍정: x, 중립: y, 부정: z}} 형태로 정리
    result = {}
    for row in cursor:
        cat = row["_id"]["cat"]
        sent = row["_id"]["sent"]
        cnt = row["count"]

        if cat not in result:
            result[cat] = {"긍정": 0, "중립": 0, "부정": 0}
        result[cat][sent] = cnt

    return {
        "data": result,
        "meta": {
            "days": days,
            "last_refreshed": datetime.now().isoformat(),
            "total_docs": sum(sum(v.values()) for v in result.values())
        }
    }
