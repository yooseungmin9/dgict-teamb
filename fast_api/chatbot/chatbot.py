# chatbot.py — DB 최신뉴스 우선 라우팅 + RAG(문서) + GPT-5 일반 답변 (최적화판 - 오류 수정)

from fastapi import FastAPI, UploadFile, File, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pathlib import Path
from typing import Optional, Dict, Any, List
from openai import OpenAI
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
import os, sys, logging, subprocess, io, requests, tempfile, re, shutil
from google.cloud import texttospeech
from google.oauth2 import service_account
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd

# ===== 로깅 =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("chatbot")

# ===== OpenAI (중복 생성 금지, ASCII 헤더만) =====
API_KEY = "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"
client = OpenAI(api_key=API_KEY, default_headers={"User-Agent": "dgict-bot/1.0"})

# ===== 시스템 프롬프트 =====
SYSTEM_INSTRUCTIONS = """
너는 'AI 기반 경제 뉴스 분석 웹서비스'의 안내 챗봇이다. 사용자는 '바로 결과'를 원한다.
- 결론부터 3~6문장 또는 불릿으로 간결히 답하라. 유도 질문/군더더기 금지.
- 가능하면 '제목(링크) · 발행일(KST) · 한줄 요약' 구조를 쓴다.
- 어려운 용어는 괄호로 짧게 보충한다. (예: 리프라이싱=재가격조정)
- 에러/빈결과는 한 줄로 원인 + 1가지 대안만 제시한다.

라우팅(서버 정책):
1) '최신 경제 뉴스' 요청은 서버가 DB에서 처리해 결과만 전달한다.
2) '웹서비스 기능/도움말' 요청은 파일검색(RAG)로 문서를 바탕으로 답한다.
3) 그 외 일반 질문(금리 포함)은 너의 모델 지식만으로 바로 답한다.
4) '100대 경제지표' 또는 특정 경제지표(금리, 물가, GDP 등) 요청은 한국은행 ECOS API로 실시간 조회한다.
"""

# ===== 벡터스토어 ID (RAG) =====
VS_ID_PATH = Path(".vector_store_id")
if not VS_ID_PATH.exists():
    log.error(".vector_store_id 없음. watcher.py 먼저 실행하세요.")
    sys.exit(1)
VS_ID = VS_ID_PATH.read_text().strip()
log.info(f"VectorStore ID: {VS_ID}")

# ===== MongoDB =====
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME = "test123"
COLL_NAME = "chatbot_rag"

# ===== ECOS =====
ECOS_API_KEY = "VIU3HJ9GYAQ9P9OMDTCV"
ECOS_BASE = "https://ecos.bok.or.kr/api"

# ===== FFmpeg =====
FFMPEG = os.getenv("FFMPEG_BIN") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

def _ffmpeg_to_wav16k(in_path: str) -> str:
    if not os.path.exists(FFMPEG):
        raise RuntimeError(f"ffmpeg not found: {FFMPEG}")
    out_path = in_path + ".wav"
    cp = subprocess.run(
        [FFMPEG, "-y", "-i", in_path, "-ac", "1", "-ar", "16000", out_path],
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {cp.stderr[:300]}")
    return out_path

# ===== KST (통일) =====
KST = ZoneInfo("Asia/Seoul")

# ===== MongoDB 헬퍼 =====
def _get_db():
    return MongoClient(MONGO_URI)[DB_NAME]

def _ensure_indexes():
    """앱 시작 시 한 번만 실행"""
    coll = _get_db()[COLL_NAME]
    coll.create_index([("published_at", DESCENDING)])
    coll.create_index([("collected_at", DESCENDING)])
    log.info("MongoDB 인덱스 확인 완료")

# ===== ECOS 100대 지표 전체 조회 =====
def fetch_all_key_statistics() -> dict:
    """한국은행 ECOS 100대 주요통계지표 전체 조회"""
    try:
        url = f"{ECOS_BASE}/KeyStatisticList/{ECOS_API_KEY}/json/kr/1/200/"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return {"error": f"API 호출 실패: {response.status_code}"}

        data = response.json()
        rows = data.get("KeyStatisticList", {}).get("row", [])

        if not rows:
            return {"error": "데이터가 없습니다"}

        return {"ok": True, "count": len(rows), "indicators": rows}
    except Exception as e:
        log.exception("ECOS 100대 지표 조회 오류")
        return {"error": str(e)}


def fetch_ecos_stat_by_code(stat_code: str, start_ym: str = None, end_ym: str = None) -> dict:
    """
    ECOS 통계표 코드로 특정 지표 조회
    예: stat_code='901Y009' (소비자물가지수)
    """
    try:
        if not end_ym:
            end_ym = datetime.now(KST).strftime("%Y%m")
        if not start_ym:
            start_dt = datetime.now(KST) - timedelta(days=365)
            start_ym = start_dt.strftime("%Y%m")

        url = (f"{ECOS_BASE}/StatisticSearch/{ECOS_API_KEY}/json/kr/"
               f"1/100/{stat_code}/M/{start_ym}/{end_ym}/")

        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return {"error": f"API 호출 실패: {response.status_code}"}

        data = response.json()
        rows = data.get("StatisticSearch", {}).get("row", [])

        if not rows:
            return {"error": f"통계코드 {stat_code}에 대한 데이터가 없습니다"}

        return {"ok": True, "stat_code": stat_code, "data": rows}
    except Exception as e:
        log.exception(f"ECOS 통계코드 {stat_code} 조회 오류")
        return {"error": str(e)}


def get_indicator_by_keyword(keyword: str) -> str:
    """키워드로 ECOS 100대 지표 검색"""
    result = fetch_all_key_statistics()
    if "error" in result:
        return f"지표 조회 실패: {result['error']}"

    indicators = result.get("indicators", [])
    keyword_upper = keyword.strip().upper()
    matched = []

    for ind in indicators:
        name = (ind.get("KEYSTAT_NAME") or "").upper()
        if keyword_upper in name:
            matched.append(ind)

    if not matched:
        return f"'{keyword}' 관련 지표를 찾을 수 없습니다."

    output = [f"**'{keyword}' 관련 경제지표** ({len(matched)}개)"]
    for i, ind in enumerate(matched[:5], 1):
        name = ind.get("KEYSTAT_NAME", "이름 없음")
        value = ind.get("DATA_VALUE", "-")
        unit = ind.get("UNIT_NAME", "")
        time = ind.get("TIME", "")
        output.append(f"{i}. **{name}**: {value} {unit} (기준: {time})")

    return "\n".join(output)


# ===== 특정 경제지표 조회 함수들 =====
def get_cpi_data() -> str:
    """소비자물가지수(CPI) 조회 - ECOS 통계코드: 901Y009"""
    result = fetch_ecos_stat_by_code("901Y009")
    if "error" in result:
        return f"CPI 조회 실패: {result['error']}"

    data = result.get("data", [])
    if not data:
        return "CPI 데이터가 없습니다."

    latest = data[-1]
    prev = data[-2] if len(data) >= 2 else None

    value = latest.get("DATA_VALUE", "N/A")
    time = latest.get("TIME", "")

    output = [
        "**소비자물가지수(CPI)**",
        f"• 최신값: {value} (기준: {time})"
    ]

    if prev:
        try:
            prev_value = float(prev.get("DATA_VALUE", 0))
            curr_value = float(value)
            change = curr_value - prev_value
            output.append(f"• 전월 대비: {change:+.2f}%p")
        except (ValueError, TypeError):
            pass

    return "\n".join(output)


def get_ppi_data() -> str:
    """생산자물가지수(PPI) 조회 - ECOS 통계코드: 404Y014"""
    result = fetch_ecos_stat_by_code("404Y014")
    if "error" in result:
        return f"PPI 조회 실패: {result['error']}"

    data = result.get("data", [])
    if not data:
        return "PPI 데이터가 없습니다."

    latest = data[-1]
    value = latest.get("DATA_VALUE", "N/A")
    time = latest.get("TIME", "")

    return f"**생산자물가지수(PPI)**\n• 최신값: {value} (기준: {time})"


def get_gdp_data() -> str:
    """GDP 성장률 조회 - ECOS 통계코드: 200Y101"""
    result = fetch_ecos_stat_by_code("200Y101",
                                     start_ym=(datetime.now(KST) - timedelta(days=730)).strftime("%Y"),
                                     end_ym=datetime.now(KST).strftime("%Y"))
    if "error" in result:
        return f"GDP 조회 실패: {result['error']}"

    data = result.get("data", [])
    if not data:
        return "GDP 데이터가 없습니다."

    latest = data[-1]
    value = latest.get("DATA_VALUE", "N/A")
    time = latest.get("TIME", "")

    return f"**GDP 성장률**\n• 최신값: {value}% (기준: {time})"


def get_trade_balance() -> str:
    """무역수지 조회 - ECOS 통계코드: 901Y011 (수출), 901Y012 (수입)"""
    export_result = fetch_ecos_stat_by_code("901Y011")
    import_result = fetch_ecos_stat_by_code("901Y012")

    if "error" in export_result or "error" in import_result:
        return "무역수지 조회 실패"

    export_data = export_result.get("data", [])
    import_data = import_result.get("data", [])

    if not export_data or not import_data:
        return "무역수지 데이터가 없습니다."

    exp_latest = export_data[-1]
    imp_latest = import_data[-1]

    try:
        exp_value = float(exp_latest.get("DATA_VALUE", 0))
        imp_value = float(imp_latest.get("DATA_VALUE", 0))
        balance = exp_value - imp_value
        time = exp_latest.get("TIME", "")

        return (f"**무역수지**\n"
                f"• 수출: ${exp_value:,.0f}백만\n"
                f"• 수입: ${imp_value:,.0f}백만\n"
                f"• 무역수지: ${balance:+,.0f}백만 (기준: {time})")
    except (ValueError, TypeError):
        return "무역수지 데이터 파싱 오류"


def get_current_account() -> str:
    """경상수지 조회 - ECOS 통계코드: 301Y013"""
    result = fetch_ecos_stat_by_code("301Y013")
    if "error" in result:
        return f"경상수지 조회 실패: {result['error']}"

    data = result.get("data", [])
    if not data:
        return "경상수지 데이터가 없습니다."

    latest = data[-1]
    value = latest.get("DATA_VALUE", "N/A")
    time = latest.get("TIME", "")

    return f"**경상수지**\n• 최신값: ${value}백만 (기준: {time})"


def get_base_rate() -> str:
    """기준금리 조회 - 100대 지표에서 검색"""
    try:
        result = fetch_all_key_statistics()
        if "error" in result:
            return f"기준금리 조회 실패: {result['error']}"

        indicators = result.get("indicators", [])
        for ind in indicators:
            name = (ind.get("KEYSTAT_NAME") or "").upper()
            if "기준금리" in name or "BASE RATE" in name:
                rate = ind.get("DATA_VALUE", "N/A")
                unit = ind.get("UNIT_NAME", "%")
                time = ind.get("TIME", "")
                return (f"**한국은행 기준금리**\n"
                        f"• 현재 금리: {rate}{unit} (기준: {time})")

        return "기준금리 정보를 찾을 수 없습니다."
    except Exception as e:
        return f"기준금리 조회 오류: {e}"


def fetch_bok_base_rate_from_keystats() -> dict:
    """
    ECOS 100대 지표 목록 중 '기준금리' 관련 항목을 찾아 최신값을 리턴.
    반환: {"rate": float, "unit": str, "name": str, "time": str}
    """
    result = fetch_all_key_statistics()
    if "error" in result:
        raise RuntimeError(result["error"])

    rows = result.get("indicators", []) or []
    name_keys = ["기준금리", "기준 금리", "콜금리", "Base rate", "Policy rate", "BOK Base"]
    cand = []
    for r in rows:
        nm = (r.get("KEYSTAT_NAME") or "").strip()
        up = nm.upper()
        if any(k.upper() in up for k in name_keys):
            cand.append(r)

    if not cand:
        raise RuntimeError("기준금리 관련 지표를 찾지 못했습니다.")

    def score(x):
        unit = (x.get("UNIT_NAME") or "").strip()
        nm = (x.get("KEYSTAT_NAME") or "").strip()
        s = 0
        if "%" in unit:
            s += 10
        if "기준" in nm:
            s += 5
        if "콜" in nm:
            s += 2
        return s

    cand.sort(key=score, reverse=True)
    top = cand[0]

    val = top.get("DATA_VALUE")
    unit = top.get("UNIT_NAME") or "%"
    name = top.get("KEYSTAT_NAME") or "기준금리"
    time = top.get("TIME") or top.get("CYCLE") or ""

    try:
        rate = float(str(val).replace(",", ""))
    except Exception:
        raise RuntimeError(f"기준금리 수치 파싱 실패: {val}")

    return {"rate": rate, "unit": unit, "name": name, "time": time}


# ===== yfinance =====
INDEX_MAP: Dict[str, Dict[str, str]] = {
    "KOSPI": {"ticker": "^KS11", "name": "코스피"},
    "KOSDAQ": {"ticker": "^KQ11", "name": "코스닥"},
    "NASDAQ": {"ticker": "^IXIC", "name": "나스닥 종합"},
    "SP500": {"ticker": "^GSPC", "name": "S&P 500"},
    "DOW": {"ticker": "^DJI", "name": "다우존스 산업평균"},
    "RUSSELL": {"ticker": "^RUT", "name": "러셀 2000"},
    "VIX": {"ticker": "^VIX", "name": "VIX 변동성 지수"},
}

FX_MAP = {
    "USD_KRW": {"ticker": "USDKRW=X", "name": "달러/원"},
    "JPY_KRW": {"ticker": "JPYKRW=X", "name": "엔/원"},
    "EUR_USD": {"ticker": "EURUSD=X", "name": "유로/달러"},
}


def _round_or_none(v, nd=2):
    try:
        return round(float(v), nd)
    except Exception:
        return None


def fetch_quote_yf(ticker: str) -> Dict[str, Any]:
    """yfinance로 실시간 시세 조회 (1분봉 → 일봉 폴백)"""
    price = prev_close = change = change_pct = None

    try:
        hist = yf.Ticker(ticker).history(period="1d", interval="1m", auto_adjust=False)
        closes: pd.Series = hist["Close"].dropna()
        if len(closes) >= 2:
            price = float(closes.iloc[-1])
            prev_close = float(closes.iloc[-2])
        elif len(closes) == 1:
            price = float(closes.iloc[-1])
    except Exception:
        pass

    if prev_close is None:
        try:
            d = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            dcloses: pd.Series = d["Close"].dropna()
            if price is None and len(dcloses) >= 1:
                price = float(dcloses.iloc[-1])
            if len(dcloses) >= 2:
                prev_close = float(dcloses.iloc[-2])
        except Exception:
            pass

    if price is not None and prev_close is not None and prev_close != 0:
        change = price - prev_close
        change_pct = (change / prev_close) * 100.0

    now_kst = datetime.now(KST).isoformat()

    return {
        "ticker": ticker,
        "price": _round_or_none(price, 2),
        "prevClose": _round_or_none(prev_close, 2),
        "change": _round_or_none(change, 2),
        "changePct": _round_or_none(change_pct, 2),
        "ts_kst": now_kst,
    }


def get_market_indices() -> str:
    """주요 지수 조회"""
    results = []
    for key, info in INDEX_MAP.items():
        q = fetch_quote_yf(info["ticker"])
        name = info["name"]
        price = q.get("price")
        change_pct = q.get("changePct")

        if price is not None:
            if change_pct is not None:
                sign = "+" if change_pct >= 0 else ""
                results.append(f"• **{name}**: {price:,.2f} ({sign}{change_pct:.2f}%)")
            else:
                results.append(f"• **{name}**: {price:,.2f}")
        else:
            results.append(f"• **{name}**: 데이터 없음")

    return "**주요 지수 (실시간)**\n" + "\n".join(results)


def get_fx_rates() -> str:
    """주요 환율 조회"""
    results = []
    for key, info in FX_MAP.items():
        q = fetch_quote_yf(info["ticker"])
        name = info["name"]
        price = q.get("price")
        change_pct = q.get("changePct")

        if price is not None:
            if change_pct is not None:
                sign = "+" if change_pct >= 0 else ""
                results.append(f"• **{name}**: {price:,.2f} ({sign}{change_pct:.2f}%)")
            else:
                results.append(f"• **{name}**: {price:,.2f}")
        else:
            results.append(f"• **{name}**: 데이터 없음")

    return "**주요 환율 (실시간)**\n" + "\n".join(results)


def get_kospi_index() -> str:
    """코스피 지수 조회"""
    q = fetch_quote_yf("^KS11")
    price = q.get("price")
    change = q.get("change")
    change_pct = q.get("changePct")

    if price is None:
        return "**코스피 지수**\n• 현재 데이터를 가져올 수 없습니다."

    sign = "+" if (change or 0) >= 0 else ""
    change_str = f"{sign}{change:,.2f}" if change is not None else "N/A"
    pct_str = f"{sign}{change_pct:.2f}%" if change_pct is not None else "N/A"

    return (f"**코스피 지수 (실시간)**\n"
            f"• 현재가: {price:,.2f}\n"
            f"• 변동: {change_str} ({pct_str})")

def get_kosdk_index() -> str:
    """코스닥 지수 조회"""
    q = fetch_quote_yf("^KQ11")
    price = q.get("price")
    change = q.get("change")
    change_pct = q.get("changePct")

    if price is None:
        return "**코스닥 지수**\n• 현재 데이터를 가져올 수 없습니다."

    sign = "+" if (change or 0) >= 0 else ""
    change_str = f"{sign}{change:,.2f}" if change is not None else "N/A"
    pct_str = f"{sign}{change_pct:.2f}%" if change_pct is not None else "N/A"

    return (f"**코스닥 지수 (실시간)**\n"
            f"• 현재가: {price:,.2f}\n"
            f"• 변동: {change_str} ({pct_str})")

def get_usd_krw() -> str:
    """원달러 환율 조회"""
    q = fetch_quote_yf("USDKRW=X")
    price = q.get("price")
    change = q.get("change")
    change_pct = q.get("changePct")

    if price is None:
        return "**원/달러 환율**\n• 현재 데이터를 가져올 수 없습니다."

    sign = "+" if (change or 0) >= 0 else ""
    change_str = f"{sign}{change:,.2f}원" if change is not None else "N/A"
    pct_str = f"{sign}{change_pct:.2f}%" if change_pct is not None else "N/A"

    return (f"**원/달러 환율 (실시간)**\n"
            f"• 현재: {price:,.2f}원\n"
            f"• 변동: {change_str} ({pct_str})")

def get_jpy_krw() -> str:
    """원엔 환율 조회"""
    q = fetch_quote_yf("JPYKRW=X")
    price = q.get("price")
    change = q.get("change")
    change_pct = q.get("changePct")

    if price is None:
        return "**원/엔 환율**\n• 현재 데이터를 가져올 수 없습니다."

    sign = "+" if (change or 0) >= 0 else ""
    change_str = f"{sign}{change:,.2f}원" if change is not None else "N/A"
    pct_str = f"{sign}{change_pct:.2f}%" if change_pct is not None else "N/A"

    return (f"**원/엔 환율 (실시간)**\n"
            f"• 현재: {price:,.2f}원\n"
            f"• 변동: {change_str} ({pct_str})")

def get_eur_usd() -> str:
    """유로달러 환율 조회"""
    q = fetch_quote_yf("EURUSD=X")
    price = q.get("price")
    change = q.get("change")
    change_pct = q.get("changePct")

    if price is None:
        return "**유로/달러 환율**\n• 현재 데이터를 가져올 수 없습니다."

    sign = "+" if (change or 0) >= 0 else ""
    change_str = f"{sign}{change:,.2f}달러" if change is not None else "N/A"
    pct_str = f"{sign}{change_pct:.2f}%" if change_pct is not None else "N/A"

    return (f"**유로/달러 환율 (실시간)**\n"
            f"• 현재: {price:,.2f}달러\n"
            f"• 변동: {change_str} ({pct_str})")

# ===== MongoDB - 최신 뉴스 조회 =====
def fetch_latest_topn_from_mongo(n: int = 5):
    """MongoDB에서 최신 뉴스 N건 조회"""
    coll = _get_db()[COLL_NAME]
    pipeline = [
        {"$addFields": {"_p": {"$ifNull": ["$published_at", "$collected_at"]}}},
        {"$sort": {"_p": -1}},
        {"$limit": int(n)},
        {"$project": {"_id": 0, "title": 1, "url": 1, "published_at": 1}},
    ]
    rows = list(coll.aggregate(pipeline))

    for r in rows:
        pa = r.get("published_at")
        if isinstance(pa, datetime):
            if pa.tzinfo is None:
                pa = pa.replace(tzinfo=timezone.utc)
            r["published_at"] = pa.astimezone(KST).strftime("%Y-%m-%d")
        elif isinstance(pa, str):
            pass
        else:
            r["published_at"] = ""
    return rows


def format_topn_md(rows):
    """최신 뉴스 N건 포맷팅"""
    if not rows:
        return "최신 경제 뉴스가 없습니다."
    out = ["**최신 경제 뉴스**"]
    for i, r in enumerate(rows, start=1):
        title = (r.get("title") or "").strip() or "(제목 없음)"
        url = (r.get("url") or "").strip()
        date = r.get("published_at", "")
        if url:
            out.append(f"{i}. [{title}]\n출처: ({url}) · 날짜: {date}")
        else:
            out.append(f"{i}. {title} · {date}")
    return "\n".join(out)


# ===== 의도 판별 패턴 =====
CPI_PATTERNS = [r"(소비자\s*물가|CPI|소비자물가지수|물가상승률)"]
PPI_PATTERNS = [r"(생산자\s*물가|PPI|생산자물가지수)"]
GDP_PATTERNS = [r"(GDP|국내총생산|경제성장률|성장률)"]
TRADE_PATTERNS = [r"(무역수지|수출입|수출\s*수입)"]
CURRENT_ACCOUNT_PATTERNS = [r"(경상수지|경기수지)"]
RATE_PATTERNS = [r"(기준\s*금리|정책\s*금리|금리|한국은행\s*금리)"]
KOSPI_PATTERNS = [r"(코스피|KOSPI|한국\s*주가)"]
KOSDAQ_PATTERNS = [r"(코스닥|KOSDAQ)"]
FX_PATTERNS_JPY = [r"(원\s*엔|엔\s*원|엔화\s*환율|JPY|엔\s*환율|엔화|일본\s*엔)"]
FX_PATTERNS_USD = [r"(원\s*달러|달러\s*원|달러\s*환율|USD|미국\s*달러)"]
FX_PATTERNS_EUR = [r"(유로\s*달러|유로\s*환율|EUR|유로)"]
MARKET_PATTERNS = [r"(지수|다우|나스닥|S&P|VIX|주가지수)"]
NEWS_PATTERNS = [r"(최신\s*뉴스|경제\s*뉴스|뉴스|top\s*\d+)"]

ECOS_100_PATTERNS = [
    r"100대\s*(지표|통계)",
    r"경제지표\s*(전체|목록|리스트)",
    r"주요\s*경제지표",
]

LATEST_NEWS_PATTERNS = [
    r"최신\s*경제\s*뉴스",
    r"오늘\s*경제\s*뉴스",
    r"실시간\s*경제\s*뉴스",
    r"경제\s*뉴스\s*top\s*\d+",
]

SITE_HELP_PATTERNS = [
    r"(웹|웹\s*서비스|사이트).*?(기능|도움말|사용법|소개|무엇|뭐가|설명)",
    r"(기능|도움말|사용법|소개)\s*(알려줘|설명|가이드)",
]


def match_intent(q: str, patterns: list) -> bool:
    return any(re.search(p, q, flags=re.IGNORECASE) for p in patterns)


def is_rate_query(q: str) -> bool:
    return match_intent(q, RATE_PATTERNS)


def is_latest_news_query(q: str) -> bool:
    q = (q or "").lower()
    return match_intent(q, LATEST_NEWS_PATTERNS) or ("뉴스" in q and ("최신" in q or "top" in q))


def is_site_help_query(q: str) -> bool:
    return match_intent(q, SITE_HELP_PATTERNS)


def parse_topn(q: str, default_n: int = 5) -> int:
    if not q:
        return default_n
    m = re.search(r"top\s*(\d{1,2})", q, flags=re.IGNORECASE)
    if m:
        return max(1, min(50, int(m.group(1))))
    m2 = re.search(r"(\d{1,2})\s*(개|건)", q)
    return max(1, min(50, int(m2.group(1)))) if m2 else default_n


# ===== FastAPI 앱 =====
app = FastAPI(title="Chat+RAG+News+Indicators")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 세션 메모리 (간단한 히스토리, 프로덕션에서는 Redis 등 사용 권장)
history = []
MAX_HISTORY_LENGTH = 50  # 메모리 누수 방지


# ===== 메인 챗 라우팅 =====
@app.post("/chat")
@app.post("/api/chat")
async def chat(payload: dict):
    global history
    q = (payload.get("message") or "").strip()
    if not q:
        return {"answer": "질문이 비어있습니다."}

    # 히스토리 길이 제한
    if len(history) > MAX_HISTORY_LENGTH:
        history = history[-MAX_HISTORY_LENGTH:]

    # 1) 최신 뉴스 → Mongo
    if is_latest_news_query(q):
        try:
            n = parse_topn(q, default_n=5)
            rows = fetch_latest_topn_from_mongo(n)
            return {"answer": format_topn_md(rows)}
        except Exception as e:
            log.exception("Mongo 최신뉴스 조회 오류")
            return {"answer": f"DB 조회 오류: {e}"}

    # 2) CPI
    if match_intent(q, CPI_PATTERNS):
        return {"answer": get_cpi_data()}

    # 3) PPI
    if match_intent(q, PPI_PATTERNS):
        return {"answer": get_ppi_data()}

    # 4) GDP
    if match_intent(q, GDP_PATTERNS):
        return {"answer": get_gdp_data()}

    # 5) 무역수지
    if match_intent(q, TRADE_PATTERNS):
        return {"answer": get_trade_balance()}

    # 6) 경상수지
    if match_intent(q, CURRENT_ACCOUNT_PATTERNS):
        return {"answer": get_current_account()}

    # 7) 기준금리
    if is_rate_query(q):
        try:
            info = fetch_bok_base_rate_from_keystats()
            rate = info["rate"]
            unit = info.get("unit") or "%"
            nm = info.get("name") or "기준금리"
            tm = info.get("time") or ""
            ans = (
                "• 금리: 돈을 빌리거나 예치할 때의 가격(이자율)입니다.\n"
                "• 한국은행 기준금리: 금통위가 정하는 단일 정책금리로 단기시장금리의 기준입니다.\n"
                f"• 최신 {nm}: **{rate:.2f}{unit}**" + (f" (기준시점: {tm})" if tm else "") + "\n"
                f"• 출처: 한국은행 ECOS 100대 주요통계지표"
            )
            return {"answer": ans}
        except Exception as e:
            log.warning(f"ECOS 기준금리 조회 실패: {e}")
            return {
                "answer": "실시간 기준금리 조회에 실패했습니다. 최신값은 한국은행 보도자료(금통위 의결 결과)에서 확인해 주세요."
            }

    # 8) 코스피, 코스닥
    if match_intent(q, KOSPI_PATTERNS):
        return {"answer": get_kospi_index()}

    if match_intent(q, KOSDAQ_PATTERNS):
        return {"answer": get_kosdk_index()}

    # 9) 환율
    if match_intent(q, FX_PATTERNS_USD):
        return {"answer": get_usd_krw()}

    if match_intent(q, FX_PATTERNS_JPY):
        return {"answer": get_jpy_krw()}

    if match_intent(q, FX_PATTERNS_EUR):
        return {"answer": get_eur_usd()}

    # 10) 주요 지수
    if match_intent(q, MARKET_PATTERNS):
        indices = get_market_indices()
        fx = get_fx_rates()
        return {"answer": f"{indices}\n\n{fx}"}

    # 11) 웹서비스 기능/도움말 → RAG(file_search)
    if is_site_help_query(q):
        history.append({"role": "user", "content": [{"type": "input_text", "text": q}]})
        try:
            resp = client.responses.create(
                model="gpt-5",
                instructions=SYSTEM_INSTRUCTIONS,
                tools=[{"type": "file_search", "vector_store_ids": [VS_ID]}],
                input=history,
            )
            answer = (getattr(resp, "output_text", "") or "").strip()
            if not answer:
                answer = "문서를 확인했지만 응답을 생성하지 못했어요."
            history.append({"role": "assistant", "content": [{"type": "output_text", "text": answer}]})
            return {"answer": answer}
        except Exception as e:
            log.exception("RAG 호출 실패")
            return {"answer": f"RAG 호출 실패: {e}"}

    # 12) 그 외 → GPT-5 단독
    history.append({"role": "user", "content": [{"type": "input_text", "text": q}]})
    try:
        resp = client.responses.create(
            model="gpt-5",
            instructions=SYSTEM_INSTRUCTIONS,
            input=history,
        )
        answer = (getattr(resp, "output_text", "") or "").strip()
        if not answer:
            answer = "응답이 비었습니다."
        history.append({"role": "assistant", "content": [{"type": "output_text", "text": answer}]})
        return {"answer": answer}
    except Exception as e:
        log.exception("모델 호출 실패")
        return {"answer": f"모델 호출 실패: {e}"}


# ===== API 엔드포인트 =====
@app.get("/api/indices")
def api_indices():
    """주요 지수 API 엔드포인트"""
    results = []
    for key, info in INDEX_MAP.items():
        q = fetch_quote_yf(info["ticker"])
        results.append({"key": key, "name": info["name"], **q})
    return {"data": results, "ts_kst": datetime.now(KST).isoformat()}


@app.get("/api/fx")
def api_fx():
    """환율 API 엔드포인트"""
    results = []
    for key, info in FX_MAP.items():
        q = fetch_quote_yf(info["ticker"])
        results.append({"key": key, "name": info["name"], **q})
    return {"data": results, "ts_kst": datetime.now(KST).isoformat()}


@app.get("/api/markets")
def api_markets(indices: int = 1, fx: int = 1):
    """통합 마켓 데이터 API"""
    payload = {"ts_kst": datetime.now(KST).isoformat(), "data": {}}
    if indices:
        idx_items = [{"key": k, "name": v["name"], **fetch_quote_yf(v["ticker"])}
                     for k, v in INDEX_MAP.items()]
        payload["data"]["indices"] = idx_items
    if fx:
        fx_items = [{"key": k, "name": v["name"], **fetch_quote_yf(v["ticker"])}
                    for k, v in FX_MAP.items()]
        payload["data"]["fx"] = fx_items
    return payload


# ===== 가이드 =====
@app.get("/api/chat")
def chat_get_info():
    return {"detail": 'Use POST /api/chat with JSON: {"message":"..."}'}


@app.get("/chat")
def chat_get_info2():
    return {"detail": 'Use POST /chat with JSON: {"message":"..."}'}


# ===== CLOVA STT =====
CLOVA_KEY_ID = "xfug9sgeb9"
CLOVA_KEY = "LxSiEpOQ0JKENstLGHyVSQJKybKOqPfwIhBqfdxk"
CSR_URL = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt"

LANG_MAP = {"ko": "Kor", "en": "Eng", "ja": "Jpn"}


def normalize_lang(l: str) -> str:
    if not l:
        return "Kor"
    if l.lower() in ("kor", "eng", "jpn"):
        return l.title()
    return LANG_MAP.get(l.split("-")[0].lower(), "Kor")


@app.post("/api/stt")
async def stt_clova(audio_file: UploadFile = File(...), lang: str = Query("Kor")):
    lang = normalize_lang(lang)
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(audio_file.filename or "")[1]
    ) as tmp:
        raw = await audio_file.read()
        tmp.write(raw)
        src_path = tmp.name
    wav_path = None
    try:
        wav_path = _ffmpeg_to_wav16k(src_path)
        headers = {
            "X-NCP-APIGW-API-KEY-ID": CLOVA_KEY_ID,
            "X-NCP-APIGW-API-KEY": CLOVA_KEY,
            "Content-Type": "application/octet-stream",
        }
        url = f"{CSR_URL}?lang={lang}"
        with open(wav_path, "rb") as f:
            res = requests.post(url, headers=headers, data=f.read(), timeout=60)
        if res.status_code != 200:
            return JSONResponse(
                {"error": f"CSR 실패: {res.status_code} {res.text}"}, status_code=500
            )
        return {"text": res.text.strip(), "lang": lang}
    except Exception as e:
        log.exception("STT 처리 오류")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        for p in (src_path, wav_path):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


# ===== Google Cloud TTS =====
DEFAULT_VOICE = {
    "ko-KR": "ko-KR-Neural2-B",
    "en-US": "en-US-Neural2-C",
    "ja-JP": "ja-JP-Neural2-B",
}


def _pick_voice(lang: str, voice: Optional[str]) -> str:
    if voice:
        return voice
    base = (lang or "ko-KR").split(",")[0]
    return DEFAULT_VOICE.get(base, "ko-KR-Neural2-B")


@app.post("/api/tts")
def tts_google_post(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    lang = payload.get("lang") or "ko-KR"
    voice = payload.get("voice") or None
    fmt = payload.get("fmt") or "MP3"
    rate = float(payload.get("rate") or 1.0)
    pitch = float(payload.get("pitch") or 0.0)
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)

    GCP_KEY_PATH = "/Users/yoo/key/absolute-text-473306-c1-b75ae69ab526.json"
    gcp_credentials = service_account.Credentials.from_service_account_file(
        GCP_KEY_PATH
    )
    tts_client = texttospeech.TextToSpeechClient(credentials=gcp_credentials)

    try:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice_name = _pick_voice(lang, voice)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=lang, name=voice_name
        )

        if fmt == "MP3":
            audio_cfg = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=rate,
                pitch=pitch,
            )
            media_type, ext = "audio/mpeg", "mp3"
        elif fmt == "OGG_OPUS":
            audio_cfg = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
                speaking_rate=rate,
                pitch=pitch,
            )
            media_type, ext = "audio/ogg", "ogg"
        else:
            audio_cfg = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=rate,
                pitch=pitch,
            )
            media_type, ext = "audio/wav", "wav"

        resp = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice_params, audio_config=audio_cfg
        )
        headers = {
            "Content-Type": media_type,
            "Cache-Control": "no-cache",
            "Content-Disposition": f'inline; filename="speech.{ext}"',
        }
        return StreamingResponse(io.BytesIO(resp.audio_content), headers=headers)
    except Exception as e:
        log.exception("Google TTS 실패")
        return JSONResponse({"error": f"TTS 실패: {e}"}, status_code=500)


# ===== 유틸 =====
@app.post("/reset")
@app.post("/api/reset")
async def reset():
    global history
    history = []
    return {"status": "ok", "message": "대화 기록 초기화 완료"}


@app.get("/health")
def health():
    return {"status": "ok", "ts_kst": datetime.now(KST).isoformat()}


# ===== 스케줄러 =====
scheduler = BackgroundScheduler(timezone=KST)


def _job_naver():
    try:
        from crawler_rag import crawl_today
        crawl_today(limit_per_run=50)
    except Exception as e:
        log.exception("네이버 수집 실패: %s", e)


@app.on_event("startup")
def _start_scheduler():
    # MongoDB 인덱스 초기화
    try:
        _ensure_indexes()
    except Exception as e:
        log.exception("인덱스 생성 실패")

    # 스케줄러 시작
    try:
        scheduler.add_job(
            _job_naver,
            "interval",
            hours=1,
            id="naver_hourly",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        scheduler.start()
        log.info("APScheduler started.")
    except Exception:
        log.exception("APScheduler 시작 실패")


@app.on_event("shutdown")
def _stop_scheduler():
    try:
        scheduler.shutdown()
        log.info("APScheduler stopped.")
    except Exception:
        log.exception("APScheduler 종료 실패")
