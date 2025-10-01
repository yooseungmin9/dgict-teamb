# backfill_keywords_clean.py
import re, math, argparse
from pymongo import MongoClient, UpdateOne
from konlpy.tag import Okt

okt = Okt()

MONGODB_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME = "test123"
COLLECTION = "shared_articles"

# 아주 자주 튀는 불용어 (원하는대로 추가/수정)
STOPWORDS = {
    # 조사/어미/접속
    "은","는","이","가","을","를","에","에서","으로","로","과","와","의","도","만","보다","까지","에게","한테","부터","라도",
    "하다","했다","하며","하며","했다","했다며","밝혔다","밝혀","통해","대한","대해","있다","있어","있는","있네","됐다","된다","되어",
    "것","수","등","및","중","또","또한","이번","최근","지난","오늘","내일","모두","각","해","더","가장","만에","까지",
    # 미디어/관용
    "기자","사진","무단","전재","배포","금지","연합뉴스","뉴스","속보","제공","네이버",
    "위해", "올해", "운영", "기사", "추가", "동영상", "경우", "계획", "kbs",
    "예정", "이후", "대상",
}
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")

def normalize_token(t: str) -> str:
    t = t.strip().lower()
    return t

def extract_keywords(text: str):
    # 1) 형태소 분석
    pos = okt.pos(text, norm=True, stem=True)
    # 2) 명사(일반/고유), 외래어 위주로 추출
    cand = [w for (w, p) in pos if p in ("Noun", "Alpha")]
    # 3) 정규식/길이/불용어 필터
    tokens = []
    for w in cand:
        w = normalize_token(w)
        if not TOKEN_RE.fullmatch(w):
            continue
        if len(w) < 2:
            continue
        if w in STOPWORDS:
            continue
        tokens.append(w)
    # 4) 과도한 중복 방지(원문 한 건 내에서 중복 제거)
    uniq = []
    seen = set()
    for t in tokens:
        if t not in seen:
            uniq.append(t); seen.add(t)
    return uniq

def backfill(batch_size=500, clear_first=False):
    client = MongoClient(MONGODB_URI)
    col = client[DB_NAME][COLLECTION]

    if clear_first:
        r = col.update_many({}, {"$unset": {"keywords": ""}})
        print(f"cleared keywords: modified={r.modified_count}")

    total = col.count_documents({})
    pages = math.ceil(total / batch_size)
    print(f"total={total}, batches={pages}")

    for i in range(pages):
        cursor = col.find({}, {"_id": 1, "title": 1, "content": 1}).skip(i*batch_size).limit(batch_size)
        ops = []
        for doc in cursor:
            text = f"{doc.get('title','')} {doc.get('content','')}".strip()
            if not text:
                continue
            kws = extract_keywords(text)
            ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"keywords": kws}}))
        if ops:
            col.bulk_write(ops)
        print(f"batch {i+1}/{pages} updated={len(ops)}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear-first", action="store_true", help="기존 keywords 필드 삭제 후 재생성")
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()
    backfill(batch_size=args.batch, clear_first=args.clear_first)
    print("✅ done.")
