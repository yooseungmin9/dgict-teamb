# books_api.py (핵심만)
import os, requests
from typing import List, Dict, Optional
from fastapi import FastAPI, Query, HTTPException
from datetime import datetime

app = FastAPI()
ALADIN_URL = "http://www.aladin.co.kr/ttb/api/ItemList.aspx"
TTBKEY = "ttb2win0min1217001"

# 1) 환경변수에서 읽기 (예: ALADIN_ECON_CATEGORY_IDS="3065,3057,3059")
def _load_ids_from_env() -> List[int]:
    raw = os.getenv("ALADIN_ECON_CATEGORY_IDS", "").strip()
    if not raw:
        return []
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]

# 2) 파일에서 읽기 (한 줄에 하나씩 숫자) — 없으면 무시
def _load_ids_from_file(path="categories_econ.txt") -> List[int]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            out = []
            for line in f:
                s = line.strip().split(",")[0]
                if s.isdigit(): out.append(int(s))
            return out
    except FileNotFoundError:
        return []

# 최종 기본 리스트: .env > 파일 > [3065]
DEFAULT_ECON_IDS = [
    170, 3057, 3059, 3061, 3062, 3063, 8586, 3065, 3140, 8587,
    2172, 3103, 2173, 2841, 8593, 2747, 3123, 3069, 2028, 853,
    852, 854, 261, 268, 273, 1632, 55058, 2169, 263, 172, 141092,
    11502, 175, 11501, 2225, 174, 177, 3048, 32288, 180, 249,
    3049, 3104, 2408, 3110, 11503, 6189
]

def fetch(cid: int, start: int, max_results: int) -> str:
    params = {
        "ttbkey": TTBKEY, "QueryType": "Bestseller",
        "MaxResults": max_results, "start": start,
        "SearchTarget": "Book", "CategoryId": cid,
        "output": "xml", "Version": 20131101,
    }
    r = requests.get(ALADIN_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.text

@app.get("/books")
def books(
    # ▶ 별도 지정이 없으면 경제 화이트리스트 사용
    category_ids: List[int] = Query(None, description="알라딘 CategoryId. 미지정 시 경제 화이트리스트 사용"),
    start: int = Query(1, ge=1),
    pages: int = Query(1, ge=1, le=5),
    per_page: int = Query(20, ge=1, le=50),
    since: Optional[str] = None,
):
    from xml.etree import ElementTree as ET
    from datetime import datetime

    if not TTBKEY: raise HTTPException(500, "Missing ALADIN_TTBKEY")
    ids = category_ids or DEFAULT_ECON_IDS

    # --- XML 파서 (기존 parse_aladin_xml 그대로 써도 됨) ---
    def parse(xml_text: str) -> List[Dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        for el in root.iter():
            if isinstance(el.tag, str) and '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        out = []
        for it in root.iter("item"):
            def get(tag):
                n = it.find(tag);
                return (n.text or "").strip() if n is not None else ""
            out.append({
                "title": get("title"),
                "author": get("author"),
                "pubDate": get("pubDate"),
                "link": get("link"),
                "cover": get("cover"),
                # 필요 시 추가: "isbn13": get("isbn13")
            })
        return out
    # ----------------------------------------------------

    all_items: List[Dict] = []
    for cid in ids:
        s = start
        for _ in range(pages):
            try:
                xml = fetch(cid, s, per_page)
                all_items.extend(parse(xml))
            except requests.RequestException:
                pass
            s += 1

    # 중복 제거 (link 기준)
    seen, dedup = set(), []
    for it in all_items:
        link = (it.get("link") or "").strip()
        if link and link not in seen:
            seen.add(link)
            dedup.append(it)

    # since 필터 (YYYY-MM-DD)
    if since:
        try:
            since_dt = datetime.strptime(since[:10], "%Y-%m-%d")
            filtered = []
            for it in dedup:
                pub = (it.get("pubDate") or "")[:10]
                try:
                    if datetime.strptime(pub, "%Y-%m-%d") >= since_dt:
                        filtered.append(it)
                except Exception:
                    filtered.append(it)
            dedup = filtered
        except ValueError:
            pass

    return {"count": len(dedup), "items": dedup}
