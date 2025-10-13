# -*- coding: utf-8 -*-
"""
네이버 경제 뉴스 크롤러 (경제 뉴스 날짜별 50개 저장)
- category: 텍스트 키워드 기반 분류
- 요약 + 출처 + 감성분석 + 키워드추출 + DB저장
"""

import re, time, logging
from datetime import datetime, timedelta
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, ASCENDING
from transformers import pipeline
from konlpy.tag import Okt
from dateutil import parser  # 날짜 파싱

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
# 카테고리 키워드 (텍스트 기반)
# -------------------
CATEGORY_KEYWORDS_WEIGHT: Dict[str, Dict[str, float]] = {
    # --------------------- #
    # 📈 증권
    # --------------------- #
    "증권": {
        "증시": 3.0, "주식": 3.0, "코스피": 2.8, "코스닥": 2.8, "상장": 2.2,
        "IPO": 2.0, "ETF": 2.0, "리츠": 2.0, "거래소": 2.0, "시가총액": 2.0,
        "매수": 1.8, "매도": 1.8, "외국인": 1.8, "기관투자자": 1.8,
        "선물": 1.8, "옵션": 1.8, "공매도": 1.6, "유동성": 1.5, "PER": 1.5, "PBR": 1.5,
        "테마주": 1.4, "호재": 1.2, "악재": 1.2, "배당": 1.2, "리밸런싱": 1.0,
        "증권사": 1.5, "투자자": 1.5, "포트폴리오": 1.3, "시황": 1.2, "주가": 2.0
    },

    # --------------------- #
    # 💰 금융
    # --------------------- #
    "금융": {
        "금융": 3.0, "은행": 2.8, "금리": 3.0, "대출": 2.5, "예금": 2.3, "보험": 2.3,
        "채권": 2.3, "카드": 2.0, "연준": 2.8, "한국은행": 2.5, "환율": 2.3,
        "통화정책": 2.3, "기준금리": 2.5, "여신": 2.0, "수신": 1.8,
        "핀테크": 2.0, "P2P": 1.5, "머니마켓": 1.8, "리스크관리": 1.8,
        "부채": 1.8, "부실채권": 1.8, "신용등급": 1.5, "CB": 1.5, "회사채": 1.5,
        "암호화폐": 2.0, "비트코인": 2.0, "이더리움": 1.8, "CBDC": 1.5, "STO": 1.5,
        "금융시장": 2.3, "금융위": 1.8, "금융감독원": 1.8, "예대금리차": 1.5,
        "긴축": 2.0, "양적완화": 1.8, "유동성위기": 2.2
    },

    # --------------------- #
    # 🏠 부동산
    # --------------------- #
    "부동산": {
        "부동산": 3.0, "아파트": 3.0, "주택": 2.8, "전세": 2.5, "매매": 2.5,
        "청약": 2.3, "분양": 2.3, "재건축": 2.3, "재개발": 2.3, "PF": 3.0,
        "부동산PF": 3.0, "프로젝트파이낸싱": 2.5, "건설사": 2.0, "공시지가": 2.0,
        "집값": 2.5, "시세": 2.0, "매매가": 2.0, "전세가": 2.0, "임대차": 1.8,
        "리모델링": 1.5, "부동산투자": 1.8, "리츠": 1.8, "대출규제": 1.8,
        "전세사기": 2.0, "미분양": 2.0, "입주": 1.5, "거래절벽": 1.5,
        "종부세": 1.8, "재산세": 1.8, "도시계획": 1.5, "생활권": 1.2,
        "강남구": 1.5, "서초구": 1.5, "송파구": 1.5, "분당": 1.2, "일산": 1.2,
        "부동산시장": 2.0, "전월세": 1.8, "부동산대출": 2.0, "주거복지": 1.2
    },

    # --------------------- #
    # ⚙️ 산업
    # --------------------- #
    "산업": {
        "산업": 3.0, "기업": 2.8, "제조": 2.5, "반도체": 3.0, "배터리": 2.8,
        "자동차": 2.8, "전기차": 2.5, "수소차": 2.0, "조선": 2.0, "항공": 2.0,
        "물류": 2.0, "유통": 2.0, "중공업": 2.0, "화학": 2.0, "철강": 2.0,
        "에너지": 2.3, "플랜트": 1.8, "로봇": 2.3, "AI": 2.5, "클라우드": 2.3,
        "5G": 1.8, "6G": 1.8, "디지털전환": 2.3, "스마트팩토리": 2.0,
        "리튬이온": 2.0, "이차전지": 2.0, "양극재": 1.8, "음극재": 1.8,
        "소재": 1.8, "R&D": 1.8, "산단": 1.5, "그린산업": 1.5, "탄소중립": 1.8,
        "공급망": 2.3, "AI반도체": 3.0, "첨단산업": 2.5, "혁신": 1.8
    },

    # --------------------- #
    # 🌍 글로벌경제
    # --------------------- #
    "글로벌경제": {
        "글로벌": 3.0, "국제": 2.8, "해외": 2.5, "세계": 2.3, "미국": 3.0, "중국": 3.0,
        "일본": 2.5, "유럽": 2.5, "달러": 2.3, "엔화": 2.0, "위안화": 2.0,
        "WTI": 2.3, "브렌트유": 2.3, "유가": 2.3, "IMF": 2.3, "OECD": 2.3, "WTO": 2.0,
        "FOMC": 2.5, "ECB": 2.3, "BOJ": 2.0, "PBOC": 2.0,
        "나스닥": 2.3, "다우": 2.3, "S&P500": 2.3,
        "무역": 2.3, "수출": 2.3, "수입": 2.3, "관세": 2.0, "브릭스": 2.0, "신흥국": 2.0,
        "글로벌경기": 2.5, "환율전쟁": 2.0, "리스크온": 1.5, "리스크오프": 1.5,
        "OPEC": 1.8, "OPEC+": 1.8, "공급망위기": 1.8, "지정학": 1.8, "미중갈등": 2.3,
        "G20": 1.5, "유로존": 1.5, "국제유가": 2.3, "달러강세": 2.0
    },

    # --------------------- #
    # 🧾 일반경제
    # --------------------- #
    "일반": {
        "경제": 3.0, "물가": 2.8, "소비": 2.5, "경기": 2.5, "성장률": 2.3,
        "GDP": 2.3, "고용": 2.3, "실업": 2.0, "노동": 2.0, "임금": 2.0,
        "생활": 2.0, "소득": 2.0, "지출": 2.0, "가계부채": 2.3,
        "창업": 2.0, "자영업": 2.0, "소상공인": 2.0, "프랜차이즈": 1.8,
        "내수": 2.0, "물가상승": 2.3, "경기침체": 2.3, "경기회복": 2.0,
        "체감경기": 1.8, "생활비": 1.8, "물가상승률": 1.8,
        "저출산": 1.5, "고령화": 1.5, "복지": 1.5, "서민경제": 1.8,
        "소비심리": 1.8, "리쇼어링": 1.2, "고용률": 1.5, "실업률": 1.5
    }
}
POSITIVE_WORDS = [
    # 경기/시장
    "호황","상승","성장","호재","강세","호전","이익","흑자","개선","회복","확대","신기록",
    "안정","긍정","달성","돌파","활황","활성화","호조","약진","강화","호평","낙관",
    "풍부","풍년","도약","혁신","최고치","고공행진","기대감","훈풍","견조","탄탄",
    # 정책/금융
    "금리인하","감세","지원","투자확대","정책효과","유입","순이익","배당","호실적","자금흐름",
    "고용증가","소득증가","매출호조","흑자전환","증가세","상향조정","수익성개선","시장확대",
    # 글로벌/산업
    "수출호조","수출증가","무역흑자","글로벌호황","협력강화","유치성공","합의","협상타결",
    "기술혁신","돌파구","안착","성공","성과","호응","신규투자","성장동력"
]

NEGATIVE_WORDS = [
    # 경기/시장
    "불황","하락","적자","위기","약세","손실","침체","악화","위축","급락","붕괴","불안",
    "부정","파산","부도","폭락","퇴보","하향","부진","침하","역성장","역풍","충격","리스크",
    "침체국면","하방압력","둔화","위기감","경색","악재","경착륙","불투명","침체우려",
    # 정책/금융
    "금리인상","긴축","부담","부채","적자전환","채무불이행","신용위기","파산신청","연체",
    "구조조정","매출감소","순손실","마이너스","부도위기","투자위축","투자감소",
    # 글로벌/산업
    "수출감소","무역적자","관세부과","무역분쟁","불확실","차질","고용감소","실업","폐업",
    "철수","감산","파업","노사갈등","소송","규제","불매운동","제재","침체심화","유출",
    "대량해고","적자누적","타격","불협화음","갈등","분쟁"
]
# -------------------
# Summarizer 설정
# -------------------
MODEL_ID   = "EbanLee/kobart-summary-v3"
summarizer = pipeline("summarization", model=MODEL_ID, tokenizer=MODEL_ID, device=-1)
MAX_LEN, MIN_LEN, NUM_BEAMS, DO_SAMPLE, PRE_CUT = 400, 50, 6, False, 1500

def preprocess_txt(text: str) -> str:
    return text.replace("\n"," ").replace("\t"," ").strip()[:PRE_CUT] if text else ""

def summarize_text(text: str) -> str:
    clean = preprocess_txt(text)
    if not clean: return ""
    try:
        out = summarizer(clean, max_length=MAX_LEN, min_length=MIN_LEN,
                         num_beams=NUM_BEAMS, do_sample=DO_SAMPLE)
        return out[0]["summary_text"].strip()
    except Exception:
        return ""

# -------------------
# 카테고리 & 감성분석
# -------------------
def classify_category_weighted(title: str, content: str) -> str:
    """
    제목(title) + 본문(content)을 기반으로 카테고리별 키워드 가중치 점수를 계산
    - 제목은 1.5배 가중치
    - CATEGORY_KEYWORDS_WEIGHT 딕셔너리를 기반으로 합산
    """
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

# -------------------
# 키워드 추출
# -------------------
from pathlib import Path
from typing import Set

okt = Okt()
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")

from typing import Optional, Set

def load_stopwords(path: str = "stopwords.txt", extra: Optional[Set[str]] = None) -> set:
    """
    한국어 뉴스용 불용어 로더 (Python 3.9~3.10 호환).
    - 파일이 없으면 기본 세트를 사용.
    - extra 인자로 추가 단어를 합침.
    """
    base = {
        # 조사·접속사
        "은","는","이","가","을","를","에","에서","으로","로","과","와","의","도","만",
        "보다","까지","했다","있다","되다","하다","위해","통해","대한","및","등","중","것","수","때문","관련","대해",
        # 시점·빈출 서술
        "오늘","어제","내일","현재","최근","당시","작년","올해","이번","지난","금주","전일","전날","기자","사진","영상","속보"
    }

    try:
        with open(path, encoding="utf-8") as f:
            base |= {w.strip().lower() for w in f if w.strip()}
    except FileNotFoundError:
        pass

    if extra:
        base |= {w.lower() for w in extra}

    return base

# 언론사명(OIDS 값)을 불용어에 자동 포함
PRESS_WORDS = {v for v in OIDS.values()}  # 예: {"연합뉴스","한국경제",...}
STOPWORDS = load_stopwords(extra=PRESS_WORDS)

def extract_keywords(text: str) -> List[str]:
    """
    형태소 분석 → 명사/알파벳 → 정규식 필터 → 불용어 제거 → 중복 제거
    초보 팁: 'stopwords.txt'를 같은 디렉터리에 두고 단어를 줄바꿈으로 추가하세요.
    """
    if not text:
        return []
    pos = okt.pos(text, norm=True, stem=True)  # 정규화+어간화
    candidates = (w for (w, p) in pos if p in ("Noun", "Alpha"))

    tokens, seen = [], set()
    for w in candidates:
        w = w.lower()
        if not TOKEN_RE.fullmatch(w):      # 2자 이상 한/영/숫자만
            continue
        if w in STOPWORDS:                  # 불용어 제거
            continue
        if len(w) < 2:                      # 안전 길이 필터
            continue
        if w not in seen:
            tokens.append(w)
            seen.add(w)
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

# -------------------
# 실행 본체
# -------------------
def crawl_and_save(days: int = 1, limit_per_day: int = 100):
    col = get_collection()
    counters = {}

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        logging.info("📅 수집 시작: %s", date)
        inserted, page = 0, 1

        while inserted < limit_per_day:
            url = build_url(date, page)
            res = requests.get(url, headers=UA, timeout=10)
            res.raise_for_status()
            links = extract_links(res.text)
            if not links: break

            for title, link in links:
                if col.find_one({"url": link}): continue
                art = fetch_article(link)
                if not art["published_at"]: continue

                pub_date = art["published_at"].date()
                if pub_date.strftime("%Y%m%d") != date: continue
                if counters.get(pub_date, 0) >= limit_per_day: continue

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
                    "published_at": art["published_at"].isoformat(),  # 기사 발행일 기준
                }
                try:
                    col.insert_one(doc)
                    counters[pub_date] = counters.get(pub_date, 0) + 1
                    inserted += 1
                    logging.info("[OK] 저장됨: %s (%s)", link, pub_date)
                except Exception as e:
                    logging.warning("[SKIP] 저장 실패: %s", e)

                if inserted >= limit_per_day: break

            page += 1
            time.sleep(0.3)

        logging.info("▶ %s 날짜 결과: %d개", date, inserted)

    logging.info("✅ 전체 수집 완료 (일별 카운트: %s)", counters)

if __name__ == "__main__":
    crawl_and_save(days=1, limit_per_day=100)
