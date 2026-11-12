import sqlite3, time, itertools, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
d = pd.read_pickle(K + "out/angle_base.pkl")[["race_id", "combo", "odds", "popularity", "r0_mk_rank", "r1_mk_rank", "r2_mk_rank", "date", "entries_number", "grade", "nlines", "n_strong_nige"]]
# rider market rank per race (from combo positions)
cb = d.combo.str.split("-", expand=True).astype(int)
rk = pd.concat([pd.DataFrame({"race_id": d.race_id, "num": cb[k], "mk": d[f"r{k}_mk_rank"]}) for k in range(3)]).dropna().drop_duplicates(["race_id", "num"])
race = d.groupby("race_id").agg(fav=("odds", "min"), date=("date", "first"), n=("entries_number", "first"), grade=("grade", "first"), nlines=("nlines", "first"), nige=("n_strong_nige", "first"), minpop=("popularity", "min")).reset_index()
del d
# payouts: small chunked read-only (exploration period is not being written)
c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
ids = list(race.race_id); P = []
for i in range(0, len(ids), 500):
    q = ids[i:i + 500]
    P.append(pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単' AND race_id IN ({','.join('?'*len(q))})", c, params=q)); time.sleep(0.3)
c.close()
P = pd.concat(P)
race = race.merge(P.groupby("race_id").agg(win=("combo", "first"), pay=("payout", "max"), nwin=("combo", "size")).reset_index(), on="race_id")
race = race[race.nwin == 1]
rkm = {k: dict(zip(g.num, g.mk)) for k, g in rk.groupby("race_id")}
def box_nums(r, lo, hi):
    m = rkm.get(r, {}); return {n for n, v in m.items() if lo <= v <= hi}
rows = []
for r in race.itertuples():
    w = [int(x) for x in r.win.split("-")]
    for name, lo, hi in [("人気上位3人BOX(6点)", 1, 3), ("人気上位4人BOX(24点)", 1, 4), ("人気上位5人BOX(60点)", 1, 5), ("人気4〜7番手の4人BOX(24点)", 4, 7)]:
        s = box_nums(r.race_id, lo, hi); k = len(s)
        if k != hi - lo + 1: continue
        cost = k * (k - 1) * (k - 2) * 100
        ret = r.pay if set(w) <= s else 0
        rows.append((r.race_id, name, cost, ret))
B = pd.DataFrame(rows, columns=["race_id", "box", "cost", "ret"]).merge(race, on="race_id")
B["fav_band"] = pd.cut(B.fav, [0, 10, 20, 40, 1e9], labels=["一番人気10倍未満(堅い)", "10〜20倍", "20〜40倍", "40倍以上(大荒れ予想)"])
B["half"] = np.where(B.date < "20251226", "前半", "後半")
def summ(g):
    return pd.Series({"レース数": len(g), "回収率%": round(100 * g.ret.sum() / g.cost.sum(), 1), "当たり%": round(100 * (g.ret > 0).mean(), 1), "元が取れた%": round(100 * (g.ret >= g.cost).mean(), 1)})
pd.set_option("display.width", 200)
print("races", len(race), "payout share of top", race.fav.describe().round(1).to_dict())
print(B.groupby(["box", "fav_band"], observed=True).apply(summ).to_string())
print(B.groupby(["box", "fav_band", "half"], observed=True).apply(lambda g: round(100 * g.ret.sum() / g.cost.sum(), 1)).unstack().to_string())
# overall payout distribution by band
race["fav_band"] = pd.cut(race.fav, [0, 10, 20, 40, 1e9])
print(race.groupby("fav_band", observed=True).pay.describe(percentiles=[.5, .9]).round(0).to_string())
