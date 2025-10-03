import requests
import pandas as pd

# ===== ECOS 기본설정 =====
ECOS_API_KEY = "VIU3HJ9GYAQ9P9OMDTCV"  # 이미 ecos.py 안에 있던 키
ECOS_BASE = "https://ecos.bok.or.kr/api"

# ===== 100대 주요지표 불러오기 =====
def ecos_get(url: str):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def load_key_statistics():
    url = f"{ECOS_BASE}/KeyStatisticList/{ECOS_API_KEY}/json/kr/1/200/"
    js = ecos_get(url)
    rows = (js or {}).get("KeyStatisticList", {}).get("row", [])
    return rows if isinstance(rows, list) else []

def pick_by_names(rows, names):
    up_rows = [
        {**r, "_UP_NAME": (r.get("KEYSTAT_NAME") or "").strip().upper()}
        for r in rows
    ]
    for name in names:
        key_up = name.strip().upper()
        for r in up_rows:
            if key_up in r["_UP_NAME"]:
                return r
    return None

def to_simple_record(r):
    if not r:
        return {"name": None, "value": None, "cycle": None, "unit": None, "class": None}
    return {
        "name": r.get("KEYSTAT_NAME"),
        "value": float(str(r.get("DATA_VALUE")).replace(",","")) if r.get("DATA_VALUE") else None,
        "cycle": r.get("CYCLE"),
        "unit": r.get("UNIT_NAME"),
        "class": r.get("CLASS_NAME"),
    }

# ===== 실제 호출 =====
TARGETS = {
    "policy_rate": ["한국은행 기준금리"],
    "gdp_qoq": ["경제성장률(실질, 계절조정 전기대비)"],
    "cpi": ["소비자물가지수(전년동월비)", "소비자물가지수"],
    "unemployment": ["실업률"],
}

rows = load_key_statistics()
ecos_out = {}
for key, names in TARGETS.items():
    ecos_out[key] = to_simple_record(pick_by_names(rows, names))

df_ecos = pd.DataFrame.from_dict(ecos_out, orient="index").reset_index()
df_ecos.rename(columns={"index":"indicator"}, inplace=True)

print(df_ecos)
