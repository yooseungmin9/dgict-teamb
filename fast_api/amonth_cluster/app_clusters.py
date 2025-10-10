from __future__ import annotations
import os
from typing import Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING
from bson import ObjectId
from dotenv import load_dotenv
from dateutil import parser as dtp

load_dotenv()

MONGO_URI  = os.getenv("MONGO_URI", "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
DB_NAME    = os.getenv("MONGO_DB",  "test123")
COL_CLU    = os.getenv("MONGO_COL_CLU", "clusters")
COL_PREP   = os.getenv("MONGO_COL_PREP", "articles_preprocessed")

app = FastAPI(title="SUMMARIX Clusters API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

def db():
    return MongoClient(MONGO_URI)[DB_NAME]

@app.get("/health")
def health():
    return {"ok": True, "service": "clusters", "time": datetime.now().isoformat()}

@app.get("/api/clusters/summary")
def clusters_summary(top:int=60, min_size:int=2, since:Optional[str]=None):
    q = {"count": {"$gte": min_size}}
    if since:
        try:
            q["updated_at"] = {"$gte": dtp.parse(since)}
        except Exception:
            raise HTTPException(400, "since must be ISO8601 datetime")
    cur = db()[COL_CLU].find(
        q,
        {"_id":0, "cluster_id":1, "cluster":1, "label_gpt":1, "cluster_label":1, "label":1, "count":1}
    ).sort("count", DESCENDING).limit(top)

    items = [{
        "id": c.get("cluster_id", c.get("cluster")),
        "name": c.get("label_gpt") or c.get("cluster_label") or c.get("label") or f"Cluster {c.get('cluster_id', c.get('cluster'))}",
        "value": c.get("count", 0)
    } for c in cur]
    return {"items": items}

def _to_obj_ids(ids: List[Any]) -> List[Any]:
    out: List[Any] = []
    for x in ids:
        if isinstance(x, ObjectId):
            out.append(x)
        else:
            s = str(x)
            out.append(ObjectId(s) if len(s) == 24 else s)
    return out

@app.get("/api/clusters/table")
def clusters_table(cluster_id: int = Query(...), limit: int = 10):
    clu = db()[COL_CLU].find_one({
        "$or": [
            {"cluster_id": cluster_id},
            {"cluster": cluster_id},
            {"cluster_id": str(cluster_id)}
        ]
    })
    if not clu:
        raise HTTPException(404, "cluster not found")

    ids = list(clu.get("ref_ids") or clu.get("article_ids") or [])
    ids = _to_obj_ids(ids)[:limit]

    proj = {"_id":1, "title":1, "press":1, "published_at":1, "url":1}
    coll = db()[COL_PREP]

    if ids:
        arts = list(
            coll.find({"_id": {"$in": ids}}, proj)
                .sort("published_at", DESCENDING)
                .limit(limit)
        )
    else:
        arts = list(
            coll.find(
                {"$or": [
                    {"cluster_id": cluster_id},
                    {"cluster": cluster_id},
                    {"cluster_id": str(cluster_id)},
                    {"cluster": str(cluster_id)},
                ]},
                proj
            ).sort("published_at", DESCENDING).limit(limit)
        )

    for a in arts:
        if "_id" in a:
            a["_id"] = str(a["_id"])

    return {
        "cluster_id": clu.get("cluster_id", clu.get("cluster")),
        "label_gpt": clu.get("label_gpt") or clu.get("cluster_label") or clu.get("label"),
        "size": int(clu.get("count", len(arts))),
        "representative": (arts[0] if arts else None),
        "articles": arts
    }
