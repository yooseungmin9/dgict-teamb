import subprocess, sys, signal, os

# 실행할 서버 목록
SERVERS = [
    ("C:/dgict-teamb/fast_api/chatbot", "chatbot:app", 8002, None),
    ("C:/dgict-teamb/fast_api/recommend", "youtube_api:app", 8004, None),
    ("C:/dgict-teamb/fast_api/brief", "main:app", 8005, None),
    ("C:/dgict-teamb/fast_api/trend", "category_trends:app", 8006, None),
    ("C:/dgict-teamb/fast_api/senti_keyword", "main:app", 8007, None),
    ("C:/dgict-teamb/fast_api/analysis", "opinion_mining:app", 8008, None),
    ("C:/dgict-teamb/fast_api/dashboard_analysis", "emoa:app", 8009, None),
    ("C:/dgict-teamb/fast_api/dashboard_analysis", "headline:app", 8010, None),
    ("C:/dgict-teamb/fast_api/dashboard_analysis", "count:app", 8011, None),
    ("C:/dgict-teamb/fast_api/amonth_cluster", "app_clusters:app", 8012, None),
]

PROCS = []

# 실행할 서버 명렁어 조합
def launch(cwd, app, port, python_path=None):
    py = python_path or sys.executable
    cmd = [py, "-m", "uvicorn", app, "--host", "0.0.0.0", "--port", str(port), "--reload"]
    print(f"[START] {cmd} (cwd={cwd})")
    creationflags = 0
    if os.name == "nt":
        creationflags = 0

    p = subprocess.Popen(cmd, cwd=cwd, creationflags=creationflags)
    PROCS.append(p)

# 실행 / 종료
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

# 스크립트를 직접 실행 시 main을 수행
if __name__ == "__main__":
    main()
