# -*- coding: utf-8 -*-
# FastAPI + Aladin API → (필터/중복제거) → [옵션] MongoDB 저장(save=true)
# 실행:
#   pip install fastapi uvicorn pymongo requests
#   uvicorn main:app --reload --host 0.0.0.0 --port 8000
# 사용 예:
#   GET /books?pages=2&per_page=50&save=true
#   GET /_ping_write  ← Mongo 쓰기 확인용
#   POST /_repair_isbn_index  ← isbn13:null 정리 + 인덱스 재생성

import requests
from typing import List, Dict, Optional
from fastapi import FastAPI, Query, HTTPException
from datetime import datetime
from xml.etree import ElementTree as ET

from pymongo import MongoClient, UpdateOne, ASCENDING, TEXT
from pymongo.errors import DuplicateKeyError, BulkWriteError

# =========================
# 🔧 고정 설정(여기만 수정)
# =========================
# 1) 알라딘 TTB 키
TTBKEY = "ttb2win0min1217001"  # ← 네 키로 교체

# 2) MongoDB 연결 및 DB/컬렉션 이름
MONGODB_URI = "mongodb+srv://Dgict_TeamB:team1234@cluster0.5d0uual.mongodb.net/"
MONGODB_DB  = "test123"

# 👉 컬렉션 이름은 여기서 한 번만 지정
BOOKS_COLLECTION      = "aladin_books"
CATEGORIES_COLLECTION = "aladin_categories"

# 3) 기본 경제 카테고리(필요시 수정/추가)
DEFAULT_ECON_CATEGORY_IDS = [
    170, 3057, 3059, 3061, 3062, 3063, 8586, 3065, 3140, 8587,
    2172, 3103, 2173, 2841, 8593, 2747, 3123, 3069, 2028, 853,
    852, 854, 261, 268, 273, 1632, 55058, 2169, 263, 172, 141092,
    11502, 175, 11501, 2225, 174, 177, 3048, 32288, 180, 249,
    3049, 3104, 2408, 3110, 11503, 6189
]

# 4) 알라딘 API 기본
ALADIN_URL = "http://www.aladin.co.kr/ttb/api/ItemList.aspx"

app = FastAPI(title="Aladin Save-First API (Mongo)")

# =========================
# 공통 유틸
# =========================
def normalize_category_ids(raw_ids: Optional[List[str]]) -> List[int]:
    """'3065,3057' 이든 ['3065','3057'] 이든 정수 리스트로 정규화"""
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
    return list(dict.fromkeys(out))  # 중복 제거(순서 보존)

# =========================
# Mongo 유틸
# =========================
def get_db():
    client = MongoClient(MONGODB_URI)
    return client[MONGODB_DB]

def drop_index_if_exists(coll, name: str):
    try:
        coll.drop_index(name)
        print(f"[ensure_indexes] dropped index: {name}")
    except Exception:
        # 존재하지 않으면 무시
        pass

def ensure_indexes(db):
    # 카테고리
    db[CATEGORIES_COLLECTION].create_index([("id", ASCENDING)], unique=True, name="uk_category_id")
    db[CATEGORIES_COLLECTION].create_index([("name", ASCENDING)], name="idx_category_name")

    # 도서
    db[BOOKS_COLLECTION].create_index([("uniqueKey", ASCENDING)], unique=True, sparse=True, name="uk_uniquekey")

    # (핵심) isbn13 인덱스: partialFilterExpression 쓰지 않고 unique + sparse 사용
    #   → isbn13 필드가 "존재하지 않는" 문서는 인덱스 대상에서 제외됨.
    # 먼저 이전에 실패/기존에 있던 인덱스가 있으면 정리
    drop_index_if_exists(db[BOOKS_COLLECTION], "uk_isbn13")
    db[BOOKS_COLLECTION].create_index([("isbn13", ASCENDING)], unique=True, sparse=True, name="uk_isbn13")

    db[BOOKS_COLLECTION].create_index([("link", ASCENDING)], unique=True, sparse=True, name="uk_link")
    db[BOOKS_COLLECTION].create_index([("categoryId", ASCENDING), ("pubDate", ASCENDING)], name="idx_cat_pubDate")
    db[BOOKS_COLLECTION].create_index([("pubDate", ASCENDING)], name="idx_pubDate")
    db[BOOKS_COLLECTION].create_index([("title", TEXT), ("author", TEXT)], name="txt_title_author")

# =========================
# 유지보수/진단 엔드포인트
# =========================
@app.get("/_ping_write")
def ping_write():
    """MongoDB 연결/쓰기 확인용 간단 테스트"""
    try:
        db = get_db()
        ensure_indexes(db)
        now = datetime.utcnow()
        doc = {
            "uniqueKey": f"_ping_{now.timestamp()}",
            "title": "PING",
            "author": "SYSTEM",
            "pubDate": now,
            "categoryId": 0,
            "source": "TEST",
            "ingestedAt": now,
            "updatedAt": now,
        }
        db[BOOKS_COLLECTION].insert_one(doc)
        return {"ok": True, "collection": BOOKS_COLLECTION, "db": MONGODB_DB}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/_repair_isbn_index")
def repair_isbn_index():
    """
    1) isbn13:null 문서 정리(unset)
    2) uk_isbn13 인덱스 재생성(sparse unique)
    """
    db = get_db()
    # 1) isbn13:null → 필드 제거
    res = db[BOOKS_COLLECTION].update_many({"isbn13": None}, {"$unset": {"isbn13": ""}})
    # 2) 인덱스 재생성
    drop_index_if_exists(db[BOOKS_COLLECTION], "uk_isbn13")
    db[BOOKS_COLLECTION].create_index([("isbn13", ASCENDING)], unique=True, sparse=True, name="uk_isbn13")
    return {"ok": True, "unset_null_count": res.modified_count, "index": "uk_isbn13 (unique,sparse)"}

# =========================
# Aladin 호출 & 파싱
# =========================
def fetch_xml(cid: int, start: int, max_results: int) -> str:
    if not TTBKEY:
        raise HTTPException(500, "ALADIN_TTBKEY 가 설정되어 있지 않습니다.")
    params = {
        "ttbkey": TTBKEY,
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

def parse_xml(xml_text: str) -> List[Dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    for el in root.iter():
        if isinstance(el.tag, str) and '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    out = []
    for it in root.iter("item"):
        def get(tag):
            n = it.find(tag)
            return (n.text or "").strip() if n is not None else ""
        out.append({
            "title":  get("title"),
            "author": get("author"),
            "pubDate": get("pubDate")[:10],  # YYYY-MM-DD
            "link":   get("link"),
            "cover":  get("cover"),
            "isbn13": get("isbn13"),
        })
    return out

# =========================
# Mongo 저장(업서트) + 진단 로그
# =========================
def save_to_mongo(items: List[Dict], category_ids: List[int]):
    print(f"[save_to_mongo] incoming items: {len(items)}  cats={category_ids}")
    db = get_db()
    ensure_indexes(db)

    # 카테고리 upsert
    for cid in set(category_ids):
        db[CATEGORIES_COLLECTION].update_one(
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
            # isbn도 link도 없으면 스킵
            continue

        pub_dt = None
        if it.get("pubDate"):
            try:
                pub_dt = datetime.strptime(it["pubDate"], "%Y-%m-%d")
            except Exception:
                pub_dt = None

        # category_ids가 단일이면 그 값을 categoryId로, 복수면 아이템에 심어놓은 값 사용
        cat_id = category_ids[0] if len(category_ids) == 1 else it.get("categoryId")

        # $set 필드 구성 (isbn13이 None이면 아예 저장하지 않음)
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

        update_doc = {"$set": set_fields, "$setOnInsert": {"ingestedAt": now, "uniqueKey": unique_key}}
        # 혹시 이전에 isbn13:null 이 저장된 적이 있다면 제거
        if isbn is None:
            update_doc["$unset"] = {"isbn13": ""}

        ops.append(UpdateOne({"uniqueKey": unique_key}, update_doc, upsert=True))

    if not ops:
        print("[save_to_mongo] no ops to write (missing isbn13/link?)")
        return

    try:
        result = db[BOOKS_COLLECTION].bulk_write(ops, ordered=False)
        print(f"[save_to_mongo] bulk_write OK. upserted={result.upserted_count} matched={result.matched_count} modified={result.modified_count}")
    except DuplicateKeyError as e:
        print(f"[save_to_mongo] DuplicateKeyError: {e}")
    except BulkWriteError as bwe:
        # 일부 문서 실패 시에도 성공분은 반영됨. 세부 사유만 로그
        print(f"[save_to_mongo] BulkWriteError: {bwe.details}")
    except Exception as e:
        print(f"[save_to_mongo] bulk_write error: {e}")
        raise

# =========================
# API 엔드포인트
# =========================
@app.get("/books")
def books(
    # 콤마/반복 허용
    category_ids: Optional[List[str]] = Query(
        None, description="예: 3065,3057 또는 category_ids=3065&category_ids=3057"
    ),
    start: int  = Query(1, ge=1),
    pages: int  = Query(1, ge=1, le=5),
    per_page: int = Query(20, ge=1, le=50),
    since: Optional[str] = None,  # YYYY-MM-DD
    save: bool = Query(False, description="true면 MongoDB에 저장 후 반환"),
):
    # 1) 카테고리 정규화
    ids = normalize_category_ids(category_ids)
    if not ids:
        ids = DEFAULT_ECON_CATEGORY_IDS
    if not ids:
        raise HTTPException(400, "category_ids가 비어있습니다.")

    # 2) 수집
    collected: List[Dict] = []
    for cid in ids:
        s = start
        for _ in range(pages):
            try:
                xml = fetch_xml(cid, s, per_page)
                parsed = parse_xml(xml)
                # 호출당시 cid를 각 아이템에 심어둠
                for it in parsed:
                    it.setdefault("categoryId", cid)
                collected.extend(parsed)
            except requests.RequestException as e:
                print(f"[books] request error (cid={cid}, page={s}): {e}")
            s += 1

    print(f"[books] collected={len(collected)} before dedup")

    # 3) 중복 제거 (isbn13 우선, 없으면 link)
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

    # 4) since 필터 (선택)
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
                    filtered.append(it)
            dedup = filtered
            print(f"[books] after since filter={len(dedup)} (since={since})")
        except ValueError:
            print(f"[books] invalid since format, ignored: {since}")

    # 5) save=true이면 Mongo에 업서트
    if save:
        try:
            save_to_mongo(dedup, ids)
        except Exception as e:
            raise HTTPException(500, f"Mongo 저장 실패: {e}")

    return {"count": len(dedup), "items": dedup, "saved": bool(save)}
