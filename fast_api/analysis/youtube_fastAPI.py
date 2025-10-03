# app.py
from fastapi import FastAPI
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware

# ------------------
# FastAPI 초기화
# ------------------
app = FastAPI()

# CORS 허용 (프론트에서 fetch 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 배포시 도메인 지정 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------
# MongoDB 연결
# ------------------
MONGO_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["test123"]
col = db["youtube_db2"]


# ------------------
# API 라우트
# ------------------

@app.get("/videos")
def get_videos():
    """유튜브 영상 리스트 반환"""
    docs = col.find({}, {"video_id": 1, "title": 1, "thumbnail_url": 1, "_id": 0})
    return [
        {
            "video_id": d["video_id"],
            "title": d["title"],
            "thumbnail": d.get("thumbnail_url", "")
        }
        for d in docs
    ]


@app.get("/videos/{video_id}")
def get_video_detail(video_id: str):
    """특정 영상 메타정보 반환"""
    doc = col.find_one({"video_id": video_id})
    if not doc:
        return {"error": "Video not found"}

    return {
        "video_id": doc["video_id"],
        "title": doc["title"],
        "category": doc.get("category", ""),
        "published_at": doc["published_at"],
        "views": doc.get("view_count", 0),
        "comments": doc.get("comment_count", 0),
        "thumbnail": doc.get("thumbnail_url", ""),
        "video_url": f"https://www.youtube.com/embed/{doc['video_id']}"
    }


@app.get("/analysis/{video_id}")
def get_analysis(video_id: str):
    """특정 영상 댓글 기반 분석 결과 반환"""
    doc = col.find_one({"video_id": video_id})
    if not doc:
        return {"error": "Video not found"}

    # 감정 카운트
    sentiment_count = {"기쁨": 0, "슬픔": 0, "분노": 0, "놀람": 0}
    word_freq = {}
    sample_comments = []

    for c in doc.get("comments", []):
        emo = c.get("emotion", "")
        if "Joy" in emo or "기쁨" in emo: sentiment_count["기쁨"] += 1
        if "Sadness" in emo or "슬픔" in emo: sentiment_count["슬픔"] += 1
        if "Anger" in emo or "분노" in emo: sentiment_count["분노"] += 1
        if "Surprise" in emo or "놀람" in emo: sentiment_count["놀람"] += 1

        # 워드클라우드 단어 빈도
        for w in c["text"].split():
            word_freq[w] = word_freq.get(w, 0) + 1

        # 대표 댓글 샘플 3개만
        if len(sample_comments) < 3:
            sample_comments.append({"text": c["text"], "emotion": c.get("emotion", "")})

    return {
        "video_id": doc["video_id"],
        "sentiment": sentiment_count,
        "wordcloud": [{"text": k, "count": v} for k, v in word_freq.items()],
        "summary": f"이 영상 댓글 중 기쁨이 {sentiment_count['기쁨']}건으로 가장 많음",
        "comments": sample_comments
    }
