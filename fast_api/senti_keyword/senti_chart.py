# senti_chart.py
# 입문자 주석: 기존의 app = FastAPI() 를 쓰지 말고 APIRouter 사용
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, date, time
from dateutil.parser import isoparse
from pymongo import MongoClient
import pandas as pd

# === 공통 상수(기존 값 그대로) ===
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"
COL_THRES = "sentiment_score"

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

# ----- 유틸: 임계값 로드 -----
def load_thresholds() -> dict:
    cli = MongoClient(MONGO_URI)
    docs = list(cli[DB_NAME][COL_THRES].find({}, {"_id":0,"label":1,"min":1,"max":1}))
    cli.close()
    if not docs:
        docs = [{"label":"부정","min":-999,"max":-1},
                {"label":"중립","min":0,"max":0},
                {"label":"긍정","min":1,"max":999}]
    by = {d["label"]:(d["min"], d["max"]) for d in docs}
    for k in ("부정","중립","긍정"):
        if k not in by: raise ValueError("sentiment_score 라벨 누락")
    return by

def bucket_for(score: float, th: dict) -> str:
    try: s=float(score)
    except: return "미정"
    for label,(mn,mx) in th.items():
        if mn <= s <= mx: return label
    return "미정"

@router.get("/line")
def sentiment_daily(
    mode: str = Query("count", pattern="^(count|ratio)$"),
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    score_key: str = "sentiment_score"
):
    today = datetime.utcnow().date()
    to_d   = isoparse(date_to).date()   if date_to   else today
    from_d = isoparse(date_from).date() if date_from else (to_d - timedelta(days=89))

    try:
        th = load_thresholds()
    except Exception as e:
        raise HTTPException(500, f"임계값 로드 실패: {e}")

    start_dt = datetime.combine(from_d, time.min)
    end_dt   = datetime.combine(to_d,   time.max)

    pipeline = [
        {"$addFields": {"dt": {"$dateFromString": {"dateString": "$published_at"}}}},
        {"$match": {"dt": {"$gte": start_dt, "$lte": end_dt}}},
        {"$project": {"_id":0,
                      "date":{"$dateToString":{"format":"%Y-%m-%d","date":"$dt"}},
                      score_key:1}}
    ]

    cli = MongoClient(MONGO_URI)
    rows = list(cli[DB_NAME][COLL_NAME].aggregate(pipeline, allowDiskUse=True))
    cli.close()

    labels_all = pd.date_range(from_d, to_d, freq="D").strftime("%Y-%m-%d").tolist()
    if not rows:
        return [{"date": d, "부정":0, "중립":0, "긍정":0} for d in labels_all]

    df = pd.DataFrame(rows)
    if score_key not in df.columns:
        raise HTTPException(500, f"문서에 '{score_key}' 필드 없음")
    df.rename(columns={score_key:"score"}, inplace=True)
    df["date"] = df["date"].astype(str)
    df["bucket"] = df["score"].apply(lambda s: bucket_for(s, th))

    daily = (df.groupby(["date","bucket"]).size()
               .unstack(fill_value=0)
               .reindex(columns=["부정","중립","긍정"], fill_value=0))
    daily = daily.reindex(labels_all, fill_value=0)
    if mode == "ratio":
        tot = daily.sum(axis=1).replace(0,1)
        daily = (daily.div(tot, axis=0) * 100).round(2)

    return daily.reset_index().to_dict(orient="records")