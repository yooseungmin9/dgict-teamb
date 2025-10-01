# api/routers/trends.py
# [입문자용] trend 라우터: 카테고리 관심도(네이버 데이터랩) + 키워드 랭킹(Mongo)
from fastapi import APIRouter, Query
from datetime import date, timedelta, datetime
import requests
from pymongo import MongoClient

# 패키지 경로 기준 임포트 (api/common/config.py)
from api.common.config import (
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    CATEGORIES,
    CATEGORY_KEYWORDS,
    chunked,
)

router = APIRouter()

# ===== Mongo 연결(상수 고정) =====
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

def mongo_col():
    """공용 컬렉션 핸들 반환(간단 버전)"""
    return MongoClient(MONGO_URI)[DB_NAME][COLL_NAME]

# ===== Naver DataLab 호출 유틸 =====
def call_naver_datalab_groups(start_date: str, end_date: str, time_unit: str, groups_dict: dict):
    """
    groups_dict 예: {"증권": ["증권","주식",...], "금융": [...], ...}
    DataLab API는 키워드 그룹 5개씩만 허용 → chunked()로 나눠 호출
    """
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
            "timeUnit": time_unit,  # "date"|"week"|"month"
            "keywordGroups": [{"groupName": k, "keywords": v} for k, v in batch.items()],
        }
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        j = r.json()
        all_results.extend(j.get("results", []))
    return {"results": all_results}

# =========================
# 1) 카테고리 관심도 추이
# =========================
@router.get("/category-trends")
def category_trends(
    days: int = Query(30, ge=7, le=365),
    time_unit: str = Query("date"),  # "date"|"week"|"month"
):
    """
    네이버 데이터랩 기준 카테고리 관심도(ratio) 시계열 반환
    반환: {"source":"naver","dates":[...],"categories":{"증권":[..],...}}
    """
    end = date.today()
    start = end - timedelta(days=days)
    start_date = start.strftime("%Y-%m-%d")
    end_date   = end.strftime("%Y-%m-%d")

    raw = call_naver_datalab_groups(start_date, end_date, time_unit, CATEGORY_KEYWORDS)

    # 라벨(기간) 수집
    all_dates = set()
    for result in raw.get("results", []):
        for item in result.get("data", []):
            all_dates.add(item["period"])
    labels = sorted(all_dates)

    # 카테고리별 시계열 매핑
    categories = {}
    for result in raw.get("results", []):
        cat = result.get("title")
        series = {d["period"]: d["ratio"] for d in result.get("data", [])}
        categories[cat] = [int(round(series.get(dt, 0))) for dt in labels]

    # 누락 카테고리는 0으로 채워 일관성 유지
    for cat in CATEGORIES:
        categories.setdefault(cat, [0] * len(labels))

    return {"source": "naver", "dates": labels, "categories": categories}

# =========================
# 2) 키워드 랭킹 (Mongo)
# =========================
@router.get("/keyword-ranking")
def keyword_ranking(
    days: int = Query(30, ge=7, le=365),
    topn: int = Query(100, ge=10, le=500),
):
    """
    최근 N일 간 문서의 keywords 배열을 펼쳐 {키워드, 카테고리}별 카운트 집계
    반환: [{rank, keyword, category, count}]  ※ rank는 프런트에서 다시 매겨도 OK
    요구 필드: news_date(YYYYMMDD), category, keywords(List[str])
    """
    col = mongo_col()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    pipeline = [
        {"$match": {
            "news_date": {"$gte": since},
            "keywords": {"$exists": True, "$ne": []}
        }},
        {"$unwind": "$keywords"},
        {"$group": {"_id": {"kw": "$keywords", "cat": "$category"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": topn * 10},   # 통합합산용 넉넉히 제공
    ]
    rows = list(col.aggregate(pipeline))

    out = []
    for r in rows:
        kw  = r["_id"]["kw"]
        cat = r["_id"]["cat"] or "-"
        cnt = int(r["count"])
        out.append({"rank": 0, "keyword": kw, "category": cat, "count": cnt})

    return out

# === (로컬) 간단 테스트 예시 ===
# uvicorn api.main:app --reload --port 8000
# curl "http://127.0.0.1:8000/api/trends/category-trends?days=30"
# curl "http://127.0.0.1:8000/api/trends/keyword-ranking?days=30&topn=50"