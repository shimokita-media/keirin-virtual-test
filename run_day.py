"""当日ループ: 開催一覧更新 → 締切30〜90分前で B0 固定 → 締切直前で B1 固定 → 確定後に結果回収。
使い方: python run_day.py [--once]
B0/B1 は締切前にしか作成されない（kr.decide が時刻条件を検証）。predictions は SQLite トリガーで追記専用。"""
import os
import sqlite3
import sys
import time
import traceback

import kr


def keep_awake(on=True):
    """環境変数 KEIRIN_KEEP_AWAKE=1 のときだけ、実行中の Windows アイドルスリープを抑止する。
    既定は抑止しない（PCを使っている間だけ動かし、電気代を増やさない方針）"""
    if os.environ.get("KEIRIN_KEEP_AWAKE") != "1":
        return
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass

B0_TARGET = 45   # 締切まで45分以下(30分以上)になった最初のループで B0
B1_WINDOW = (1.0, 4.0)  # 締切まで1〜4分で B1


DAY = os.environ.get("KEIRIN_DAY") or kr.now().strftime("%Y%m%d")  # 起動日で固定（日付またぎ対策）
MAX_SEC = float(os.environ.get("KEIRIN_MAX_SEC", 24 * 3600))


def rows(con):
    con.row_factory = sqlite3.Row
    return con.execute("SELECT * FROM races WHERE date=? ORDER BY close_at", (DAY,)).fetchall()


def has(con, rid, phase):
    return con.execute("SELECT 1 FROM predictions WHERE race_id=? AND phase=?", (rid, phase)).fetchone() is not None


def say(*a):
    print(kr.now().strftime("%H:%M:%S"), *a, flush=True)


def tick(con, done_results):
    # 締切前の処理(B0/B1)を最優先し、結果回収は1ループあたり最大3件に制限
    rs = rows(con)
    t = time.time()
    pre = [r for r in rs if r["close_at"] > t]
    post = [r for r in rs if r["close_at"] <= t - 480 and r["race_id"] not in done_results][:3]
    for r in pre + post:
        rid, mins = r["race_id"], (r["close_at"] - time.time()) / 60
        try:
            if 30 <= mins <= B0_TARGET and not has(con, rid, "B0"):
                rd, odds, meta = kr.fetch_race(con, r, "B0")
                nk, _ = kr.fetch_nk_odds(con, r, "B0")
                if odds and odds["3連単"]:
                    r = con.execute("SELECT * FROM races WHERE race_id=?", (rid,)).fetchone()
                    res = kr.decide(con, r, "B0", odds, meta, nk)
                    say("B0", r["venue"], r["race_no"], "R", res and (res["race_rating"], res["total"]))
                else:
                    say("B0 skip (odds unavailable)", rid)
            elif B1_WINDOW[0] <= mins <= B1_WINDOW[1] and not has(con, rid, "B1"):
                rd, odds, meta = kr.fetch_race(con, r, "B1")
                nk, _ = kr.fetch_nk_odds(con, r, "B1")
                if odds and odds["3連単"]:
                    r = con.execute("SELECT * FROM races WHERE race_id=?", (rid,)).fetchone()
                    res = kr.decide(con, r, "B1", odds, meta, nk)
                    say("B1", r["venue"], r["race_no"], "R", res and (res["race_rating"], res["total"]))
            elif mins < -8 and rid not in done_results:
                # 発走後: 確定済みなら結果と最終オッズを回収（判断の作成・修正は行わない）
                if con.execute("SELECT 1 FROM payouts WHERE race_id=?", (rid,)).fetchone():
                    done_results.add(rid); continue
                kr.fetch_race(con, r, "POST")
                if con.execute("SELECT 1 FROM payouts WHERE race_id=?", (rid,)).fetchone():
                    done_results.add(rid); say("result", r["venue"], r["race_no"], "R")
        except Exception:
            say("ERR", rid, traceback.format_exc()[-400:])


def single_instance():
    """重複起動の防止（ローカルのポートを確保できなければ、既に動いているとみなして終了）"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 47615))
    except OSError:
        say("already running; exit")
        sys.exit(0)
    return s


def main():
    _lock = single_instance()  # noqa: F841  プロセス終了まで保持
    con = kr.db()
    once = "--once" in sys.argv
    global START
    START = time.time()
    keep_awake(True)
    done = set()
    last_daily = 0
    while True:
        if time.time() - last_daily > 600 and kr.now().strftime("%Y%m%d") == DAY:
            try:
                say("daily", kr.fetch_daily(con))
            except Exception:
                say("daily ERR", traceback.format_exc()[-300:])
            last_daily = time.time()
        tick(con, done)
        rs = rows(con)
        if once or (rs and all(r["race_id"] in done or r["status"] == 9 for r in rs)):
            break
        if time.time() - START > MAX_SEC:  # 実行上限（GitHub Actions では1回6時間未満で区切る）
            say("max runtime reached")
            break
        time.sleep(30)
    say("finished")
    keep_awake(False)
    import subprocess
    finished_all = all(r["race_id"] in done or r["status"] == 9 for r in rows(con))
    for script in (("export.py", "history.py") if finished_all else ("export.py",)):
        try:
            subprocess.run([sys.executable, script, *([DAY] if script == "export.py" else [])],
                           cwd=kr.BASE, timeout=1800, capture_output=True)
            say(script, "done")
        except Exception:
            say(script, "ERR", traceback.format_exc()[-300:])


if __name__ == "__main__":
    main()
