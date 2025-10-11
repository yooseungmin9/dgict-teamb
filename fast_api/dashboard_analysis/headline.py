from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import re, requests, html
from urllib.parse import urlparse, parse_qs

NAVER_CLIENT_ID = "TxScmBoNbELMfRqjtQpG"
NAVER_CLIENT_SECRET = "mcFuF9QBPw"

app = FastAPI(title="KR Econ News via NAVER")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False
)

SAFE_SIDS = {"101", "104", "105"}  # 경제, 세계, IT/과학
ENT_SIDS  = {"106"}                # 연예

BLOCK_RE = re.compile(r"(연예|엔터|스타|아이돌|컴백|뮤직|음원|보이그룹|걸그룹|배우|드라마|영화|예능|화보|포토|팬미팅|티저)", re.I)
ALLOW_TOKENS = ["경제","증시","코스피","환율","금리","물가","인플레","수출","무역","산업","고용","GDP","연준","FRB","Fed","달러","원화","나스닥","S&P","다우"]

def _clean(txt: str) -> str:
    if not txt: return ""
    # 네이버는 <b>태그 포함 → 제거
    txt = re.sub(r"<\/?b>", "", txt)
    return html.unescape(txt)

def _is_econ(title: str, desc: str) -> bool:
    t = f"{title} {desc}"
    if BLOCK_RE.search(t):
        return False
    return any(tok.lower() in t.lower() for tok in ALLOW_TOKENS)

def _is_entertain_link(url: str) -> bool:
    if not url: return False
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if "entertain" in host:  # m.entertain.naver.com, entertain.naver.com
        return True
    qs = parse_qs(p.query)
    sid = (qs.get("sid") or [""])[0]
    return sid in ENT_SIDS

def _is_allowed_news(url: str) -> bool:
    if not url: return True
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if "news.naver.com" in host or "n.news.naver.com" in host:
        qs = parse_qs(p.query)
        sid = (qs.get("sid") or [""])[0]
        return (sid in SAFE_SIDS) if sid else True
    return True

@app.get("/naver/econ")
def naver_econ_news(
    q: str = Query('미국 경제 -연예 -스포츠 -드라마 -영화 -음악 -아이돌 -스타 -포토 -화보'),
    n: int = Query(5, ge=1, le=100),
    sort: str = Query("date")
):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": q, "display": min(50, max(n*4, n)), "start": 1, "sort": sort}  # 여유로 받아서 필터
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json().get("items", [])
        cleaned = []
        for it in raw:
            title = _clean(it.get("title", ""))
            desc = _clean(it.get("description", ""))
            link = it.get("link", "")

            if _is_entertain_link(link):  # 엔터 도메인/섹션 차단
                continue
            if not _is_allowed_news(link):  # 네이버 뉴스면 sid 화이트리스트(101,104,105)
                continue
            if _is_econ(title, desc):  # 제목·요약 경제성 필터
                cleaned.append({"title": title, "link": link})
            if len(cleaned) >= n:
                break
        return {"count": len(cleaned), "articles": cleaned}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Naver API error: {e}")
