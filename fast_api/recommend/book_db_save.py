# -*- coding: utf-8 -*-
from __future__ import annotations

import os, requests
from typing import List, Dict, Optional
from fastapi import FastAPI, Query, HTTPException
from datetime import datetime
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING, TEXT
from pymongo.errors import DuplicateKeyError, BulkWriteError

# 0) .env 로드 (없으면 조용히 패스)
load_dotenv()

# 1) 환경변수
ALADIN_TTBKEY = os.getenv("ALADIN_TTBKEY", "")  # 필수
MONGO_URI     = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB      = os.getenv("MONGO_DB", "test123")
COL_BOOKS     = os.getenv("MONGO_COL_ALADIN_BOOKS", "aladin_books")
COL_CATS      = os.getenv("MONGO_COL_ALADIN_CATEGORIES", "aladin_categories")

# 2) 상수(서비스 로직): 기본 경제 카테고리 (코드 내부 유지 권장)
DEFAULT_ECON_CATEGORY_IDS = [
    170, 3057, 3059, 3061, 3062, 3063, 8586, 3065, 3140, 8587,
    2172, 3103, 2173, 2841, 8593, 2747, 3123, 3069, 2028, 853,
    852, 854, 261, 268, 273, 1632, 55058, 2169, 263, 172, 141092,
    11502, 175, 11501, 2225, 174, 177, 3048, 32288, 180, 249,
    3049, 3104, 2408, 3110, 11503, 6189
]

ALADIN_URL = "http://www.aladin.co.kr/ttb/api/ItemList.aspx"

# 3) FastAPI
app = FastAPI(title="Aladin Save-First API (Mongo, rank+salesPoint)")

# 4) 유틸
def normalize_category_ids(raw_ids: Optional[List[str]]) -> List[int]:
    if not raw_ids:
        return []
    out: List[int] = []
    for v in raw_ids:
        if v is None:
            continue
        for part in str(v).split(","):
            p = part.strip()
            if p.isdigit():
                out.append(int(p))
    return list(dict.fromkeys(out))

def get_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]

def drop_index_if_exists(coll, name: str):
    try:
        coll.drop_index(name)
        print(f"[ensure_indexes] dropped index: {name}")
    except Exception:
        pass

def ensure_indexes(db):
    # 카테고리
    db[COL_CATS].create_index([("id", ASCENDING)], unique=True, name="uk_category_id")
    db[COL_CATS].create_index([("name", ASCENDING)], name="idx_category_name")

    # 도서
    db[COL_BOOKS].create_index([("uniqueKey", ASCENDING)], unique=True, sparse=True, name="uk_uniquekey")
    drop_index_if_exists(db[COL_BOOKS], "uk_isbn13")
    db[COL_BOOKS].create_index([("isbn13", ASCENDING)], unique=True, sparse=True, name="uk_isbn13")
    db[COL_BOOKS].create_index([("link", ASCENDING)], unique=True, sparse=True, name="uk_link")
    db[COL_BOOKS].create_index([("categoryId", ASCENDING), ("pubDate", ASCENDING)], name="idx_cat_pubDate")
    db[COL_BOOKS].create_index([("pubDate", ASCENDING)], name="idx_pubDate")
    db[COL_BOOKS].create_index([("title", TEXT), ("author", TEXT)], name="txt_title_author")
    db[COL_BOOKS].create_index([("salesPoint", DESCENDING)], name="idx_salesPoint")
    db[COL_BOOKS].create_index([("bestseller.rank", ASCENDING), ("bestseller.categoryId", ASCENDING)], name="idx_bsr_cat")

# 5) 알라딘 호출
def fetch_xml(cid: int, start: int, max_results: int) -> str:
    if not ALADIN_TTBKEY:
        raise HTTPException(500, "ALADIN_TTBKEY 가 설정되어 있지 않습니다.")
    params = {
        "ttbkey": ALADIN_TTBKEY,
        "QueryType": "Bestseller",
        "MaxResults": max_results,
        "start": start,
        "SearchTarget": "Book",
        "CategoryId": cid,
        "output": "xml",
        "Version": 20131101,
    }
    r = requests.get(ALADIN_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.text

# 6) XML 파싱
def parse_xml(xml_text: str) -> List[Dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # 네임스페이스 제거
    for el in root.iter():
        if isinstance(el.tag, str) and '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]

    out = []
    for idx, it in enumerate(root.iter("item")):
        def get(tag):
            n = it.find(tag)
            return (n.text or "").strip() if n is not None else ""

        sp_raw = get("salesPoint")
        try:
            sales_point = int(sp_raw) if sp_raw else None
        except ValueError:
            sales_point = None

        out.append({
            "title":  get("title"),
            "author": get("author"),
            "pubDate": get("pubDate")[:10],
            "link":   get("link"),
            "cover":  get("cover"),
            "isbn13": get("isbn13"),
            "salesPoint": sales_point,
            "__index_in_page": idx
        })
    return out

# 7) 저장(업서트)
def save_to_mongo(items: List[Dict], category_ids: List[int]):
    print(f"[save_to_mongo] incoming items: {len(items)}  cats={category_ids}")
    db = get_db()
    ensure_indexes(db)

    # 카테고리 upsert
    for cid in set(category_ids):
        db[COL_CATS].update_one(
            {"id": int(cid)},
            {"$set": {"id": int(cid), "name": "ECON"},
             "$setOnInsert": {"createdAt": datetime.utcnow()}},
            upsert=True,
        )

    ops = []
    now = datetime.utcnow()
    for it in items:
        raw_isbn = (it.get("isbn13") or "").strip()
        isbn = raw_isbn if raw_isbn else None
        link = (it.get("link") or "").strip() or None
        unique_key = isbn or link
        if not unique_key:
            continue

        pub_dt = None
        if it.get("pubDate"):
            try:
                pub_dt = datetime.strptime(it["pubDate"], "%Y-%m-%d")
            except Exception:
                pub_dt = None

        cat_id = category_ids[0] if len(category_ids) == 1 else it.get("categoryId")

        set_fields = {
            "title": it.get("title") or "",
            "author": it.get("author") or "",
            "cover": it.get("cover") or None,
            "pubDate": pub_dt,
            "categoryId": int(cat_id) if cat_id else None,
            "source": "ALADIN",
            "link": link,
            "updatedAt": now,
        }
        if isbn is not None:
            set_fields["isbn13"] = isbn

        if it.get("salesPoint") is not None:
            try:
                set_fields["salesPoint"] = int(it["salesPoint"])
            except Exception:
                pass

        if it.get("bestsellerRank") is not None:
            set_fields["bestseller"] = {
                "rank": int(it["bestsellerRank"]),
                "categoryId": int(cat_id) if cat_id else None,
                "capturedAt": now
            }

        update_doc = {"$set": set_fields, "$setOnInsert": {"ingestedAt": now, "uniqueKey": unique_key}}
        if isbn is None:
            update_doc["$unset"] = {"isbn13": ""}

        ops.append(UpdateOne({"uniqueKey": unique_key}, update_doc, upsert=True))

    if not ops:
        print("[save_to_mongo] no ops to write (missing isbn13/link?)")
        return

    try:
        result = db[COL_BOOKS].bulk_write(ops, ordered=False)
        print(f"[save_to_mongo] bulk_write OK. upserted={result.upserted_count} matched={result.matched_count} modified={result.modified_count}")
    except DuplicateKeyError as e:
        print(f"[save_to_mongo] DuplicateKeyError: {e}")
    except BulkWriteError as bwe:
        print(f"[save_to_mongo] BulkWriteError: {bwe.details}")
    except Exception as e:
        print(f"[save_to_mongo] bulk_write error: {e}")
        raise

# 8) API 엔드포인트
@app.get("/books")
def books(
    category_ids: Optional[List[str]] = Query(
        None, description="예: 3065,3057 또는 category_ids=3065&category_ids=3057"
    ),
    start: int  = Query(1, ge=1),
    pages: int  = Query(1, ge=1, le=5),
    per_page: int = Query(20, ge=1, le=50),
    since: Optional[str] = None,  # YYYY-MM-DD
    save: bool = Query(False, description="true면 MongoDB에 저장 후 반환"),
):
    ids = normalize_category_ids(category_ids)
    if not ids:
        ids = DEFAULT_ECON_CATEGORY_IDS
    if not ids:
        raise HTTPException(400, "category_ids가 비어있습니다.")

    collected: List[Dict] = []
    for cid in ids:
        s = start
        for _ in range(pages):
            try:
                xml = fetch_xml(cid, s, per_page)
                parsed = parse_xml(xml)

                base = (s - 1) * per_page
                for it in parsed:
                    it.setdefault("categoryId", cid)
                    local_idx = it.pop("__index_in_page", None)
                    if local_idx is not None:
                        it["bestsellerRank"] = base + local_idx + 1

                collected.extend(parsed)
            except requests.RequestException as e:
                print(f"[books] request error (cid={cid}, page={s}): {e}")
            s += 1

    print(f"[books] collected={len(collected)} before dedup")

    # dedup by isbn13/link
    seen = set()
    dedup = []
    for it in collected:
        key = it.get("isbn13") or it.get("link")
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        dedup.append(it)

    print(f"[books] after dedup={len(dedup)}")

    if since:
        try:
            since_dt = datetime.strptime(since[:10], "%Y-%m-%d")
            filtered = []
            for it in dedup:
                pub = (it.get("pubDate") or "")[:10]
                try:
                    if datetime.strptime(pub, "%Y-%m-%d") >= since_dt:
                        filtered.append(it)
                except Exception:
                    # 날짜 파싱 실패 시 필터링 제외(보존)
                    filtered.append(it)
            dedup = filtered
            print(f"[books] after since filter={len(dedup)} (since={since})")
        except ValueError:
            print(f"[books] invalid since format, ignored: {since}")

    if save:
        try:
            save_to_mongo(dedup, ids)
        except Exception as e:
            raise HTTPException(500, f"Mongo 저장 실패: {e}")

    return {"count": len(dedup), "items": dedup, "saved": bool(save)}

@app.get("/_refresh_bestseller_meta")
def refresh_meta(
    category_ids: Optional[List[str]] = Query(None),
    start: int = Query(1, ge=1),
    pages: int = Query(1, ge=1, le=5),
    per_page: int = Query(20, ge=1, le=50),
):
    ids = normalize_category_ids(category_ids) or DEFAULT_ECON_CATEGORY_IDS
    if not ids:
        raise HTTPException(400, "category_ids가 비어있습니다.")

    all_items: List[Dict] = []
    for cid in ids:
        s = start
        for _ in range(pages):
            try:
                xml = fetch_xml(cid, s, per_page)
                parsed = parse_xml(xml)
                base = (s - 1) * per_page
                for it in parsed:
                    it.setdefault("categoryId", cid)
                    local_idx = it.pop("__index_in_page", None)
                    if local_idx is not None:
                        it["bestsellerRank"] = base + local_idx + 1
                all_items.extend(parsed)
            except requests.RequestException as e:
                print(f"[_refresh_bestseller_meta] request error (cid={cid}, page={s}): {e}")
            s += 1

    # 부분 업서트 (rank/salesPoint/updatedAt)
    db = get_db()
    ensure_indexes(db)
    ops = []
    now = datetime.utcnow()
    for it in all_items:
        key = (it.get("isbn13") or "").strip() or (it.get("link") or "").strip()
        if not key:
            continue
        cat_id = ids[0] if len(ids) == 1 else it.get("categoryId")
        set_fields = {"updatedAt": now}
        if it.get("salesPoint") is not None:
            try:
                set_fields["salesPoint"] = int(it["salesPoint"])
            except Exception:
                pass
        if it.get("bestsellerRank") is not None:
            set_fields["bestseller"] = {
                "rank": int(it["bestsellerRank"]),
                "categoryId": int(cat_id) if cat_id else None,
                "capturedAt": now,
            }
        ops.append(UpdateOne({"uniqueKey": key}, {"$set": set_fields}, upsert=False))

    if ops:
        db[COL_BOOKS].bulk_write(ops, ordered=False)

    return {"ok": True, "updated": len(ops)}
