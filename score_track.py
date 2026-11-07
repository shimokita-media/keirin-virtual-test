"""点数方式と「3番手絡み」の追跡（11月以降・ガールズ除く・各100円の事後計算。買い目の記録には触らない）。
点数（各1点）：同じライン／3番手絡み／割安度0.913以上／人気6〜10番／そのレースで2点以上。
A. 最終オッズで選んだ場合（実際には買えない。傾向の確認用）
B. 締切前のオッズ（判断時の記録 B1R、なければ締切5分前 T5）で選んだ場合（実際に近い）
出力: out/score_track.md（GitHub では reports/ に保存）
使い方: python score_track.py [開始日=20261101]"""
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

import kr

CLEAN_FROM = "20261108"  # 点数方式を決めた後に出てきたデータ（ここからが本当の確認）


def picks(od, lines):
    ev = kr.evaluate(od)
    pk = sorted([e for e in ev if e["bet_type"] == "ワイド" and 6 <= e["odds"] <= 10 and e["evc"] >= 0.85],
                key=lambda e: -e["evc"])[:5]
    lid = {v: i for i, l in enumerate(lines) for v in l}
    pos = {v: k for l in lines for k, v in enumerate(l)}
    out = []
    for e in pk:
        a, b = map(int, e["combo"].split("-"))
        same = a in lid and lid.get(a) == lid.get(b)
        third = same and 2 in (pos.get(a), pos.get(b))
        sc = int(same) + int(third) + int(e["evc"] >= 0.913) + int((e["pop"] or 99) <= 10) + int(len(pk) >= 2)
        out.append((e["combo"], e["odds"], sc, third))
    return out


def picks3(od, lines):
    """3〜20倍・割安度0.85以上で、同じラインの3番手を含むワイド（1レースの点数制限なし）"""
    pos = {v: k for l in lines for k, v in enumerate(l)}
    lid = {v: i for i, l in enumerate(lines) for v in l}
    out = []
    for e in kr.evaluate(od):
        if e["bet_type"] != "ワイド" or not (3 <= e["odds"] <= 20) or e["evc"] < 0.85:
            continue
        a, b = map(int, e["combo"].split("-"))
        if a in lid and lid.get(a) == lid.get(b) and 2 in (pos.get(a), pos.get(b)):
            out.append((e["combo"], e["odds"], 0, True))
    return out


def load(con, rid, phase):
    fa = con.execute("SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase=? AND source='winticket'", (rid, phase)).fetchone()[0]
    if not fa:
        return None
    od = {bt: {} for bt in kr.BET_TYPES}
    for bt, cb, o, om, p in con.execute("SELECT bet_type, combo, odds, odds_max, popularity FROM odds WHERE race_id=? AND phase=? AND fetched_at=? AND source='winticket'",
                                        (rid, phase, fa)):
        od[bt][cb] = (o, om, p)
    return od if od["3連単"] and od["ワイド"] else None


def build(con, d0):
    pay = {(a, b): p for a, b, p in con.execute("SELECT race_id, combo, payout FROM payouts WHERE bet_type='ワイド'")}
    rows = []
    for rid, date, lj in con.execute("""SELECT race_id, date, line_json FROM races WHERE date>=? AND class!='L級'
                                        AND race_id IN (SELECT race_id FROM payouts) ORDER BY close_at""", (d0,)).fetchall():
        lines = [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(lj if isinstance(lj, str) else "[]")]
        fin = load(con, rid, "POST")
        for kind, od in (("A", fin), ("B", load(con, rid, "B1R") or load(con, rid, "T5"))):
            if not od:
                continue
            for k2, fn in ((kind, picks), (kind + "3", picks3)):
                for cb, o, sc, third in fn(od, lines):
                    fo = fin["ワイド"].get(cb, (None,))[0] if fin else None
                    rows.append(dict(kind=k2, race_id=rid, date=date, combo=cb, odds=o, fin=fo, 点=sc, 三番手=third,
                                     ret=pay.get((rid, cb), 0) / 100))
    return pd.DataFrame(rows)


def line(g):
    if len(g) == 0:
        return "| 0 | − | − |"
    rng = np.random.default_rng(0)
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size"))
    a, b = gg.r.to_numpy(), gg.n.to_numpy()
    i = rng.integers(0, len(gg), (1000, len(gg)))
    bs = a[i].sum(1) / b[i].sum(1)
    return f"| {len(g)} | {g.ret.mean():.0%}（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}） | {(g.ret > 0).mean():.0%}（{int((g.ret > 0).sum())}本） |"


def main(d0="20261101"):
    con = sqlite3.connect(os.path.join(kr.BASE, "keirin.sqlite"))
    df = build(con, d0)
    L = [f"# 点数方式と3番手絡みの追跡（{d0}〜・ガールズ除く・各100円の事後計算）\n",
         "点数（各1点）：同じライン／3番手絡み／割安度0.913以上／人気6〜10番／そのレースで2点以上。",
         f"{CLEAN_FROM} 以降は、点数方式を決めた後に出てきたデータ（本当の確認）。カッコ内は運のブレを考えた95%の範囲。\n"]
    for kind, title in (("B", "B. 締切前のオッズで選んだ場合（判断時の記録、なければ締切5分前）← 実際に近い"),
                        ("A", "A. 最終オッズで選んだ場合（実際には買えない・傾向の確認用）")):
        d = df[df.kind == kind] if len(df) else df
        L.append(f"\n## {title}\n")
        if not len(d):
            L.append("（まだデータなし）")
            continue
        for lab, dd in ((f"{d0}〜", d), (f"{CLEAN_FROM}〜", d[d.date >= CLEAN_FROM])):
            L += [f"\n**{lab}**（{dd.date.nunique()}日）\n", "| 買う条件 | 点数 | 回収率 | 的中率 |", "|---|---|---|---|"]
            for name, m in (("全部", dd.index == dd.index), ("2点以上", dd.点 >= 2), ("3点以上", dd.点 >= 3),
                            ("4点以上", dd.点 >= 4), ("3番手絡みだけ", dd.三番手)):
                L.append(f"| {name} " + line(dd[m]))
        if kind == "B" and d.fin.notna().any():
            x = d[d.fin.notna()]
            L.append(f"\n選んだ後、最終までの倍率の変化（中央）：全部 {(x.fin / x.odds - 1).median():+.0%}"
                     f"／3点以上 {(x[x.点 >= 3].fin / x[x.点 >= 3].odds - 1).median():+.0%}"
                     f"／3番手絡み {(x[x.三番手].fin / x[x.三番手].odds - 1).median():+.0%}")
        g = d.groupby("date").apply(lambda g: pd.Series({"全部": f"{len(g)}点 {g.ret.mean():.0%}",
                                                          "3点以上": f"{(g.点 >= 3).sum()}点 {g[g.点 >= 3].ret.mean():.0%}" if (g.点 >= 3).any() else "−",
                                                          "3番手絡み": f"{g.三番手.sum()}点 {g[g.三番手].ret.mean():.0%}" if g.三番手.any() else "−"}))
        L += ["\n日ごと\n", g.to_markdown()]
    # D. 本命候補：3〜20倍・同じラインの3番手（2〜11月の最終オッズで118%、全10か月105%以上）
    L.append("\n## D. 本命候補：3〜20倍・割安度0.85以上・同じラインの3番手を含むワイド（点数制限なし）\n")
    L.append("2〜11月の最終オッズでは118%（2〜4月116%・5〜11月118%）。締切前で選んだ場合が本当の確認。\n")
    for kind, title in (("B3", "締切前のオッズで選んだ場合 ← 実際に近い"), ("A3", "最終オッズで選んだ場合（参考）")):
        d = df[df.kind == kind] if len(df) else df
        L.append(f"\n**{title}**\n")
        if not len(d):
            L.append("（まだデータなし）")
            continue
        L += ["| 範囲 | 点数 | 回収率 | 的中率 |", "|---|---|---|---|"]
        for name, m in ((f"{d0}〜 全部", d.index == d.index), (f"{d0}〜 8〜10倍（参考の帯）", d.odds.between(8, 10)),
                        (f"{CLEAN_FROM}〜 全部", d.date >= CLEAN_FROM), (f"{CLEAN_FROM}〜 8〜10倍", (d.date >= CLEAN_FROM) & d.odds.between(8, 10))):
            L.append(f"| {name} " + line(d[m]))
        if kind == "B3" and d.fin.notna().any():
            x = d[d.fin.notna()]
            L.append(f"\n選んだ後、最終までの倍率の変化（中央）：{(x.fin / x.odds - 1).median():+.0%}")
        g = d.groupby("date").apply(lambda g: f"{len(g)}点 {g.ret.mean():.0%}")
        L += ["\n日ごと：" + " ／ ".join(f"{k[4:6]}/{k[6:]} {v}" for k, v in g.items())]
    # C. 実際に通知したワイド枠を、通知に出した「新しい点数」ごとに（2026-11-08〜、判断時に記録した点数）
    live = pd.read_sql("""SELECT p.race_id, r.date, p.bet_rating,
        COALESCE((SELECT payout FROM payouts y WHERE y.race_id=p.race_id AND y.bet_type='ワイド' AND y.combo=p.combo), 0) / 100.0 AS ret
        FROM predictions p JOIN races r USING(race_id) WHERE p.phase='B1W' AND p.stake>0 AND p.bet_rating LIKE '%点%'
        AND EXISTS (SELECT 1 FROM payouts y WHERE y.race_id=p.race_id)""", con)
    L.append("\n## C. 実際に通知したワイド枠 × 新しい点数（判断時に記録した点数・ガールズ込み）\n")
    if len(live):
        live["点"] = live.bet_rating.str.extract(r"点(\d)").astype(int)
        L += ["| 買う条件 | 点数 | 回収率 | 的中率 |", "|---|---|---|---|"]
        for name, m in (("全部", live.点 >= 0), ("2点以上", live.点 >= 2), ("3点以上", live.点 >= 3), ("4点以上", live.点 >= 4)):
            L.append(f"| {name} " + line(live[m]))
        L.append("\n点ごと：" + " ／ ".join(f"{k}点 {len(g)}点 {g.ret.mean():.0%}" for k, g in live.groupby("点")))
    else:
        L.append("（まだデータなし）")
    txt = "\n".join(L)
    os.makedirs(os.path.join(kr.BASE, "out"), exist_ok=True)
    open(os.path.join(kr.BASE, "out", "score_track.md"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main(*sys.argv[1:2])
