# -*- coding: utf-8 -*-
"""
네이버 경제 뉴스 크롤러 + 자동 카테고리 분류 + 감정분석
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, ASCENDING

# -------------------
# MongoDB Atlas 연결 정보
# -------------------
MONGODB_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "test123"
COLL_NAME = "shared_articles"
USER_AGENT = "Mozilla/5.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# -------------------
# 키워드 기반 카테고리 매핑
# -------------------
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "증권": ["주식", "코스피", "코스닥", "증권", "상장", "거래소", "증시", "공모주", "IPO", "PER", "ETF"],
    "금융": ["은행", "금리", "대출", "예금", "적금", "보험", "카드", "금융", "Fed", "연준", "금통위", "채권"],
    "부동산": ["부동산", "아파트", "주택", "분양", "전세", "매매", "청약", "재건축", "부동산시장"],
    "산업": ["산업", "제조", "재계", "기업", "자동차", "반도체", "철강", "바이오", "IT", "공장", "에너지"],
    "글로벌경제": ["글로벌", "세계", "해외", "국제", "미국", "중국", "일본", "달러", "위안", "유럽"],
    "일반": []  # 매칭 안되면 기본
}

# ------------------- 감성사전
POSITIVE_WORDS = [
    # 경제 전반 긍정
    "호황", "상승", "성장", "호재", "강세", "이익", "흑자", "개선", "회복",
    "확대", "신기록", "안정", "긍정", "달성", "돌파",
    # 투자 관련
    "급등", "활성화", "강화", "호응", "호조", "수익", "실적개선", "최고치",
    "안정세", "호전", "가속화", "약진", "확보", "혁신", "선도", "진출",
    # 사회적/정책적
    "지원", "투자", "고용확대", "활황", "도약", "성공", "성과", "전망밝음"
]

NEGATIVE_WORDS = [
    # 경제 전반 부정
    "불황", "하락", "적자", "위기", "약세", "손실", "침체", "악화", "위축",
    "급락", "붕괴", "불안", "부정", "파산", "부도",
    # 투자 관련
    "급감", "경고", "위협", "추락", "마이너스", "적자폭", "저조", "감소세",
    "급등락", "위험", "불확실", "부진", "급증세", "약화", "정체", "소멸",
    # 사회적/정책적
    "해고", "구조조정", "폐업", "논란", "갈등", "침체기", "실패", "차질"
]
# -------------------
# MongoDB 유틸
# -------------------
def get_collection():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
    db = client[DB_NAME]
    col = db[COLL_NAME]

    col.create_index([("link", ASCENDING)], name="uniq_link", unique=True)
    col.create_index([("category", ASCENDING), ("news_date", ASCENDING)], name="q_cat_date")
    return col

# -------------------
# 크롤링 유틸
# -------------------
def build_url(date: str, page: int) -> str:
    base = "https://news.naver.com/main/list.naver"
    return f"{base}?mode=LSD&mid=sec&sid1=101&date={date}&page={page}"

def extract_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("ul.type06_headline li dt a, ul.type06 li dt a")
    return [(a.get_text(strip=True), a["href"]) for a in anchors if "/article/" in a.get("href", "")]

def fetch_article(link: str, headers: Dict[str, str]) -> str:
    r = requests.get(link, headers=headers, timeout=10)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    node = s.select_one("article#dic_area")
    return node.get_text(" ", strip=True) if node else "본문 추출 실패"

# -------------------
# NLP 유틸
# -------------------
def classify_category(text: str) -> str:
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "일반"

def analyze_sentiment(text: str) -> str:
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    if pos > neg:
        return "긍정"
    elif neg > pos:
        return "부정"
    else:
        return "중립"

# -------------------
# 크롤러 본체
# -------------------
def crawl_and_save(days: int = 30, limit_per_day: int = 50) -> None:
    col = get_collection()
    headers = {"User-Agent": USER_AGENT}

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        logging.info("📅 %s | 경제 전체", date)

        page, inserted, skipped = 1, 0, 0

        while inserted < limit_per_day:
            url = build_url(date, page)
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            links = extract_links(res.text)
            if not links:
                break

            for title, link in links:
                if col.find_one({"link": link}):
                    skipped += 1
                    continue

                try:
                    content = fetch_article(link, headers)
                except Exception as e:
                    content = f"본문 에러: {e}"

                # 카테고리/감정 분석
                category = classify_category(title + " " + content)
                sentiment = analyze_sentiment(content)

                doc = {
                    "title": title,
                    "link": link,
                    "content": content,
                    "category": category,
                    "sentiment": sentiment,
                    "news_date": date,
                    "saved_at": datetime.now().isoformat(),
                }

                col.insert_one(doc)
                inserted += 1

                if inserted >= limit_per_day:
                    break

            page += 1
            time.sleep(0.2)

        logging.info("   ▶ 저장 결과 | insert=%d, skip=%d", inserted, skipped)

    logging.info("✅ 전체 수집 완료")

# -------------------
# 실행부
# -------------------
if __name__ == "__main__":
    crawl_and_save(days=30, limit_per_day=50)
