import sqlite3, time, os, itertools, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"; os.makedirs(S, exist_ok=True)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
race, _ = pd.read_pickle(S + "are_cache.pkl")
race["type"] = np.select([(race.fav >= 15) & (race.nlines >= 4), race.fav >= 15, race.fav >= 10], ["荒れ予想", "一番人気15倍以上(3ライン以下)", "中間"], "堅い(一番人気10倍未満)")
race["half"] = np.where(race.date < "20251226", "前", "後")
RT = race.set_index("race_id")
if not os.path.exists(S + "multi_cache.pkl"):
    cols = ["race_id", "combo", "odds", "ret", "popularity"]
    rc = ["mk_rank", "pt_rank", "p1", "p3", "style", "pos", "ls", "single", "lead_rank", "line_idx", "age", "h_surp_rate", "prediction_mark"]
    d = pd.read_pickle(K + "out/angle_base.pkl")[cols + [f"r{k}_{c}" for k in range(3) for c in rc]]
    A = d[cols].copy()
    cb = d.combo.str.split("-", expand=True).astype(int)
    R = pd.concat([d[[f"r{k}_{c}" for c in rc]].set_axis(rc, axis=1).assign(race_id=d.race_id.values, num=cb[k].values) for k in range(3)]).drop_duplicates(["race_id", "num"])
    del d
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    ids = list(race.race_id); P = []
    for i in range(0, len(ids), 500):
        q = ids[i:i + 500]
        P.append(pd.read_sql(f"SELECT race_id, bet_type, combo, payout FROM payouts WHERE race_id IN ({','.join('?'*len(q))})", c, params=q)); time.sleep(0.3)
    c.close(); P = pd.concat(P)
    pd.to_pickle((A, R, P), S + "multi_cache.pkl")
A, R, P = pd.read_pickle(S + "multi_cache.pkl")
A = A[A.race_id.isin(RT.index)]; A = A.join(RT[["type", "half"]], on="race_id")

print("=== A. 3連単の目のオッズ帯 × レースの型（回収率%、表に入っている目だけ）===")
A["band"] = pd.cut(A.odds, [0, 30, 100, 300, 1000, 1e9], labels=["30倍未満", "30〜100倍", "100〜300倍", "300〜1000倍", "1000倍以上"])
t = A.groupby(["type", "band"], observed=True).agg(点数=("ret", "size"), 回収率=("ret", "mean")); t["回収率"] = (t.回収率 * 100).round(1)
h = A.groupby(["type", "band", "half"], observed=True).ret.mean().mul(100).round(1).unstack()
print(t.join(h).to_string())

print("\n=== B. 1着になる選手の型（市場の見込み p1 と実際の1着率、1着固定の流し回収率）===")
win = race.set_index("race_id").win.str.split("-", expand=True).astype(int)
R = R[R.race_id.isin(RT.index)].copy()
R = R.join(win.rename(columns={0: "w1", 1: "w2", 2: "w3"}), on="race_id").join(RT[["type", "half", "n", "pay"]], on="race_id")
R["is1"] = R.num == R.w1; R["in3"] = (R.num == R.w1) | (R.num == R.w2) | (R.num == R.w3)
pw = P[P.bet_type == "2車単"].groupby("race_id").payout.max()
R["ex_pay"] = R.race_id.map(pw)
R["ex_ret"] = np.where(R.is1, R.ex_pay, 0); R["ex_cost"] = (R.n - 1) * 100
R["tri_ret"] = np.where(R.is1, R.pay, 0); R["tri_cost"] = (R.n - 1) * (R.n - 2) * 100
R["grp_style"] = R["style"].astype(str) + "・" + np.where(R.single, "単騎", np.where(R.pos == 0, "先頭", np.where(R.pos == 1, "番手", "3番手以降")))
R["mk"] = R.mk_rank.clip(upper=7).astype("Int64")
def bsum(g):
    return pd.Series({"選手数": len(g), "見込み1着%": round(100 * g.p1.mean(), 1), "実際1着%": round(100 * g.is1.mean(), 1),
                      "2車単1着流し%": round(100 * g.ex_ret.sum() / g.ex_cost.sum(), 1), "3連単1着流し%": round(100 * g.tri_ret.sum() / g.tri_cost.sum(), 1),
                      "前": round(100 * g[g.half == "前"].tri_ret.sum() / g[g.half == "前"].tri_cost.sum(), 1), "後": round(100 * g[g.half == "後"].tri_ret.sum() / g[g.half == "後"].tri_cost.sum(), 1)})
for key in ["mk", "grp_style"]:
    for ty in [None, "荒れ予想"]:
        g = R if ty is None else R[R.type == ty]
        tb = g.groupby(key).apply(bsum); tb = tb[tb.選手数 >= 300]
        print(f"\n-- {key}（{'全レース' if ty is None else ty}）"); print(tb.to_string())

print("\n=== C. 車券の種類ごと：人気上位の選手で買ったときの回収率（レースの型別）===")
mk = R[["race_id", "num", "mk_rank"]].dropna()
mkm = {k: g.sort_values("mk_rank").num.tolist() for k, g in mk.groupby("race_id")}
Pg = {k: g for k, g in P.groupby("race_id")}
specs = [("2車複 上位4人BOX(6点)", "2車複", 1, 4, 2, False), ("2車単 上位4人BOX(12点)", "2車単", 1, 4, 2, True), ("ワイド 上位4人BOX(6点)", "ワイド", 1, 4, 2, False),
         ("3連複 上位5人BOX(10点)", "3連複", 1, 5, 3, False), ("3連単 上位5人BOX(60点)", "3連単", 1, 5, 3, True),
         ("ワイド 2〜5番手BOX(6点)", "ワイド", 2, 5, 2, False), ("3連複 2〜6番手BOX(10点)", "3連複", 2, 6, 3, False), ("2車複 2〜5番手BOX(6点)", "2車複", 2, 5, 2, False)]
rows = []
for r in race.itertuples():
    L = mkm.get(r.race_id); pg = Pg.get(r.race_id)
    if L is None or pg is None: continue
    for name, bt, lo, hi, k, ordered in specs:
        if len(L) < hi: continue
        s = L[lo - 1:hi]
        combos = list(itertools.permutations(s, k)) if ordered else list(itertools.combinations(sorted(s), k))
        keys = {"-".join(map(str, c)) for c in combos}
        pp = pg[pg.bet_type == bt]
        ret = pp[pp.combo.isin(keys)].payout.sum()
        rows.append((r.race_id, name, len(combos) * 100, ret, r.type, r.half))
C = pd.DataFrame(rows, columns=["race_id", "spec", "cost", "ret", "type", "half"])
def csum(g):
    return pd.Series({"レース数": len(g), "回収率%": round(100 * g.ret.sum() / g.cost.sum(), 1), "前": round(100 * g[g.half == "前"].ret.sum() / g[g.half == "前"].cost.sum(), 1), "後": round(100 * g[g.half == "後"].ret.sum() / g[g.half == "後"].cost.sum(), 1), "元が取れた%": round(100 * (g.ret >= g.cost).mean(), 1)})
print(C.groupby(["spec", "type"]).apply(csum).to_string())
