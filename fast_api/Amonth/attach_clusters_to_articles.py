# attach_clusters_to_articles.py
from __future__ import annotations
import os
from pymongo import MongoClient, UpdateOne, ASCENDING
from bson import ObjectId
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(".env", usecwd=True))

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
DB_NAME   = os.getenv("MONGO_DB",  "test123")

COL_ART   = os.getenv("MONGO_COL_PREP", "articles_preprocessed")  # 대상
COL_MAP   = os.getenv("MONGO_COL_CLUSTER_MAP", "article_clusters") # ref_id별 매핑이 있으면 우선 사용
COL_SUM   = os.getenv("MONGO_COL_CLUSTERS", "clusters")            # 요약 컬렉션(멤버 배열 보유 시 사용)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def ensure_indexes():
    db[COL_ART].create_index([("ref_id", ASCENDING)], name="ref_id")

def load_mapping():
    # 1) 명시적 매핑 컬렉션: {ref_id, cluster|cluster_id, label|cluster_label}
    if COL_MAP in db.list_collection_names():
        cur = db[COL_MAP].find({}, {"_id":0, "ref_id":1, "cluster":1, "cluster_id":1, "label":1, "cluster_label":1})
        m = []
        for d in cur:
            cid = d.get("cluster_id", d.get("cluster"))
            lab = d.get("cluster_label", d.get("label"))
            rid = d.get("ref_id")
            if rid and cid is not None:
                m.append({"ref_id": rid, "cluster_id": cid, "cluster_label": lab})
        if m:
            return m

    # 2) 요약 컬렉션에서 멤버 배열을 풀어 ref_id 추출
    member_keys = ["ref_ids", "members", "docs", "articles", "items"]
    label_keys  = ["cluster_label", "label", "name", "title"]
    cur = db[COL_SUM].find({}, {"_id":0})
    m = []
    for cdoc in cur:
        cid = cdoc.get("cluster_id", cdoc.get("cluster"))
        if cid is None:
            continue
        lab = None
        for k in label_keys:
            if k in cdoc:
                lab = cdoc[k]
                break
        members = None
        for k in member_keys:
            if k in cdoc and isinstance(cdoc[k], list):
                members = cdoc[k]; break
        if not members:
            continue
        for it in members:
            if isinstance(it, dict):
                rid = it.get("ref_id") or it.get("id") or it.get("_id")
            else:
                rid = it
            if rid:
                m.append({"ref_id": str(rid), "cluster_id": cid, "cluster_label": lab})
    return m

def update_articles(maps):
    if not maps:
        print("no mapping found"); return
    ensure_indexes()
    ops = []
    for d in maps:
        rid = str(d["ref_id"])
        cid = d["cluster_id"]
        lab = d.get("cluster_label")
        # 우선 ref_id 매칭, 없으면 _id(ObjectId) 매칭
        ops.append(UpdateOne({"ref_id": rid},
                             {"$set": {"cluster_id": cid, "cluster_label": lab}}, upsert=False))
        try:
            oid = ObjectId(rid)
            ops.append(UpdateOne({"_id": oid},
                                 {"$set": {"cluster_id": cid, "cluster_label": lab}}, upsert=False))
        except Exception:
            pass
    # 실행
    if ops:
        res = db[COL_ART].bulk_write(ops, ordered=False)
        print({"matched": res.matched_count, "modified": res.modified_count, "upserts": len(res.upserted_ids)})

if __name__ == "__main__":
    maps = load_mapping()
    update_articles(maps)
