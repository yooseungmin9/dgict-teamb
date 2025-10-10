# app_naver.py — CORS 포함(변경 없음, 재확인용)
# 실행: uvicorn app_naver:app --reload --port 8010
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

NAVER_CLIENT_ID = "Dg2N296yjI3TGkftcbyW"
NAVER_CLIENT_SECRET = "_oEjrRP7N3"

app = FastAPI(title="KR Econ News via NAVER")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False
)

@app.get("/naver/econ")
def naver_econ_news(q: str = Query("미국 경제"), n: int = Query(5, ge=1, le=100), sort: str = Query("date")):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": q, "display": n, "start": 1, "sort": sort}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
        return {"count": len(items), "articles": [{"title": it.get("title"), "link": it.get("link")} for it in items]}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Naver API error: {e}")