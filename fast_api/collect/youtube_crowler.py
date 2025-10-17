# -*- coding: utf-8 -*-
"""
유튜브 API + 댓글 + 다중 감정분석(7클래스, 배치 처리) → MongoDB 실시간 저장
"""

from googleapiclient.discovery import build
from pymongo import MongoClient
import googleapiclient.errors
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch
import os
from dotenv import load_dotenv
from difflib import SequenceMatcher

# 1. API & DB 설정
load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

youtube = build("youtube", "v3", developerKey=API_KEY, static_discovery=False)
client = MongoClient(MONGO_URI)
db = client["test123"]
col = db["youtube_db2"]

# 2. 한국어 감정 분석 모델 로드
MODEL_NAME = "dlckdfuf141/korean-emotion-kluebert-v2"

id2label = {
    0: "공포(Fear)",
    1: "놀람(Surprise)",
    2: "분노(Anger)",
    3: "슬픔(Sadness)",
    4: "중립(Neutral)",
    5: "행복(Happiness)",
    6: "혐오(Disgust)"
}
label2id = {v: k for k, v in id2label.items()}

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=7,
    id2label=id2label,
    label2id=label2id
)

emotion_classifier = pipeline(
    "text-classification",
    model=model,
    tokenizer=tokenizer,
    top_k=None,
    batch_size=32,
    device=0 if torch.cuda.is_available() else -1
)

# 3. 배치 감정 분석 함수
def classify_emotions_batch(texts):
    """여러 댓글을 한 번에 감정 분류"""
    preds = emotion_classifier(texts, truncation=True, max_length=256)
    results = []
    for pred in preds:
        scores = {p["label"]: float(p["score"]) for p in pred}
        best = max(scores, key=scores.get)
        results.append({"label": best, "scores": scores})
    return results

# 4. 영상 정보
def get_video_info(video_id: str, category: str):
    request = youtube.videos().list(part="snippet,statistics", id=video_id)
    response = request.execute()
    if not response["items"]:
        return None

    item = response["items"][0]
    snippet = item["snippet"]
    stats = item["statistics"]

    return {
        "video_id": video_id,
        "category": category,
        "title": snippet["title"],
        "published_at": snippet["publishedAt"],
        "view_count": int(stats.get("viewCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "thumbnail_url": snippet["thumbnails"]["medium"]["url"],
    }

# 5. 댓글 수집 + 배치 감정 분석
def get_video_comments(video_id: str, max_total: int = 1000):
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_total:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat="plainText"
            )
            response = request.execute()

            batch_texts = []
            raw_items = []

            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                text = snippet.get("textDisplay", "")
                batch_texts.append(text)
                raw_items.append(snippet)

                if len(comments) + len(batch_texts) >= max_total:
                    break

            if batch_texts:
                emotions = classify_emotions_batch(batch_texts)
                for snip, emo in zip(raw_items, emotions):
                    comments.append({
                        "author": snip.get("authorDisplayName"),
                        "text": snip.get("textDisplay", ""),
                        "published_at": snip.get("publishedAt"),
                        "like_count": snip.get("likeCount", 0),
                        "emotion": emo["label"],
                        "emotion_scores": emo["scores"]
                    })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except googleapiclient.errors.HttpError as e:
        if "commentsDisabled" in str(e):
            print(f"댓글 꺼짐 → 수집 안 함 (video_id={video_id})")
            return None

    return comments

# 6. 메인 수집 (중복·무관 필터링 포함)
def is_similar(a: str, b: str, threshold: float = 0.8) -> bool:
    """문자열 유사도 계산"""
    return SequenceMatcher(None, a, b).ratio() > threshold

def collect_videos_with_emotions(query: str, category: str, target_count: int = 10):
    saved_count = 0
    next_page_token = None
    seen_titles = []

    while saved_count < target_count:
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            order="relevance",
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response["items"]:
            if saved_count >= target_count:
                break

            video_id = item["id"]["videoId"]

            if col.find_one({"video_id": video_id}):
                print(f"중복 영상 → 스킵 ({video_id})")
                continue

            info = get_video_info(video_id, category)
            if not info:
                continue

            title = info["title"].strip()
            desc = item["snippet"].get("description", "")

            if any(is_similar(title, t) for t in seen_titles):
                print(f"유사 제목 → 스킵: {title}")
                continue

            if info["comment_count"] < 20:
                print(f"댓글 {info['comment_count']}개 → 스킵: {title}")
                continue

            comments = get_video_comments(video_id, max_total=1000)
            if not comments:
                continue

            info["comments"] = comments
            col.insert_one(info)
            saved_count += 1
            seen_titles.append(title)
            print(f"저장 완료: {title} ({len(comments)}개 댓글)")

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            print("더 이상 검색 결과 없음")
            break

    print(f"최종 저장된 영상 수: {saved_count}")

# 7. 실행
if __name__ == "__main__":
    query = "산업 뉴스"
    category = "산업"
    collect_videos_with_emotions(query, category, target_count=20)
