from pymongo import MongoClient
import matplotlib.pyplot as plt
import matplotlib as mpl
import platform
import os

SAVE_DIR = os.path.dirname(__file__)

MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
MONGO_DB = "test123"
MONGO_COL_REPRINT = "reprints"
MONGO_COL_PREP = "articles_preprocessed"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# 한글 폰트 설정
if platform.system() == "Windows":
    mpl.rc("font", family="Malgun Gothic")
else:
    mpl.rc("font", family="AppleGothic")
plt.rcParams["axes.unicode_minus"] = False

# 전체/재보도 건수
total = db[MONGO_COL_PREP].count_documents({})
reprints = db[MONGO_COL_REPRINT].count_documents({})

# Pie
plt.figure(figsize=(4,4))
plt.pie([reprints, max(total - reprints, 0)],
        labels=["재보도", "단독보도"], autopct="%.1f%%", startangle=90,
        colors=["#f77", "#aaf"])
plt.title("전체 대비 재보도 비율")
plt.tight_layout()
plt.savefig(os.path.join(SAVE_DIR, "reprint_ratio.png"))

# Bar
pipeline = [
    {"$group": {"_id": "$press", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
]
data = list(db[MONGO_COL_REPRINT].aggregate(pipeline))
press = [str(d["_id"] or "미상") for d in data]
counts = [int(d["count"]) for d in data]

plt.figure(figsize=(8,4))
plt.bar(list(press), list(counts), color="#69c")
plt.title("언론사별 재보도 건수")
plt.xlabel("언론사")
plt.ylabel("건수")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig(os.path.join(SAVE_DIR, "reprint_by_press.png"))

print("완료: reprint_ratio.png, reprint_by_press.png 생성됨.")