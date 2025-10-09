from __future__ import annotations
import os, math, json, warnings
from datetime import datetime, time, timedelta, timezone
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
from statsmodels.tsa.seasonal import STL
import re

warnings.filterwarnings("ignore")

# ====== 환경설정 ======
TZ = timezone(timedelta(hours=9))
NOW = datetime.now(TZ)

MONGO_URI   = os.getenv("MONGO_URI", "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
DB_NAME     = os.getenv("MONGO_DB",  "test123")
COL_PREP    = os.getenv("MONGO_COL_PREP", "articles_preprocessed")   # 표준명
COL_OUT_TS  = os.getenv("MONGO_COL_TRENDS_DAILY", "trends_daily")
COL_OUT_WK  = os.getenv("MONGO_COL_TRENDS_WEEKLY", "trends_weekly_reports")
COL_BURST = os.getenv("MONGO_COL_BURST", "burst_keywords")

# 클러스터 소스(요약/맵핑 컬렉션). 없으면 자동 탐색
COL_CLU_SUM = os.getenv("MONGO_COL_CLUSTERS", "clusters")            # 클러스터 요약(집계)
COL_CLU_MAP = os.getenv("MONGO_COL_CLUSTER_MAP", "article_clusters") # ref_id↔cluster 매핑이 있다면 사용

# 분석 파라미터
LOOKBACK_DAYS = int(os.getenv("TRENDS_LOOKBACK_DAYS", "50"))
MIN_SERIES_LEN = int(os.getenv("TRENDS_MIN_SERIES_LEN", "21"))  # STL 최소 길이 확보용
SPIKE_Q = float(os.getenv("TRENDS_SPIKE_UPPER_Q", "0.95"))      # 상위 5%
MA_WINDOW = int(os.getenv("TRENDS_MA_WINDOW", "7"))              # 7일 이동평균
WEEK_START_ISO = int(os.getenv("TRENDS_WEEK_START_ISO", "1"))    # 1=월
TOP_K_ARTS_PER_SPIKE = int(os.getenv("TRENDS_TOP_ARTS", "3"))
GROUP_BY = os.getenv("TRENDS_GROUP_BY", "cluster")  # 기본 cluster, 필요시 topic

TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")

# ====== 공통 ======

def _mongo():
    return MongoClient(MONGO_URI)[DB_NAME]


def _ensure_indexes():
    db = _mongo()
    db[COL_PREP].create_index([("published_at", DESCENDING)], name="pub_desc")
    db[COL_OUT_TS].create_index([("group_key", ASCENDING), ("date", ASCENDING)], unique=True, name="gk_date")
    db[COL_OUT_WK].create_index([("week_start", DESCENDING)], name="wk_desc")
    db[COL_BURST].create_index([("keyword", ASCENDING), ("date", ASCENDING)], unique=True, name="kw_date")
    db[COL_BURST].create_index([("date", DESCENDING), ("ratio", DESCENDING)], name="date_ratio")


def _floor_date(d: datetime) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=TZ)

# ====== 클러스터 매핑 로더 ======

def _load_cluster_mapping(db) -> Optional[pd.DataFrame]:
    """ref_id→(cluster_id, cluster_label) 매핑을 찾는다.
    우선순위:
      1) COL_CLU_MAP 컬렉션에 {ref_id, cluster, label?} 문서
      2) COL_CLU_SUM 컬렉션에 {cluster, label, ref_ids[]|members[]} 문서
      3) 없으면 None
    """
    # 1) article_clusters 스타일
    try:
        if COL_CLU_MAP in db.list_collection_names():
            cur = db[COL_CLU_MAP].find({}, {"_id":0, "ref_id":1, "cluster":1, "label":1, "cluster_id":1, "cluster_label":1}).limit(1)
            probe = list(cur)
            if probe:
                # 전체 로드
                rows = list(db[COL_CLU_MAP].find({}, {"_id":0, "ref_id":1, "cluster":1, "label":1, "cluster_id":1, "cluster_label":1}))
                df = pd.DataFrame(rows)
                if df.empty:
                    return None
                # 표준화
                if "cluster_id" not in df.columns:
                    if "cluster" in df.columns:
                        df["cluster_id"] = df["cluster"]
                if "cluster_label" not in df.columns:
                    if "label" in df.columns:
                        df["cluster_label"] = df["label"]
                keep = [c for c in ["ref_id", "cluster_id", "cluster_label"] if c in df.columns]
                if set(["ref_id", "cluster_id"]).issubset(keep):
                    return df[keep].copy()
    except Exception:
        pass

    # 2) clusters 요약 컬렉션에 멤버 배열이 들어있는 형태
    try:
        if COL_CLU_SUM in db.list_collection_names():
            # 멤버 키 후보
            member_keys = ["ref_ids", "members", "docs", "articles", "items"]
            # 라벨 키 후보
            label_keys = ["cluster_label", "label", "name", "title"]
            rows = list(db[COL_CLU_SUM].find({}, {"_id":0}))
            if not rows:
                return None
            maps = []
            for r in rows:
                cid = r.get("cluster") or r.get("cluster_id")
                # label
                lab = None
                for lk in label_keys:
                    if lk in r:
                        lab = r[lk]
                        break
                # members
                members = None
                for mk in member_keys:
                    if mk in r and isinstance(r[mk], list):
                        members = r[mk]
                        break
                if cid is not None and members:
                    for m in members:
                        # m이 dict면 ref_id 키 시도
                        if isinstance(m, dict):
                            rid = m.get("ref_id") or m.get("id") or m.get("_id")
                        else:
                            rid = m
                        if rid:
                            maps.append({"ref_id": rid, "cluster_id": cid, "cluster_label": lab})
            if maps:
                return pd.DataFrame(maps)
    except Exception:
        pass

    return None

# ====== 데이터 로드 ======

def load_articles(days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    db = _mongo()
    since = _floor_date(NOW - timedelta(days=days))
    cur = db[COL_PREP].find(
        {"published_at": {"$gte": since}},
        {
            "_id": 0,
            "ref_id": 1,
            "published_at": 1,
            "url": 1,
            "title": 1,
            "title_clean": 1,
            "content": 1,
            "body_clean": 1,
            "topic": 1,
            "topic_label": 1,
            "cluster_id": 1,
            "cluster_label": 1,
            "content_len": 1,
        },
    )
    rows = list(cur)
    if not rows:
        return pd.DataFrame(columns=["date", "url", "title", "content_len", "group_key"])  # 빈 DF

    df = pd.DataFrame(rows)

    # 날짜
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True).dt.tz_convert(TZ)
    df["date"] = df["published_at"].dt.date

    if "title" not in df.columns:
        df["title"] = df.get("title_clean", "")
    df["title"] = df["title"].fillna("").astype(str)

    if "url" not in df.columns:
        df["url"] = ""

    # 본문 길이 대체
    if "content" in df.columns:
        df["content_len"] = df["content"].fillna("").astype(str).str.len()
    elif "body_clean" in df.columns:
        df["content_len"] = df["body_clean"].fillna("").astype(str).str.len()
    else:
        df["content_len"] = 0

    # 1) 기사에 이미 클러스터/토픽이 붙어있으면 그걸 사용
    gk_col = None
    pref_order = [
        ("cluster_label", "cluster"), ("cluster_id", "cluster"),
        ("topic_label", "topic"), ("topic", "topic")
    ]
    for c, typ in pref_order:
        if c in df.columns:
            gk_col = c
            break

    # 2) 없으면 외부 매핑 컬렉션에서 조인(ref_id 기준)
    if gk_col is None:
        cmap = _load_cluster_mapping(db)
        if cmap is not None and "ref_id" in df.columns:
            df = df.merge(cmap, on="ref_id", how="left")
            for c in ["cluster_label", "cluster_id", "topic_label", "topic"]:
                if c in df.columns:
                    gk_col = c
                    break

    # 3) 그래도 없으면 전체 그룹(_all)
    if gk_col and gk_col in df.columns:
        df["group_key"] = df[gk_col].astype(str).fillna("_nan")
    else:
        df["group_key"] = "_all"

    keep = ["date", "url", "title", "content_len", "group_key"]
    return df[keep].copy()

# ====== 일별 시계열 구축 ======

def build_daily_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["group_key", "date", "count", "ma7", "adj_count", "resid", "is_spike"])

    dmin, dmax = df["date"].min(), df["date"].max()
    full_index = pd.date_range(start=dmin, end=dmax, freq="D").date

    out = []
    for g, sub in df.groupby("group_key"):
        daily = (
            sub.groupby("date").size().reindex(full_index, fill_value=0).rename("count").to_frame()
        )
        daily.index.name = "date"
        daily.reset_index(inplace=True)
        daily["group_key"] = g

        # 이동평균
        daily["ma7"] = daily["count"].rolling(window=MA_WINDOW, min_periods=1).mean()

        # 요일 효과 보정(단순 OLS)
        wk = pd.to_datetime(daily["date"]).dt.weekday
        X = pd.get_dummies(wk, drop_first=False).astype(float)
        y = daily["count"].astype(float).values
        try:
            beta = np.linalg.pinv(X.values) @ y
            fitted = X.values @ beta
            weekday_effect = pd.Series(fitted - fitted.mean())
            daily["adj_count"] = daily["count"] - weekday_effect
        except Exception:
            daily["adj_count"] = daily["count"]

        # STL 잔차
        if len(daily) >= MIN_SERIES_LEN:
            try:
                stl = STL(daily["adj_count"].values, period=7, robust=True)
                res = stl.fit()
                daily["resid"] = res.resid
            except Exception:
                daily["resid"] = daily["adj_count"] - daily["adj_count"].rolling(7, min_periods=1).mean()
        else:
            daily["resid"] = daily["adj_count"] - daily["adj_count"].rolling(7, min_periods=1).mean()

        thr = np.quantile(daily["resid"].dropna(), SPIKE_Q) if daily["resid"].notna().any() else np.inf
        daily["is_spike"] = (daily["resid"] >= thr).astype(int)

        out.append(daily)

    out_df = pd.concat(out, ignore_index=True)
    return out_df[["group_key", "date", "count", "ma7", "adj_count", "resid", "is_spike"]]

# ====== 주간 리포트 ======

def _week_start(d: datetime) -> datetime:
    dt = pd.Timestamp(d).to_pydatetime()
    offset = (dt.isoweekday() - WEEK_START_ISO) % 7
    ws = datetime(dt.year, dt.month, dt.day, tzinfo=TZ) - timedelta(days=offset)
    return datetime(ws.year, ws.month, ws.day, tzinfo=TZ)


def select_representative_articles(raw_df: pd.DataFrame, gk: str, day: datetime.date, k: int = TOP_K_ARTS_PER_SPIKE) -> List[Dict[str, Any]]:
    sub = raw_df[(raw_df["group_key"] == gk) & (raw_df["date"] == day)]
    if sub.empty:
        return []
    sub = sub.sort_values(["content_len"], ascending=False).head(k)
    return [{"title": r.get("title", ""), "url": r.get("url", "")} for _, r in sub.iterrows()]


def weekly_categorize(ts: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    if ts.empty:
        return {"new": [], "surging": [], "fading": []}

    today = _floor_date(NOW).date()
    ws = _week_start(datetime.combine(today, datetime.min.time(), tzinfo=TZ)).date()
    we = (ws + timedelta(days=7))

    res = []
    for g, sub in ts.groupby("group_key"):
        sub = sub.sort_values("date")
        this_week = sub[(sub["date"] >= ws) & (sub["date"] < we)]
        prev_week = sub[(sub["date"] >= ws - timedelta(days=7)) & (sub["date"] < ws)]
        prev2_week = sub[(sub["date"] >= ws - timedelta(days=14)) & (sub["date"] < ws - timedelta(days=7))]
        past_30 = sub[(sub["date"] >= ws - timedelta(days=30)) & (sub["date"] < ws)]

        tw_sum = int(this_week["count"].sum())
        pw_sum = int(prev_week["count"].sum())
        p2_sum = int(prev2_week["count"].sum())
        p30_sum = int(past_30["count"].sum())
        tw_spikes = int(this_week["is_spike"].sum())

        res.append({
            "group_key": g,
            "this_week": tw_sum,
            "prev_week": pw_sum,
            "prev2_week": p2_sum,
            "past30": p30_sum,
            "this_week_spikes": tw_spikes,
        })

    wk_df = pd.DataFrame(res)
    if wk_df.empty:
        return {"new": [], "surging": [], "fading": []}

    new_mask = (wk_df["past30"] == 0) & (wk_df["this_week"] > 0)
    surge_mask = (wk_df["prev_week"] > 0) & ((wk_df["this_week"] / wk_df["prev_week"].replace(0, np.nan)) >= 2) & (wk_df["this_week_spikes"] >= 1)
    fade_mask = ((wk_df["prev_week"] + wk_df["prev2_week"]) > 0) & (wk_df["this_week"] == 0)

    return {
        "new": wk_df[new_mask].sort_values("this_week", ascending=False).to_dict("records"),
        "surging": wk_df[surge_mask].sort_values("this_week", ascending=False).to_dict("records"),
        "fading": wk_df[fade_mask].sort_values(["prev_week", "prev2_week"], ascending=False).to_dict("records"),
    }

# ====== Mongo 업서트 ======
import pymongo  # 지연 임포트

def upsert_daily(ts: pd.DataFrame):
    if ts.empty:
        return
    db = _mongo()
    ops = []
    for _, r in ts.iterrows():
        # 날짜 안전 변환
        d = pd.Timestamp(r["date"]).to_pydatetime().date()
        k = {"group_key": r["group_key"],
             "date": datetime(d.year, d.month, d.day, tzinfo=TZ)}

        # 키 접근 + NaN 처리
        cnt = int(float(r["count"]))
        ma7 = None if pd.isna(r["ma7"]) else float(r["ma7"])
        adj = None if pd.isna(r["adj_count"]) else float(r["adj_count"])
        res = None if pd.isna(r["resid"]) else float(r["resid"])
        spk = int(r["is_spike"])

        v = {"$set": {
            "count": cnt,
            "ma7": ma7,
            "adj_count": adj,
            "resid": res,
            "is_spike": spk,
            "updated_at": NOW,
        }}
        ops.append(pymongo.UpdateOne(k, v, upsert=True))
    if ops:
        db[COL_OUT_TS].bulk_write(ops, ordered=False)


def build_weekly_report(raw_df: pd.DataFrame, ts_df: pd.DataFrame) -> Dict[str, Any]:
    today = _floor_date(NOW).date()
    ws = _week_start(datetime.combine(today, datetime.min.time(), tzinfo=TZ)).date()
    we = (ws + timedelta(days=7))

    cats = weekly_categorize(ts_df)

    week_spikes = ts_df[(ts_df["date"] >= ws) & (ts_df["date"] < we) & (ts_df["is_spike"] == 1)]
    spikes: List[Dict[str, Any]] = []
    for (gk, day), sub in week_spikes.groupby(["group_key", "date"]):
        reps = select_representative_articles(raw_df, gk, day, TOP_K_ARTS_PER_SPIKE)
        spikes.append({
            "group_key": gk,
            "date": str(day),
            "count": int(sub["count"].sum()),
            "ma7": float(sub["ma7"].mean()),
            "adj_count": float(sub["adj_count"].mean()),
            "resid": float(sub["resid"].mean()),
            "articles": reps,
        })

    report = {
        "week_start": datetime(ws.year, ws.month, ws.day, tzinfo=TZ),
        "generated_at": NOW,
        "params": {
            "group_by": GROUP_BY,
            "lookback_days": LOOKBACK_DAYS,
            "ma_window": MA_WINDOW,
            "spike_quantile": SPIKE_Q,
        },
        "categories": cats,
        "spikes": spikes,
        "notes": [
            "30일 데이터는 계절성 추정에 제약이 있어 STL 결과가 불안정할 수 있음.",
            "설명은 대표 기사 링크로 보강할 것.",
        ],
    }
    return report

def _tokens(s: str) -> list[str]:
    return TOKEN.findall((s or "").lower())

def save_burst_keywords(raw_df: pd.DataFrame, ts_df: pd.DataFrame, top_n: int = 10):
    if raw_df.empty: return
    db = _mongo()
    ops = []
    for day in sorted(raw_df["date"].unique()):
        sub = raw_df[raw_df["date"] == day]
        # 일자 토큰 빈도
        day_counts = {}
        for _, r in sub.iterrows():
            for t in _tokens(r.get("title","")):
                day_counts[t] = day_counts.get(t, 0) + 1
        if not day_counts: continue
        # 기준선: 최근 7일(당일 제외) 평균
        base_df = raw_df[(raw_df["date"] < day) & (raw_df["date"] >= (pd.to_datetime(day) - pd.Timedelta(days=7)).date())]
        base_counts = {}
        for _, r in base_df.iterrows():
            for t in _tokens(r.get("title","")):
                base_counts[t] = base_counts.get(t, 0) + 1
        rows = []
        for k, v in day_counts.items():
            base = base_counts.get(k, 0) / 7.0
            ratio = float(v) / (base if base > 0 else 0.5)   # 스무딩
            rows.append((k, v, base, ratio))
        rows.sort(key=lambda x: x[3], reverse=True)
        for k, cnt, base, ratio in rows[:top_n]:
            ops.append(pymongo.UpdateOne(
                {"keyword": k, "date": datetime.combine(day, time(0, 0, 0), tzinfo=TZ)},
                {"$set": {"count": int(cnt), "baseline": float(base), "ratio": float(ratio), "updated_at": NOW}},
                upsert=True
            ))
    if ops: db[COL_BURST].bulk_write(ops, ordered=False)
# ====== GPT 요약(옵션) ======

def _gpt_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _summarize_spike_with_gpt(spike: Dict[str, Any], group_by: str) -> Optional[str]:
    if not _gpt_available():
        return None
    try:
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        titles_urls = "\n".join([f"- {a['title']} ({a['url']})" for a in spike.get("articles", [])])
        prompt = (
            f"다음 {group_by}의 특정 날짜 스파이크 원인을 3문장으로 한국어 요약하라.\n"
            f"그룹: {spike['group_key']}\n날짜: {spike['date']}\n"
            f"대표 기사:\n{titles_urls}\n"
            f"요약은 과도한 해석 없이 기사 근거 위주로. 마지막 줄에 핵심 키워드 3개를 해시태그로 제시."
        )
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message["content"].strip()
    except Exception:
        return None


def enrich_report_with_gpt(report: Dict[str, Any]) -> Dict[str, Any]:
    if not _gpt_available():
        return report
    updated = []
    for sp in report.get("spikes", []):
        summ = _summarize_spike_with_gpt(sp, report["params"]["group_by"])  # type: ignore
        if summ:
            sp["gpt_summary"] = summ
        updated.append(sp)
    report["spikes"] = updated
    return report

# ====== 메인 ======

def run() -> Dict[str, Any]:
    _ensure_indexes()
    raw = load_articles(LOOKBACK_DAYS)
    ts = build_daily_timeseries(raw)
    upsert_daily(ts)

    save_burst_keywords(raw, ts, top_n=10)

    report = build_weekly_report(raw, ts)
    report = enrich_report_with_gpt(report)
    save_weekly_report(report)

    return {
        "status": "ok",
        "now": NOW.isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "groups": int(ts["group_key"].nunique()) if not ts.empty else 0,
        "daily_rows": int(len(ts)),
        "week_start": report["week_start"].isoformat() if report else None,
        "spikes_this_week": int(len(report.get("spikes", []))) if report else 0,
    }


def save_weekly_report(doc: Dict[str, Any]) -> None:
    db = _mongo()
    ws = doc["week_start"]
    db[COL_OUT_WK].update_one({"week_start": ws}, {"$set": doc}, upsert=True)


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False))