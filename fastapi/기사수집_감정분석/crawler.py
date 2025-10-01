# crawler.py
# pip install requests beautifulsoup4 lxml
import re, time, csv
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from saver import save_results

UA = {"User-Agent":"Mozilla/5.0","Referer":"https://news.naver.com/"}
BASE_LIST = "https://news.naver.com/main/list.naver"  # 경제 sid1=101
OIDS = {
    "015":"한국경제", "009":"매일경제", "011":"서울경제",
    "014":"파이낸셜뉴스", "008":"머니투데이",
}

OUT = Path("data/raw_daily.csv")

def list_url(oid:int, page:int=1)->str:
    return f"{BASE_LIST}?mode=LPOD&mid=sec&oid={oid}&sid1=101&page={page}"

def to_mobile(url:str)->str:
    m = re.search(r"/article/(\d+)/(\d+)", url)
    if not m: return ""
    return f"https://n.news.naver.com/mnews/article/{m.group(1)}/{m.group(2)}"

def get_html(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=12)
    r.raise_for_status()
    # 기사(mnews)는 UTF-8, 리스트는 가끔 EUC-KR
    if "n.news.naver.com" in url or "mnews" in url:
        r.encoding = "utf-8"
    else:
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def extract_links(list_html:str)->list[str]:
    soup = BeautifulSoup(list_html, "lxml")
    hrefs = set()
    for a in soup.select("a[href]"):
        h = a["href"]
        if "/article/" in h:
            if h.startswith("/"): h = "https://news.naver.com"+h
            hrefs.add(h.split("?")[0])
    # 모바일 URL로 정규화
    mob = [to_mobile(h) for h in hrefs]
    return [u for u in mob if u]

def parse_article(mobile_url: str) -> tuple[str, str]:
    html = get_html(mobile_url)
    soup = BeautifulSoup(html, "lxml")
    title = (soup.select_one("h2.media_end_head_headline, #title_area") or {}).get_text(strip=True)
    body  = (soup.select_one("#dic_area, #newsct_article") or {}).get_text("\n", strip=True).replace("\xa0", " ")
    return title, body

def crawl_one_press(oid:str, pages:int=1, per_press_limit:int=40):
    seen=set(); rows=[]
    for p in range(1, pages+1):
        lst = get_html(list_url(oid, p))
        links = extract_links(lst)
        for u in links:
            if u in seen: continue
            seen.add(u)
            t, b = parse_article(u)
            if t and b:
                aid = u.rsplit("/",1)[-1]
                rows.append([oid, OIDS[oid], aid, t, b, u])
            if len(rows) >= per_press_limit: break
            time.sleep(0.25)
        if len(rows) >= per_press_limit: break
        time.sleep(0.5)
    return rows

def main(pages=1, per_press_limit=40):
    OUT.parent.mkdir(exist_ok=True)
    all_rows = []  # ← 추가
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["oid","press","aid","title","body","url"])
        total = 0
        for oid in ["015","009","011","014","008"]:
            rows = crawl_one_press(oid, pages=pages, per_press_limit=per_press_limit)
            for r in rows:
                w.writerow(r)
            all_rows.extend(rows)               # ← 추가
            print(f"{OIDS[oid]} 수집: {len(rows)}")
            total += len(rows)

    save_results(all_rows)  # ← 루프 밖에서 전체 저장
    print("저장:", OUT, "rows:", total)


if __name__ == "__main__":
    main(pages=1, per_press_limit=40)
