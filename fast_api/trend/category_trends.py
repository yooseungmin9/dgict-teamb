from itertools import islice

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta
import requests
from pymongo import MongoClient

# ====== NAVER ======
NAVER_CLIENT_ID = "zltdiHFAdmmvXlRwBuqA"
NAVER_CLIENT_SECRET = "3Y5I7ZkpmP"

# ====== MongoDB ======
mongo_client = MongoClient("mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
mongo_col = mongo_client["test123"]["shared_articles"]

CATEGORIES = ["증권", "금융", "부동산", "산업", "글로벌경제", "일반"]

CATEGORY_KEYWORDS = {
    "증권": ["증권", "주식", "코스피", "코스닥"],
    "금융": ["금융", "예금", "대출", "금리"],
    "부동산": ["부동산", "아파트", "전세", "매매"],
    "산업": ["산업", "제조업", "반도체", "수출"],
    "글로벌경제": ["글로벌 경제", "미국 금리", "중국 경기", "달러"],
    "일반": ["소비", "물가", "경기", "실업률"],
}

app = FastAPI(title="Trend API (Naver Datalab)", version="1.0.0")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== 유틸 ======
def chunked(iterable, size):
    """딕셔너리를 size 개씩 나눔"""
    it = iter(iterable.items())
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield dict(batch)

def call_naver_datalab_groups(start_date: str, end_date: str, time_unit: str, groups_dict: dict):
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
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        j = r.json()
        all_results.extend(j.get("results", []))
    return {"results": all_results}

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

    categories = {}
    for result in raw.get("results", []):
        cat = result.get("title")
        series_map = {d["period"]: d["ratio"] for d in result.get("data", [])}
        categories[cat] = [int(round(series_map.get(dt, 0))) for dt in labels]

    for cat in CATEGORIES:
        categories.setdefault(cat, [0] * len(labels))

    return {"source": "naver", "dates": labels, "categories": categories}

@app.get("/sentiment/line")
def sentiment_line():
    data = [
        {"date":"2025-10-01","positive":50,"neutral":30,"negative":20},
        {"date":"2025-10-02","positive":48,"neutral":31,"negative":21}
    ]
    return {"labels": [d["date"] for d in data],
            "series": {
                "positive": [d["positive"] for d in data],
                "neutral": [d["neutral"] for d in data],
                "negative": [d["negative"] for d in data]
            }}

@app.get("/health")
def health():
    return {"ok": True, "service": "trends"}
