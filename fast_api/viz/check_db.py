from pymongo import MongoClient
from dotenv import load_dotenv
import os, pprint

load_dotenv()
cli = MongoClient(os.getenv("MONGO_URI"))
db  = cli[os.getenv("MONGO_DB", "test123")]

def show(name, proj):
    col = db[name]
    print(f"\n[{name}] count =", col.count_documents({}))
    doc = col.find_one({}, proj)
    if doc:
        pprint.pp(doc)
    else:
        print("(no documents)")

show(os.getenv("MONGO_COL_CLU", "clusters"),
     {"_id":0, "cluster_id":1, "size":1, "count":1, "label_gpt":1, "article_ids":{"$slice":3}})

show(os.getenv("MONGO_COL_TREND", "trends_daily"),
     {"_id":0, "date":1, "keyword":1, "count":1, "group":1})

show(os.getenv("MONGO_COL_BURST", "burst_keywords"),
     {"_id":0, "date":1, "keyword":1, "score":1, "count":1})