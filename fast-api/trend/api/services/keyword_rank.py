# api/services/keyword_rank.py
# [입문자용] MongoDB에서 최근 N일간 keyword 집계 서비스 로직

from pymongo import MongoClient
from datetime import datetime, timedelta

# ====== MongoDB (상수 고정) ======
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

def mongo_col():
    return MongoClient(MONGO_URI)[DB_NAME][COLL_NAME]

def get_keyword_ranking(days: int = 30, topn: int = 100):
    """
    최근 N일 기준 keywords 배열을 펼쳐 카테고리별 언급량 집계
    반환: [{rank, keyword, category, count}]
    - rank는 프론트에서 다시 매기므로 여기선 0 고정
    """
    col = mongo_col()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    pipeline = [
        {"$match": {"news_date": {"$gte": since}, "keywords": {"$exists": True, "$ne": []}}},
        {"$unwind": "$keywords"},
        {"$group": {"_id": {"kw": "$keywords", "cat": "$category"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": topn * 10}  # 전체 합산 위해 여유 있게
    ]
    rows = list(col.aggregate(pipeline))

    out = []
    for r in rows:
        kw  = r["_id"]["kw"]
        cat = r["_id"]["cat"] or "-"
        cnt = int(r["count"])
        out.append({"rank": 0, "keyword": kw, "category": cat, "count": cnt})

    return out
