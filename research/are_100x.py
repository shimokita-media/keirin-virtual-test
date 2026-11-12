import sqlite3, time, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"; os.makedirs(S, exist_ok=True)
if not os.path.exists(S + "are_cache.pkl"):
    d = pd.read_pickle(K + "out/angle_base.pkl")[["race_id", "combo", "odds", "r0_mk_rank", "r1_mk_rank", "r2_mk_rank", "r0_style", "r1_style", "r2_style", "date", "entries_number", "grade", "class", "nlines", "n_strong_nige", "day_index", "race_no", "race_type", "venue", "wind", "S", "G"]]
    cb = d.combo.str.split("-", expand=True).astype(int)
    rk = pd.concat([pd.DataFrame({"race_id": d.race_id, "num": cb[k], "mk": d[f"r{k}_mk_rank"], "style": d[f"r{k}_style"]}) for k in range(3)]).dropna(subset=["mk"]).drop_duplicates(["race_id", "num"])
    race = d.groupby("race_id").agg(fav=("odds", "min"), date=("date", "first"), n=("entries_number", "first"), grade=("grade", "first"), cls=("class", "first"), nlines=("nlines", "first"), nige=("n_strong_nige", "first"), day=("day_index", "first"), rno=("race_no", "first"), rtype=("race_type", "first"), venue=("venue", "first"), wind=("wind", "first"), Sv=("S", "first"), Gv=("G", "first")).reset_index()
    del d
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    ids = list(race.race_id); P = []
    for i in range(0, len(ids), 500):
        q = ids[i:i + 500]
        P.append(pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単' AND race_id IN ({','.join('?'*len(q))})", c, params=q)); time.sleep(0.3)
    c.close(); P = pd.concat(P)
    race = race.merge(P.groupby("race_id").agg(win=("combo", "first"), pay=("payout", "max"), nwin=("combo", "size")).reset_index(), on="race_id")
    race = race[race.nwin == 1]
    pd.to_pickle((race, rk), S + "are_cache.pkl")
race, rk = pd.read_pickle(S + "are_cache.pkl")
race["big"] = race.pay >= 10000
race["half"] = np.where(race.date < "20251226", "前半", "後半")
print("全レース", len(race), "100倍以上の割合 %.1f%%" % (100 * race.big.mean()), "1000倍以上 %.1f%%" % (100 * (race.pay >= 100000).mean()))
pd.set_option("display.width", 220)
def rate(col, bins=None):
    x = pd.cut(race[col], bins) if bins is not None else race[col]
    t = race.groupby([x, "half"], observed=True).big.mean().unstack().mul(100).round(1)
    t["レース数"] = race.groupby(x, observed=True).size(); return t
print("\n一番人気の3連単オッズ別"); print(rate("fav", [0, 5, 10, 15, 20, 30, 1e9]).to_string())
print("\n車立て"); print(rate("n").to_string())
print("\nライン数"); print(rate("nlines").to_string())
print("\n強い逃げの数"); print(rate("nige").to_string())
print("\nグレード"); print(rate("grade").to_string())
print("\n級"); print(rate("cls").to_string())
print("\n風"); print(rate("wind", [-1, 2, 4, 6, 99]).to_string())
# combined: fav>=15 & nlines>=4 & n==9
m = (race.fav >= 15) & (race.nlines >= 4) & (race.n == 9)
print("\n一番人気15倍以上×4ライン以上×9車:", m.sum(), race[m].groupby("half").big.mean().mul(100).round(1).to_dict())
# BOX strategies
rkm = {k: dict(zip(g.num, g.mk)) for k, g in rk.groupby("race_id")}
specs = [("1番人気を外した2〜6番手の5人BOX(60点)", 2, 6), ("2〜5番手の4人BOX(24点)", 2, 5), ("3〜7番手の5人BOX(60点)", 3, 7), ("人気上位6人BOX(120点)", 1, 6), ("人気上位5人BOX(60点)", 1, 5)]
rows = []
for r in race.itertuples():
    w = set(int(x) for x in r.win.split("-")); m_ = rkm.get(r.race_id, {})
    for name, lo, hi in specs:
        s = {n for n, v in m_.items() if lo <= v <= hi}; k = len(s)
        if k != hi - lo + 1: continue
        cost = k * (k - 1) * (k - 2) * 100; ret = r.pay if w <= s else 0
        rows.append((r.race_id, name, cost, ret))
B = pd.DataFrame(rows, columns=["race_id", "box", "cost", "ret"]).merge(race, on="race_id")
B["荒れ予想"] = np.where((B.fav >= 15) & (B.nlines >= 4), "荒れ予想(一番人気15倍以上×4ライン以上)", "その他")
def summ(g):
    return pd.Series({"レース数": len(g), "回収率%": round(100 * g.ret.sum() / g.cost.sum(), 1), "前半%": round(100 * g[g.half == "前半"].ret.sum() / g[g.half == "前半"].cost.sum(), 1), "後半%": round(100 * g[g.half == "後半"].ret.sum() / g[g.half == "後半"].cost.sum(), 1), "当たり%": round(100 * (g.ret > 0).mean(), 1), "元が取れた%": round(100 * (g.ret >= g.cost).mean(), 1), "100倍以上を取れた%": round(100 * (g.ret >= 10000).mean(), 1)})
print(); print(B.groupby(["box", "荒れ予想"]).apply(summ).to_string())
# all-combos baseline by payout band: what share of 100x+ races does each box catch
print("\n100倍以上のレースのうちBOXに入っていた割合")
bb = B[B.pay >= 10000]; print(bb.groupby("box").apply(lambda g: round(100 * (g.ret > 0).mean(), 1)).to_string())
