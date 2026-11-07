"""ワイド枠の買い目を、出走表の B（バック回数）・S（スタート取り回数）で分けて成績を見る（確定オッズでの事後計算・各100円）。
使い方: python sb_analysis.py 開始 終了 [ガールズを含める=0]"""
import json
import sqlite3
import sys

import numpy as np
import pandas as pd

import kr


def build(d0, d1, girls=False):
    con = kr.db()
    con.row_factory = sqlite3.Row
    pay = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT p.race_id, p.combo, p.payout FROM payouts p JOIN races r USING(race_id) WHERE p.bet_type='ワイド' AND r.date BETWEEN ? AND ?", (d0, d1))}
    rows = []
    for r in con.execute("""SELECT * FROM races WHERE date BETWEEN ? AND ? AND race_id IN (SELECT race_id FROM payouts)
                            ORDER BY close_at""", (d0, d1)).fetchall():
        if not girls and r["class"] == "L級":
            continue
        ent = {x["number"]: x for x in con.execute("SELECT * FROM entries WHERE race_id=? AND absent=0", (r["race_id"],))}
        if not ent or any(x["n_back"] is None for x in ent.values()):
            continue
        od = {bt: {} for bt in kr.BET_TYPES}
        for bt, cb, o, om, p in con.execute("""SELECT bet_type, combo, odds, odds_max, popularity FROM odds WHERE race_id=? AND phase='POST'
                AND source='winticket' AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase='POST' AND source='winticket')""",
                                            (r["race_id"], r["race_id"])):
            od[bt][cb] = (o, om, p)
        if not od["3連単"]:
            continue
        picks = sorted([e for e in kr.evaluate(od) if e["bet_type"] == "ワイド" and 6 <= e["odds"] <= 10 and e["evc"] >= 0.85],
                       key=lambda e: -e["evc"])[:5]
        if not picks:
            continue
        lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(r["line_json"] or "[]")]
        lid = {n: i for i, l in enumerate(lines) for n in l}
        pos = {n: k for l in lines for k, n in enumerate(l)}
        B = {n: x["n_back"] or 0 for n, x in ent.items()}
        S = {n: x["n_standing"] or 0 for n, x in ent.items()}
        leaders = [l[0] for l in lines if len(l) >= 2 and l[0] in B]
        lead_b = sorted((B[n] for n in leaders), reverse=True)
        top_b_no = max(B, key=B.get)
        n_senko = sum(1 for n in leaders if B[n] >= 5)  # B5回以上の先頭（先行型）の数
        for e in picks:
            a, b = map(int, e["combo"].split("-"))
            same = lid.get(a) is not None and lid.get(a) == lid.get(b)
            third = same and 2 in (pos.get(a), pos.get(b))
            # 2人が属するラインの先頭のB
            lb = [B[lines[lid[n]][0]] for n in (a, b) if lid.get(n) is not None and lines[lid[n]][0] in B]
            rows.append({"race_id": r["race_id"], "月": r["date"][:6], "払戻": pay.get((r["race_id"], e["combo"]), 0) / 100,
                         "同じライン": same, "3番手絡み": third,
                         "2人のB合計": B.get(a, 0) + B.get(b, 0), "2人のB最大": max(B.get(a, 0), B.get(b, 0)),
                         "ライン先頭のB": max(lb) if lb else 0,
                         "レース最多Bの選手を含む": top_b_no in (a, b),
                         "レース最多Bのラインに乗る": any(lid.get(n) is not None and lid.get(n) == lid.get(top_b_no) for n in (a, b)),
                         "先行型の先頭の数": n_senko, "B1位と2位の差": (lead_b[0] - lead_b[1]) if len(lead_b) >= 2 else 99,
                         "2人のS合計": S.get(a, 0) + S.get(b, 0)})
    return pd.DataFrame(rows)


def show(df, col, bins=None, labels=None):
    s = pd.cut(df[col], bins, labels=labels, include_lowest=True) if bins else df[col]
    rng = np.random.default_rng(0)
    print(f"\n## {col}")
    for k, g in df.groupby(s, observed=True):
        if len(g) < 40:
            continue
        gg = g.groupby("race_id").agg(r=("払戻", "sum"), n=("払戻", "size"))
        a, b = gg.r.to_numpy(), gg.n.to_numpy()
        i = rng.integers(0, len(gg), (1000, len(gg)))
        bs = a[i].sum(1) / b[i].sum(1)
        print(f"  {k}: {len(g)}点 回収率{g.払戻.sum() / len(g):.0%} [{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}] 的中率{(g.払戻 > 0).mean():.0%}")


if __name__ == "__main__":
    df = build(sys.argv[1], sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == "1")
    print(f"対象 {df.race_id.nunique()} レース・{len(df)} 点・回収率 {df.払戻.sum() / len(df):.0%}")
    show(df, "2人のB合計", [0, 0.5, 3, 7, 99], ["0", "1〜3", "4〜7", "8以上"])
    show(df, "2人のB最大", [0, 0.5, 3, 7, 99], ["0", "1〜3", "4〜7", "8以上"])
    show(df, "ライン先頭のB", [0, 0.5, 3, 7, 99], ["0", "1〜3", "4〜7", "8以上"])
    show(df, "レース最多Bの選手を含む")
    show(df, "レース最多Bのラインに乗る")
    show(df, "先行型の先頭の数")
    show(df, "B1位と2位の差", [-1, 1, 4, 98, 99], ["0〜1（互角）", "2〜4", "5以上（1人が抜けている）", "先頭が1人"])
    show(df, "2人のS合計", [0, 0.5, 3, 99], ["0", "1〜3", "4以上"])
    t = df[df["3番手絡み"]]
    print("\n# 同じラインで3番手が絡むワイドだけ")
    show(t, "ライン先頭のB", [0, 0.5, 3, 7, 99], ["0", "1〜3", "4〜7", "8以上"])
    show(t, "レース最多Bのラインに乗る")
    show(t, "先行型の先頭の数")
    df.to_pickle(f"out/sb_picks_{sys.argv[1]}_{sys.argv[2]}.pkl")
