from __future__ import annotations
import os, re, time, urllib.parse, json
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from .database import upsert_many

load_dotenv()
CID = os.getenv("NAVER_CLIENT_ID", "")
CSECRET = os.getenv("NAVER_CLIENT_SECRET", "")
UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"}
TIMEOUT = 10

TAG = re.compile(r"<[^>]+>")
def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", s or "")).strip()

def _to_mobile(url: str) -> str:
    # blog.naver.com/{id}/{postId} → m.blog.naver.com/{id}/{postId}
    try:
        u = urllib.parse.urlparse(url)
        if "blog.naver.com" in u.netloc:
            parts = u.path.strip("/").split("/")
            if len(parts) >= 2 and parts[1].isdigit():
                return f"https://m.blog.naver.com/{parts[0]}/{parts[1]}"
    except Exception:
        pass
    return url

def _fetch_body(url: str) -> Dict[str, str]:
    r = requests.get(_to_mobile(url), headers=UA, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.select_one("h3.se_textarea, h3#title_1, meta[property='og:title']")
    title = (title.get("content") if title and title.name == "meta" else (title.get_text() if title else "")).strip()
    body = soup.select_one("#postViewArea, div.se-main-container")
    text = _clean(body.get_text(" ")) if body else ""
    og = soup.select_one('meta[property="og:image"]')
    image = og["content"] if og and og.get("content") else ""
    return {"title": title, "content": text, "image": image}

def _search_blog(q: str, display: int) -> List[Dict]:
    url = f"https://openapi.naver.com/v1/search/blog?query={urllib.parse.quote(q)}&display={display}"
    r = requests.get(url, headers={
        "X-Naver-Client-Id": CID, "X-Naver-Client-Secret": CSECRET
    }, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", [])
    out = []
    for it in items:
        link = it.get("link")
        if not link:
            continue
        try:
            fetched = _fetch_body(link)
        except Exception:
            fetched = {"title": _clean(it.get("title", "")),
                       "content": _clean(it.get("description", "")),
                       "image": ""}
        out.append({
            "source": "naver_blog",
            "url": link,
            **fetched
        })
        time.sleep(0.2)
    return out

def run(q: str = "경제", display: int = 50) -> int:
    docs = _search_blog(q, display)
    return upsert_many("blogs", docs, keys=["source", "url"])
