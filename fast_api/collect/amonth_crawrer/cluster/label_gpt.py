from openai import OpenAI
import os
from pymongo import MongoClient, ASCENDING, UpdateOne
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(filename=".env", usecwd=True))
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB", "test123")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def label_with_gpt(result):
    client = OpenAI(api_key=OPENAI_API_KEY)

    for r in result:
        context = "\n".join(r["titles"])
        prompt = (
            f"다음 기사 제목들은 같은 이슈를 다룹니다:\n{context}\n\n"
            "요약 후 3~6단어로 대표 이슈명을 만들어줘."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        r["label"] = resp.choices[0].message.content.strip()
        r["cluster_label"] = r["label"]
    # Mongo 저장: upsert
    coll = MongoClient(MONGO_URI)[DB_NAME]["clusters"]
    coll.create_index([("cluster", ASCENDING)], unique=True, name="cluster_uidx")
    ops = [UpdateOne({"cluster": r["cluster"]}, {"$set": r}, upsert=True) for r in result]
    coll.bulk_write(ops)