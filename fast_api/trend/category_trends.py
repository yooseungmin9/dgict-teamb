# -*- coding: utf-8 -*-
from __future__ import annotations

from itertools import islice
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta
from typing import Dict, Any, Optional
import os, requests
from pymongo import MongoClient
from dotenv import load_dotenv

# 0) .env 로드 (없으면 조용히 패스)
load_dotenv()

# ====== ENV ======
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "test123")
MONGO_COL_SHARED = os.getenv("MONGO_COL_SHARED", "shared_articles")

NAVER_TIMEOUT = int(os.getenv("NAVER_TIMEOUT", "15"))

# ====== MongoDB (옵션: 실제로는 현재 엔드포인트에서 사용하지 않지만, 기존 코드 호환 유지)
mongo_client = MongoClient(MONGO_URI)
mongo_col = mongo_client[MONGO_DB][MONGO_COL_SHARED]

# ====== APP ======
app = FastAPI(title="Trend API (Naver Datalab)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 필요시 ENV로 빼도 됨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CATEGORIES = ["증권", "금융", "부동산", "산업", "글로벌경제", "일반"]

CATEGORY_KEYWORDS: Dict[str, list[str]] = {
    "증권": ["증권", "주식", "코스피", "코스닥"],
    "금융": ["금융", "예금", "대출", "금리"],
    "부동산": ["부동산", "아파트", "전세", "매매"],
    "산업": ["산업", "제조업", "반도체", "수출"],
    "글로벌경제": ["글로벌 경제", "미국 금리", "중국 경기", "달러"],
    "일반": ["소비", "물가", "경기", "실업률"],
}

# ====== 유틸 ======
def chunked(d: Dict[str, list[str]], size: int):
    it = iter(d.items())
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield dict(batch)

def _require_naver_keys():
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise HTTPException(500, "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 필요합니다.")

# 데이터랩에서 5개씩 끊어서 호출 후 병합
def call_naver_datalab_groups(start_date: str, end_date: str, time_unit: str, groups_dict: dict):
    _require_naver_keys()
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    }

    all_results = []
    for batch in chunked(groups_dict, 5):
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": [{"groupName": k, "keywords": v} for k, v in batch.items()],
        }
        r = requests.post(url, headers=headers, json=payload, timeout=NAVER_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        all_results.extend(j.get("results", []))
    return {"results": all_results}

# ====== 엔드포인트 ======
# 현재 기준 최근 N일 날짜 라벨과 카테고리별 값 배열 정렬 / 반환
@app.get("/category-trends")
def category_trends(days: int = 30, time_unit: str = "date"):
    end = date.today()
    start = end - timedelta(days=days)
    start_date = start.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")

    raw = call_naver_datalab_groups(start_date, end_date, time_unit, CATEGORY_KEYWORDS)

    all_dates = set()
    for result in raw.get("results", []):
        for item in result.get("data", []):
            all_dates.add(item["period"])
    labels = sorted(all_dates)

    categories: Dict[str, list[int]] = {}
    for result in raw.get("results", []):
        cat = result.get("title")
        series_map = {d["period"]: d["ratio"] for d in result.get("data", [])}
        categories[cat] = [int(round(series_map.get(dt, 0))) for dt in labels]

    for cat in CATEGORIES:
        categories.setdefault(cat, [0] * len(labels))

    return {"source": "naver", "dates": labels, "categories": categories}

# 샘플 데이터 확인
@app.get("/sentiment/line")
def sentiment_line():
    data = [
        {"date": "2025-10-01", "positive": 50, "neutral": 30, "negative": 20},
        {"date": "2025-10-02", "positive": 48, "neutral": 31, "negative": 21},
    ]
    return {
        "labels": [d["date"] for d in data],
        "series": {
            "positive": [d["positive"] for d in data],
            "neutral": [d["neutral"] for d in data],
            "negative": [d["negative"] for d in data],
        },
    }

# api의 유효성 체크
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "trends",
        "has_naver_keys": bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET),
        "db": {"db": MONGO_DB, "collection": MONGO_COL_SHARED},
    }
