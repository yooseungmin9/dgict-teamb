# common/config.py
import os
from pymongo import MongoClient
from itertools import islice

# ====== NAVER ======
NAVER_CLIENT_ID = "zltdiHFAdmmvXlRwBuqA"
NAVER_CLIENT_SECRET = "3Y5I7ZkpmP"

# ====== MongoDB ======
mongo_client = MongoClient("mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/")
mongo_col = mongo_client["test123"]["shared_articles"]

# ====== Categories ======
CATEGORIES = ["증권", "금융", "부동산", "산업", "글로벌경제", "일반"]

CATEGORY_KEYWORDS = {
    "증권": ["증권", "주식", "코스피", "코스닥"],
    "금융": ["금융", "예금", "대출", "금리"],
    "부동산": ["부동산", "아파트", "전세", "매매"],
    "산업": ["산업", "제조업", "반도체", "수출"],
    "글로벌경제": ["글로벌 경제", "미국 금리", "중국 경기", "달러"],
    "일반": ["소비", "물가", "경기", "실업률"],
}

# ====== 유틸 ======
def chunked(iterable, size):
    """딕셔너리를 size 개씩 나눔"""
    it = iter(iterable.items())
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield dict(batch)
