"""目標：「一番人気15倍以上×単騎の選手がいるレース」で、レースごとの的中率50%以上の買い方を作り、回収率と再現性（2024年）を確かめる。
買い方の中身（しきい値）は探索期間（2025/02〜2026/11）で決め、2024年の表（2023/11〜2025/01）にそのまま当てる。"""
import sqlite3, time, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"
pd.set_option("display.width", 250)
def read_db(ids, path, sql_fn):
    if os.path.exists(path): return pd.read_pickle(path)
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30); out = []
    for i in range(0, len(ids), 100):
        q = ids[i:i + 100]; out.append(sql_fn(c, q)); time.sleep(1.0)
    c.close(); out = pd.concat(out); out.to_pickle(path); return out
def odds_sql(c, q):
    o = pd.read_sql(f"SELECT race_id, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND bet_type='3連単' AND odds>0 AND race_id IN ({','.join('?'*len(q))})", c, params=q)
    return o[o.fetched_at == o.groupby("race_id").fetched_at.transform("max")].drop(columns="fetched_at")
def pay_sql(c, q):
    return pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単' AND race_id IN ({','.join('?'*len(q))})", c, params=q)
# --- 探索期間 ---
race, _ = pd.read_pickle(S + "are_cache.pkl"); _, R, _ = pd.read_pickle(S + "multi_cache.pkl")
O1 = pd.read_pickle(S + "tri_odds.pkl")
sg1 = R[R.single == True].groupby("race_id").num.apply(set).rename("sg")
r1 = race[["race_id", "win", "pay", "date"]].join(O1.groupby("race_id").odds.min().rename("fav"), on="race_id").join(sg1, on="race_id")
# --- 2024年 ---
a24 = pd.read_pickle(K + "out/y2024full/ana.pkl")
ids24 = sorted(a24.race_id.unique())
O2 = read_db(ids24, S + "tri_odds_2024.pkl", odds_sql)
P2 = read_db(ids24, S + "pay_2024.pkl", pay_sql)
p2 = P2.groupby("race_id").agg(win=("combo", "first"), pay=("payout", "max"), nw=("combo", "size"))
p2 = p2[p2.nw == 1].drop(columns="nw")
sg2 = a24[a24.single == True].groupby("race_id").number.apply(set).rename("sg")
r2 = p2.reset_index().join(O2.groupby("race_id").odds.min().rename("fav"), on="race_id").join(sg2, on="race_id")
r2["date"] = r2.race_id.map(a24.drop_duplicates("race_id").set_index("race_id").date)
def target(r, O):
    t = r[(r.fav >= 15) & r.sg.notna()].copy()
    X = O[O.race_id.isin(t.race_id)].merge(t[["race_id", "sg", "win", "pay", "date"]], on="race_id")
    cb = X.combo.str.split("-", expand=True).astype(int)
    X["s1"] = [a in s for a, s in zip(cb[0], X.sg)]
    X["hit"] = X.combo == X.win; X["inv"] = 1 / X.odds
    X = X.sort_values(["race_id", "odds"]); X["rk"] = X.groupby("race_id").cumcount() + 1
    X["cum"] = X.groupby("race_id").inv.cumsum()
    return t, X
t1, X1 = target(r1, O1); t2, X2 = target(r2, O2)
print("対象レース：探索期間", len(t1), "2024年", len(t2))
def flat(sel, t):
    g = sel.assign(r=np.where(sel.hit, sel.odds, 0)).groupby("race_id").agg(ret=("r", "sum"), n=("r", "size"))
    g = g.reindex(t.race_id).fillna(0)
    return dict(点数=round(g.n.mean(), 1), 的中率=round(100 * (g.ret > 0).mean(), 1), 元が取れた=round(100 * (g.ret >= g.n).mean(), 1), 回収率=round(100 * g.ret.sum() / g.n.sum(), 1))
def dutch(sel, t, pays):
    g = sel.assign(hv=sel.inv * sel.hit).groupby("race_id").agg(si=("inv", "sum"), hi=("hv", "sum"), n=("inv", "size")).reindex(t.race_id)
    g = g.join(pays, on=g.index.name if g.index.name else "race_id")
    g["ret"] = (g.hi / g.si * g.pay / 100).fillna(0); bought = g.n.notna()
    gg = g[bought]
    return dict(点数=round(gg.n.mean(), 1), 的中率=round(100 * (gg.ret > 0).mean(), 1), 元が取れた=round(100 * (gg.ret >= 1).mean(), 1), 回収率=round(100 * gg.ret.mean(), 1))
pay1 = t1.set_index("race_id").pay; pay2 = t2.set_index("race_id").pay
rows = []
# 買い方① 単騎1着の目＋人気上位N点（均等100円）。N は探索期間で的中率50%に届く最小値
for N in range(0, 60, 2):
    f1 = flat(X1[X1.s1 | (X1.rk <= N)], t1)
    if f1["的中率"] >= 50: break
rows.append(("①単騎1着の総流し＋人気上位%d点（均等）" % N, "探索期間", *f1.values())); rows.append(("", "2024年", *flat(X2[X2.s1 | (X2.rk <= N)], t2).values()))
# 買い方② 人気順に合成オッズTまで（金額配分）。T は探索期間で的中率50%以上の最大値
for T in np.arange(2.0, 1.0, -0.05):
    d1 = dutch(X1[1 / X1.cum >= T], t1, pay1)
    if d1["的中率"] >= 50: break
rows.append(("②人気順に合成%.2f倍まで（金額配分）" % T, "探索期間", *d1.values())); rows.append(("", "2024年", *dutch(X2[1 / X2.cum >= T], t2, pay2).values()))
# 買い方③ 単騎1着の目は必ず入れ、残りを人気順に足して合成T3まで（金額配分）
for T3 in np.arange(1.6, 0.6, -0.05):
    def sel3(X):
        base = X[X.s1]; rest = X[~X.s1].copy(); rest["c2"] = rest.groupby("race_id").inv.cumsum() + rest.race_id.map(base.groupby("race_id").inv.sum()).fillna(0)
        return pd.concat([base, rest[1 / rest.c2 >= T3]])
    d3 = dutch(sel3(X1), t1, pay1)
    if d3["的中率"] >= 50: break
rows.append(("③単騎1着の目＋人気順に足して合成%.2f倍まで（金額配分）" % T3, "探索期間", *d3.values())); rows.append(("", "2024年", *dutch(sel3(X2), t2, pay2).values()))
# 参考：単騎1着の総流し
rows.append(("（参考）単騎1着の総流しだけ", "探索期間", *flat(X1[X1.s1], t1).values())); rows.append(("", "2024年", *flat(X2[X2.s1], t2).values()))
print(pd.DataFrame(rows, columns=["買い方", "期間", "1レースの点数", "的中率%", "元が取れた%", "回収率%"]).to_string())
