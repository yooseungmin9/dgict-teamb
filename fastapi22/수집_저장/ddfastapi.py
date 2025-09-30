# dd_api.py
from fastapi import FastAPI
from pymongo import MongoClient
from konlpy.tag import Okt
import pandas as pd
from datetime import datetime, timedelta

app = FastAPI()

@app.get("/keywords")
def keywords():
    # MongoDB 연결
    client = MongoClient("mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/?retryWrites=true&w=majority")
    db = client["test123"]
    col = db["sungjin_articles"]

    today = datetime.now()
    week_ago = today - timedelta(days=7)

    # 모든 데이터 불러오기
    docs = list(col.find())

    # 문자열 saved_at → datetime 변환 + 최근 7일 필터링
    valid_docs = []
    for d in docs:
        try:
            saved_at = pd.to_datetime(d.get("saved_at"))
            if saved_at >= week_ago:
                d["saved_at"] = saved_at
                valid_docs.append(d)
        except Exception:
            continue

    # 형태소 분석
    okt = Okt()
    stopwords = ["기자", "뉴스", "사진", "오늘", "정부"]

    records = []
    for d in valid_docs:
        content = d.get("content", "")
        date = d["saved_at"].date()
        nouns = [w for w in okt.nouns(content) if w not in stopwords and len(w) > 1]
        for n in nouns:
            records.append({"date": str(date), "keyword": n})

    df = pd.DataFrame(records)

    # 데이터 없으면 빈 JSON 반환
    if df.empty:
        return {"dates": [], "keywords": {}}

    # 상위 키워드 5개
    top_keywords = df["keyword"].value_counts().nlargest(5).index.tolist()

    # 피벗 테이블
    pivot = pd.pivot_table(
        df[df["keyword"].isin(top_keywords)],
        index="date",
        columns="keyword",
        aggfunc=len,
        fill_value=0
    )

    # JSON 응답
    return {
        "dates": pivot.index.astype(str).tolist(),
        "keywords": {col: pivot[col].tolist() for col in pivot.columns}
    }
