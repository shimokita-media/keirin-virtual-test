"""全券種（3連単・3連複・2車単・2車複・ワイド）について、3連単から見た割安度 × 倍率の帯ごとに
回収率を月別に出す（確定オッズでの事後計算・各100円・ガールズ除外）。
使い方: python bettype_scan.py 開始 終了 -> out/bettype_scan_{開始}_{終了}.md"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

import kr

BANDS = {"3連単": [0, 20, 50, 100, 300, 1e9], "3連複": [0, 10, 30, 100, 1e9], "2車単": [0, 5, 10, 20, 50, 1e9],
         "2車複": [0, 5, 10, 20, 1e9], "ワイド": [0, 3, 6, 10, 20, 1e9]}


def build(d0, d1):
    cache = os.path.join(kr.BASE, "out", f"bettype_scan_{d0}_{d1}.pkl")
    if os.path.exists(cache):
        return pd.read_pickle(cache)
    con = kr.db()
    con.row_factory = sqlite3.Row
    pay = {(r[0], r[1], r[2]): r[3] for r in con.execute(
        "SELECT p.race_id, p.bet_type, p.combo, p.payout FROM payouts p JOIN races r USING(race_id) WHERE r.date BETWEEN ? AND ?", (d0, d1))}
    rows = []
    for r in con.execute("""SELECT race_id, date, class FROM races WHERE date BETWEEN ? AND ? AND class!='L級'
                            AND race_id IN (SELECT race_id FROM payouts) ORDER BY close_at""", (d0, d1)).fetchall():
        od = {bt: {} for bt in kr.BET_TYPES}
        for bt, cb, o, om, p in con.execute("""SELECT bet_type, combo, odds, odds_max, popularity FROM odds WHERE race_id=? AND phase='POST'
                AND source='winticket' AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase='POST' AND source='winticket')""",
                                            (r["race_id"], r["race_id"])):
            od[bt][cb] = (o, om, p)
        if not od["3連単"]:
            continue
        for e in kr.evaluate(od):
            if e["evc"] < 0.85:
                continue
            rows.append((r["race_id"], r["date"][:6], e["bet_type"], e["odds"], e["evc"],
                         pay.get((r["race_id"], e["bet_type"], e["combo"]), 0) / 100))
    df = pd.DataFrame(rows, columns=["race_id", "月", "券種", "倍率", "割安度", "払戻"])
    df.to_pickle(cache)
    return df


def main(d0, d1):
    df = build(d0, d1)
    df["割安"] = pd.cut(df.割安度, [0.85, 1.0, 1.2, 1e9], labels=["0.85〜1.0", "1.0〜1.2", "1.2以上"], include_lowest=True)
    rng = np.random.default_rng(0)
    L = [f"# 全券種の割安度×倍率（{d0}〜{d1}・確定オッズ・各100円・ガールズ除外）\n",
         "◎=95%範囲の下限も100%超、かつ7か月中6か月以上で100%超。200点未満は省略。\n",
         "| 券種 | 倍率 | 割安度 | 点数 | 回収率 | 95%の範囲 | 100%超の月 | 判定 |", "|---|---|---|---|---|---|---|---|"]
    for bt, bands in BANDS.items():
        d = df[df.券種 == bt].copy()
        d["帯"] = pd.cut(d.倍率, bands)
        for (band, w), g in d.groupby(["帯", "割安"], observed=True):
            if len(g) < 200:
                continue
            gg = g.groupby("race_id").agg(r=("払戻", "sum"), n=("払戻", "size"))
            a, b = gg.r.to_numpy(), gg.n.to_numpy()
            i = rng.integers(0, len(gg), (1000, len(gg)))
            bs = a[i].sum(1) / b[i].sum(1)
            m = g.groupby("月").払戻.mean()
            lo, hi = np.percentile(bs, [2.5, 97.5])
            ok = "◎" if lo > 1 and (m > 1).sum() >= len(m) - 1 else ("×" if g.払戻.mean() < 0.8 else "")
            lab = f"{band.left:g}〜{band.right:g}倍" if band.right < 1e8 else f"{band.left:g}倍以上"
            L.append(f"| {bt} | {lab} | {w} | {len(g)} | {g.払戻.mean():.0%} | {lo:.0%}〜{hi:.0%} | {(m > 1).sum()}/{len(m)} | {ok} |")
    txt = "\n".join(L)
    open(os.path.join(kr.BASE, "out", f"bettype_scan_{d0}_{d1}.md"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
