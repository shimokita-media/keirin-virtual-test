"""法則を作るときに使っていない期間（例: 9月）で、法則枠・ワイド枠を確かめる（確定オッズでの事後計算）。
法則の条件は 10/5〜11/5 のデータを見て決めたので、それ以外の期間は「まだ見ていないデータ」になる。
使い方: python validate_holdout.py 20260901 20261004 -> out/holdout_YYYYMMDD_YYYYMMDD.md"""
import os
import sys

import numpy as np
import pandas as pd

import kr


def race_rows(con, d0, d1):
    return con.execute("SELECT * FROM races WHERE date BETWEEN ? AND ? AND race_id IN (SELECT race_id FROM payouts) "
                       "ORDER BY close_at", (d0, d1)).fetchall()


def main(d0, d1):
    import sqlite3
    con = kr.db()
    con.row_factory = sqlite3.Row
    pay = {(r[0], r[1], r[2]): r[3] for r in con.execute(
        "SELECT race_id, bet_type, combo, payout FROM payouts p WHERE race_id IN (SELECT race_id FROM races WHERE date BETWEEN ? AND ?)", (d0, d1))}
    rows = []
    races = race_rows(con, d0, d1)
    for r in races:
        od = {bt: {} for bt in kr.BET_TYPES}
        for bt, cb, o, om, p in con.execute("""SELECT bet_type, combo, odds, odds_max, popularity FROM odds WHERE race_id=? AND phase='POST'
                AND source='winticket' AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase='POST' AND source='winticket')""",
                                            (r["race_id"], r["race_id"])):
            od[bt][cb] = (o, om, p)
        if not od["3連単"]:
            continue
        rule, cond = kr.rule_picks(con, r, od)                                    # 法則枠（レース条件つき・最大5点）
        allx = [e for e in kr.evaluate(od) if e["bet_type"] in kr.RULE_TYPES and e["evc"] >= 1.0]   # 条件なしの元の法則
        wide = sorted([e for e in kr.evaluate(od) if e["bet_type"] == "ワイド" and 6 <= e["odds"] <= 10 and e["evc"] >= 0.85],
                      key=lambda e: -e["evc"])[:5]                               # ワイド枠
        for name, lst in [("法則枠", rule), ("元の法則（条件なし）", allx), ("ワイド枠", wide)]:
            for e in lst:
                rows.append({"race_id": r["race_id"], "date": r["date"], "枠": name, "券種": e["bet_type"],
                             "払戻": pay.get((r["race_id"], e["bet_type"], e["combo"]), 0) / 100})
    d = pd.DataFrame(rows)
    rng = np.random.default_rng(0)
    L = [f"# まだ見ていない期間での検証 {d0}〜{d1}\n",
         f"対象 {len(races)} レース（確定オッズでの事後計算・各100円）。法則の条件は 2026/10/05〜11/05 のデータで決めたもの。\n"]
    out = []
    for name, g in d.groupby("枠", sort=False):
        gg = g.groupby("race_id").agg(r=("払戻", "sum"), n=("払戻", "size"))
        a, b = gg.r.to_numpy(), gg.n.to_numpy()
        idx = rng.integers(0, len(gg), (2000, len(gg)))
        bs = a[idx].sum(1) / b[idx].sum(1)
        days = g.groupby("date").apply(lambda x: x.払戻.sum() / len(x))
        out.append({"枠": name, "レース数": len(gg), "点数": len(g), "的中": int((g.払戻 > 0).sum()),
                    "回収率": f"{g.払戻.sum() / len(g):.0%}", "95%の範囲": f"{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}",
                    "100%以下の確率": f"{(bs <= 1).mean():.1%}", "勝った日": f"{int((days > 1).sum())}/{len(days)}日",
                    "1日の回収率の中央値": f"{days.median():.0%}"})
    L.append(pd.DataFrame(out).to_markdown(index=False))
    L.append("\n券種別")
    t = d.groupby(["枠", "券種"]).agg(点数=("払戻", "size"), 回収率=("払戻", lambda x: f"{x.sum() / len(x):.0%}"))
    L.append(t.to_markdown())
    txt = "\n".join(L)
    open(os.path.join(kr.BASE, "out", f"holdout_{d0}_{d1}.md"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
