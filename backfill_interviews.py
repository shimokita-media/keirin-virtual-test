"""過去のインタビューを集める（WINTICKET。2026-11-10 追加、ユーザー依頼）。オッズ・出走表などは書かない（重複を増やさない）。

--kind pre（既定）：前検日インタビュー。各開催の初日のレース（その開催の選手がほぼ全員走る）の出走表ページを開き、interviews に保存
--kind after       ：レース後インタビュー。全レースの結果ページ（/raceresult/…?type=race_result_interview）を開き、result_interviews に保存
開いたレースは interview_scan（前検）・result_interview_scan（レース後）に記録して次回は飛ばす。レース後は保存済みのレースも飛ばす。
WINTICKET に残っているのは、どちらも 2025/12 ごろ以降の開催だけ（それより前のページは中身が空）。F1・F2 の最終日のレース後は取材対象外。

使い方: python backfill_interviews.py 開始日 終了日 [--kind pre|after] [--interval 秒] [--races-db レース一覧を読むDB] [--max-per-day N]
  --interval   WINTICKET へのアクセス間隔（既定 2秒＝kr.REQ_INTERVAL）。取り込み（backfill.py）と同時に動かすときは広げる（例 3）
  --races-db   レース一覧（races）を別のDBから読む（例: 本番DBの写し out/live_db/keirin.sqlite）。保存先は常に kr.BASE の keirin.sqlite
  --max-per-day  1日あたり開くレース数の上限（試し用）
※ import kr するので python の -I は付けない（python -X utf8 backfill_interviews.py …）
"""
import argparse
import sqlite3

import kr


def main(a, b, interval=None, races_db=None, max_per_day=None, kind="pre"):
    if interval:
        kr.REQ_INTERVAL = float(interval)
    con = kr.db()
    scan = "interview_scan" if kind == "pre" else "result_interview_scan"
    con.execute(f"CREATE TABLE IF NOT EXISTS {scan}(race_id TEXT PRIMARY KEY, at TEXT, n_iv INT, n_new INT)")
    con.commit()
    src = sqlite3.connect(f"file:{races_db}?mode=ro", uri=True, timeout=60) if races_db else con
    src.row_factory = sqlite3.Row
    # レース一覧は最初に1回だけまとめて読む（取り込み中のDBを長く読まないため）
    cond = "AND day_index=1" if kind == "pre" else ""
    allr = [dict(r) for r in src.execute(f"""SELECT race_id, date, slug, cup_id, day_index, race_no, venue_id FROM races
        WHERE date BETWEEN ? AND ? {cond} AND slug IS NOT NULL ORDER BY date, venue_id, race_no""", (a, b))]
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
            if con.execute(f"SELECT 1 FROM {scan} WHERE race_id=?", (r["race_id"],)).fetchone():
                continue
            if kind == "after" and con.execute("SELECT 1 FROM result_interviews WHERE race_id=? LIMIT 1", (r["race_id"],)).fetchone():
                continue
            url = kr.race_url(r) if kind == "pre" else kr.result_url(r)
            try:
                q, _ = kr.wt_state(url)
            except Exception as e:
                kr.log(con, "winticket", url, r["race_id"], 0, 0, f"interviews({kind}) {e!r}")
                continue
            n_req += 1
            t = kr.now().isoformat(timespec="seconds")
            if kind == "pre":
                iv = q.get("FETCH_KEIRIN_INSPECTION_DAY_INTERVIEW_LIST") or {}
                k = sum(1 for it in iv.get("interviews") or [] if it.get("threads"))
                new = kr.save_interviews(con, q, r["race_id"], t, r["cup_id"])
            else:
                k, new = kr.save_result_interviews(con, q, r["race_id"], t)
            con.execute(f"INSERT OR REPLACE INTO {scan} VALUES(?,?,?,?)", (r["race_id"], t, k, new))
            con.commit()
            n_new += new
            n_iv += k
        tot_req += n_req
        tot_new += n_new
        print(d, kind, f"races={len(rs)} requests={n_req} with_interview={n_iv} new={n_new}", kr.now().strftime("%H:%M:%S"), flush=True)
    print("total", kind, "requests", tot_req, "new", tot_new, flush=True)
    return tot_req, tot_new


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--kind", choices=["pre", "after"], default="pre")
    ap.add_argument("--interval", type=float)
    ap.add_argument("--races-db")
    ap.add_argument("--max-per-day", type=int)
    x = ap.parse_args()
    main(x.start, x.end, x.interval, x.races_db, x.max_per_day, x.kind)
