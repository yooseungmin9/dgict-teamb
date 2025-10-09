from __future__ import annotations
import os, math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
from collections import defaultdict, Counter

from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

TZ = timezone(timedelta(hours=9))
MONGO_URI   = os.getenv("MONGO_URI", "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
DB_NAME     = os.getenv("MONGO_DB",  "test123")
COL_PREP    = os.getenv("MONGO_COL_PREP", "articles_preprocessed")  # 표준명
COL_OUT     = os.getenv("MONGO_COL_REPRINT", "reprints")
TOP_N       = int(os.getenv("REPRINT_TOP_N", "10"))
STRICT      = os.getenv("REPRINT_STRICT", "0") == "1"
THRESH      = 0.90 if STRICT else 0.88
WINDOW_H    = int(os.getenv("REPRINT_WINDOW_H", "72"))

# ====== 유틸 ======
def _dt(x) -> datetime:
    # 문자열/Datetime 모두 허용
    if isinstance(x, datetime):
        return x.astimezone(TZ)
    return datetime.fromisoformat(str(x).replace("Z","+09:00")).astimezone(TZ)

class UF:
    def __init__(self, n: int):
        self.p = list(range(n))
        self.r = [0]*n
    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a: int, b: int):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return
        if self.r[ra] < self.r[rb]: ra, rb = rb, ra
        self.p[rb] = ra
        if self.r[ra] == self.r[rb]: self.r[ra] += 1

def _norm_rows(mat: List[List[float]]) -> List[List[float]]:
    out = []
    for v in mat:
        s = math.sqrt(sum(x*x for x in v)) or 1.0
        out.append([x/s for x in v])
    return out

def _cos_from_ip(ip: float) -> float:
    # 노멀라이즈 후 inner product == cosine
    return ip

def _load_docs():
    cli = MongoClient(MONGO_URI)
    db  = cli[DB_NAME]
    coll = db[COL_PREP]

    cur = coll.find(
        {},  # 필터는 로컬에서 걸러냄
        {
            "_id":1, "url":1, "title":1, "title_clean":1,
            "press":1, "model.press":1, "media":1, "source":1,
            "published_at":1,
            "sbert":1, "emb_sbert_f32":1, "embedding":1, "vec":1
        }
    ).sort([("published_at", ASCENDING)])

    docs = []
    for d in cur:
        v = d.get("sbert") or d.get("emb_sbert_f32") or d.get("embedding") or d.get("vec")
        t = d.get("published_at")
        if not isinstance(v, list) or not t:
            continue
        d["sbert"] = v
        d["published_at"] = _dt(t)
        d["media"] = d.get("media") or d.get("press") or (d.get("model", {}) or {}).get("press") or d.get("source") or "unknown"
        d["title"] = d.get("title") or d.get("title_clean") or ""
        docs.append(d)

    return docs, db

# ====== 인덱스 구성 (FAISS 우선) ======
def _build_index(vecs: List[List[float]]):
    if not vecs or not vecs[0]:
        return ("none", None)
    dim = len(vecs[0]) if vecs else 0
    use_annoy = False
    try:
        import faiss  # type: ignore
        xb = _norm_rows(vecs)
        import numpy as np
        xb_np = np.asarray(xb, dtype="float32")
        index = faiss.IndexFlatIP(dim)
        index.add(xb_np)
        return ("faiss", index)
    except Exception:
        use_annoy = True

    if use_annoy:
        from annoy import AnnoyIndex  # type: ignore
        idx = AnnoyIndex(dim, "angular")  # angular ~ cosine
        for i, v in enumerate(vecs):
            idx.add_item(i, v)
        idx.build(50)
        return ("annoy", idx)

# ====== 근접 탐색 ======
def _search_neighbors(engine, index, vecs, k: int = 50):
    if engine == "faiss":
        import numpy as np
        import faiss  # type: ignore
        X = np.asarray(_norm_rows(vecs), dtype="float32")
        D, I = index.search(X, k)  # inner product == cosine
        # 반환: 각 i에 대해 (j, sim) 리스트
        res = []
        for i in range(len(vecs)):
            pairs = []
            for j, ip in zip(I[i], D[i]):
                if j == -1 or j == i:
                    continue
                pairs.append((j, float(_cos_from_ip(ip))))
            res.append(pairs)
        return res
    else:
        # annoy
        res = []
        for i, v in enumerate(vecs):
            nn = index.get_nns_by_item(i, k, include_distances=True)
            ids, dists = nn
            pairs = []
            for j, dist in zip(ids, dists):
                if j == i:
                    continue
                # angular 거리 → cosine 근사
                # angular dist d ≈ 2*(1 - cos), → cos ≈ 1 - d/2
                cos = 1.0 - (float(dist)/2.0)
                pairs.append((j, cos))
            res.append(pairs)
        return res

# ====== 그래프 생성 (시간 윈도우 + 임계값) ======
def _build_graph(docs, neighbors):
    n = len(docs)
    uf = UF(n)
    need_gpt: List[Tuple[int,int,float]] = []

    for i in range(n):
        ti = docs[i]["published_at"]
        for j, sim in neighbors[i]:
            tj = docs[j]["published_at"]
            # 최초보도 기준 ±72h 규칙:
            t0 = min(ti, tj)
            ok_time = (max(ti, tj) - t0) <= timedelta(hours=WINDOW_H)
            if not ok_time:
                continue
            if sim >= THRESH:
                uf.union(i, j)
            elif 0.86 <= sim < THRESH:
                need_gpt.append((i, j, sim))

    # 컴포넌트 별 모음
    groups = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    # 단일 노드(사건 아님) 제외
    events = [sorted(ids, key=lambda x: docs[x]["published_at"]) for ids in groups.values() if len(ids) > 1]
    return events, need_gpt

# ====== 지표 계산 ======
def _event_stats(event_ids: List[int], docs) -> Dict[str, Any]:
    arts = [docs[i] for i in event_ids]
    arts_sorted = sorted(arts, key=lambda d: d["published_at"])
    first = arts_sorted[0]
    delays_h = [(a["published_at"] - first["published_at"]).total_seconds()/3600.0 for a in arts_sorted[1:]]
    media_set = {a["media"] for a in arts_sorted}
    media_counts = Counter([a["media"] for a in arts_sorted])
    return {
        "size": len(arts_sorted),
        "first_article_id": str(first["_id"]),
        "first_media": first["media"],
        "first_published_at": first["published_at"].isoformat(),
        "avg_delay_h": (sum(delays_h)/len(delays_h)) if delays_h else 0.0,
        "media_diversity": len(media_set),
        "media_counts": dict(media_counts),
        "article_ids": [str(a["_id"]) for a in arts_sorted],
        "titles_sample": [a["title"] for a in arts_sorted[:3]],
    }

def _global_metrics(events, total_docs, docs):
    reprint_articles = sum(len(e)-1 for e in events)
    first_media = Counter(docs[e[0]]["media"] for e in events if e)
    follower_media = Counter(docs[i]["media"] for e in events for i in e[1:])
    return {
        "reprint_rate": reprint_articles / max(total_docs, 1),
        "events": len(events),
        "first_media_top": first_media.most_common(10),
        "follower_media_top": follower_media.most_common(10),
    }

# ====== 저장 ======
def _save(db, events_stats, global_stats, need_gpt_pairs, docs):
    out = db[COL_OUT]
    out.create_index([("created_at", DESCENDING)], name="created_at_desc")
    now = datetime.now(tz=TZ)

    doc = {
        "created_at": now,
        "threshold": THRESH,
        "window_h": WINDOW_H,
        "event_count": len(events_stats),
        "global": global_stats,
        "top_events": events_stats[:TOP_N],
        "need_gpt_pairs": [
            {
                "a_id": str(docs[i]["_id"]),
                "b_id": str(docs[j]["_id"]),
                "sim": round(sim, 4),
                "a_title": docs[i]["title"],
                "b_title": docs[j]["title"],
            } for (i,j,sim) in need_gpt_pairs
        ],
    }
    out.insert_one(doc)
    return doc["_id"]

def main():
    print(f"[reprint] cfg: THRESH={THRESH} WINDOW_H={WINDOW_H} TOP_N={TOP_N} COL_PREP={COL_PREP} COL_OUT={COL_OUT}")
    docs, db = _load_docs()
    if not docs:
        print("[reprint] no docs")
        return

    vecs = [d["sbert"] for d in docs]
    engine, index = _build_index(vecs)
    if engine == "none":
        print("[reprint] no embeddings");
        return
    neighbors = _search_neighbors(engine, index, vecs, k=50)

    events, need_gpt = _build_graph(docs, neighbors)
    # 사건 크기 기준 정렬
    events = sorted(events, key=lambda ids: len(ids), reverse=True)

    events_stats = [_event_stats(ids, docs) for ids in events]
    global_stats = _global_metrics(events, len(docs), docs)

    _id = _save(db, events_stats, global_stats, need_gpt, docs)

    # 콘솔 요약
    print(f"[reprint] events={len(events)} reprint_rate={global_stats['reprint_rate']:.3f} saved_id={_id}")
    print("[reprint] Top events:")
    for e in events_stats[:TOP_N]:
        print(f"  size={e['size']:>2} avg_delay_h={e['avg_delay_h']:.1f} media_div={e['media_diversity']} first={e['first_media']} {e['first_published_at']}")
        for t in e["titles_sample"]:
            print("    -", t)

    if need_gpt:
        # GPT 확인 대상: 임계값 근접쌍(0.86~THRESH 미만)
        print(f"[reprint] near-threshold pairs for GPT check: {len(need_gpt)}")

if __name__ == "__main__":
    main()
