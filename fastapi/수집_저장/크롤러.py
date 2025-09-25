
"""
네이버 경제 뉴스 다건 크롤러 (페이지 순회 방식)
pip install requests beautifulsoup4 pymongo
"""

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, errors
from datetime import datetime
import json


def fetch_economic_news(limit: int = 50, date: str = None):
    """네이버 경제 뉴스에서 여러 페이지 순회하여 기사 가져오기
    Parameters
    ----------
    limit : int
        가져올 최대 기사 수
    date : str, optional
        YYYYMMDD 형식 (기본값: 오늘)
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    headers = {"User-Agent": "Mozilla/5.0"}
    articles = []
    page = 1

    while len(articles) < limit:
        url = (
            f"https://news.naver.com/main/list.naver"
            f"?mode=LSD&mid=shm&sid1=101&date={date}&page={page}"
        )
        res = requests.get(url, headers=headers)
        res.raise_for_status()

        soup = BeautifulSoup(res.text, "html.parser")
        links = [
            a for a in soup.select("ul.type06_headline li dt a")
            if "/article/" in a["href"]
        ]
        if not links:  # 더 이상 기사가 없으면 종료
            break

        for a in links:
            link = a["href"]
            title = a.get_text(strip=True)
            try:
                art_res = requests.get(link, headers=headers)
                art_res.raise_for_status()
                art_soup = BeautifulSoup(art_res.text, "html.parser")
                content = art_soup.select_one("article#dic_area")
                content = content.get_text(" ", strip=True) if content else "본문 추출 실패"
            except Exception as e:
                content = f"본문 에러: {e}"

            articles.append({
                "title": title,
                "link": link,
                "content": content,
                "saved_at": datetime.now().isoformat()
            })
            if len(articles) >= limit:
                break
        page += 1

    return articles


def save_to_mongo_or_json(docs: list):
    """MongoDB 저장 시도 → 실패하면 JSON 저장"""
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        client.server_info()  # 연결 확인
        db = client["newsdb"]
        col = db["articles"]

        for doc in docs:
            result = col.update_one({"link": doc["link"]}, {"$set": doc}, upsert=True)
            if result.upserted_id:
                print("🆕 MongoDB 새로 저장:", doc["title"])
            elif result.modified_count > 0:
                print("✏️ MongoDB 업데이트:", doc["title"])
            else:
                print("⚠ 동일 데이터 있음:", doc["title"])
    except errors.ServerSelectionTimeoutError:
        print("⚠ MongoDB 실행 안됨 → JSON 저장합니다.")
        with open("news.json", "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        print("✅ news.json 저장 완료.")


if __name__ == "__main__":
    news_list = fetch_economic_news(limit=50)
    print("가져온 기사 개수:", len(news_list))
    for n in news_list:
        print(f"[{n['title']}] {n['link']}")
    save_to_mongo_or_json(news_list)
