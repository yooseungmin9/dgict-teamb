# chat_server2.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from openai import OpenAI
import os, sys, json, logging
import oracledb
from datetime import datetime

# ====== 로깅 설정 ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("chat_server")

# ==== OpenAI ====
API_KEY= "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"
client = OpenAI(api_key=API_KEY)

# ==== 벡터스토어 ID ====
VS_ID_PATH = Path(".vector_store_id")
if not VS_ID_PATH.exists():
    log.error(".vector_store_id 없음. watcher.py 먼저 실행하세요.")
    sys.exit(1)
VS_ID = VS_ID_PATH.read_text().strip()
log.info(f"VectorStore ID: {VS_ID}")

# ==== Oracle 연결 설정 ====
ORACLE_USER = "hr"
ORACLE_PASSWORD = "hr"
ORACLE_DSN = "localhost:1521/XEPDB1"

def get_oracle_conn():
    # cx_Oracle.connect 대신 oracledb.connect 사용
    return oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN
    )

def fetch_today_topn_from_oracle(n: int = 5):
    sql = """
    SELECT ranking, title, summary, url, view_count, published_at
    FROM (
        SELECT ranking, title, summary, url, view_count, published_at
        FROM popular_news
        WHERE collected_at >= TRUNC(SYSDATE)
        ORDER BY ranking ASC
    )
    WHERE ROWNUM <= :n
    """
    rows = []
    with get_oracle_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, [n])
            for r in cur:
                rows.append({
                    "ranking": r[0],
                    "title": r[1],
                    "summary": r[2],
                    "url": r[3],
                    "view_count": int(r[4]) if r[4] is not None else None,
                    "published_at": r[5].strftime("%Y-%m-%d") if isinstance(r[5], datetime) else (r[5] or None),
                })
    return rows

# ==== 시스템 프롬프트 ====
SYSTEM_INSTRUCTIONS = """
너는 'AI 기반 경제 뉴스 분석 웹서비스'의 안내 챗봇이다.

툴 사용 규칙:
- 문서/기능 안내: 반드시 file_search 툴 사용
 + 변경 사항은 마지막 버전의 문서로만 안내해
- 사용자가 '오늘의 인기 뉴스 Top N', '오늘 가장 많이 본 경제 기사', '오늘 경제 뉴스 Top5/Top 10' 등 TopN 질문:
  반드시 query_oracle_top_news 툴을 호출하라.
  사용자가 N을 명시하지 않으면 기본값 5로 호출하라.

툴 호출 예시:
- 입력: "오늘의 경제 뉴스 Top5"
  → query_oracle_top_news 를 arguments: {"n": 5} 로 호출
- 입력: "오늘 인기 뉴스 3개만"
  → query_oracle_top_news 를 arguments: {"n": 3} 로 호출

응답 작성:
- 툴 결과를 받은 후 한국어로 3~5문장으로 요약하고, 필요 시 불릿을 사용한다.
- 링크(url), 조회수, 발행일을 간단히 보여준다.
"""

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

history = []

# ====== 디버그: Responses 덤프 ======
def dump_response_debug(tag: str, resp):
    try:
        safe = {
            "output_text": getattr(resp, "output_text", None),
            "output_len": len(getattr(resp, "output", []) or []),
            "items": [],
        }
        for out in getattr(resp, "output", []) or []:
            item = {"type": getattr(out, "type", None)}
            content_list = getattr(out, "content", None)
            if content_list:
                dump_items = []
                for c in content_list:
                    # 가능한 모든 방법으로 구조를 찍어본다
                    dump_items.append({
                        "repr": repr(c),
                        "as_dict": getattr(c, "model_dump", lambda: {} )()
                    })
                item["content_debug"] = dump_items
            safe["items"].append(item)
        log.info(f"[{tag}] resp deep-dump: {json.dumps(safe, ensure_ascii=False, default=str)}")
    except Exception as e:
        log.warning(f"[{tag}] dump_response_debug 실패: {e}")


# ====== 도구 호출 탐지 (tool_call + function_call 지원) ======
def find_first_tool_call(resp):
    for out in getattr(resp, "output", []) or []:
        otype = getattr(out, "type", None)
        # 1) output 레벨에 function_call 있을 수 있음
        if otype == "function_call":
            name = getattr(out, "name", None)
            tool_call_id = getattr(out, "id", None)
            args = getattr(out, "arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            log.info(f"[tool_detected@output] name={name}, id={tool_call_id}, args={args}")
            return tool_call_id, name, args

        # 2) content 안쪽에도 tool_call/function_call 있을 수 있음 (백업용)
        content_list = getattr(out, "content", None)
        if content_list:
            for c in content_list:
                ctype = getattr(c, "type", None)
                if ctype in ("tool_call", "function_call"):
                    tc = getattr(c, "tool_call", None) or getattr(c, "function_call", None)
                    if not tc:
                        continue
                    name = getattr(tc, "name", None)
                    tool_call_id = getattr(tc, "id", None)
                    args = getattr(tc, "arguments", {}) or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    log.info(f"[tool_detected@content] name={name}, id={tool_call_id}, args={args}")
                    return tool_call_id, name, args

    log.info("[tool_call/function_call] 없음")
    return None, None, None


def format_topn_md(rows):
    if not rows:
        return "오늘 수집된 인기 뉴스 Top N 데이터가 없습니다."
    lines = ["**오늘의 경제 뉴스 Top N**"]
    for r in rows:
        lines.append(
            f"{r['ranking']}. [{r['title']}]({r['url']})\n"
            f"   - 요약: {r.get('summary') or ''}\n"
            f"   - 조회수: {r.get('view_count','-')} · 발행일: {r.get('published_at','')}"
        )
    return "\n".join(lines)

@app.post("/chat")
async def chat(payload: dict):
    global history
    q = (payload.get("message") or "").strip()
    if not q:
        return {"answer": "질문이 비어있습니다."}

    log.info(f"[Q] {q}")
    history.append({"role": "user", "content": [{"type": "input_text", "text": q}]})

    # 1) 1차 호출
    resp = client.responses.create(
        model="gpt-5",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[
            {"type": "file_search", "vector_store_ids": [VS_ID]},
            {
                "type": "function",
                "name": "query_oracle_top_news",
                "description": "오늘의 경제 뉴스 Top N을 Oracle DB에서 가져온다.",
                "parameters": {
                    "type": "object",
                    "properties": {"n": {"type": "integer", "description": "조회할 개수 (기본 5)"}} ,
                    "required": ["n"],
                },
            },
        ],
        input=history,
    )
    dump_response_debug("first_call", resp)

    # 2) 툴 호출 감지
    tool_call_id, tool_name, args = find_first_tool_call(resp)
    if tool_name == "query_oracle_top_news":
        n = int(args.get("n", 5) or 5)
        try:
            rows = fetch_today_topn_from_oracle(n)
            log.info(f"[oracle] rows={len(rows)}")
        except Exception as e:
            log.exception("DB 조회 중 오류")
            return {"answer": f"DB 조회 중 오류: {e}"}

        # 3) 서버 포맷으로 바로 응답
        answer = format_topn_md(rows)
        log.info("[server-format] 모델 2차 호출 생략, 서버 포맷으로 응답")

        history.append({"role": "assistant", "content": [{"type": "output_text", "text": answer}]})
        return {"answer": answer}

    # 4) 일반 답변
    answer = (getattr(resp, "output_text", "") or "").strip()
    if not answer:
        log.warning("[warn] 툴도 안 쓰고 output_text도 비었음")
        return {"answer": "응답이 비었습니다. (디버그: 툴 호출/출력 없음)"}

    history.append({"role": "assistant", "content": [{"type": "output_text", "text": answer}]})
    return {"answer": answer}


@app.post("/reset")
async def reset():
    global history
    history = []
    return {"status": "ok", "message": "대화 기록 초기화 완료"}
