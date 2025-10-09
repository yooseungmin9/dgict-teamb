from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta, time
from contextlib import asynccontextmanager
import math, pytz

# ===== 설정 =====
KST = pytz.timezone("Asia/Seoul")
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

CLIENT = MongoClient(MONGO_URI)
COLL = CLIENT[DB_NAME][COLL_NAME]

def _ensure_indexes():
    try:
        COLL.create_index("published_at")
    except Exception:
        pass

def _normalize_0_100(x: float) -> float:
    try:
        s = float(x)
    except Exception:
        return math.nan
    if 0 <= s <= 1:
        y = s * 100
    elif -1 <= s <= 1:
        y = (s + 1) / 2 * 100
    elif -100 <= s <= 100:
        y = (s + 100) / 200 * 100
    elif 0 <= s <= 100:
        y = s
    else:
        y = max(0, min(100, s))
    return round(max(0, min(100, y)), 2)

def _avg_for(day, score_key: str):
    s = KST.localize(datetime.combine(day, time.min))
    e = KST.localize(datetime.combine(day, time.max))
    pipe = [
        {"$addFields": {"_dt": {"$toDate": "$published_at"}}},
        {"$match": {"_dt": {"$gte": s, "$lte": e}}},
        {"$project": {
            "_id": 0,
            "score": {
                "$convert": {
                    "input": f"${score_key}",
                    "to": "double",
                    "onError": None,
                    "onNull": None
                }
            }
        }},
        {"$match": {"score": {"$ne": None}}},
        {"$group": {"_id": None, "avg_raw": {"$avg": "$score"}}},
    ]
    rows = list(COLL.aggregate(pipe))
    if not rows:
        return None
    v = rows[0]["avg_raw"]
    return None if v is None else _normalize_0_100(v)

@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_indexes()
    yield
    CLIENT.close()

app = FastAPI(title="EMOA API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],   # OPTIONS 허용
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/emoa/score")
def emoa_score(score_key: str = "sentiment_score"):
    today = datetime.now(KST).date()
    yest  = today - timedelta(days=1)

    avg_today = _avg_for(today, score_key)
    avg_yest  = _avg_for(yest,  score_key)
    delta = None if (avg_today is None or avg_yest is None) else round(avg_today - avg_yest, 2)
    weekday_ko = ["월","화","수","목","금","토","일"][today.weekday()]

    return {
        "date": str(today),
        "weekday": weekday_ko,
        "avg": avg_today,
        "delta": delta
    }