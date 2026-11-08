"""3連単枠が出たレースで、買い方（組み方）を比べる。払戻は確定の払戻表（3連単・3連複）、最終オッズの成績"""
import sqlite3, itertools, numpy as np, pandas as pd
exec(open("robust.py", encoding="utf-8").read().split("def per(d)")[0].replace('pd.read_pickle(K + "fresh2/tri.pkl")]', 'pd.read_pickle(K + "fresh2/tri.pkl"), pd.read_pickle(K + "fresh3/tri.pkl")]'))
TB = TB[TB.date <= "20250911"].copy() if False else TB
c = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = TB.race_id.unique().tolist(); pay = []
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900]))
    pay.append(pd.read_sql(f"SELECT race_id, bet_type, combo, payout FROM payouts WHERE bet_type IN ('3連単','3連複','2車単','2車複','ワイド') AND race_id IN ({q})", c, params=ids[i:i+900]))
pay = pd.concat(pay).drop_duplicates(["race_id", "bet_type", "combo"]); PD = {(r, b, x): p / 100 for r, b, x, p in pay.itertuples(index=False)}
TB["per"] = np.where(TB.date.between("20250530", "20250911"), "未使用", "探す")
top = TB.sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(1).set_index("race_id")
rows = []
for rid, g in TB.groupby("race_id"):
    t = top.loc[rid]; a, b, d = map(int, t.combo.split("-")); per = t.per
    trio = "-".join(map(str, sorted((a, b, d))))
    R = lambda bt, cb: PD.get((rid, bt, cb), 0.0)
    S = {
     "今の3連単枠（最大6点）": [R("3連単", x) for x in g.combo],
     "一番の目だけ（3連単1点）": [R("3連単", t.combo)],
     "一番の目＋2-3着入替（2点）": [R("3連単", t.combo), R("3連単", f"{a}-{d}-{b}")],
     "一番の目＋1-2着入替（2点）": [R("3連単", t.combo), R("3連単", f"{b}-{a}-{d}")],
     "1・2着は順不同、3着固定（2点）": [R("3連単", f"{a}-{b}-{d}"), R("3連単", f"{b}-{a}-{d}")],
     "1着固定・2-3着順不同（2点）": [R("3連単", f"{a}-{b}-{d}"), R("3連単", f"{a}-{d}-{b}")],
     "同じ3人の3連単ボックス（6点）": [R("3連単", "-".join(map(str, p))) for p in itertools.permutations((a, b, d))],
     "同じ3人の3連複（1点）": [R("3連複", trio)],
     "1-2着の2車単（1点）": [R("2車単", f"{a}-{b}")],
     "1-2着の2車複（1点）": [R("2車複", "-".join(map(str, sorted((a, b)))))],
     "3人のワイド3点": [R("ワイド", "-".join(map(str, sorted(p)))) for p in itertools.combinations((a, b, d), 2)],
    }
    for k, v in S.items(): rows.append((k, per, rid, len(v), sum(v)))
D = pd.DataFrame(rows, columns=["買い方", "per", "race_id", "n", "r"])
def st(g):
    i = np.random.default_rng(0).integers(0, len(g), (1000, len(g))); bs = g.r.to_numpy()[i].sum(1) / g.n.to_numpy()[i].sum(1)
    hr = (g.r > 0).mean()
    return f"{g.r.sum()/g.n.sum():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 当たるレース{hr:.0%}"
print(f"3連単枠が出たレース {D.race_id.nunique()}（探す {D[D.per=='探す'].race_id.nunique()}・未使用 {D[D.per=='未使用'].race_id.nunique()}）")
print("| 買い方 | 1レースの点数 | 探す | 未使用（25/5/30〜9/11） |"); print("|---|---|---|---|")
for k in D.買い方.unique():
    g = D[D.買い方 == k]; print(f"| {k} | {g.n.mean():.1f} | {st(g[g.per=='探す'])} | {st(g[g.per=='未使用'])} |")
