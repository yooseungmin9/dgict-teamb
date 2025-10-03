# main.py  (핵심만 발췌) — 올바른 라우터 임포트/등록
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pathlib

from senti_chart import router as senti_router           # 기존 감성 라우터
from keywords import keywords_router as kw_router        # ← 파일명이 keywords.py 임

app = FastAPI(title="Dashboard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

BASE_DIR   = pathlib.Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(STATIC_DIR))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ✅ 라우터 합치기
app.include_router(senti_router)
app.include_router(kw_router)

# [간단 테스트]
# /sentiment/line, /keywords/top 가 200 이어야 함