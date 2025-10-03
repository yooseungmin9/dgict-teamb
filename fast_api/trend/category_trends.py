# app_trends.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta
import requests
from common.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, CATEGORIES, CATEGORY_KEYWORDS, chunked

app = FastAPI(title="Trend API (Naver Datalab)", version="1.0.0")

# ====== CORS ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/health")
def health():
    return {"ok": True, "service": "trends"}
