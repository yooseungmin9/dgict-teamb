# chat_server2.py — (합본) 챗봇 + CLOVA STT/TTS + 안전한 /chat
# 실행: uvicorn chat_server2:app --reload --port 8000
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pathlib import Path
from openai import OpenAI
from datetime import datetime
import os, sys, json, logging, subprocess, io, requests, tempfile
import oracledb
# import pyttsx3
from google.cloud import texttospeech
from google.oauth2 import service_account
# chat_server2.py (상단 몇 줄만 추가/수정)
# 1) .env 로드 + 부팅 시 환경 체크 로그 + 디버그 엔드포인트

# ====== 로깅 설정 ======
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("chat_server")

# ===== OpenAI =====
API_KEY= "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"
client = OpenAI(api_key=API_KEY)

# ==== 벡터스토어 ID ====
VS_ID_PATH = Path(".vector_store_id")
if not VS_ID_PATH.exists():
    log.error(".vector_store_id 없음. watcher.py 먼저 실행하세요.")
    sys.exit(1)
VS_ID = VS_ID_PATH.read_text().strip()
log.info(f"VectorStore ID: {VS_ID}")


# ===== Oracle =====
ORACLE_USER = "hr"
ORACLE_PASSWORD = "hr"
ORACLE_DSN = "localhost:1521/XEPDB1"
def get_oracle_conn():
    """
    Thin 모드는 Oracle Client 미필요.
    DSN 형식: "host:port/service_name"
    예: "localhost:1521/XEPDB1"
    """
    return oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,     # "localhost:1521/XEPDB1"
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

app = FastAPI(title="Chat+STT+TTS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

history = []

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
    if not rows: return "오늘 수집된 인기 뉴스 Top N 데이터가 없습니다."
    lines = ["오늘의 경제 뉴스 Top N"]
    for r in rows:
        lines.append(f"{r['ranking']}. [{r['title']}]({r['url']})\n"
                     f"   - 요약: {r.get('summary') or ''}\n"
                     f"   - 조회수: {r.get('view_count','-')} · 발행일: {r.get('published_at','')}")
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

# ===== CLOVA STT =====
CLOVA_KEY_ID = "qiivats8e3"
CLOVA_KEY    = "QCKIyNgJc3dZURDK9yQdSqd7qknZiwPvDVdI9yHL"
CSR_URL = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt"

def _ffmpeg_to_wav16k(in_path: str) -> str:
    out_path = in_path + ".wav"
    subprocess.run(["ffmpeg","-y","-i",in_path,"-ac","1","-ar","16000",out_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out_path

LANG_MAP = {"ko":"Kor","en":"Eng","ja":"Jpn"}
def normalize_lang(l: str) -> str:
    if not l: return "Kor"
    if l.lower() in ("kor","eng","jpn"): return l.title()
    return LANG_MAP.get(l.split("-")[0].lower(), "Kor")

@app.post("/api/stt")
async def stt_clova(audio_file: UploadFile = File(...),
                    lang: str = Query("Kor")):
    lang = normalize_lang(lang)
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.filename or "")[1]) as tmp:
        raw = await audio_file.read(); tmp.write(raw); src_path = tmp.name
    wav_path = None
    try:
        wav_path = _ffmpeg_to_wav16k(src_path)
        headers = {"X-NCP-APIGW-API-KEY-ID": CLOVA_KEY_ID,
                   "X-NCP-APIGW-API-KEY": CLOVA_KEY,
                   "Content-Type": "application/octet-stream"}
        url = f"{CSR_URL}?lang={lang}"
        with open(wav_path, "rb") as f:
            res = requests.post(url, headers=headers, data=f.read(), timeout=60)
        if res.status_code != 200:
            return JSONResponse({"error": f"CSR 실패: {res.status_code} {res.text}"}, status_code=500)
        return {"text": res.text.strip(), "lang": lang}
    except Exception as e:
        log.exception("STT 처리 오류"); return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        for p in (src_path, wav_path):
            try:
                if p and os.path.exists(p): os.remove(p)
            except: pass

# ===== Google Cloud TTS =====
# 선택안하면 언어별 기본 음성 (원하면 표 늘리면 됨)
DEFAULT_VOICE = {
    "ko-KR": "ko-KR-Standard-B",   # 깔끔한 남성
    "en-US": "en-US-Neural2-C",
    "ja-JP": "ja-JP-Neural2-B",
}

def _pick_voice(lang: str, voice: Optional[str]) -> str:
    if voice:
        return voice
    base = (lang or "ko-KR").split(",")[0]
    return DEFAULT_VOICE.get(base, "ko-KR-Neural2-B")

@app.get("/api/tts")
def tts_google(
    text: str = Query(..., min_length=1),
    lang: str = Query("ko-KR"),
    voice: Optional[str] = Query(None),
    rate: float = Query(1.0, ge=0.25, le=4.0),
    pitch: float = Query(0.0, ge=-20.0, le=20.0),
    fmt: str = Query("MP3", regex="^(MP3|OGG_OPUS|LINEAR16)$"),
):
    """
    Google Cloud Text-to-Speech
    - 기본: MP3 / ko-KR / Neural2-B
    - rate, pitch 조절 가능
    """

    # 서비스 계정 키 JSON 경로를 상수로 지정
    GCP_KEY_PATH = "/Users/yoo/key/absolute-text-473306-c1-b75ae69ab526.json"

    # credentials 객체 직접 생성
    gcp_credentials = service_account.Credentials.from_service_account_file(GCP_KEY_PATH)

    # 클라이언트 초기화 시 credentials 지정
    tts_client = texttospeech.TextToSpeechClient(credentials=gcp_credentials)

    try:
        client = tts_client

        # 입력
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # 음성 선택
        voice_name = _pick_voice(lang, voice)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=lang,
            name=voice_name,
        )

        # 오디오 포맷
        if fmt == "MP3":
            audio_cfg = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=rate,
                pitch=pitch,
            )
            media_type = "audio/mpeg"
            ext = "mp3"
        elif fmt == "OGG_OPUS":
            audio_cfg = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
                speaking_rate=rate,
                pitch=pitch,
            )
            media_type = "audio/ogg"
            ext = "ogg"
        else:  # LINEAR16 (WAV PCM)
            audio_cfg = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=rate,
                pitch=pitch,
            )
            media_type = "audio/wav"
            ext = "wav"

        # 합성
        resp = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_cfg,
        )

        # 스트리밍 응답
        headers = {
            "Content-Type": media_type,
            "Cache-Control": "no-cache",
            "Content-Disposition": f'inline; filename="speech.{ext}"',
        }
        return StreamingResponse(io.BytesIO(resp.audio_content), headers=headers)
    except Exception as e:
        log.exception("Google TTS 실패")
        return JSONResponse({"error": f"TTS 실패: {e}"}, status_code=500)

@app.post("/reset")
async def reset():
    global history
    history = []
    return {"status": "ok", "message": "대화 기록 초기화 완료"}

@app.get("/health")
def health(): return {"status":"ok"}

"""
[간단 테스트]
- STT: curl -F "audio_file=@/PATH/sample.wav" "http://127.0.0.1:8000/stt/clova?lang=Kor"
- TTS: curl --get -L --data-urlencode "text=안녕하세요" "http://127.0.0.1:8000/tts/clova" -o out.mp3
- Chat: curl -H "Content-Type: application/json" -d '{"message":"오늘의 경제 뉴스 Top5"}' http://127.0.0.1:8000/chat
"""