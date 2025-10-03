# -*- coding: utf-8 -*-
"""
네이버 경제 뉴스 크롤러 + 요약 + 카테고리 + 출처 + 감성분석 + 키워드추출 + DB저장
"""

import re, time, logging
from datetime import datetime, timedelta
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, ASCENDING
from transformers import pipeline
from konlpy.tag import Okt   # ✅ 키워드 추출용

# -------------------
# MongoDB Atlas 연결 정보
# -------------------
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "shared_articles"

# -------------------
# UA & 언론사 매핑
# -------------------
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://news.naver.com/"}
BASE_LIST = "https://news.naver.com/main/list.naver"
OIDS = {
  "056": "KBS",
  "015": "한국경제",
  "009": "매일경제",
  "014": "파이낸셜뉴스",
  "119": "데일리안",
  "005": "국민일보",
  "421": "뉴스1",
  "047": "오마이뉴스",
  "001": "연합뉴스",
  "629": "더팩트",
  "029": "디지털타임스",
  "008": "머니투데이",
  "028": "한겨레",
  "448": "TV조선",
  "023": "조선일보",
  "082": "부산일보",
  "277": "아시아경제",
  "422": "연합뉴스TV",
  "018": "이데일리",
  "092": "지디넷코리아",
  "052": "YTN",
  "020": "동아일보",
  "055": "SBS",
  "003": "뉴시스",
  "469": "한국일보",
  "366": "조선비즈",
  "025": "중앙일보",
  "079": "노컷뉴스",
  "659": "전주MBC",
  "437": "JTBC",
  "016": "헤럴드경제",
  "032": "경향신문",
  "214": "MBC",
  "215": "한국경제TV",
  "138": "디지털데일리",
  "011": "서울경제",
  "586": "시사저널",
  "044": "코리아헤럴드",
  "002": "프레시안",
  "021": "문화일보",
  "087": "강원일보",
  "081": "서울신문",
  "666": "경기일보",
  "088": "매일신문",
  "057": "MBN",
  "449": "채널A",
  "022": "세계일보",
  "374": "SBS Biz",
  "030": "전자신문",
  "346": "헬스조선",
  "037": "주간동아",
  "656": "대전일보",
  "031": "아이뉴스24",
  "648": "비즈워치",
  "660": "kbc광주방송",
  "640": "코리아중앙데일리",
  "654": "강원도민일보",
  "607": "뉴스타파",
  "661": "JIBS",
  "006": "미디어오늘",
  "310": "여성신문",
  "262": "신동아",
  "094": "월간 산",
  "308": "시사IN",
  "024": "매경이코노미",
  "293": "블로터",
  "123": "조세일보",
  "657": "대구MBC",
  "662": "농민신문",
  "243": "이코노미스트",
  "417": "머니S",
  "036": "한겨레21",
  "584": "동아사이언스",
  "007": "일다",
  "050": "한경비즈니스",
  "655": "CJB청주방송",
  "033": "주간경향",
  "296": "코메디닷컴",
  "053": "주간조선",
  "127": "기자협회보",
  "658": "국제신문",
  "665": "더스쿠프",
  "353": "중앙SUNDAY",
  "145": "레이디경향"
}

# -------------------
# 카테고리 키워드
# -------------------
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "증권": ["주식","코스피","코스닥","증권","상장","거래소","증시","공모주","IPO","PER","ETF"],
    "금융": ["은행","금리","대출","예금","적금","보험","카드","금융","Fed","연준","금통위","채권"],
    "부동산": ["부동산","아파트","주택","분양","전세","매매","청약","재건축","부동산시장"],
    "산업": ["산업","제조","재계","기업","자동차","반도체","철강","바이오","IT","공장","에너지"],
    "글로벌경제": ["글로벌","세계","해외","국제","미국","중국","일본","달러","위안","유럽"],
    "일반": []
}

POSITIVE_WORDS = ["호황","상승","성장","호재","강세","이익","흑자","개선","회복","확대","신기록","안정","긍정","달성","돌파"]
NEGATIVE_WORDS = ["불황","하락","적자","위기","약세","손실","침체","악화","위축","급락","붕괴","불안","부정","파산","부도"]

# -------------------
# Summarizer 설정
# -------------------
MODEL_ID   = "EbanLee/kobart-summary-v3"
summarizer = pipeline("summarization", model=MODEL_ID, tokenizer=MODEL_ID, device=-1)

MAX_LEN, MIN_LEN, NUM_BEAMS, DO_SAMPLE, PRE_CUT = 400, 50, 6, False, 1500

def preprocess_txt(text: str) -> str:
    if not text: return ""
    text = text.replace("\n", " ").replace("\t", " ").strip()
    return text[:PRE_CUT]

def summarize_text(text: str) -> str:
    clean = preprocess_txt(text)
    if not clean: return ""
    try:
        out = summarizer(clean, max_length=MAX_LEN, min_length=MIN_LEN,
                         num_beams=NUM_BEAMS, do_sample=DO_SAMPLE)
        return out[0]["summary_text"].strip()
    except Exception as e:
        logging.warning("요약 실패: %s", e)
        return ""

# -------------------
# 카테고리 & 감성분석
# -------------------
def classify_category(text: str) -> str:
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "일반"

def sentiment_score(text: str) -> int:
    score = sum(1 for w in POSITIVE_WORDS if w in text)
    score -= sum(1 for w in NEGATIVE_WORDS if w in text)
    return score

# -------------------
# 키워드 추출 (Okt 사용)
# -------------------
okt = Okt()
STOPWORDS = {"은","는","이","가","을","를","에","에서","으로","로","과","와","의","도","만","보다","까지","했다","있다"}
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")

def extract_keywords(text: str) -> List[str]:
    pos = okt.pos(text, norm=True, stem=True)
    cand = [w for (w,p) in pos if p in ("Noun","Alpha")]
    tokens, seen = [], set()
    for w in cand:
        w = w.lower()
        if not TOKEN_RE.fullmatch(w): continue
        if w in STOPWORDS: continue
        if w not in seen:
            tokens.append(w); seen.add(w)
    return tokens

# -------------------
# MongoDB
# -------------------
def get_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    col = client[DB_NAME][COLL_NAME]
    col.create_index([("url", ASCENDING)], name="uniq_url", unique=True)
    return col

# -------------------
# 크롤링
# -------------------
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
    title = title_node.get("content") if title_node and title_node.name=="meta" else (title_node.get_text(strip=True) if title_node else "")

    body_node = s.select_one("article#dic_area, div#articeBody, div#newsct_article")
    content = body_node.get_text(" ", strip=True) if body_node else ""

    og = s.select_one('meta[property="og:image"]')
    image_url = og["content"] if og and og.get("content") else ""

    # 언론사 추출
    press = ""
    m = re.search(r"article/(\d{3})/", link)
    if m and m.group(1) in OIDS:
        press = OIDS[m.group(1)]

    return {"title": title, "content": content, "image": image_url, "press": press}

# -------------------
# 실행 본체
# -------------------
def crawl_and_save(days: int = 30, limit_per_day: int = 50):
    col = get_collection()

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        logging.info("📅 %s | 경제 전체", date)

        page, inserted = 1, 0
        while inserted < limit_per_day:
            url = build_url(date, page)
            res = requests.get(url, headers=UA, timeout=10)
            res.raise_for_status()
            links = extract_links(res.text)
            if not links: break

            for title, link in links:
                if col.find_one({"url": link}): continue
                try:
                    art = fetch_article(link)
                except Exception as e:
                    logging.warning("본문 에러: %s", e)
                    continue

                # 요약, 카테고리, 감성, 키워드
                summary = summarize_text(art["content"])
                cat = classify_category(art["title"] + " " + art["content"])
                senti = sentiment_score(art["title"] + " " + art["content"])
                kws = extract_keywords(art["title"] + " " + art["content"])

                doc = {
                    "title": art["title"] or title,
                    "url": link,
                    "content": art["content"],
                    "image": art["image"],
                    "summary": summary,
                    "press": art["press"],
                    "category": cat,
                    "sentiment_score": senti,
                    "keywords": kws,
                    "published_at": datetime.now().isoformat(),
                }
                try:
                    col.insert_one(doc)
                    logging.info("[OK] 저장됨: %s", link)
                    inserted += 1
                except Exception as e:
                    logging.warning("[SKIP] 저장 실패: %s", e)

                if inserted >= limit_per_day: break

            page += 1
            time.sleep(0.3)

        logging.info("▶ 저장 결과 | insert=%d", inserted)

    logging.info("✅ 전체 수집 완료")

if __name__ == "__main__":
    crawl_and_save(days=30, limit_per_day=50)
