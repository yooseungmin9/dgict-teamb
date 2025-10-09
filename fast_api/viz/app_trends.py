from __future__ import annotations
import os
from typing import Any, Dict, List
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI   = os.getenv("MONGO_URI", "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
DB_NAME     = os.getenv("MONGO_DB",  "test123")
COL_TREND = os.getenv("MONGO_COL_TREND", "trends_daily")
COL_BURST = os.getenv("MONGO_COL_BURST", "burst_keywords")

app = FastAPI(title="SUMMARIX Trends API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

def db(): return MongoClient(MONGO_URI)[DB_NAME]

@app.get("/health")
def health():
    return {"ok": True, "service": "trends", "time": datetime.now().isoformat()}

@app.get("/api/trends/top")
def trends_top(
    date_from: str|None = None,
    date_to:   str|None = None,
    top: int = 30,
    group: str|None = None,   # 예: 산업군/토픽 그룹
):
    """
    COL_TRENDS 스키마 가정:
      {date:'YYYY-MM-DD', keyword:str, count:int, group?:str, zscore?:float, pct_change?:float}
    """
    q: Dict[str, Any] = {}
    if date_from or date_to:
        q["date"] = {}
        if date_from: q["date"]["$gte"] = date_from
        if date_to:   q["date"]["$lte"] = date_to
        if not q["date"]: del q["date"]
    if group: q["group"] = group

    pipeline = [
        {"$match": q},
        {"$group": {"_id":"$keyword", "value":{"$sum":"$count"}}},
        {"$sort": {"value": -1}},
        {"$limit": top},
        {"$project": {"_id":0, "name":"$_id", "value":"$value"}}
    ]
    items = list(db()[COL_TREND].aggregate(pipeline))
    return {"items": items}

@app.get("/api/trends/wordcloud")
def trends_wordcloud(date_from: str|None=None, date_to:str|None=None, top:int=80, group:str|None=None):
    return trends_top(date_from, date_to, top, group)

@app.get("/api/trends/series")
def trends_series(keyword: str = Query(...), limit:int=120, group:str|None=None):
    q: Dict[str, Any] = {"keyword": keyword}
    if group: q["group"] = group
    cur = db()[COL_TREND].find(q, {"_id":0}).sort([("date", ASCENDING)]).limit(limit)
    items = [{"date": d["date"], "count": d.get("count", 0), "z": d.get("zscore")} for d in cur]
    if not items: raise HTTPException(404, "no series")
    return {"keyword": keyword, "series": items}

@app.get("/api/trends/spikes")
def trends_spikes(week_start: str|None = None, top:int=20):
    """
    COL_SPIKES 스키마 가정:
      {week_start:'YYYY-MM-DD', keyword:str, score:float, delta:int, example_titles:[...]}
    """
    q: Dict[str, Any] = {}
    if week_start: q["week_start"] = week_start
    cur = db()[COL_BURST].find(q, {"_id":0}).sort([("score", DESCENDING)]).limit(top)
    items = list(cur)
    return {"items": items}
