import re, pandas as pd
from transformers import pipeline
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from pathlib import Path

CSV_IN  = "data/raw_daily.csv"        # 오늘 크롤링한 원본 입력
OUT_LATEST = "data/sentiment_today.csv"   # 오늘 분석 결과
HIST_OUT   = "data/sentiment_history.csv" # 누적 분석 결과
BATCH   = 16
THRESH  = 0.70  # ML 신뢰도 미만이면 규칙으로 대체

# ----- 규칙 기반 -----
POS = {"성장","상승","호재","회복","강세","기대","확대","급등","혁신","강화","돌파","수익","진전","도약","확장","안정","성과"}
NEG = {"하락","악재","부진","적자","위기","침체","감소","실패","논란","취약","추락","불안","손실","퇴출","경고","위축"}
HARD_NEG = {"파산","부도","붕괴","참사","사망","구속","기소","횡령","배임","사기","성폭력","뇌물"}
NEGATORS = {"아니","않","못","무산","불가","중단"}
INTENS = {"매우","대폭","크게","급격","역대","사상","초강력","초대형"}
DEINTENS = {"다소","소폭","부분적","일부","점진","완만"}
TOK = re.compile(r"[가-힣A-Za-z]+")

def rule_sent(text:str):
    if any(w in (text or "") for w in HARD_NEG): return "부정", 1.0, "rules_hard_neg"
    toks = TOK.findall(text or "")
    score = 0.0
    for i,w in enumerate(toks):
        s = (1.0 if w in POS else 0.0) - (1.0 if w in NEG else 0.0)
        if s == 0: continue
        prev = toks[max(0,i-4):i]
        if any(p in INTENS for p in prev): s *= 1.5
        if any(p in DEINTENS for p in prev): s *= 0.7
        if any(p in NEGATORS for p in prev): s *= -1.0
        score += s
    if abs(score) < 0.35: return "중립", 0.6, "rules_only"
    return ("긍정", min(0.99, abs(score)/4+0.5), "rules_only") if score>0 else ("부정", min(0.99, abs(score)/4+0.5), "rules_only")

def predict_long(text, max_len=512):
    tokens = tok(text, return_tensors="pt", truncation=False)["input_ids"][0]
    chunks = [tokens[i:i+max_len] for i in range(0, len(tokens), max_len)]
    preds = []
    for ch in chunks:
        out = tok.decode(ch)
        preds.append(sa(out, truncation=True, max_length=max_len)[0])
    return max(preds, key=lambda x: x["score"])


# ----- ML 파이프라인 (PyTorch 강제) -----
MODEL_ID = "snunlp/KR-FinBert-SC"
device = 0 if torch.cuda.is_available() else -1

tok = AutoTokenizer.from_pretrained(MODEL_ID)
mdl = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)

sa = pipeline(
    "text-classification",
    model=mdl,
    tokenizer=tok,
    framework="pt",
    device=device,
    truncation=True,
    max_length=512
)

def map_star_to_label(pred):
    # 두 모델 모두 'positive/neutral/negative' 반환 → 바로 매핑
    lab = pred["label"].lower()
    if "pos" in lab: return "긍정"
    if "neg" in lab: return "부정"
    return "중립"

# ----- 처리 -----
df = pd.read_csv(CSV_IN)
texts = df["body"].fillna("").astype(str).tolist()

labels_ml, scores_ml = [], []
for text in texts:
    if not text.strip() or len(text) < 200:
        p = None
    elif len(text) > 1500:
        p = predict_long(text)
    else:
        p = sa(text)[0]

    if p:
        labels_ml.append(map_star_to_label(p))
        scores_ml.append(float(p.get("score", 0.0)))
    else:
        labels_ml.append("중립"); scores_ml.append(0.0)

# ----- ML 예측 완료 후 하이브리드 결합 -----
final_label, final_conf, source = [], [], []
for t, l_ml, s_ml in zip(texts, labels_ml, scores_ml):
    if not t.strip():
        l, sc, src = "중립", 0.0, "empty"
    elif s_ml >= THRESH:
        l, sc, src = l_ml, s_ml, "ml"
    else:
        l, sc, src = rule_sent(t)
    final_label.append(l); final_conf.append(sc); source.append(src)

df["sentiment"] = final_label
df["confidence"] = final_conf
df["source"] = source

# 오늘 결과 저장
df.to_csv(OUT_LATEST, index=False, encoding="utf-8-sig")
print("saved today:", OUT_LATEST)

# 누적 파일 업데이트
if Path(HIST_OUT).exists():
    old = pd.read_csv(HIST_OUT)
    merged = pd.concat([old, df], ignore_index=True).drop_duplicates(subset=["url"])
else:
    merged = df
merged.to_csv(HIST_OUT, index=False, encoding="utf-8-sig")
print("updated history:", HIST_OUT)

print(df[["press","title","sentiment","confidence","source"]].head(40).to_string(index=False))
# [df["press"]=="언론사"]