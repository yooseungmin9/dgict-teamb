# run_many.py
import subprocess, sys, signal, os

# ❗️여기에 서버 목록을 추가하세요.
#   (작업폴더, "모듈:앱", 포트, [선택]가상환경 파이썬 경로)
SERVERS = [
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/chatbot", "chatbot:app", 8002, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/recommend", "youtube_api:app", 8004, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/brief", "main:app", 8005, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/trend", "category_trends:app", 8006, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/senti_keyword", "main:app", 8007, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/analysis", "youtube_fastapi:app", 8008, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/dashboard_analysis", "main:app", 8009, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/global_news", "main:app", 8010, None),
    ("/Users/yoo/bootcamp_dgict/dgict-teamb/fast_api/new_count", "main:app", 8011, None),
]

PROCS = []

def launch(cwd, app, port, python_path=None):
    # 현재 파이썬으로 실행하거나, 지정된 venv 파이썬으로 실행
    py = python_path or sys.executable
    cmd = [py, "-m", "uvicorn", app, "--host", "0.0.0.0", "--port", str(port), "--reload"]
    print(f"[START] {cmd}  (cwd={cwd})")
    # Windows에서 새 창 없이 백그라운드로 돌리고 싶으면 CREATE_NO_WINDOW 사용 가능
    creationflags = 0
    if os.name == "nt":
        creationflags = 0  # subprocess.CREATE_NO_WINDOW  # 필요 시 주석 해제

    p = subprocess.Popen(cmd, cwd=cwd, creationflags=creationflags)
    PROCS.append(p)

def main():
    for (cwd, app, port, py) in SERVERS:
        launch(cwd, app, port, py)

    try:
        for p in PROCS:
            p.wait()
    except KeyboardInterrupt:
        print("\n[STOPPING] sending SIGINT...")
        for p in PROCS:
            try:
                p.send_signal(signal.SIGINT)
            except Exception:
                pass
        for p in PROCS:
            try:
                p.wait()
            except Exception:
                pass
        print("[DONE]")

if __name__ == "__main__":
    main()
