# main.py — 통합본: /news, /news/{id}, /briefing/yesterday, /health
# 실행: uvicorn main:app --reload --port 8000
# 필요 패키지:
#   pip install "fastapi>=0.110" uvicorn "pydantic<3" "pymongo==4.10.1" "openai>=1.46.0" "bson>=0.5.10"

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
COLL_NAME = "news"

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
def list_news(limit: int = Query(10, ge=1, le=50)) -> List[Dict[str, Any]]:
    """
    요약은 이미 DB에 저장되어 있다고 가정.
    title, url, summary, published_at, image 만 projection하여 최신순 반환
    """
    has_pub = coll.count_documents({"published_at": {"$exists": True}}) > 0
    sort_key = "published_at" if has_pub else "_id"

    # ✅ 이미지 후보 필드를 projection에 포함(누락 방지)
    cursor = coll.find(
        {},
        {"title":1,"url":1,"summary":1,"published_at":1, "image":1, "thumbnail":1, "img":1, "cover":1}
    ).sort(sort_key, -1).limit(limit)

    out: List[Dict[str, Any]] = []
    for d in cursor:
        out.append({
            "_id": oid_str(d.get("_id")),
            "title": d.get("title",""),
            "url": d.get("url",""),
            "summary": d.get("summary",""),
            "published_at": to_iso(d.get("published_at","")),
            "image": pick_image(d),  # ✅ 좌측 썸네일로 사용할 값
        })
    return out

# =========================
# (5) /news/{id} — 상세(모달용)
# =========================
@app.get("/news/{news_id}")
def get_news_detail(news_id: str) -> Dict[str, Any]:
    """
    MongoDB에서 단일 뉴스 상세 조회
    반환: {id,title,updated_at,image,content,url,source}
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
    source  = doc.get("source", "")
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
        "source": source,
    }

# =========================
# (6) /briefing/yesterday — DB 미사용, GPT 직접 생성
# =========================
_oai = OpenAI(api_key=OPENAI_API_KEY)

def _extract_json(text: str) -> Dict[str, Any]:
    """GPT 응답에서 JSON 블럭만 추출(앞뒤 설명 제거 대비)"""
    try:
        return json.loads(text)
    except:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except:
                pass
    return {}

@app.get("/briefing/yesterday")
def briefing_yesterday() -> Dict[str, Any]:
    """
    반환: { "date": "YYYY-MM-DD", "summary": "...", "highlights": ["...","...","..."] }
    (주의) 호출 실패 시 안내 문구 반환
    """
    # KST 기준 어제 날짜
    KST = timezone(timedelta(hours=9))
    today0 = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    y0 = today0 - timedelta(days=1)
    y_date = y0.date().isoformat()

    sys_msg = (
        "너는 경제 뉴스 편집자다. "
        "어제의 주요 경제 뉴스를 확인하고, 핵심 이슈를 1~2문장으로 요약하고, "
        "핵심 토픽 3~5개를 한국어 단어로 뽑아라. 반드시 JSON만 반환해라."
    )
    user_msg = f"""
어제({y_date}) 한국 및 글로벌 경제 뉴스의 주요 브리핑을 작성하라.

반환 JSON 스키마:
{{
  "date": "{y_date}",
  "summary": "<한글 1~2문장 요약>",
  "highlights": ["<토픽1>","<토픽2>","<토픽3>"]
}}
JSON만 출력해라.
"""

    try:
        resp = _oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()
        data = _extract_json(text)

        summary = (data.get("summary") or "").strip()
        highlights = [str(h).strip() for h in (data.get("highlights") or []) if str(h).strip()][:5]
        if not summary:
            raise ValueError("empty summary")
        if not highlights:
            highlights = ["경제동향"]

        return {"date": y_date, "summary": summary, "highlights": highlights}
    except Exception:
        return {
            "date": y_date,
            "summary": "전일 브리핑 생성에 실패했습니다. 잠시 후 다시 시도하세요.",
            "highlights": ["시스템오류"]
        }

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