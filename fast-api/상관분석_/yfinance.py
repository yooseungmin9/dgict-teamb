# === (B) 전체 동작 "단일 파일" 예시: app_indices_fx.py ===
# 실행: uvicorn app_indices_fx:app --reload --port 8000
# 설치: pip install fastapi uvicorn yfinance pandas
# 테스트:
#  - 지수: curl -s "http://127.0.0.1:8000/api/indices" | python -m json.tool
#  - 환율: curl -s "http://127.0.0.1:8000/api/fx" | python -m json.tool
#  - 합본: curl -s "http://127.0.0.1:8000/api/markets?indices=1&fx=1" | python -m json.tool

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf

app = FastAPI(title="Index & FX API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

KST = ZoneInfo("Asia/Seoul")

# ----- 지수 상수 -----
INDEX_MAP: Dict[str, Dict[str, str]] = {
    "KOSPI":  {"ticker": "^KS11", "name": "코스피"},
    "KOSDAQ": {"ticker": "^KQ11", "name": "코스닥"},
    "NASDAQ": {"ticker": "^IXIC", "name": "나스닥"},
    "SP500":  {"ticker": "^GSPC", "name": "S&P 500"},
}

# ----- 환율 상수 -----
FX_MAP = {
    "USD_KRW": {"ticker": "USDKRW=X", "name": "달러/원"},
    "JPY_KRW": {"ticker": "JPYKRW=X", "name": "엔/원"},
    "CNY_KRW": {"ticker": "CNYKRW=X", "name": "위안/원"},
    "EUR_USD": {"ticker": "EURUSD=X", "name": "유로/달러"},
}

def _round_or_none(v, nd=4):
    # 환율은 소수 4자리까지 보는 경우가 많아 기본 4자리
    try:
        return round(float(v), nd)
    except Exception:
        return None

def fetch_quote_yf(ticker: str) -> Dict[str, Any]:
    """
    공용 시세 조회(지수/환율 공통):
    - 1분봉(1d,1m) 우선 → 없으면 일봉(5d,1d) 폴백
    - price, prevClose, change, changePct, ts_kst/ts_utc 반환
    """
    price = prev_close = change = change_pct = None

    # 1) 1분봉
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

    # 2) 일봉 폴백
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

    now_utc = datetime.now(timezone.utc).isoformat()
    now_kst = datetime.now(KST).isoformat()

    return {
        "ticker": ticker,
        "price": _round_or_none(price),
        "prevClose": _round_or_none(prev_close),
        "change": _round_or_none(change),
        "changePct": _round_or_none(change_pct, 2),
        "ts_kst": now_kst,
        "ts_utc": now_utc,
        "source": "yfinance",
    }

@app.get("/api/indices")
def get_indices() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for key, info in INDEX_MAP.items():
        q = fetch_quote_yf(info["ticker"])
        results.append({"key": key, "name": info["name"], **q})
    return {
        "meta": {
            "count": len(results),
            "ts_kst": datetime.now(KST).isoformat(),
            "note": "야후 파생 데이터이며 지연될 수 있습니다.",
        },
        "data": results,
    }

@app.get("/api/fx")
def get_fx() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for key, info in FX_MAP.items():
        q = fetch_quote_yf(info["ticker"])
        results.append({"key": key, "name": info["name"], **q})
    return {
        "meta": {"count": len(results), "ts_kst": datetime.now(KST).isoformat()},
        "data": results,
    }

@app.get("/api/markets")
def get_markets(indices: int = 1, fx: int = 1):
    payload = {"meta": {"ts_kst": datetime.now(KST).isoformat()}, "data": {}}
    if indices:
        idx_items = [{"key": k, "name": v["name"], **fetch_quote_yf(v["ticker"])} for k, v in INDEX_MAP.items()]
        payload["data"]["indices"] = {"count": len(idx_items), "items": idx_items}
    if fx:
        fx_items = [{"key": k, "name": v["name"], **fetch_quote_yf(v["ticker"])} for k, v in FX_MAP.items()]
        payload["data"]["fx"] = {"count": len(fx_items), "items": fx_items}
    return payload

@app.get("/health")
def health():
    return {"ok": True, "ts_kst": datetime.now(KST).isoformat()}