# api/services/category_trends.py
# [입문자용] 네이버 데이터랩 카테고리 관심도 추이 로직만 담당

import requests
from datetime import date, timedelta
from api.common.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, CATEGORIES, CATEGORY_KEYWORDS, chunked

def call_naver_datalab_groups(start_date: str, end_date: str, time_unit: str, groups_dict: dict):
    """
    네이버 데이터랩 API 호출 (키워드 그룹 5개씩 제한 → chunked로 분할)
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
            "timeUnit": time_unit,
            "keywordGroups": [{"groupName": k, "keywords": v} for k, v in batch.items()],
        }
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        j = r.json()
        all_results.extend(j.get("results", []))
    return {"results": all_results}

def get_category_trends(days: int = 30, time_unit: str = "date"):
    """
    최근 N일 기준 카테고리 관심도 추이 계산
    반환: {"source":"naver","dates":[...],"categories":{"증권":[..],...}}
    """
    end = date.today()
    start = end - timedelta(days=days)
    start_date = start.strftime("%Y-%m-%d")
    end_date   = end.strftime("%Y-%m-%d")

    raw = call_naver_datalab_groups(start_date, end_date, time_unit, CATEGORY_KEYWORDS)

    # 전체 라벨(기간) 수집
    all_dates = set()
    for result in raw.get("results", []):
        for item in result.get("data", []):
            all_dates.add(item["period"])
    labels = sorted(all_dates)

    # 카테고리별 시계열 매핑
    categories = {}
    for result in raw.get("results", []):
        cat = result.get("title")
        series_map = {d["period"]: d["ratio"] for d in result.get("data", [])}
        categories[cat] = [int(round(series_map.get(dt, 0))) for dt in labels]

    # 누락 카테고리는 0으로 채움
    for cat in CATEGORIES:
        categories.setdefault(cat, [0] * len(labels))

    return {"source": "naver", "dates": labels, "categories": categories}