"""週次レポート: 直近7日（終了日を含む）の法則枠・ワイド枠を振り返り、前の7日と比べる。
Discord に送り、out/weekly_YYYYMMDD.md に保存する（GitHub Actions では reports/ にコミットされる）。
使い方: python weekly.py [終了日YYYYMMDD]"""
import datetime as dt
import os
import sys

import numpy as np

import kr
import notify


def bets(con, d0, d1, ph):
    """期間 [d0, d1] の確定済みの買い目。(race_id, 券種, 組番, 金額, 参照倍率, 払戻, 最終倍率, 日程, 並び, 時間帯)"""
    rows = con.execute("""
        SELECT p.race_id, p.bet_type, p.combo, p.stake, p.ref_odds,
               COALESCE((SELECT payout FROM payouts y WHERE y.race_id=p.race_id AND y.bet_type=p.bet_type AND y.combo=p.combo), 0),
               (SELECT odds FROM odds o WHERE o.race_id=p.race_id AND o.bet_type=p.bet_type AND o.combo=p.combo
                  AND o.phase='POST' AND o.source='winticket' ORDER BY o.fetched_at DESC LIMIT 1),
               r.cup_id, r.date, r.line_type, r.start_at, r.race_type
        FROM predictions p JOIN races r USING(race_id)
        WHERE p.phase=? AND p.stake>0 AND r.date BETWEEN ? AND ?
          AND EXISTS (SELECT 1 FROM payouts y WHERE y.race_id=p.race_id)
        ORDER BY r.close_at, p.pred_id""", (ph, d0, d1)).fetchall()
    out = []
    for rid, bt, cb, st, ro, pay, fo, cup, date, lt, start, rtype in rows:
        day = "初日" if date == cup[:8] else ("最終日" if "決勝" in (rtype or "") else "中日")
        h = dt.datetime.fromtimestamp(start, kr.JST).hour
        tb = "朝" if h <= 11 else "昼" if h <= 15 else "夕方" if h <= 18 else "ナイター" if h <= 20 else "深夜"
        out.append((rid, bt, cb, st, ro, pay, fo, day, lt or "不明", tb))
    return out


def summary(b):
    if not b:
        return None
    races = {}
    for x in b:
        races.setdefault(x[0], [0, 0])
        races[x[0]][0] += x[3]
        races[x[0]][1] += x[5]
    inv = np.array([v[0] for v in races.values()], float)
    ret = np.array([v[1] for v in races.values()], float)
    idx = np.random.default_rng(0).integers(0, len(inv), (2000, len(inv)))
    bs = ret[idx].sum(1) / inv[idx].sum(1)
    net = np.cumsum(ret - inv)
    dd = (np.maximum.accumulate(np.concatenate([[0], net])) - np.concatenate([[0], net])).max()
    drift = [x[6] / x[4] - 1 for x in b if x[6] and x[4]]
    return {"races": len(races), "bets": len(b), "inv": inv.sum(), "ret": ret.sum(), "roi": ret.sum() / inv.sum(),
            "lo": np.percentile(bs, 2.5), "hi": np.percentile(bs, 97.5), "dd": dd, "hits": sum(1 for x in b if x[5] > 0),
            "drift": np.median(drift) if drift else None}


def final_value(con, b):
    """最終の倍率で計算し直した割安度（1.0以上の割合と中央値）"""
    vals = []
    for rid in {x[0] for x in b}:
        od = {bt: {} for bt in kr.BET_TYPES}
        for bt, cb, o in con.execute("""SELECT bet_type, combo, odds FROM odds WHERE race_id=? AND phase='POST' AND source='winticket'
                AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase='POST' AND source='winticket')""", (rid, rid)):
            od[bt][cb] = (o, None, None)
        if not od["3連単"]:
            continue
        ev = {(e["bet_type"], e["combo"]): e["evc"] for e in kr.evaluate(od)}
        vals += [ev[(x[1], x[2])] for x in b if x[0] == rid and (x[1], x[2]) in ev]
    return (np.median(vals), np.mean(np.array(vals) >= 1)) if vals else (None, None)


def breakdown(b, i, name):
    g = {}
    for x in b:
        g.setdefault(x[i], [0, 0, 0])
        g[x[i]][0] += x[3]
        g[x[i]][1] += x[5]
        g[x[i]][2] += 1
    return f"　{name}: " + " / ".join(f"{k} {v[1] / v[0]:.0%}({v[2]}点)" for k, v in sorted(g.items(), key=lambda kv: -kv[1][2]))


def main(end=None):
    end = end or kr.now().strftime("%Y%m%d")
    e = dt.datetime.strptime(end, "%Y%m%d")
    d0, d1 = (e - dt.timedelta(days=6)).strftime("%Y%m%d"), end
    p0, p1 = (e - dt.timedelta(days=13)).strftime("%Y%m%d"), (e - dt.timedelta(days=7)).strftime("%Y%m%d")
    con = kr.db()
    L = [f"【週次レポート】{d0[4:6]}/{d0[6:]}〜{d1[4:6]}/{d1[6:]}（全て仮想記録）"]
    for ph, label in notify.LABEL.items():
        b = bets(con, d0, d1, ph)
        s = summary(b)
        if not s:
            L.append(f"▼{label}: この週の確定した買い目なし")
            continue
        prev = summary(bets(con, p0, p1, ph))
        fv_med, fv_ok = final_value(con, b)
        L.append(f"▼{label}（{s['races']}レース・{s['bets']}点・的中{s['hits']}）")
        L.append(f"　回収率 {s['roi']:.0%}（95%の範囲 {s['lo']:.0%}〜{s['hi']:.0%}）／ 損益 {int(s['ret'] - s['inv']):+,}円 ／ 最大のへこみ -{int(s['dd']):,}円")
        if prev:
            L.append(f"　前の週: 回収率 {prev['roi']:.0%}（{prev['races']}レース）→ 今週 {s['roi'] - prev['roi']:+.0%}")
        if s["drift"] is not None:
            L.append(f"　買った時→最終の倍率の変化: 中央値 {s['drift']:+.0%}")
        if fv_med is not None:
            L.append(f"　最終の倍率での割安度: 中央値 {fv_med:.2f}、1.0以上は {fv_ok:.0%}（ここが増えるほど本物）")
        L.append(breakdown(b, 1, "券種別"))
        L.append(breakdown(b, 7, "日程別"))
        L.append(breakdown(b, 8, "並び別"))
        L.append(breakdown(b, 9, "時間帯別"))
    for x in (notify.timing_report(con, "B1W", since=d0), notify.subgroup_report(con, "B1W", since=d0)):
        if x:
            L.append(x)
    L.append("※ 1週間分は点数が少なく、回収率は運で大きくぶれます。判断は「最終の倍率での割安度」と数週間の流れで。")
    txt = chr(10).join(L)
    os.makedirs(os.path.join(kr.BASE, "out"), exist_ok=True)
    open(os.path.join(kr.BASE, "out", f"weekly_{end}.md"), "w", encoding="utf-8").write(txt)
    return txt


if __name__ == "__main__":
    t = main(sys.argv[1] if len(sys.argv) > 1 else None)
    print(t)
    if "--send" in sys.argv:
        notify.discord(t)
