from pymongo import MongoClient
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB", "test123")
COL_PREP  = os.getenv("MONGO_COL_PREP", "articles_preprocessed")

def load_articles():
    coll = MongoClient(MONGO_URI)[DB_NAME][COL_PREP]
    cur = coll.find(
        {"emb_sbert_f32": {"$exists": True}},   # ← 필수 필드
        {
            "_id": 1,
            "title_clean": 1,
            "tokens": 1,
            "emb_sbert_f32": 1,                 # ← SBERT
            "published_at": 1,
            "press": 1
        }
    )
    df = pd.DataFrame(list(cur))
    # 파이프라인 내부에서 쓰는 표준 컬럼명으로 맞춤
    df = df.rename(columns={"emb_sbert_f32":"sbert_vec", "title_clean":"title"})
    return df