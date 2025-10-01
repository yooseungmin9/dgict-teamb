# api/main.py
# [입문자용] 라우터 경로 정리: /api/sentiment, /api/trends/**

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import sentiment, trends  # routers/__init__.py 필요

app = FastAPI(title="EcoNews API", version="1.0.0")

# CORS (개발용: 전체 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 배포 시 특정 도메인으로 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✔ 라우터 등록
# sentiment 라우터 내부가 @router.get("/sentiment") 이므로 prefix는 "/api"로
app.include_router(sentiment.router, prefix="/api", tags=["Sentiment"])

# trends 라우터는 "/category-trends", "/keyword-ranking" 이므로 "/api/trends"로
app.include_router(trends.router, prefix="/api/trends", tags=["Trends"])

@app.get("/health")
def health():
    return {"ok": True, "service": "EcoNews API"}