"""法則枠の買い目を、Windows の通知と「今日の買い目」ファイル（デスクトップ）で知らせる。"""
import base64
import json
import os
import sqlite3
import subprocess
import sys

import kr
import requests

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")


QUIET_HOURS = (0, 7)  # 0時〜7時は Discord に送らない（2026-11-07〜）


def is_quiet():
    return QUIET_HOURS[0] <= kr.now().hour < QUIET_HOURS[1]


def discord(text):
    """環境変数 KEIRIN_DISCORD_WEBHOOK（GitHub のシークレット）に設定された Discord に送る。未設定なら何もしない。
    失敗したら最大3回やり直し、それでも失敗したら内容をログに残す"""
    url = os.environ.get("KEIRIN_DISCORD_WEBHOOK")
    if not url:
        return
    if is_quiet():
        print(kr.now().strftime("%H:%M:%S"), "quiet hours, not sent:", text.splitlines()[0] if text else "", flush=True)
        return
    import time as _t
    for i in range(0, len(text), 1900):  # Discord は1通2000文字まで
        part = text[i:i + 1900]
        for attempt in range(3):
            try:
                r = requests.post(url, json={"content": part}, timeout=15)
                if r.status_code in (200, 204):
                    print(kr.now().strftime("%H:%M:%S"), "discord sent:", part.splitlines()[0], flush=True)
                    break
                wait = float(r.json().get("retry_after", 2)) if r.status_code == 429 else 2
                print(kr.now().strftime("%H:%M:%S"), "discord status", r.status_code, "retry", flush=True)
                _t.sleep(min(wait, 10))
            except Exception as e:
                print(kr.now().strftime("%H:%M:%S"), "discord error", repr(e)[:200], flush=True)
                _t.sleep(2)
        else:
            print(kr.now().strftime("%H:%M:%S"), "discord FAILED:", part.splitlines()[0], flush=True)


LABEL = {"B1R": "法則枠", "B1W": "ワイド枠"}


def result_message(con, rid, phases=None):
    """法則枠・ワイド枠で買い目があったレースの結果を1通にまとめる（枠ごとに損益を出す）"""
    r = con.execute("SELECT venue, race_no FROM races WHERE race_id=?", (rid,)).fetchone()
    res = [x[0] for x in con.execute("SELECT number FROM results WHERE race_id=? AND rank BETWEEN 1 AND 3 ORDER BY rank", (rid,))]
    if not res:
        return None
    out = [f"【結果】{r[0]}{r[1]}R 着順 {'-'.join(map(str, res))}"]
    for ph, label in LABEL.items():
        if phases and ph not in phases:
            continue
        buys = con.execute("SELECT bet_type, combo FROM predictions WHERE race_id=? AND phase=? AND stake>0", (rid, ph)).fetchall()
        if not buys:
            continue
        lines, ret = [], 0
        for bt, cb in buys:
            p = con.execute("SELECT payout FROM payouts WHERE race_id=? AND bet_type=? AND combo=?", (rid, bt, cb)).fetchone()
            ret += p[0] if p else 0
            lines.append(f"{bt}{cb} {'◎ ' + format(p[0], ',') + '円' if p else '×'}")
        out.append(f"▼{label}: " + " / ".join(lines))
        out.append(f"　投資 {len(buys) * 100:,}円 → 払戻 {ret:,}円（{ret - len(buys) * 100:+,}円）")
    return chr(10).join(out) if len(out) > 1 else None


def toast(title, body):
    """Windows 標準のトースト通知（追加インストール不要）。失敗しても処理は止めない"""
    if sys.platform != "win32":
        return
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "''")
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{esc(title)}</text><text>{esc(body)}</text></binding></visual></toast>')
$n = [Windows.UI.Notifications.ToastNotification]::new($x)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($n)
"""
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                       capture_output=True, timeout=20)
    except Exception:
        pass


def write_today(con, day):
    """その日の法則枠・ワイド枠の買い目と結果を、デスクトップの「競輪 今日の買い目.txt」に書き出す"""
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT p.*, r.venue, r.race_no, r.grade FROM predictions p JOIN races r USING(race_id)
                          WHERE p.phase IN ('B1R','B1W') AND r.date=? ORDER BY r.close_at, p.phase, p.pred_id""", (day,)).fetchall()
    L = [f"競輪 今日の買い目 {day[:4]}/{day[4:6]}/{day[6:]}  更新 {kr.now():%H:%M}",
         "※ 仮想記録と同じ内容です。実際に買うかどうか・金額はご自身の判断で、遊べる範囲で。",
         "※ 法則枠: 7車立て・本命の1着見込み30〜60%・二分戦か三分戦のレースで、3連単から見て割安なワイド",
         "※ ワイド枠: 全レースで、倍率6〜10倍・3連単から見た割安度0.85以上のワイド",
         "※ どちらも各100円、締切2〜3分前の倍率で判断（11/6までは4〜7分前）。Discordへの通知はワイド枠のみ", ""]
    tot = {ph: [0, 0] for ph in LABEL}
    by = {}
    for r in rows:
        by.setdefault(r["race_id"], []).append(r)
    for rid, rs in by.items():
        buys = [x for x in rs if x["stake"]]
        if not buys:
            continue
        r0 = rs[0]
        res = [x[0] for x in con.execute("SELECT number FROM results WHERE race_id=? AND rank BETWEEN 1 AND 3 ORDER BY rank", (rid,))]
        head = f"■ {r0['venue']}{r0['race_no']}R（{r0['grade']}） 締切 {r0['close_at'][11:16]}"
        if res:
            head += f"  結果 {'-'.join(map(str, res))}"
        L.append(head)
        for x in buys:
            tot[x["phase"]][0] += x["stake"]
            p = con.execute("SELECT payout FROM payouts WHERE race_id=? AND bet_type=? AND combo=?",
                            (rid, x["bet_type"], x["combo"])).fetchone()
            mark = ""
            if res:
                mark = f"  → 的中 {p[0]:,}円" if p else "  → 外れ"
                tot[x["phase"]][1] += p[0] if p else 0
            L.append(f"   [{LABEL[x['phase']]}] {x['bet_type']} {x['combo']}  {x['ref_odds']}倍  100円{mark}")
        L.append("")
    for ph, (inv, ret) in tot.items():
        L.append(f"{LABEL[ph]}: 買い目 {inv // 100}点 {inv:,}円 ／ 確定分の払戻 {ret:,}円")
    txt = chr(10).join(L)
    for path in (os.path.join(DESKTOP, "競輪 今日の買い目.txt"), os.path.join(kr.BASE, "out", f"today_{day}.txt")):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8-sig").write(txt)
        except Exception:
            pass
    return txt


def metrics(con):
    """法則枠・ワイド枠の累計の指標（回収率以外の見方）を文章にする
    ① 買った倍率→最終の倍率の変化（プラスなら、後から買いが入って倍率が下がった＝先に割安なものを買えた）
    ② 収支が一番良かった時からの最大のへこみ、最大の連敗数（レース単位）
    ③ 累計の回収率と95%の範囲（レース単位のブートストラップ）"""
    import numpy as np
    out = ["【累計の指標】"]
    for ph, label in LABEL.items():
        rows = con.execute("""SELECT p.race_id, p.bet_type, p.combo, p.stake, p.ref_odds, r.close_at,
                   (SELECT payout FROM payouts y WHERE y.race_id=p.race_id AND y.bet_type=p.bet_type AND y.combo=p.combo),
                   (SELECT odds FROM odds o WHERE o.race_id=p.race_id AND o.bet_type=p.bet_type AND o.combo=p.combo
                      AND o.phase='POST' AND o.source='winticket' ORDER BY o.fetched_at DESC LIMIT 1),
                   (SELECT 1 FROM payouts y WHERE y.race_id=p.race_id LIMIT 1)
                   FROM predictions p JOIN races r USING(race_id) WHERE p.phase=? AND p.stake>0 ORDER BY r.close_at""", (ph,)).fetchall()
        rows = [x for x in rows if x[8]]  # 確定済みのみ
        if not rows:
            continue
        clv = [x[7] / x[4] - 1 for x in rows if x[7] and x[4]]
        by, order = {}, []
        for x in rows:
            if x[0] not in by:
                by[x[0]] = [0, 0]
                order.append(x[0])
            by[x[0]][0] += x[3]
            by[x[0]][1] += x[6] or 0
        net = np.cumsum([by[k][1] - by[k][0] for k in order])
        dd = int((np.maximum.accumulate(np.concatenate([[0], net])) - np.concatenate([[0], net])).max())
        streak = cur = 0
        for k in order:
            cur = 0 if by[k][1] > 0 else cur + 1
            streak = max(streak, cur)
        inv = np.array([by[k][0] for k in order], float)
        ret = np.array([by[k][1] for k in order], float)
        rng = np.random.default_rng(0)
        idx = rng.integers(0, len(order), (2000, len(order)))
        bs = ret[idx].sum(1) / inv[idx].sum(1)
        out.append(f"▼{label}（{len(order)}レース・{len(rows)}点）")
        if clv:
            out.append(f"　①-1 買った時→最終の倍率の変化: 中央値 {np.median(clv):+.0%}（{len(clv)}点。マイナスは払戻が減ったという意味）")
        # 最終の倍率で計算し直した割安度（払戻は最終の倍率で決まるので、これが1.0以上なら本当に割安だった）
        fin_evc = []
        for rid in order:
            od = {bt: {} for bt in kr.BET_TYPES}
            for bt, cb, o in con.execute("""SELECT bet_type, combo, odds FROM odds WHERE race_id=? AND phase='POST' AND source='winticket'
                                            AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase='POST' AND source='winticket')""", (rid, rid)):
                od[bt][cb] = (o, None, None)
            if not od["3連単"]:
                continue
            ev = {(e["bet_type"], e["combo"]): e["evc"] for e in kr.evaluate(od)}
            fin_evc += [ev[(x[1], x[2])] for x in rows if x[0] == rid and (x[1], x[2]) in ev]
        if fin_evc:
            fe = np.array(fin_evc)
            out.append(f"　①-2 最終の倍率での割安度: 中央値 {np.median(fe):.2f}（1.0以上だったのは {np.mean(fe >= 1):.0%}。1.0以上が多いほど本物）")
        out.append(f"　② 最大のへこみ {-dd:+,}円 ／ 最大の連敗 {streak}レース ／ 累計損益 {int(net[-1]):+,}円")
        out.append(f"　③ 累計の回収率 {ret.sum() / inv.sum():.0%}（95%の範囲 {np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）")
    extra = [x for x in (timing_report(con, "B1W"), subgroup_report(con, "B1W")) if x]
    out += extra
    return chr(10).join(out) if len(out) > 1 else ""



PHASE_LABEL = [("T10", "10分前"), ("T5", "5分前"), ("B1R", "2〜3分前（判断）"), ("T1", "1分前"), ("POST", "最終")]


def _snapshot(con, rid, ph):
    """そのレースの、ある時点の全組番の倍率（最後に取得したもの）"""
    od = {bt: {} for bt in kr.BET_TYPES}
    for bt, cb, o, om in con.execute("""SELECT bet_type, combo, odds, odds_max FROM odds WHERE race_id=? AND phase=? AND source='winticket'
            AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase=? AND source='winticket')""", (rid, ph, rid, ph)):
        od[bt][cb] = (o, om, None)
    return od


def timing_report(con, ph="B1W", since=None):
    """② 買い目の倍率が、締切10分前→5分前→2〜3分前→1分前→最終でどう動いたか。各時点の割安度1.0以上の割合も"""
    import numpy as np
    q = """SELECT p.race_id, p.combo FROM predictions p JOIN races r USING(race_id) WHERE p.phase=? AND p.stake>0
           AND EXISTS (SELECT 1 FROM payouts y WHERE y.race_id=p.race_id)""" + (" AND r.date>=?" if since else "")
    picks = con.execute(q, (ph, since) if since else (ph,)).fetchall()
    if not picks:
        return ""
    by = {}
    for rid, cb in picks:
        by.setdefault(rid, []).append(cb)
    drift = {k: [] for k, _ in PHASE_LABEL}
    value = {k: [] for k, _ in PHASE_LABEL}
    for rid, cbs in by.items():
        snaps = {k: _snapshot(con, rid, k) for k, _ in PHASE_LABEL}
        fin = snaps["POST"]["ワイド"]
        for k, _ in PHASE_LABEL:
            od = snaps[k]
            if not od["3連単"]:
                continue
            ev = {e["combo"]: e["evc"] for e in kr.evaluate(od) if e["bet_type"] == "ワイド"}
            for cb in cbs:
                if cb in od["ワイド"] and cb in fin and fin[cb][0]:
                    drift[k].append(od["ワイド"][cb][0] / fin[cb][0] - 1)
                if cb in ev:
                    value[k].append(ev[cb] >= 1.0)
    out = [f"② 時点ごとの倍率（{LABEL.get(ph, ph)}の買い目 {len(picks)}点）　※最終と比べて何%高かったか／その時点で割安度1.0以上だった割合"]
    for k, name in PHASE_LABEL:
        if drift[k] or value[k]:
            d = f"{np.median(drift[k]):+.0%}" if drift[k] and k != "POST" else "−"
            v = f"{np.mean(value[k]):.0%}" if value[k] else "−"
            out.append(f"　{name}: 最終より {d} ／ 割安 {v}（{len(value[k])}点）")
    return chr(10).join(out)


def subgroup_report(con, ph="B1W", since=None):
    """③ 過去データで見つけた条件ごとの成績（新しい条件は探さない）"""
    import datetime as _dt
    q = """SELECT p.race_id, p.combo, p.ref_odds, p.bet_rating, r.start_at, r.line_json,
              COALESCE((SELECT payout FROM payouts y WHERE y.race_id=p.race_id AND y.bet_type=p.bet_type AND y.combo=p.combo), 0)
           FROM predictions p JOIN races r USING(race_id) WHERE p.phase=? AND p.stake>0
           AND EXISTS (SELECT 1 FROM payouts y WHERE y.race_id=p.race_id)""" + (" AND r.date>=?" if since else "")
    rows = con.execute(q, (ph, since) if since else (ph,)).fetchall()
    if not rows:
        return ""
    groups = {"同じラインで3番手が絡む": [], "割安度0.95以上": [], "倍率6〜7倍台": [], "朝・夕方のレース": []}
    rest = {k: [] for k in groups}
    for rid, cb, o, tag, start, lj, pay in rows:
        try:
            lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(lj or "[]")]
        except Exception:
            lines = []
        a, b = map(int, cb.split("-"))
        same3 = any(a in l and b in l and (l.index(a) == 2 or l.index(b) == 2) for l in lines)
        try:
            v = float(str(tag).replace("割安度", "").replace("見込み", ""))
        except ValueError:
            v = 0
        h = _dt.datetime.fromtimestamp(start, kr.JST).hour
        flags = {"同じラインで3番手が絡む": same3, "割安度0.95以上": v >= 0.95, "倍率6〜7倍台": (o or 0) < 8,
                 "朝・夕方のレース": h <= 11 or 15 <= h <= 17}
        for k, f in flags.items():
            (groups if f else rest)[k].append(pay)
    roi = lambda x: f"{sum(x) / (len(x) * 100):.0%}（{len(x)}点）" if x else "−"
    out = [f"③ 過去データで見つけた条件の成績（{LABEL.get(ph, ph)}・確定分）　当てはまる ／ 当てはまらない"]
    for k in groups:
        out.append(f"　{k}: {roi(groups[k])} ／ {roi(rest[k])}")
    return chr(10).join(out)
