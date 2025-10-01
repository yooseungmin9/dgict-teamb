# import_to_mongo.py
from datetime import datetime, timezone
from __future__ import annotations
import os, glob, hashlib
import pandas as pd
from pymongo import MongoClient, UpdateOne
from gridfs import GridFS
from dotenv import load_dotenv

# ===== .env 읽기 =====
load_dotenv()
URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DBN = os.getenv("DB_NAME", "econnews")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ===== 몽고 연결 =====
client = MongoClient(URI, tz_aware=True)
db = client[DBN]
fs = GridFS(db)
col = db.articles

# ===== 유틸 =====
def parse_date(x):
    try:
        return pd.to_datetime(x, errors="coerce")
    except Exception:
        return None

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼 이름 표준화"""
    aliases = {
        "title": ["title", "headline", "제목"],
        "url": ["url", "링크", "기사링크"],
        "press": ["press", "언론사", "매체"],
        "date": ["date", "날짜", "작성일", "published_at"],
        "sentiment": ["sentiment", "감성", "label", "pred"],
        "score": ["score", "점수", "prob", "confidence"],
        "mode": ["mode", "방법", "model"],
    }
    colmap = {}
    for k, cands in aliases.items():
        for c in cands:
            if c in df.columns:
                colmap[c] = k
                break
    df = df.rename(columns=colmap)

    # 필수 컬럼 없으면 채우기
    for need in ["title", "url"]:
        if need not in df.columns:
            df[need] = ""
    if "date" in df.columns:
        df["date"] = df["date"].apply(parse_date)
    else:
        df["date"] = None
    for opt in ["press", "sentiment", "score", "mode"]:
        if opt not in df.columns:
            df[opt] = None

    return df[["title", "url", "press", "date", "sentiment", "score", "mode"]]

def put_gridfs_once(path: str):
    with open(path, "rb") as f:
        data = f.read()
    fid = hashlib.sha1(data).hexdigest()
    if fs.exists({"filename": os.path.basename(path), "metadata.sha1": fid}):
        return
    fs.put(
        data,
        filename=os.path.basename(path),
        metadata={"sha1": fid, "path": path, "ingested_at": datetime.now(timezone.utc),}
    )

def upsert_csv(path: str):
    try:
        df = pd.read_csv(path)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp949")
    df = norm_cols(df).dropna(subset=["url"])
    ops = []
    now = datetime.now(timezone.utc)
    for r in df.to_dict("records"):
        doc = {
            "headline": r["title"],
            "url": r["url"],
            "press": r["press"],
            "date": r["date"],
            "sentiment": r["sentiment"],
            "score": float(r["score"]) if pd.notna(r["score"]) else None,
            "mode": r["mode"],
            "source_file": os.path.basename(path),
            "ingested_at": now,
        }
        ops.append(
            UpdateOne(
                {"url": doc["url"]},
                {"$set": doc, "$setOnInsert": {"first_seen": now}},
                upsert=True,
            )
        )
    if ops:
        res = col.bulk_write(ops, ordered=False)
        print(
            f"{os.path.basename(path)} -> upserted:{res.upserted_count} modified:{res.modified_count}"
        )
    put_gridfs_once(path)

# ===== 메인 =====
def main():
    csvs = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    if not csvs:
        print("no csv in ./data")
        return
    for p in csvs:
        upsert_csv(p)
    print("done")

if __name__ == "__main__":
    main()
