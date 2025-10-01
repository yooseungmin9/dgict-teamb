from __future__ import annotations
import re, time
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from .database import upsert_many
from urllib.parse import urljoin

UA = {"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9","Referer":"https://news.naver.com/"}
TIMEOUT = 10

# 언론사 OID
PRESS = {
    "015": "한국경제",
    "009": "매일경제",
    "011": "서울경제",
    "014": "파이낸셜뉴스",
    "008": "머니투데이",
}

def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or " ").strip()
    return s

def _get_body(soup: BeautifulSoup) -> str:
    sel = [
        "#newsct_article",
        "#dic_area",
        "article#newsct > div#newsct_article",
        "div.article_body",
    ]
    for css in sel:
        node = soup.select_one(css)
        if node:
            # 제거 대상
            for bad in node.select("script, style, .blind, .byline, .copyright"):
                bad.extract()
            return _clean_text(node.get_text(" "))
    return ""

def _get_main_image(soup: BeautifulSoup) -> str:
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        return og["content"]
    img = soup.select_one("#newsct_article img, #dic_area img, article img")
    return img["src"] if img and img.get("src") else ""

def _parse_article(url: str) -> Dict:
    r = requests.get(url, headers=UA, timeout=TIMEOUT); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.select_one("h2#title_area span, h2.media_end_head_headline, title")
    title = _clean_text(title.get_text()) if title else ""
    body = _get_body(soup)
    image = _get_main_image(soup)
    image = urljoin(r.url, image) if image else ""
    return {"title": title, "content": body, "image": image}

def _list_urls(oid: str, pages: int) -> List[str]:
    out = []
    bases = [
        f"https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&sid1=101&oid={oid}&page=",
        f"https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&oid={oid}&page=",
    ]
    for p in range(1, pages + 1):
        got = False
        for base in bases:
            u = f"{base}{p}"
            try:
                r = requests.get(u, headers=UA, timeout=TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                # 둘 다 허용: /read.naver? , /article/
                links = []
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    if ("/read.naver?" in href) or ("/article/" in href):
                        links.append(urljoin(r.url, href))
                out.extend(links)
                got = True
                break
            except Exception:
                continue
        if not got:
            break
        time.sleep(0.3)
    return sorted(set(out))

def run(pages: int = 1) -> int:
    docs = []
    for oid, press in PRESS.items():
        for url in _list_urls(oid, pages):
            try:
                art = _parse_article(url)
                if not art["title"] and not art["content"]:
                    continue
                docs.append({
                    "source": press,
                    "url": url,
                    **art,
                })
            except Exception:
                continue
    return upsert_many("articles", docs, keys=["source", "url"])
