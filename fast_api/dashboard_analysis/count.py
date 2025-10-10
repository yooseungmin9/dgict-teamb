from __future__ import annotations
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

KST = timezone(timedelta(hours=9))
app = FastAPI(title="SUMMARIX Count API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False
)

def _db():
    return MongoClient(MONGO_URI)[DB_NAME]

def _ensure_indexes():
    coll = _db()[COLL_NAME]
    # 기존 이름과 맞추거나 이름 제거
    try:
        coll.create_index([("published_at", ASCENDING)], name="published_at_1")
        # 또는: coll.create_index([("published_at", ASCENDING)])  # 이름 자동 => published_at_1
    except OperationFailure as e:
        if e.code != 85:
            raise

@app.get("/count")
def get_news_count():
    _ensure_indexes()
    coll = _db()[COLL_NAME]

    now = datetime.now(KST)
    t0 = datetime(now.year, now.month, now.day, tzinfo=KST)  # 오늘 00:00
    t7 = t0 - timedelta(days=6)                              # 최근 7일 시작

    total = coll.estimated_document_count()
    today = coll.count_documents({"published_at": {"$gte": t0}})
    last7 = coll.count_documents({"published_at": {"$gte": t7}})

    return {
        "ok": True,
        "collection": COLL_NAME,
        "total": int(total),
        "today": int(today),
        "last7": int(last7),
        "updated_at": now.isoformat()
    }