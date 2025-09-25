# saver.py (크롤러 끝에서 rows 리스트를 저장할 때 호출)
from pathlib import Path
from datetime import datetime
import pandas as pd

OUTDIR = Path("data"); OUTDIR.mkdir(exist_ok=True)

def save_results(rows):
    # rows = [[oid, press, aid, title, body, url], ...]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    df_new = pd.DataFrame(rows, columns=["oid","press","aid","title","body","url"])
    df_new["crawl_date"] = timestamp

    # 1) 실행 시각별 파일 저장 (중복 실행 시 새로운 파일 생성)
    daily = OUTDIR / f"daily_{timestamp}.csv"
    df_new.to_csv(daily, index=False, encoding="utf-8-sig")

    # 2) 누적 파일 업데이트 (append + dedup by url)
    all_path = OUTDIR / "all_history.csv"
    if all_path.exists():
        old = pd.read_csv(all_path)
        merged = pd.concat([old, df_new], ignore_index=True)
        merged.drop_duplicates(subset=["url"], inplace=True, keep="first")
    else:
        merged = df_new
    merged.to_csv(all_path, index=False, encoding="utf-8-sig")

    print(f"saved daily: {daily} rows={len(df_new)}")
    print(f"updated all: {all_path} rows={len(merged)}")

    # ==== MongoDB 업로드 ====
    try:
        from mongo_sink import upsert_dataframe
        count = upsert_dataframe(merged, source_file=str(all_path))
        print(f"MongoDB upserted: {count} docs")
    except Exception:
        import traceback;
        traceback.print_exc()
