# app_kr_core.py
# ------------------------------------------------------------
# 실행: uvicorn app_kr_core:app --reload --port 8000
# 설치: pip install fastapi uvicorn requests
# 간단 테스트:
#   curl -s "http://127.0.0.1:8000/api/kr-core" | python -m json.tool
# ------------------------------------------------------------
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from typing import Dict, Any, List, Optional

# ===== 1) 기본 설정 =====
app = FastAPI(title="KR Core Indicators (ECOS 100대 지표)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ===== 2) ECOS 상수 (입문자용: 실제 발급키를 상수로 고정) =====
ECOS_API_KEY = "VIU3HJ9GYAQ9P9OMDTCV"  # ← 본인 키 그대로 입력
ECOS_BASE = "https://ecos.bok.or.kr/api"

# ===== 3) 추출 대상 이름(우선순위 포함) =====
# - '소비자물가지수'는 물가상승률로 흔히 '전년동월비(%)'를 쓰므로,
#   먼저 전년동월비 이름을 찾고, 없으면 지수(레벨)로 폴백.
TARGETS: Dict[str, List[str]] = {
    "policy_rate": [
        "한국은행 기준금리",
    ],
    "gdp_qoq": [
        "경제성장률(실질, 계절조정 전기대비)",
    ],
    "cpi": [
        "소비자물가지수(전년동월비)",  # 1순위(물가상승률)
        "소비자물가지수",               # 2순위(지수 레벨, %) 아님
    ],
    "unemployment": [
        "실업률",
    ],
}

# ===== 4) 헬퍼 =====
def ecos_get(url: str) -> Dict[str, Any]:
    """단순 GET 래퍼(에러 시 {'error':...})"""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def load_key_statistics() -> List[Dict[str, Any]]:
    """100대 주요지표 전체 목록 한 번에 로드"""
    url = f"{ECOS_BASE}/KeyStatisticList/{ECOS_API_KEY}/json/kr/1/200/"
    js = ecos_get(url)
    # 정상 구조: {"KeyStatisticList":{"row":[...]}}
    rows = (js or {}).get("KeyStatisticList", {}).get("row", [])
    return rows if isinstance(rows, list) else []

def pick_by_names(rows: List[Dict[str, Any]], names: List[str]) -> Optional[Dict[str, Any]]:
    """여러 후보 이름을 순서대로 매칭해 첫 번째로 찾은 항목을 반환"""
    # 단순 부분일치(대소문자 무시). 완전일치가 필요하면 == 로 변경
    up_rows = [
        {
            **r,
            "_UP_NAME": (r.get("KEYSTAT_NAME") or "").strip().upper(),
        } for r in rows
    ]
    for name in names:
        key_up = name.strip().upper()
        for r in up_rows:
            if key_up in r["_UP_NAME"]:
                return r
    return None

def to_simple_record(r: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """필요 필드만 추려 단순화. r가 None이면 null 필드 반환"""
    if not r:
        return {"name": None, "value": None, "cycle": None, "unit": None, "class": None}
    return {
        "name": r.get("KEYSTAT_NAME"),
        "value": _to_float_or_str(r.get("DATA_VALUE")),
        "cycle": r.get("CYCLE"),       # 날짜/월/분기 등 그대로 전달
        "unit": r.get("UNIT_NAME"),    # %, 2020=100, 천명 등
        "class": r.get("CLASS_NAME"),  # 분류(시장금리, 성장률, 소비자/생산자 물가 등)
    }

def _to_float_or_str(v):
    """숫자면 float로, 아니면 원문 문자열 유지(예: '2020=100' 같은 단위는 unit 필드에서 보세요)"""
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return v

# ===== 5) 엔드포인트 =====
@app.get("/api/kr-core")
def get_kr_core() -> Dict[str, Any]:
    """
    반환 예시:
    {
      "meta": {"source":"ECOS KeyStatisticList", "ok": true},
      "data": {
        "policy_rate": {...},   # 한국은행 기준금리
        "gdp_qoq": {...},       # 경제성장률(실질, 계절조정 전기대비)
        "cpi": {...},           # 소비자물가지수(전년동월비 찾기 실패 시 지수로 폴백)
        "unemployment": {...}   # 실업률
      }
    }
    """
    rows = load_key_statistics()
    out = {
        "meta": {"source": "ECOS KeyStatisticList", "ok": True},
        "data": {}
    }
    # 각 지표 추출(이름 우선순위 매칭)
    out["data"]["policy_rate"]  = to_simple_record(pick_by_names(rows, TARGETS["policy_rate"]))
    out["data"]["gdp_qoq"]      = to_simple_record(pick_by_names(rows, TARGETS["gdp_qoq"]))
    out["data"]["cpi"]          = to_simple_record(pick_by_names(rows, TARGETS["cpi"]))
    out["data"]["unemployment"] = to_simple_record(pick_by_names(rows, TARGETS["unemployment"]))
    return out

@app.get("/health")
def health():
    return {"ok": True}

# ===== 6) 입문자 메모 =====
# - KeyStatisticList는 100대 지표(최신값)를 한 번에 내려주므로, 개별 코드/주기 고민 없이 이름으로 필터하면 됩니다.
# - CPI는 '전년동월비(%)' 항목이 리스트에 있으면 그 값을 사용(물가상승률), 없으면 '소비자물가지수'(지수 레벨)로 폴백합니다.
# - 필요 시 TARGETS 딕셔너리에 이름을 더 추가(동의어)하면 매칭 안정성이 좋아집니다.