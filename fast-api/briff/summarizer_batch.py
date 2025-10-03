# summarizer_batch.py — MongoDB의 content를 요약하여 summary로 저장 (배치 전용)
# 실행 예시:
#   pip install "transformers==4.44.2" "torch>=2.2.0" "pymongo==4.10.1"
#   python summarizer_batch.py --limit 20
#   python summarizer_batch.py --only-empty true --limit 50
#
# [입문자용 설명]
# - Atlas(test123.news)에서 요약이 비었거나 없는 문서만 골라 content → 요약 → summary 저장
# - 웹사이트는 이 결과를 /news(API)로 읽어서 카드로 표시함(요약 생성은 웹에서 하지 않음)

import argparse
from typing import List, Dict, Any
from pymongo import MongoClient
from transformers import pipeline

# ====== Atlas 고정 환경값(요청대로 상수) ======
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
DB_NAME   = "test123"
COLL_NAME = "news"

# ====== 요약 모델/하이퍼파라미터 ======
MODEL_ID   = "EbanLee/kobart-summary-v3"  # 요청 모델
DEVICE     = -1   # CPU 기본(-1), CUDA면 0 (맥 MPS는 한글 BART계 이슈 가능 → CPU 권장)
BATCH_SIZE = 4
MAX_LEN    = 400
MIN_LEN    = 50
NUM_BEAMS  = 6
DO_SAMPLE  = False

# 전처리: 너무 긴 본문 컷(문자수)
PRE_CUT = 1500

def preprocess_txt(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\t", " ").strip()
    if len(text) > PRE_CUT:
        text = text[:PRE_CUT]
    return text

def build_summarizer():
    return pipeline(
        "summarization",
        model=MODEL_ID,
        tokenizer=MODEL_ID,
        device=DEVICE,
        batch_size=BATCH_SIZE,
    )

def fetch_candidates(coll, only_empty: bool, limit: int) -> List[Dict[str, Any]]:
    """
    only_empty=True  -> summary 없거나 공백인 문서만
    only_empty=False -> content가 있고 summary가 비었거나(또는 오래된) 문서 위주로(여기선 동일 조건)
    """
    query = {
        "$and": [
            {"content": {"$exists": True, "$type": "string", "$ne": ""}},
            {"$or": [
                {"summary": {"$exists": False}},
                {"summary": ""},
                {"summary": " "}
            ]}
        ]
    } if only_empty else {
        "$and": [
            {"content": {"$exists": True, "$type": "string", "$ne": ""}},
            {"$or": [
                {"summary": {"$exists": False}},
                {"summary": ""},
                {"summary": " "}
            ]}
        ]
    }
    # projection은 content만 필수. title/url은 그대로 보존.
    cur = coll.find(query, {"content": 1}).sort("_id", -1).limit(limit)
    return list(cur)

def summarize_text(summarizer, text: str) -> str:
    clean = preprocess_txt(text)
    if not clean:
        return ""
    out = summarizer(
        clean,
        max_length=MAX_LEN,
        min_length=MIN_LEN,
        num_beams=NUM_BEAMS,
        do_sample=DO_SAMPLE,
    )[0]["summary_text"]
    return out.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, help="최대 처리 건수(1~N)")
    parser.add_argument("--only-empty", type=str, default="true",
                        help="요약 없는 문서만 처리(true/false, 기본 true)")
    args = parser.parse_args()

    only_empty = str(args.only_empty).lower() in ("1", "true", "yes", "y")
    limit = max(1, int(args.limit))

    client = MongoClient(MONGO_URI)
    coll = client[DB_NAME][COLL_NAME]

    # 연결 확인
    client.admin.command("ping")

    # 모델 1회 로딩
    summarizer = build_summarizer()

    # 후보 문서 조회
    candidates = fetch_candidates(coll, only_empty=only_empty, limit=limit)
    if not candidates:
        print("[info] 처리할 문서가 없습니다.")
        return

    updated = 0
    for doc in candidates:
        _id = doc["_id"]
        content = doc.get("content", "")
        try:
            sm = summarize_text(summarizer, content)
            if not sm:
                print(f"[warn] {_id} 요약 결과가 비어 건너뜀")
                continue
            res = coll.update_one({"_id": _id}, {"$set": {"summary": sm}})
            if res.modified_count == 1:
                updated += 1
                print(f"[ok] {_id} 요약 저장 완료 (길이={len(sm)})")
            else:
                print(f"[skip] {_id} 변경 없음")
        except Exception as e:
            print(f"[err] {_id} 요약 실패: {e}")

    print(f"[done] 총 {len(candidates)}건 중 {updated}건 업데이트")

if __name__ == "__main__":
    main()