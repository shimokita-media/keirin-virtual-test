"""過去日の確定データ（確定オッズ・着順・払戻・出走表・並び予想）を収集する。
使い方: python backfill.py 20261021 20261103
- WINTICKET の racecard ページのみを使用（robots.txt 許可パス）。リクエスト間隔は2秒
- 取得済み（payouts あり）のレースはスキップするので、中断しても再実行で続きから再開できる
- odds.phase = 'POST'（締切後の確定オッズ。事後分析専用で、B0/B1 の判断には使わない）"""
import datetime as dt
import sqlite3
import sys
import traceback

import kr


def daily(con, day):
    url = f"https://www.winticket.jp/keirin/racecard/{day}"
    q, _ = kr.wt_state(url)
    dd = q["FETCH_KEIRIN_DAILY_RACE"]
    venues = {v["id"]: v for v in q["FETCH_KEIRIN_VENUE_LIST"]["venues"]}
    cups = {c["id"]: c for c in dd["cups"]}
    sch = {s["id"]: s for s in dd["schedules"]}
    t = kr.now().isoformat(timespec="seconds")
    for r in dd["races"]:
        s = sch[r["scheduleId"]]
        c = cups[s["cupId"]]
        v = venues[c["venueId"]]
        con.execute("""INSERT INTO races(race_id,date,venue_id,venue,slug,cup_id,cup_name,grade,day_index,race_no,
            class,race_type,close_at,start_at,status,entries_number,advancement,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(race_id) DO UPDATE SET status=excluded.status""",
                    (r["id"], s["date"], c["venueId"], v["name"], v["slug"], c["id"], c["name"],
                     kr.GRADE.get(c["grade"], str(c["grade"])), s["index"], r["number"], r["class"], r["raceType"],
                     r["closeAt"], r["startAt"], r["status"], r["entriesNumber"],
                     r.get("advancementConditionText", ""), t))
    con.commit()
    kr.log(con, "winticket", url, "", 1, len(dd["races"]), "backfill daily")
    return len(dd["races"])


def main(a, b):
    # 取り込みの間だけ Windows のアイドルスリープを止める（終われば元に戻る。GitHub Actions では何もしない）
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass
    con = kr.db()
    con.row_factory = sqlite3.Row
    d = dt.datetime.strptime(a, "%Y%m%d")
    end = dt.datetime.strptime(b, "%Y%m%d")
    while d <= end:
        day = d.strftime("%Y%m%d")
        try:
            n = daily(con, day)
        except Exception:
            print(day, "daily ERR", traceback.format_exc()[-200:], flush=True)
            d += dt.timedelta(days=1)
            continue
        rows = con.execute("SELECT * FROM races WHERE date=? AND race_id NOT IN (SELECT race_id FROM payouts) "
                           "ORDER BY close_at", (day,)).fetchall()
        ok = 0
        for r in rows:
            rd, odds, meta = kr.fetch_race(con, r, "POST")
            ok += rd is not None
        print(day, f"races={n} fetched={ok}/{len(rows)}", kr.now().strftime("%H:%M:%S"), flush=True)
        d += dt.timedelta(days=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
