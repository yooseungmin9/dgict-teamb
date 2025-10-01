from pymongo import MongoClient
from konlpy.tag import Okt
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import matplotlib as mpl

# 한글 폰트 설정
mpl.rcParams['font.family'] = 'Malgun Gothic'   # 윈도우
mpl.rcParams['axes.unicode_minus'] = False      # 마이너스 부호 깨짐 방지

# MongoDB 연결
client = MongoClient("mongodb://localhost:27017/")
db = client["newsdb"]
col = db["articles"]

# 최근 7일 기사 불러오기
docs = list(col.find().sort("saved_at", -1).limit(50))

# 형태소 분석기
okt = Okt()

# 불용어 (예시)
stopwords = ["기자", "뉴스", "사진", "오늘", "정부"]

# 날짜별 키워드 집계
records = []
for d in docs:
    content = d.get("content", "")
    date = pd.to_datetime(d.get("saved_at")).date()
    nouns = [w for w in okt.nouns(content) if w not in stopwords and len(w) > 1]
    for n in nouns:
        records.append({"date": date, "keyword": n})

df = pd.DataFrame(records)

# 상위 키워드 5개 선정
top_keywords = df["keyword"].value_counts().nlargest(5).index.tolist()

# 피벗 테이블: 날짜별 키워드 빈도
pivot = pd.pivot_table(
    df[df["keyword"].isin(top_keywords)],
    index="date",
    columns="keyword",
    aggfunc=len,
    fill_value=0
)

print(pivot)

# 시각화
pivot.plot(kind="line", marker="o", figsize=(10, 6))
plt.title("주요 키워드 추이")
plt.xlabel("날짜")
plt.ylabel("빈도수")
plt.legend(title="Keyword")
plt.grid(True)
plt.tight_layout()
plt.show()
