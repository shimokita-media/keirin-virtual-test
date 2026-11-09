"""過去の前検日インタビューを集める（WINTICKET のレースページ。2026-11-10 追加、ユーザー依頼）。

各開催の初日のレース（その開催の選手がほぼ全員走る）のページを開き、interviews テーブルに保存する（kr.save_interviews）。
オッズ・出走表などは書かない（fetch_race を使うと最終オッズが重複して増えるため）。開いたレースは interview_scan に記録して次回は飛ばす。
WINTICKET にインタビューが残っているのは 2025年末〜2026年初めごろ以降の開催だけ（それより前のページは中身が空）。

使い方: python backfill_interviews.py 開始日 終了日 [--interval 秒] [--races-db レース一覧を読むDB] [--max-per-day N]
  --interval   WINTICKET へのアクセス間隔（既定 2秒＝kr.REQ_INTERVAL）。取り込み（backfill.py）と同時に動かすときは広げる（例 4）
  --races-db   レース一覧（races）を別のDBから読む（例: 本番DBの写し out/live_db/keirin.sqlite）。保存先は常に kr.BASE の keirin.sqlite
  --max-per-day  1日あたり開くレース数の上限（試し用）
"""
import argparse
import sqlite3

import kr


def main(a, b, interval=None, races_db=None, max_per_day=None):
    if interval:
        kr.REQ_INTERVAL = float(interval)
    con = kr.db()
    con.execute("CREATE TABLE IF NOT EXISTS interview_scan(race_id TEXT PRIMARY KEY, at TEXT, n_iv INT, n_new INT)")
    con.commit()
    src = sqlite3.connect(f"file:{races_db}?mode=ro", uri=True, timeout=60) if races_db else con
    src.row_factory = sqlite3.Row
    # レース一覧は最初に1回だけまとめて読む（取り込み中のDBを長く読まないため）
    allr = [dict(r) for r in src.execute("""SELECT race_id, date, slug, cup_id, day_index, race_no, venue_id FROM races
        WHERE date BETWEEN ? AND ? AND day_index=1 AND slug IS NOT NULL ORDER BY date, venue_id, race_no""", (a, b))]
    if src is not con:
        src.close()
    con.row_factory = None
    days = sorted({r["date"] for r in allr})
    tot_req = tot_new = 0
    for d in days:
        rs = [r for r in allr if r["date"] == d]
        n_req = n_new = n_iv = 0
        for r in rs:
            if max_per_day and n_req >= max_per_day:
                break
            if con.execute("SELECT 1 FROM interview_scan WHERE race_id=?", (r["race_id"],)).fetchone():
                continue
            url = kr.race_url(r)
            try:
                q, _ = kr.wt_state(url)
            except Exception as e:
                kr.log(con, "winticket", url, r["race_id"], 0, 0, f"interviews {e!r}")
                continue
            n_req += 1
            t = kr.now().isoformat(timespec="seconds")
            iv = q.get("FETCH_KEIRIN_INSPECTION_DAY_INTERVIEW_LIST") or {}
            k = sum(1 for it in iv.get("interviews") or [] if it.get("threads"))
            new = kr.save_interviews(con, q, r["race_id"], t, r["cup_id"])
            con.execute("INSERT OR REPLACE INTO interview_scan VALUES(?,?,?,?)", (r["race_id"], t, k, new))
            con.commit()
            n_new += new
            n_iv += k
        tot_req += n_req
        tot_new += n_new
        print(d, f"day1_races={len(rs)} requests={n_req} with_interview={n_iv} new={n_new}", kr.now().strftime("%H:%M:%S"), flush=True)
    print("total requests", tot_req, "new", tot_new, flush=True)
    return tot_req, tot_new


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--interval", type=float)
    ap.add_argument("--races-db")
    ap.add_argument("--max-per-day", type=int)
    x = ap.parse_args()
    main(x.start, x.end, x.interval, x.races_db, x.max_per_day)
