"""当日ループ: 開催一覧更新 → 締切30〜90分前で B0 固定 → 締切直前で B1 固定 → 確定後に結果回収。
使い方: python run_day.py [--once]
B0/B1 は締切前にしか作成されない（kr.decide が時刻条件を検証）。predictions は SQLite トリガーで追記専用。"""
import os
import sqlite3
import sys
import time
import traceback

import kr
import notify


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

SNAPSHOTS = {"T10": (9.0, 11.0), "T5": (4.5, 5.8), "T1": (0.4, 1.5)}  # 記録だけ（判断には使わない）
DECIDE_WINDOW = (2.0, 3.5)  # 2026-11-07〜 締切2〜3分前に判断（それまでは4〜7分前）
NOTIFY_RULE = False  # 2026-11-07〜 法則枠は通知せず記録のみ。Discord の買い目・結果はワイド枠だけ
ONLY_RULE = True  # 2026-11-06〜 法則枠(B1R)のみ記録（B0/B1・検証買い・万車券枠は停止。結果回収は継続）
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
            # 倍率が「いつ」「どれだけ」動くかを調べるため、締切10分前・5分前・1分前の倍率も記録する（2026-11-07〜）
            for ph, (lo, hi) in SNAPSHOTS.items():
                if lo <= mins <= hi and not con.execute(
                        "SELECT 1 FROM odds WHERE race_id=? AND phase=? AND source='winticket' LIMIT 1", (rid, ph)).fetchone():
                    kr.fetch_race(con, r, ph)
                    mins = (r["close_at"] - time.time()) / 60
            if not ONLY_RULE and 30 <= mins <= B0_TARGET and not has(con, rid, "B0"):
                rd, odds, meta = kr.fetch_race(con, r, "B0")
                nk, _ = kr.fetch_nk_odds(con, r, "B0")
                if odds and odds["3連単"]:
                    r = con.execute("SELECT * FROM races WHERE race_id=?", (rid,)).fetchone()
                    res = kr.decide(con, r, "B0", odds, meta, nk)
                    say("B0", r["venue"], r["race_no"], "R", res and (res["race_rating"], res["total"]))
                else:
                    say("B0 skip (odds unavailable)", rid)
            elif DECIDE_WINDOW[0] <= mins <= DECIDE_WINDOW[1] and not has(con, rid, "B1R"):
                # 締切2〜3分前に判断。ワイド枠は通知し、法則枠は通知せず記録だけする（2026-11-07〜）
                rd, odds, meta = kr.fetch_race(con, r, "B1R")
                if odds and odds["3連単"]:
                    r = con.execute("SELECT * FROM races WHERE race_id=?", (rid,)).fetchone()
                    out = kr.record_rule(con, r, odds, meta)
                    wide = kr.record_wide(con, r, odds, meta) or []
                    if out:
                        picks, cond, m = out
                        say("B1R", r["venue"], r["race_no"], "R", len(picks), "点", cond, "/ B1W", len(wide), "点")
                        show_rule = picks if NOTIFY_RULE else []
                        if show_rule or wide:
                            notify.discord(notify.picks_message(r, kr.ts(r["close_at"])[11:16], m, show_rule, wide))
                            notify.toast(f"競輪 {r['venue']}{r['race_no']}R 締切{kr.ts(r['close_at'])[11:16]}（あと{m:.0f}分）",
                                         " / ".join(f"{p['bet_type']}{p['combo']} {p['odds']}倍" for p in show_rule + wide))
                        else:
                            # 0点のときも一言だけ送る（動いていないのか、買い目がないのかを見分けるため。2026-11-07〜）
                            notify.discord(f"⏭️ {r['venue']} {r['race_no']}R（締切 {kr.ts(r['close_at'])[11:16]}）：見送り（条件に合うワイドなし）")
                        notify.write_today(con, DAY)
            elif not ONLY_RULE and B1_WINDOW[0] <= mins <= B1_WINDOW[1] and not has(con, rid, "B1"):
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
                    if has(con, rid, "B1R"):
                        notify.write_today(con, DAY)
                        msg = notify.result_message(con, rid, phases=None if NOTIFY_RULE else ("B1W",))
                        if msg:
                            notify.discord(msg)
        except Exception:
            say("ERR", rid, traceback.format_exc()[-400:])


def heartbeat(con):
    """1時間ごとの稼働連絡。レースがある時間帯だけ（次の締切まで90分以内、または直前30分以内に締切があったとき）"""
    t = time.time()
    rs = rows(con)
    if not rs or not any(t - 30 * 60 <= r["close_at"] <= t + 90 * 60 for r in rs):
        return
    since = kr.dt.datetime.fromtimestamp(t - 3600, kr.JST).isoformat(timespec="seconds")
    n_race, n_pick = con.execute("""SELECT COUNT(DISTINCT race_id), COALESCE(SUM(stake > 0), 0) FROM predictions
                                    WHERE phase='B1W' AND created_at >= ?""", (since,)).fetchone()
    nxt = [r for r in rs if r["close_at"] > t + 4 * 60]
    msg = f"⏱️ 稼働中 {kr.now():%H:%M}｜この1時間：{n_race}レース判断・ワイド枠の買い目 {n_pick}点"
    if nxt:
        r = nxt[0]
        msg += f"｜次は {r['venue']} {r['race_no']}R（締切 {kr.ts(r['close_at'])[11:16]}）"
    notify.discord(msg)


def morning(con):
    """朝7時以降の最初の1回だけ「おはようございます」を送る（その日の開催・最初の判断・毎日の一覧の置き場所）"""
    if notify.is_quiet():
        return
    con.execute("CREATE TABLE IF NOT EXISTS notices(day TEXT, kind TEXT, PRIMARY KEY(day, kind))")
    if con.execute("SELECT 1 FROM notices WHERE day=? AND kind='morning'", (DAY,)).fetchone():
        return
    rs = rows(con)
    if not rs:
        return
    t = time.time()
    nxt = [r for r in rs if r["close_at"] > t + 4 * 60]
    venues = sorted({r["venue"] for r in rs})
    w = "月火水木金土日"[kr.dt.datetime.strptime(DAY, "%Y%m%d").weekday()]
    msg = [f"☀️ **おはようございます！** {DAY[4:6]}/{DAY[6:]}（{w}）",
           f"🏟️ 今日は **{len(venues)}開催・{len(rs)}レース**", f"　{'・'.join(venues)}"]
    if nxt:
        msg.append(f"⏰ 最初の通知：{nxt[0]['venue']} {nxt[0]['race_no']}R（締切 {kr.ts(nxt[0]['close_at'])[11:16]} の2〜3分前）")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        msg.append(f"📂 前日までの一覧（レース・選手・全オッズ）→ https://github.com/{repo}/releases/tag/tables")
    notify.discord(chr(10).join(msg))
    con.execute("INSERT OR IGNORE INTO notices VALUES(?, 'morning')", (DAY,))
    con.commit()


def export_if_done(con, day):
    """その日の全レースが確定していて、まだ一覧を作っていなければ、レース・選手・全オッズの一覧を作る。
    作ったファイルは out/tables/ に置かれ、GitHub Actions の保存の段階でリリース "tables" にアップロードされる"""
    con.execute("CREATE TABLE IF NOT EXISTS exports(day TEXT PRIMARY KEY, at TEXT)")
    if con.execute("SELECT 1 FROM exports WHERE day=?", (day,)).fetchone():
        return False
    rs = con.execute("SELECT race_id, status FROM races WHERE date=?", (day,)).fetchall()
    if not rs:
        return False
    if not all(con.execute("SELECT 1 FROM payouts WHERE race_id=?", (r[0],)).fetchone() or r[1] == 9 for r in rs):
        return False
    try:
        import export_tables
        paths = export_tables.main(day)
        con.execute("INSERT OR REPLACE INTO exports VALUES(?,?)", (day, kr.now().isoformat(timespec="seconds")))
        con.commit()
        say("tables exported", day, [n for _, n in paths])
        return True
    except Exception:
        say("tables export ERR", traceback.format_exc()[-300:])
        return False


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
    # 前日分の一覧がまだなら作る（回の切り替わりで最終レースの確定を取り逃した日のため）
    export_if_done(con, (kr.dt.datetime.strptime(DAY, "%Y%m%d") - kr.dt.timedelta(days=1)).strftime("%Y%m%d"))
    done = set()
    last_daily = 0
    last_beat = kr.now().strftime("%Y%m%d%H")  # 起動した時間帯は送らない
    while True:
        if time.time() - last_daily > 600 and kr.now().strftime("%Y%m%d") == DAY:
            try:
                say("daily", kr.fetch_daily(con))
            except Exception:
                say("daily ERR", traceback.format_exc()[-300:])
            last_daily = time.time()
        tick(con, done)
        morning(con)
        hb = kr.now().strftime("%Y%m%d%H")
        if hb != last_beat:
            last_beat = hb
            heartbeat(con)
        rs = rows(con)
        if once or (rs and all(r["race_id"] in done or r["status"] == 9 for r in rs)):
            break
        if time.time() - START > MAX_SEC:  # 実行上限（GitHub Actions では1回6時間未満で区切る）
            say("max runtime reached")
            break
        time.sleep(30)
    say("finished")
    keep_awake(False)
    export_if_done(con, DAY)
    # 本日のまとめは、その日の全レースが確定したときだけ送る（途中の区切りでは送らない）
    rs_all = rows(con)
    if rs_all and all(con.execute("SELECT 1 FROM payouts WHERE race_id=?", (r["race_id"],)).fetchone()
                      or r["status"] == 9 for r in rs_all):
        try:
            notify.write_today(con, DAY)
            notify.discord(notify.day_summary(con, DAY))
            m = notify.metrics(con)
            if m:
                notify.discord(m)
            # 日曜日は、その週（月〜日）の週次レポートも送る
            if kr.dt.datetime.strptime(DAY, "%Y%m%d").weekday() == 6:
                import weekly
                notify.discord(weekly.main(DAY))
        except Exception:
            pass
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
