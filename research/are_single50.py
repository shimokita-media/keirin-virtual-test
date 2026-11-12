"""「荒れ予想×単騎の選手が1着」系を、レースごとの的中率50%まで広げると回収率はどうなるか（探索期間・全部の3連単の最終オッズ）"""
import numpy as np, pandas as pd
S = "C:/Users/take0/.claude/keirin/out/are_work/"
race, _ = pd.read_pickle(S + "are_cache.pkl"); A, R, P = pd.read_pickle(S + "multi_cache.pkl"); del A
O = pd.read_pickle(S + "tri_odds.pkl")
race["half"] = np.where(race.date < "20251226", "前", "後")
sg = R[R.single == True][["race_id", "num", "style"]]
rs = race[(race.fav >= 15)].merge(sg.groupby("race_id").num.apply(set).rename("sg").reset_index(), on="race_id")
print("一番人気15倍以上で単騎の選手がいるレース", len(rs))
O = O[O.race_id.isin(rs.race_id)].merge(rs[["race_id", "sg", "win", "pay", "half"]], on="race_id")
cb = O.combo.str.split("-", expand=True).astype(int)
O["a"], O["b"], O["c"] = cb[0], cb[1], cb[2]
O["s1"] = [a in s for a, s in zip(O.a, O.sg)]; O["s2"] = [b in s for b, s in zip(O.b, O.sg)]; O["s3"] = [c in s for c, s in zip(O.c, O.sg)]
O["hit"] = O.combo == O.win; O["inv"] = 1 / O.odds
def ev(sel, lab, dutch=False):
    if dutch:
        g = sel.assign(hv=sel.inv * sel.hit).groupby("race_id").agg(si=("inv", "sum"), hi=("hv", "sum"), n=("inv", "size")).join(rs.set_index("race_id")[["pay", "half"]])
        g["ret"] = g.hi / g.si * g.pay / 100; g["cost"] = 1.0
    else:
        g = sel.assign(r=np.where(sel.hit, sel.odds, 0)).groupby("race_id").agg(ret=("r", "sum"), cost=("r", "size"), n=("r", "size")).join(rs.set_index("race_id")[["half"]])
    f = lambda x: round(100 * x.ret.sum() / x.cost.sum(), 1)
    return (lab, len(g), round(g.n.mean(), 1), round(100 * (g.ret > 0).mean(), 1), round(100 * (g.ret >= g.cost).mean(), 1), f(g), f(g[g.half == "前"]), f(g[g.half == "後"]))
rows = [ev(O[O.s1], "単騎の選手を1着に固定・総流し"), ev(O[O.s1 | O.s2], "単騎の選手が1着か2着"), ev(O[O.s1 | O.s2 | O.s3], "単騎の選手が3着以内（その選手を含む目を全部）")]
O = O.sort_values(["race_id", "odds"]); O["cum"] = O.groupby("race_id").inv.cumsum()
for T in [1.25, 1.5, 1.6]:
    rows.append(ev(O[1 / O.cum >= T], f"人気順に合成オッズ{T}倍まで・金額配分", dutch=True))
X = O[O.s1 | O.s2 | O.s3].copy(); X["cum"] = X.groupby("race_id").inv.cumsum()
for T in [1.0, 1.25, 1.5]:
    rows.append(ev(X[1 / X.cum >= T], f"単騎を含む目を人気順に合成{T}倍まで・金額配分", dutch=True))
pd.set_option("display.width", 220)
print(pd.DataFrame(rows, columns=["買い方", "レース数", "1レースの点数", "当たり%", "元が取れた%", "回収率%", "前", "後"]).to_string())
