# -*- coding: utf-8 -*-
"""
네이버 경제 뉴스 크롤러 + 카테고리 분류 + 감정분석 + Mongo 저장 (단일 실행 스크립트)
"""

import os
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, ASCENDING, errors
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# -------------------
# 환경/상수
# -------------------
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/?retryWrites=true&w=majority",
)
DB_NAME = os.getenv("MONGODB_DB", "test123")
COLL_NAME = os.getenv("MONGODB_COLL", "news")
USER_AGENT = "Mozilla/5.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# -------------------
# 카테고리 키워드
# -------------------
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "증권": ["주식", "코스피", "코스닥", "증권", "상장", "거래소", "증시", "공모주", "IPO", "PER", "ETF"],
    "금융": ["은행", "금리", "대출", "예금", "적금", "보험", "카드", "금융", "Fed", "연준", "금통위", "채권"],
    "부동산": ["부동산", "아파트", "주택", "분양", "전세", "매매", "청약", "재건축", "부동산시장"],
    "산업": ["산업", "제조", "재계", "기업", "자동차", "반도체", "철강", "바이오", "IT", "공장", "에너지"],
    "글로벌경제": ["글로벌", "세계", "해외", "국제", "미국", "중국", "일본", "달러", "위안", "유럽"],
    "일반": [],
}

POSITIVE_WORDS = [
    "호황","상승","성장","호재","강세","이익","흑자","개선","회복","확대","신기록","안정","긍정","달성","돌파",
    "급등","활성화","강화","호응","호조","수익","실적개선","최고치","안정세","호전","가속화","약진","확보","혁신","선도","진출",
    "지원","투자","고용확대","활황","도약","성공","성과","전망밝음"
]
NEGATIVE_WORDS = [
    "불황","하락","적자","위기","약세","손실","침체","악화","위축","급락","붕괴","불안","부정","파산","부도",
    "급감","경고","위협","추락","마이너스","적자폭","저조","감소세","급등락","위험","불확실","부진","급증세","약화","정체","소멸",
    "해고","구조조정","폐업","논란","갈등","침체기","실패","차질"
]

# -------------------
# HTTP 세션 (재시도/타임아웃)
# -------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})
    retry = Retry(
        total=3,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

# -------------------
# Mongo
# -------------------
def get_collection():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # 연결 체크 (DNS, 인증, TLS 등 문제 조기 포착)
    client.admin.command("ping")
    db = client[DB_NAME]
    col = db[COLL_NAME]
    # 중복방지 및 조회 인덱스
    col.create_index([("link", ASCENDING)], name="uniq_link", unique=True)
    col.create_index([("category", ASCENDING), ("news_date", ASCENDING)], name="q_cat_date")
    col.create_index([("news_date", ASCENDING)], name="q_date")
    return col

# -------------------
# 크롤링 유틸
# -------------------
def build_list_url(date: str, page: int) -> str:
    base = "https://news.naver.com/main/list.naver"
    # 101 = 경제
    return f"{base}?mode=LSD&mid=sec&sid1=101&date={date}&page={page}"

def extract_links(html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("ul.type06_headline li dt a, ul.type06 li dt a")
    out: List[Tuple[str, str]] = []
    for a in anchors:
        href = a.get("href", "")
        if "/article/" in href:
            out.append((a.get_text(strip=True), href))
    return out

def fetch_article(session: requests.Session, link: str) -> str:
    r = session.get(link, timeout=10)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    node = s.select_one("article#dic_area")
    return node.get_text(" ", strip=True) if node else "본문 추출 실패"

# -------------------
# NLP 유틸
# -------------------
def classify_category(text: str) -> str:
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw and kw in text:
                return cat
    return "일반"

def analyze_sentiment(text: str) -> str:
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    return "긍정" if pos > neg else "부정" if neg > pos else "중립"

# -------------------
# 본문: 수집→분석→저장
# -------------------
def crawl_and_save(days: int = 5, limit_per_day: int = 50, sleep_sec: float = 0.2) -> None:
    session = make_session()
    col = get_collection()

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        logging.info("📅 %s | 경제 전체", date)

        page, inserted, skipped = 1, 0, 0

        while inserted < limit_per_day:
            url = build_list_url(date, page)
            try:
                res = session.get(url, timeout=10)
                res.raise_for_status()
            except Exception as e:
                logging.warning("목록 요청 실패: %s (page=%d) -> 다음 페이지 시도", e, page)
                page += 1
                continue

            links = extract_links(res.text)
            if not links:
                break

            for title, link in links:
                # 중복 체크
                if col.find_one({"link": link}):
                    skipped += 1
                    continue

                try:
                    content = fetch_article(session, link)
                except Exception as e:
                    content = f"본문 에러: {e}"

                category = classify_category(f"{title} {content}")
                sentiment = analyze_sentiment(content)

                # news_date는 목록 기준(YYYYMMDD). 필요시 본문에서 날짜 파싱 로직 추가 가능.
                doc = {
                    "title": title,
                    "link": link,
                    "content": content,
                    "category": category,
                    "sentiment": sentiment,
                    "news_date": date,
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }

                try:
                    col.insert_one(doc)
                    inserted += 1
                except errors.DuplicateKeyError:
                    skipped += 1
                except Exception as e:
                    logging.error("DB 저장 실패: %s | %s", e, link)

                if inserted >= limit_per_day:
                    break

                time.sleep(sleep_sec)

            page += 1

        logging.info("   ▶ 저장 결과 | insert=%d, skip=%d", inserted, skipped)

    logging.info("✅ 전체 수집 완료")

# -------------------
# 실행부
# -------------------
if __name__ == "__main__":
    # 필요에 따라 파라미터 조정
    crawl_and_save(days=5, limit_per_day=50, sleep_sec=0.2)
