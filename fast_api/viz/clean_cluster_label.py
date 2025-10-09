import os, re
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

db = MongoClient(os.getenv("MONGO_URI"))[os.getenv("MONGO_DB","test123")]
COL_CLU = os.getenv("MONGO_COL_CLU","clusters")

PAT = re.compile(r'(?:^|[\s\-\|,;])(?:이슈\s*요약|대표\s*이슈명|이슈명)\s*[:：]?\s*', re.I)

def clean(s):
    if not s: return s
    s = PAT.sub(" ", s)
    s = s.strip().strip('\'"“”‘’')
    s = re.sub(r'\s{2,}', ' ', s)
    return s

fields = ["label_gpt", "cluster_label", "label"]
proj = {f:1 for f in fields}
for d in db[COL_CLU].find({}, proj):
    upd = {}
    for f in fields:
        old = d.get(f)
        new = clean(old)
        if new != old:
            upd[f] = new
    if upd:
        db[COL_CLU].update_one({"_id": d["_id"]}, {"$set": upd})