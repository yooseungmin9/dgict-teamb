from __future__ import annotations
from fastapi22 import FastAPI, Query
from fastapi22.middleware.cors import CORSMiddleware
from fastapi22.staticfiles import StaticFiles
from fastapi22.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from pathlib import Path
from . import crawler_news, crawler_blog, analyzer

app = FastAPI(title="경제 수집·분석")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = Path(__file__).resolve().parent.parent
PUBLIC = BASE / "public"
app.mount("/static", StaticFiles(directory=str(PUBLIC), html=True), name="static")

sched = BackgroundScheduler(timezone="Asia/Seoul")
sched.start()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/run/news")
def run_news(pages: int = Query(1, ge=1, le=5)):
    n = crawler_news.run(pages=pages)
    return {"upserted": n}

@app.get("/run/blog")
def run_blog(q: str = Query("경제"), display: int = Query(30, ge=1, le=100)):
    n = crawler_blog.run(q=q, display=display)
    return {"upserted": n}

@app.get("/trends")
def trends(days: int = Query(7, ge=1, le=90), topk: int = Query(50, ge=5, le=200)):
    top = analyzer.top_keywords(days=days, topk=topk)
    img_path = str(PUBLIC / "wordcloud.png")
    analyzer.make_wordcloud(img_path, days=days, topk=200)
    return JSONResponse({"days": days, "top": top, "wordcloud": "/static/wordcloud.png"})

# 스케줄: 매시 10분 뉴스, 15분 블로그, 20분 워드클라우드
@sched.scheduled_job("cron", minute="10")
def _job_news():
    try: crawler_news.run(pages=1)
    except Exception: pass

@sched.scheduled_job("cron", minute="15")
def _job_blog():
    try: crawler_blog.run(q="경제", display=30)
    except Exception: pass

@sched.scheduled_job("cron", minute="20")
def _job_wc():
    try: analyzer.make_wordcloud(str(PUBLIC / "wordcloud.png"), days=7, topk=200)
    except Exception: pass
