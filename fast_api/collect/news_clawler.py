# -*- coding: utf-8 -*-
"""
네이버 경제 뉴스 크롤러 (경제 뉴스 날짜별 50개 저장)
- category: 텍스트 키워드 기반 분류
- 요약 + 출처 + 감성분석 + 키워드추출 + DB저장
"""

import re, time, logging, os
from datetime import datetime, timedelta
from typing import Dict, List
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, ASCENDING
from transformers import pipeline
from konlpy.tag import Okt
from dateutil import parser

# 1. 환경변수 로드 및 MongoDB 연결
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "test123"
COLL_NAME = "shared_articles"

# 2. UA & 언론사 매핑
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://news.naver.com/"}
BASE_LIST = "https://news.naver.com/main/list.naver"
OIDS = {
    "056": "KBS",
    "015": "한국경제",
    "009": "매일경제",
    "014": "파이낸셜뉴스",
    "023": "조선일보",
    "025": "중앙일보",
    "020": "동아일보",
    "018": "이데일리",
    "011": "서울경제",
    "022": "세계일보",
    "277": "아시아경제",
    "214": "MBC",
    "055": "SBS",
    "052": "YTN",
    "001": "연합뉴스"
}

# 3. 카테고리 키워드 (텍스트 기반)
CATEGORY_KEYWORDS_WEIGHT: Dict[str, Dict[str, float]] = {
    "증권": {"증시": 3.0, "주식": 3.0, "코스피": 2.8},
    "금융": {"금융": 3.0, "은행": 2.8, "금리": 3.0},
    "부동산": {"부동산": 3.0, "아파트": 3.0, "주택": 2.8},
    "산업": {"산업": 3.0, "기업": 2.8, "제조": 2.5},
    "글로벌경제": {"글로벌": 3.0, "국제": 2.8, "해외": 2.5},
    "일반": {"경제": 3.0, "물가": 2.8, "소비": 2.5}
}

POSITIVE_WORDS = ["상승", "성장", "호재", "회복", "활성화", "개선", "강세"]
NEGATIVE_WORDS = ["하락", "적자", "위기", "침체", "악화", "둔화", "불황"]

# 4. Summarizer 설정
MODEL_ID = "EbanLee/kobart-summary-v3"
summarizer = pipeline("summarization", model=MODEL_ID, tokenizer=MODEL_ID, device=-1)
MAX_LEN, MIN_LEN, NUM_BEAMS, DO_SAMPLE, PRE_CUT = 400, 50, 6, False, 1500

def preprocess_txt(text: str) -> str:
    return text.replace("\n", " ").replace("\t", " ").strip()[:PRE_CUT] if text else ""

def summarize_text(text: str) -> str:
    clean = preprocess_txt(text)
    if not clean:
        return ""
    try:
        out = summarizer(clean, max_length=MAX_LEN, min_length=MIN_LEN,
                         num_beams=NUM_BEAMS, do_sample=DO_SAMPLE)
        return out[0]["summary_text"].strip()
    except Exception:
        return ""

# 5. 카테고리 & 감성분석
def classify_category_weighted(title: str, content: str) -> str:
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS_WEIGHT.items():
        score = 0
        for kw, w in keywords.items():
            count = title.count(kw) * 1.5 + content.count(kw)
            score += count * w
        scores[cat] = score
    best_cat = max(scores, key=scores.get)
    return best_cat if scores[best_cat] > 0 else "일반"

def sentiment_score(text: str) -> int:
    score = sum(1 for w in POSITIVE_WORDS if w in text)
    score -= sum(1 for w in NEGATIVE_WORDS if w in text)
    return score

# 6. 키워드 추출
okt = Okt()
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")

def extract_keywords(text: str) -> List[str]:
    if not text:
        return []
    pos = okt.pos(text, norm=True, stem=True)
    tokens = [w.lower() for (w, p) in pos if p in ("Noun", "Alpha")]
    return [t for t in tokens if TOKEN_RE.fullmatch(t)]

# 7. MongoDB
def get_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    col = client[DB_NAME][COLL_NAME]
    col.create_index([("url", ASCENDING)], name="uniq_url", unique=True)
    return col

# 8. 크롤링
def build_url(date: str, page: int) -> str:
    return f"{BASE_LIST}?mode=LSD&mid=sec&sid1=101&date={date}&page={page}"

def extract_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("ul.type06_headline li dt a, ul.type06 li dt a")
    return [(a.get_text(strip=True), a["href"]) for a in anchors if "/article/" in a.get("href", "")]

def fetch_article(link: str) -> Dict[str, str]:
    r = requests.get(link, headers=UA, timeout=10)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")

    title_node = s.select_one("h2#title_area, h3#articleTitle, meta[property='og:title']")
    title = title_node.get("content") if title_node and title_node.name == "meta" else (
        title_node.get_text(strip=True) if title_node else "")

    body_node = s.select_one("article#dic_area, div#articeBody, div#newsct_article")
    content = body_node.get_text(" ", strip=True) if body_node else ""

    og = s.select_one('meta[property="og:image"]')
    image_url = og["content"] if og and og.get("content") else ""

    press = ""
    m = re.search(r"article/(\d{3})/", link)
    if m and m.group(1) in OIDS:
        press = OIDS[m.group(1)]

    pub_time = None
    t1 = s.select_one("span.media_end_head_info_datestamp_time")
    if t1 and t1.get("data-date-time"):
        pub_time = parser.parse(t1["data-date-time"])
    else:
        t2 = s.select_one('meta[property="og:article:published_time"]')
        if t2 and t2.get("content"):
            pub_time = parser.parse(t2["content"])

    return {"title": title, "content": content, "image": image_url, "press": press, "published_at": pub_time}

# 9. 실행 본체
def crawl_and_save(days: int = 1, limit_per_day: int = 100):
    col = get_collection()
    counters = {}

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        inserted, page = 0, 1

        while inserted < limit_per_day:
            url = build_url(date, page)
            res = requests.get(url, headers=UA, timeout=10)
            res.raise_for_status()
            links = extract_links(res.text)
            if not links:
                break

            for title, link in links:
                if col.find_one({"url": link}):
                    continue
                art = fetch_article(link)
                if not art["published_at"]:
                    continue

                pub_date = art["published_at"].date()
                if pub_date.strftime("%Y%m%d") != date:
                    continue
                if counters.get(pub_date, 0) >= limit_per_day:
                    continue

                summary = summarize_text(art["content"])
                senti = sentiment_score(art["title"] + " " + art["content"])
                kws = extract_keywords(art["title"] + " " + art["content"])
                cat = classify_category_weighted(art["title"], art["content"])

                doc = {
                    "title": art["title"] or title,
                    "url": link,
                    "content": art["content"],
                    "image": art["image"],
                    "summary": summary,
                    "press": art["press"],
                    "main_section": "경제",
                    "category": cat,
                    "sentiment_score": senti,
                    "keywords": kws,
                    "published_at": art["published_at"].isoformat(),
                }
                try:
                    col.insert_one(doc)
                    counters[pub_date] = counters.get(pub_date, 0) + 1
                    inserted += 1
                    logging.info("저장됨: %s (%s)", link, pub_date)
                except Exception as e:
                    logging.warning("저장 실패: %s", e)

                if inserted >= limit_per_day:
                    break

            page += 1
            time.sleep(0.3)

        logging.info("%s 날짜 결과: %d개", date, inserted)

    logging.info("전체 수집 완료 (일별 카운트: %s)", counters)

if __name__ == "__main__":
    crawl_and_save(days=1, limit_per_day=100)
