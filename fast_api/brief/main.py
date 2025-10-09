# main.py — 통합본: /news, /news/{id}, /briefing/yesterday, /health
# 실행: uvicorn main:app --reload --port 8000
# 필요 패키지:
#   pip install "fast_api>=0.110" uvicorn "pydantic<3" "pymongo==4.10.1" "openai>=1.46.0" "bson>=0.5.10"

from typing import List, Any, Dict
from datetime import datetime, timedelta, timezone
import json, re

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId  # 상세 조회용
from openai import OpenAI  # 전일 브리핑용

# =========================
# (1) 환경 상수 (필요 시만 수정)
# =========================
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

OPENAI_API_KEY = "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"
OPENAI_MODEL   = "gpt-4o-mini"        # 가벼운 모델 예시(원하면 다른 모델로 교체)

# =========================
# (2) FastAPI + CORS
# =========================
app = FastAPI(title="News API (All-in-one)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080", "http://127.0.0.1:8080",
        "http://localhost:8081", "http://127.0.0.1:8081"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# (3) Mongo 연결
# =========================
client = MongoClient(MONGO_URI)
coll   = client[DB_NAME][COLL_NAME]

# =========================
# (공용) 간단 유틸
# =========================
def oid_str(x: Any) -> str:
    try:
        return str(x)
    except:
        return ""

def to_iso(dt: Any) -> str:
    """datetime 또는 문자열을 ISO 문자열로 반환(문자열이면 그대로 반환)"""
    if isinstance(dt, datetime):
        return dt.isoformat()
    if isinstance(dt, str):
        return dt
    return ""

def pick_image(doc: Dict[str, Any]) -> str:
    """
    이미지 필드명이 섞여 있을 때 가장 먼저 존재하는 값을 선택
    사용 순서: image > thumbnail > img > cover
    """
    return (
        doc.get("image")
        or doc.get("thumbnail")
        or doc.get("img")
        or doc.get("cover")
        or ""
    )

# =========================
# (4) /news — 카드 목록 (title/url/summary/published_at/image)
# =========================
@app.get("/news")
def list_news(
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0)  # ← 페이지 시작 위치
) -> List[Dict[str, Any]]:
    has_pub = coll.count_documents({"published_at": {"$exists": True}}) > 0
    sort_key = "published_at" if has_pub else "_id"

    cursor = (coll.find({}, {"title":1,"url":1,"summary":1,"published_at":1,
                             "image":1,"thumbnail":1,"img":1,"cover":1})
                    .sort(sort_key, -1)
                    .skip(skip)
                    .limit(limit))

    return [
        {
            "_id": str(d.get("_id")),
            "title": d.get("title",""),
            "url": d.get("url",""),
            "summary": d.get("summary",""),
            "published_at": str(d.get("published_at","")),
            "image": d.get("image") or d.get("thumbnail") or "",
        }
        for d in cursor
    ]


# =========================
# (5) /news/{id} — 상세(모달용)
# =========================
@app.get("/news/{news_id}")
def get_news_detail(news_id: str) -> Dict[str, Any]:
    """
    MongoDB에서 단일 뉴스 상세 조회
    반환: {id,title,updated_at,image,content,url,press}
    """
    try:
        _id = ObjectId(news_id)
    except:
        raise HTTPException(status_code=400, detail="잘못된 ID 형식")

    doc = coll.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="뉴스를 찾을 수 없습니다.")

    title   = doc.get("title", "")
    url     = doc.get("url", "")
    content = doc.get("content", "")  # 기사 본문(이미 저장했다고 가정)
    image   = pick_image(doc)         # ✅ 목록과 동일 로직
    press  = doc.get("press", "")
    # updated_at 우선 → 없으면 published_at → 없으면 ObjectId 시각
    updated_at = doc.get("updated_at") or doc.get("published_at")
    if not updated_at and isinstance(doc.get("_id"), ObjectId):
        updated_at = doc["_id"].generation_time.isoformat()

    return {
        "id": oid_str(doc["_id"]),
        "title": title,
        "updated_at": to_iso(updated_at),
        "image": image,
        "content": content,
        "url": url,
        "press": press,
    }

# =========================
# (6) /briefing/yesterday — DB 기사 기반 전일 요약
# =========================
from openai import OpenAI
_oai = OpenAI(api_key=OPENAI_API_KEY)

@app.get("/briefing/yesterday")
def briefing_yesterday() -> Dict[str, Any]:
    """전날 기사 중 6개 카테고리별 요약 생성"""
    KST = timezone(timedelta(hours=9))
    today0 = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    y0, y1 = today0 - timedelta(days=1), today0
    y_date = y0.date().isoformat()

    # 1️⃣ 카테고리 고정 리스트
    categories = ["증권", "금융", "부동산", "산업", "글로벌경제", "일반"]
    results = []

    # 2️⃣ 카테고리별 기사 조회 및 요약 생성
    for cat in categories:
        docs = list(coll.find(
            {"category": cat, "published_at": {"$gte": y0.isoformat(), "$lt": y1.isoformat()}},
            {"title": 1, "summary": 1, "content": 1}
        ))

        if not docs:
            results.append({
                "category": cat,
                "summary": "해당 카테고리의 전일 기사가 없습니다.",
                "highlights": []
            })
            continue

        # 3️⃣ 입력 구성
        items = [f"- {d.get('title', '')}: {(d.get('summary') or d.get('content') or '')[:200]}" for d in docs[:5]]
        joined = "\n".join(items)

        prompt = f"""
너는 경제 뉴스 편집자다. 아래는 '{cat}' 분야의 전날 주요 기사다.
핵심 내용을 2~3문장으로 요약하고 주요 키워드 3개를 추출하라.

입력:
{joined}

JSON 스키마:
{{
  "category": "{cat}",
  "summary": "<요약>",
  "highlights": ["<키워드1>", "<키워드2>", "<키워드3>"]
}}
JSON만 출력.
"""

        try:
            resp = _oai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=400,
            )
            text = resp.choices[0].message.content.strip()
            match = re.search(r"\{.*\}", text, re.S)
            data = json.loads(match.group(0)) if match else {}
            results.append({
                "category": cat,
                "summary": data.get("summary", "요약 실패"),
                "highlights": data.get("highlights", []),
            })
        except Exception as e:
            results.append({
                "category": cat,
                "summary": "요약 생성 중 오류 발생",
                "highlights": [str(e)[:50]],
            })

    return {"date": y_date, "categories": results}

# =========================
# (7) /health — 연결 확인
# =========================
@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        client.admin.command("ping")
        return {"ok": True, "db": DB_NAME, "coll": COLL_NAME}
    except Exception as e:
        return {"ok": False, "error": str(e)}