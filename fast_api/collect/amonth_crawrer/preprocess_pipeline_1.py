from __future__ import annotations
import os, json, warnings
from datetime import datetime, timedelta, timezone
from typing import List, Any, Iterable
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import numpy as np
from pymongo import MongoClient, ASCENDING
from kiwipiepy import Kiwi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from apscheduler.schedulers.blocking import BlockingScheduler

warnings.filterwarnings("ignore")

# ===== 설정 =====
KST = timezone(timedelta(hours=9))
BASE = Path(__file__).resolve().parent
MODELS_DIR = BASE / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# --- .env에서 불러오는 부분 (필수) ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB  = os.getenv("MONGO_DB")
SRC_COL   = os.getenv("MONGO_COL_SRC", "articles")
PREP_COL  = os.getenv("MONGO_COL_PREP", "articles_preprocessed")

SBERT_MODEL = os.getenv("SBERT_MODEL", "jhgan/ko-sroberta-multitask")
LAMBDA = float(os.getenv("LAMBDA", "0.3"))

# ===== 불용어 =====
DEFAULT_STOPWORDS = {
    "있다","하였다","했다","합니다","하면","하며","하는","하기","했다","그리고","하지만","그러나",
    "대한","관련","제공","기자","사진","연합뉴스","네이버","신문","경제","기사","오늘","지난","이번",
    "것","수","등","및","더","또","중","때문","위해","에서","으로","에서는","에게","까지","로","도",
}
STOPWORD_PATH = BASE / "stopwords_ko.txt"
if STOPWORD_PATH.exists():
    DEFAULT_STOPWORDS |= {w.strip() for w in STOPWORD_PATH.read_text(encoding="utf-8").splitlines() if w.strip()}

def identity_tokenizer(x: str):
    return x.split()

# ===== 유틸 =====
def normalize_text(s: str) -> str:
    if not s:
        return ""
    import re
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w\s가-힣·\-]", " ", s)
    s = s.replace("“","\"").replace("”","\"").replace("‘","'").replace("’","'")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def kiwi_tokenize(kiwi: Kiwi, text: str) -> List[str]:
    toks = []
    for token, pos, _, _ in kiwi.tokenize(text):
        if pos.startswith("NN"):
            w = token.strip()
            if w and w not in DEFAULT_STOPWORDS and len(w) > 1:
                toks.append(w)
    return toks

def tfidf_title_dedup(titles: List[str], threshold: float=0.95) -> List[int]:
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2,4))
    X = vec.fit_transform(titles)
    sim = cosine_similarity(X, dense_output=False)
    n = len(titles)
    keep = [True]*n
    for i in range(n):
        if not keep[i]:
            continue
        col = sim.getrow(i).toarray().ravel()
        dup_idx = np.where(col > threshold)[0]
        for j in dup_idx:
            if j > i:
                keep[j] = False
    return [i for i,flag in enumerate(keep) if flag]

def batched(iterable: Iterable[Any], batch_size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

# ===== 메인 파이프라인 =====
def run_pipeline():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    src = db[SRC_COL]
    dst = db[PREP_COL]

    try:
        src.create_index([("url", ASCENDING)], unique=True)
    except Exception:
        pass
    try:
        dst.create_index([("ref_id", ASCENDING)], unique=True)
        dst.create_index([("published_at", ASCENDING)])
    except Exception:
        pass

    since = datetime.now(tz=KST) - timedelta(days=30)
    query = {"$expr": {"$gte": [{"$toDate": "$published_at"}, since]}}
    fields = {"_id": 1, "url": 1, "title": 1, "content": 1, "press": 1, "published_at": 1}
    docs = list(src.find(query, fields).sort("published_at", ASCENDING))

    if not docs:
        print("no docs")
        return

    rows = []
    for d in docs:
        title = normalize_text(d.get("title", ""))
        body = normalize_text(d.get("content", "") or d.get("body", ""))
        if len(body) < 200:
            continue

        pub = d.get("published_at")
        if isinstance(pub, str):
            try:
                pub = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue

        rows.append({
            "ref_id": str(d["_id"]),
            "url": d.get("url", ""),
            "press": d.get("press", ""),
            "published_at": pub,
            "title": title,
            "body": body,
            "title_len": len(title),
            "body_len": len(body),
        })
    if not rows:
        print("no rows after quality filter")
        return

    keep_idx = tfidf_title_dedup([r["title"] for r in rows], threshold=0.95)
    rows = [rows[i] for i in keep_idx]

    kiwi = Kiwi()
    for r in rows:
        tokens = kiwi_tokenize(kiwi, f'{r["title"]} {r["body"]}')
        r["tokens"] = tokens

    corpus = [" ".join(r["tokens"]) for r in rows]
    tfidf = TfidfVectorizer(
        tokenizer=identity_tokenizer,
        preprocessor=None,
        lowercase=False,
        ngram_range=(1,2),
        min_df=2,
        token_pattern=None
    )
    X_tfidf = tfidf.fit_transform(corpus)

    model = SentenceTransformer(SBERT_MODEL)
    texts_for_embed = [f'{r["title"]} [SEP] {r["body"][:1000]}' for r in rows]
    embs = np.zeros((len(rows), model.get_sentence_embedding_dimension()), dtype=np.float32)
    idx = 0
    for batch in batched(texts_for_embed, batch_size=64):
        E = model.encode(batch, batch_size=64, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        embs[idx:idx+len(E)] = E.astype(np.float32)
        idx += len(E)

    from sklearn.preprocessing import normalize
    X_tfidf = normalize(X_tfidf, norm="l2", copy=False)

    from sklearn.decomposition import TruncatedSVD
    svd = TruncatedSVD(n_components=min(256, X_tfidf.shape[1]-1) if X_tfidf.shape[1] > 1 else 1, random_state=42)
    X_tfidf_svd = svd.fit_transform(X_tfidf).astype(np.float32)

    combo = np.concatenate([LAMBDA*X_tfidf_svd, (1.0-LAMBDA)*embs], axis=1).astype(np.float32)

    upserts = 0
    for i, r in enumerate(rows):
        doc = {
            "ref_id": r["ref_id"],
            "url": r["url"],
            "press": r["press"],
            "published_at": r["published_at"],
            "title_clean": r["title"],
            "body_clean": r["body"],
            "tokens": r["tokens"],
            "lens": {"title": r["title_len"], "body": r["body_len"]},
            "emb_sbert_f32": embs[i].tolist(),
            "vec_tfidf_svd_f32": X_tfidf_svd[i].tolist(),
            "vec_combo_f32": combo[i].tolist(),
            "lambda": LAMBDA,
            "model": {"sbert": SBERT_MODEL, "svd_components": int(X_tfidf_svd.shape[1])},
            "updated_at": datetime.now(tz=KST),
        }
        dst.update_one({"ref_id": r["ref_id"]}, {"$set": doc}, upsert=True)
        upserts += 1

    import joblib
    joblib.dump(tfidf, MODELS_DIR / "tfidf_vectorizer.joblib")
    joblib.dump(svd,   MODELS_DIR / "svd_256.joblib")

    print(json.dumps({
        "processed": len(rows),
        "upserts": upserts,
        "since": since.isoformat(),
        "dst_collection": PREP_COL,
        "tfidf_vocab": int(len(tfidf.vocabulary_)),
        "svd_components": int(X_tfidf_svd.shape[1]),
        "sbert_dim": int(embs.shape[1]),
    }, ensure_ascii=False))
    client.close()

if __name__ == "__main__":
    mode = os.getenv("RUN_MODE", "once")  # once | schedule
    if mode == "once":
        run_pipeline()
    else:
        sched = BlockingScheduler(timezone=KST)
        sched.add_job(
            func=run_pipeline,
            trigger="cron",
            hour=7,
            minute=0,
            next_run_time=datetime.now(tz=KST)
        )
        sched.start()