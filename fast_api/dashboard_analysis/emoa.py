# emoa_api.py
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta, time
from contextlib import asynccontextmanager
import pytz
from typing import Tuple, Dict, Any, Optional

# ====== 설정 ======
KST = pytz.timezone("Asia/Seoul")

MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

CLIENT = MongoClient(MONGO_URI)
COLL   = CLIENT[DB_NAME][COLL_NAME]


def _ensure_indexes() -> None:
    try:
        COLL.create_index("published_at")
    except Exception:
        pass


# -------- MongoDB 표현식: 문서별 점수 정규화(→ 0~100) --------
def _norm_expr(field: str = "$sentiment_score") -> Dict[str, Any]:
    """
    문서 하나의 sentiment_score를 0~100으로 정규화하는 MongoDB 표현식.
    - 0~1      → *100
    - -1~1     → (x+1)/2 * 100
    - 0~100    → 그대로
    - -100~100 → (x+100)/200 * 100
    - 그 외    → [0,100]로 클램프
    """
    return {
        "$let": {
            "vars": {
                "s": {
                    "$convert": {"input": field, "to": "double", "onError": None, "onNull": None}
                }
            },
            "in": {
                "$switch": {
                    "branches": [
                        # 0~1
                        {
                            "case": {"$and": [{"$gte": ["$$s", 0]}, {"$lte": ["$$s", 1]}]},
                            "then": {"$multiply": ["$$s", 100]},
                        },
                        # -1~1
                        {
                            "case": {"$and": [{"$gte": ["$$s", -1]}, {"$lte": ["$$s", 1]}]},
                            "then": {"$multiply": [{"$divide": [{"$add": ["$$s", 1]}, 2]}, 100]},
                        },
                        # 0~100
                        {
                            "case": {"$and": [{"$gte": ["$$s", 0]}, {"$lte": ["$$s", 100]}]},
                            "then": "$$s",
                        },
                        # -100~100
                        {
                            "case": {"$and": [{"$gte": ["$$s", -100]}, {"$lte": ["$$s", 100]}]},
                            "then": {"$multiply": [{"$divide": [{"$add": ["$$s", 100]}, 200]}, 100]},
                        },
                    ],
                    "default": {
                        "$cond": [
                            {"$lt": ["$$s", 0]},
                            0,
                            {"$cond": [{"$gt": ["$$s", 100]}, 100, "$$s"]},
                        ]
                    },
                }
            },
        }
    }


def _bucket_expr(field: str = "$sentiment_score") -> Dict[str, Any]:
    """디버깅용: 문서가 어떤 스케일 분기에 걸렸는지 라벨링."""
    return {
        "$let": {
            "vars": {"s": {"$convert": {"input": field, "to": "double", "onError": None, "onNull": None}}},
            "in": {
                "$switch": {
                    "branches": [
                        {"case": {"$and": [{"$gte": ["$$s", 0]}, {"$lte": ["$$s", 1]}]}, "then": "0_1"},
                        {"case": {"$and": [{"$gte": ["$$s", -1]}, {"$lte": ["$$s", 1]}]}, "then": "neg1_pos1"},
                        {"case": {"$and": [{"$gte": ["$$s", 0]}, {"$lte": ["$$s", 100]}]}, "then": "0_100"},
                        {"case": {"$and": [{"$gte": ["$$s", -100]}, {"$lte": ["$$s", 100]}]}, "then": "neg100_pos100"},
                    ],
                    "default": "other",
                }
            },
        }
    }


# -------- 집계 헬퍼 --------
def _avg_for_day(day) -> Tuple[Optional[float], int, Dict[str, int]]:
    """
    해당 '날짜(KST 자정~자정)' 범위의 문서별 정규화 점수 평균과 카운트, 버킷 카운트.
    """
    s = KST.localize(datetime.combine(day, time.min))
    e = KST.localize(datetime.combine(day, time.max))
    pipe = [
        {"$addFields": {"_dt": {"$toDate": "$published_at"}}},
        {"$match": {"_dt": {"$gte": s, "$lte": e}}},
        {"$project": {
            "_id": 0,
            "score_norm": _norm_expr("$sentiment_score"),
            "bucket": _bucket_expr("$sentiment_score"),
        }},
        {"$match": {"score_norm": {"$ne": None}}},
        # 전체 평균 & 버킷 분포를 한 번에 계산
        {"$group": {
            "_id": None,
            "avg_norm": {"$avg": "$score_norm"},
            "cnt": {"$sum": 1},
            "buckets": {"$push": "$bucket"},
        }},
        # 버킷 분포를 {label: count} 객체로 변환
        {"$project": {
            "_id": 0,
            "avg_norm": 1,
            "cnt": 1,
            "bucket_counts": {
                "$arrayToObject": {
                    "$map": {
                        "input": {"$setUnion": ["$buckets", []]},
                        "as": "b",
                        "in": {
                            "k": "$$b",
                            "v": {"$size": {"$filter": {"input": "$buckets", "as": "x", "cond": {"$eq": ["$$x", "$$b"]}}}},
                        },
                    }
                }
            },
        }},
    ]
    rows = list(COLL.aggregate(pipe))
    if not rows:
        return None, 0, {}
    row = rows[0]
    avg = round(float(row["avg_norm"]), 2)
    return avg, int(row["cnt"]), {k: int(v) for k, v in row.get("bucket_counts", {}).items()}


def _avg_overall() -> Tuple[Optional[float], int, Dict[str, int]]:
    """
    컬렉션 전체의 문서별 정규화 점수 평균과 카운트, 버킷 카운트.
    """
    pipe = [
        {"$project": {
            "_id": 0,
            "score_norm": _norm_expr("$sentiment_score"),
            "bucket": _bucket_expr("$sentiment_score"),
        }},
        {"$match": {"score_norm": {"$ne": None}}},
        {"$group": {
            "_id": None,
            "avg_norm": {"$avg": "$score_norm"},
            "cnt": {"$sum": 1},
            "buckets": {"$push": "$bucket"},
        }},
        {"$project": {
            "_id": 0,
            "avg_norm": 1,
            "cnt": 1,
            "bucket_counts": {
                "$arrayToObject": {
                    "$map": {
                        "input": {"$setUnion": ["$buckets", []]},
                        "as": "b",
                        "in": {
                            "k": "$$b",
                            "v": {"$size": {"$filter": {"input": "$buckets", "as": "x", "cond": {"$eq": ["$$x", "$$b"]}}}},
                        },
                    }
                }
            },
        }},
    ]
    rows = list(COLL.aggregate(pipe))
    if not rows:
        return None, 0, {}
    row = rows[0]
    avg = round(float(row["avg_norm"]), 2)
    return avg, int(row["cnt"]), {k: int(v) for k, v in row.get("bucket_counts", {}).items()}


# -------- FastAPI --------
@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_indexes()
    yield
    CLIENT.close()

app = FastAPI(title="EMOA API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/emoa/score")
def emoa_score():
    today = datetime.now(KST).date()

    today_avg,  today_cnt,  today_buckets  = _avg_for_day(today)
    overall_avg, all_cnt,  overall_buckets = _avg_overall()

    weekday_ko = ["월","화","수","목","금","토","일"][today.weekday()]

    return {
        "date": str(today),
        "weekday": weekday_ko,
        "today_avg": today_avg,           # 문서별 정규화 후 평균
        "overall_avg": overall_avg,       # 문서별 정규화 후 평균
        "counts": { "today": today_cnt, "overall": all_cnt },
        "debug": {                        # 관찰/검증용: 어떤 스케일 문서가 섞였는지
            "today_bucket_counts": today_buckets,
            "overall_bucket_counts": overall_buckets
        },
        # 레거시 호환
        "avg": today_avg
    }
