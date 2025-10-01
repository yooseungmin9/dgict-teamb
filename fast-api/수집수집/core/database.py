from __future__ import annotations
import os
from datetime import datetime
from typing import List, Dict, Any
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

load_dotenv()

_MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
_DB_NAME = os.getenv("MONGO_DB", "econ")

_client = MongoClient(_MONGO_URI, uuidRepresentation="standard")
_db = _client[_DB_NAME]

def upsert_many(col: str, docs: List[Dict[str, Any]], keys: List[str]) -> int:
    if not docs:
        return 0
    for d in docs:
        d.setdefault("created_at", datetime.utcnow())
        d.setdefault("updated_at", datetime.utcnow())
    ops = []
    for d in docs:
        filt = {k: d[k] for k in keys if k in d}
        d["updated_at"] = datetime.utcnow()
        ops.append(UpdateOne(filt, {"$set": d}, upsert=True))
    res = _db[col].bulk_write(ops, ordered=False)
    return (res.upserted_count or 0) + (res.modified_count or 0)

def find_text_since(col: str, days: int) -> List[str]:
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)
    cur = _db[col].find(
        {"updated_at": {"$gte": since}},
        {"_id": 0, "title": 1, "content": 1}
    )
    out = []
    for x in cur:
        t = (x.get("title") or "") + " " + (x.get("content") or "")
        if t.strip():
            out.append(t)
    return out
