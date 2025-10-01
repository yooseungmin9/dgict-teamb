# mongo_sink.py
from datetime import datetime, timezone
import os, pandas as pd
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

load_dotenv()
URI=os.getenv("MONGO_URI","mongodb://localhost:27017")
DBN=os.getenv("DB_NAME","econnews")
_client=MongoClient(URI, tz_aware=True); _col=_client[DBN].articles

_ALIASES={
  "headline":["headline","title","제목"],
  "url":["url","링크","기사링크"],
  "press":["press","언론사","매체"],
  "date":["date","날짜","작성일","published_at","crawl_date"],
  "sentiment":["sentiment","감성","label","pred"],
  "score":["score","점수","prob","confidence"],
  "mode":["mode","방법","model"],
}

def _normalize_df(df: pd.DataFrame)->pd.DataFrame:
    df = df.copy()
    colmap = {}
    for k, cands in _ALIASES.items():
        for c in cands:
            if c in df.columns:
                colmap[c] = k; break
    df = df.rename(columns=colmap)

    for need in ["headline","url"]:
        if need not in df.columns: df[need] = None
    for opt in ["press","date","sentiment","score","mode"]:
        if opt not in df.columns: df[opt] = None

    # 날짜 파싱: crawler의 "YYYY-MM-DD_HHMM" 처리
    if "date" in df.columns:
        def _parse(x):
            if isinstance(x, str) and "_" in x and len(x) >= 13:
                return pd.to_datetime(x, format="%Y-%m-%d_%H%M", errors="coerce")
            return pd.to_datetime(x, errors="coerce")
        df["date"] = df["date"].apply(_parse)

    return df[["headline","url","press","date","sentiment","score","mode"]]

def _to_mongo_dt(x):
    if x is None or (isinstance(x,float) and pd.isna(x)) or pd.isna(x): return None
    if isinstance(x, pd.Timestamp):
        t=x
        if t.tzinfo is not None:
            try: t=t.tz_convert("UTC")
            except Exception: t=t.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
        return t.to_pydatetime().replace(tzinfo=None)
    if isinstance(x, datetime):
        return x.astimezone(timezone.utc).replace(tzinfo=None) if x.tzinfo else x
    t=pd.to_datetime(x, errors="coerce")
    return None if pd.isna(t) else t.to_pydatetime().replace(tzinfo=None)

def upsert_dataframe(df: pd.DataFrame, source_file:str="runtime")->int:
    if df is None or df.empty: return 0
    df = _normalize_df(df)
    df["date"] = df["date"].astype("object").apply(
        lambda x: None if (x is pd.NaT or pd.isna(x))
        else (x.to_pydatetime().replace(tzinfo=None) if isinstance(x, pd.Timestamp) else x)
    )
    now = datetime.utcnow()  # ← naive UTC로 저장
    ops=[]
    for r in df.to_dict("records"):
        url = (r.get("url") or "").strip()
        if not url:
            continue
        dt = r.get("date")
        if isinstance(dt, pd.Timestamp):
            date = None if pd.isna(dt) else dt.to_pydatetime().replace(tzinfo=None)
        else:
            date = None

        score = r.get("score")
        score = float(score) if score is not None and not pd.isna(score) else None

        doc = {
            "headline": r.get("headline"),
            "url": url,
            "press": r.get("press"),
            "date": date,  # ← 여기서 정리된 값만 들어감
            "sentiment": r.get("sentiment"),
            "score": score,
            "mode": r.get("mode"),
            "source_file": str(source_file),
            "ingested_at": datetime.utcnow(),
        }

        ops.append(UpdateOne(
            {"url": url},
            {"$set": doc, "$setOnInsert": {"first_seen": datetime.utcnow()}},
            upsert=True
        ))
    if not ops: return 0
    res=_col.bulk_write(ops, ordered=False)
    print("date preview:", df["date"].head(10))
    return (res.upserted_count or 0)+(res.modified_count or 0)
