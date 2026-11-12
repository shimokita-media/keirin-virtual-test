"""大荒れ×出走表の数字（B・S・上がり・決まり手・直近の着・得点・班・年齢・ギア）を多角的に。
選手ごとに「市場の見込み（p1/p3）に対する実際の1着・3着内」の比と、1着固定の流し回収率を、全レース／荒れ予想で、前半・後半に分けて出す。
先に research/are_100x.py と are_multi.py を回して out/are_work/ のキャッシュを作っておくこと。"""
import sqlite3, time, os, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
race, _ = pd.read_pickle(S + "are_cache.pkl")
race["type"] = np.where((race.fav >= 15) & (race.nlines >= 4), "荒れ予想", "その他")
race["half"] = np.where(race.date < "20251226", "前", "後")
A, R, P = pd.read_pickle(S + "multi_cache.pkl"); del A
RT = race.set_index("race_id")
if not os.path.exists(S + "entries.pkl"):
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    ids = list(race.race_id); E = []
    for i in range(0, len(ids), 300):
        q = ids[i:i + 300]
        E.append(pd.read_sql(f"""SELECT race_id, number AS num, age, class AS pcls, grp, gear, race_point, first_rate, second_rate, third_rate,
            n_front, n_stalker, n_closer, n_marker, recent_orders, n_standing, n_back, agari_avg, agari_best FROM entries
            WHERE absent=0 AND race_id IN ({','.join('?'*len(q))})""", c, params=q)); time.sleep(0.3)
    c.close(); E = pd.concat(E); E.to_pickle(S + "entries.pkl")
E = pd.read_pickle(S + "entries.pkl")
ro = E.recent_orders.apply(lambda s: json.loads(s) if isinstance(s, str) else [])
E["ro5"] = ro.apply(lambda x: np.mean(x[-5:]) if len(x) else np.nan)
E["n_kimari"] = E[["n_front", "n_stalker", "n_closer", "n_marker"]].sum(axis=1)
for col in ["n_front", "n_stalker", "n_closer", "n_marker"]:
    E[col + "_r"] = E[col] / E.n_kimari.replace(0, np.nan)
g = E.groupby("race_id")
E["B_rank"] = g.n_back.rank(ascending=False, method="min"); E["S_rank"] = g.n_standing.rank(ascending=False, method="min")
E["ag_rank"] = g.agari_avg.rank(method="min"); E["pt_rank2"] = g.race_point.rank(ascending=False, method="min")
E["B_max"] = g.n_back.transform("max"); E["B_n10"] = g.n_back.transform(lambda x: (x >= 10).sum())
E["ag_spread"] = g.agari_avg.transform(lambda x: x.max() - x.min())
D = R.drop(columns=["age"]).merge(E, on=["race_id", "num"], how="inner")
win = race.set_index("race_id").win.str.split("-", expand=True).astype(int)
D = D.join(win.rename(columns={0: "w1", 1: "w2", 2: "w3"}), on="race_id").join(RT[["type", "half", "n", "pay", "fav"]], on="race_id")
D["is1"] = D.num == D.w1; D["in3"] = D.num.isin([0]) | (D.num == D.w1) | (D.num == D.w2) | (D.num == D.w3)
pw = P[P.bet_type == "2車単"].groupby("race_id").payout.max(); D["ex_pay"] = D.race_id.map(pw)
D["tri_ret"] = np.where(D.is1, D.pay, 0); D["tri_cost"] = (D.n - 1) * (D.n - 2) * 100
D["ex_ret"] = np.where(D.is1, D.ex_pay, 0); D["ex_cost"] = (D.n - 1) * 100
D["mk"] = D.mk_rank
print("選手数", len(D), "レース", D.race_id.nunique(), "荒れ予想レース", D[D.type == "荒れ予想"].race_id.nunique())

feats = {
    "B（バック回数）": pd.cut(D.n_back, [-1, 0, 2, 5, 10, 99], labels=["0", "1-2", "3-5", "6-10", "11+"]),
    "Bのレース内順位": D.B_rank.clip(upper=5),
    "S（主導権）": pd.cut(D.n_standing, [-1, 0, 2, 5, 99], labels=["0", "1-2", "3-5", "6+"]),
    "Sのレース内順位": D.S_rank.clip(upper=5),
    "上がり平均のレース内順位": D.ag_rank.clip(upper=5),
    "決まり手で逃げの割合": pd.cut(D.n_front_r, [-.01, 0, .3, .6, 1.01], labels=["0", "〜3割", "〜6割", "6割超"]),
    "決まり手で捲りの割合": pd.cut(D.n_stalker_r, [-.01, 0, .3, .6, 1.01], labels=["0", "〜3割", "〜6割", "6割超"]),
    "決まり手で差しの割合": pd.cut(D.n_closer_r, [-.01, 0, .3, .6, 1.01], labels=["0", "〜3割", "〜6割", "6割超"]),
    "決まり手の数（勝ち数の目安）": pd.cut(D.n_kimari, [-1, 0, 2, 5, 10, 999], labels=["0", "1-2", "3-5", "6-10", "11+"]),
    "直近5走の平均着": pd.cut(D.ro5, [0, 2.5, 3.5, 4.5, 5.5, 10], labels=["〜2.5", "〜3.5", "〜4.5", "〜5.5", "5.5超"]),
    "得点のレース内順位": D.pt_rank2.clip(upper=7),
    "年齢": pd.cut(D.age, [0, 25, 30, 35, 40, 45, 99]),
    "班（1班が上）": D.grp,
    "ギア": pd.cut(D.gear, [0, 3.9, 3.93, 4.0, 9]),
    "市場の人気順位": D.mk.clip(upper=7),
}
def summ(x):
    o = {"選手数": len(x), "見込み1着%": 100 * x.p1.mean(), "実際1着%": 100 * x.is1.mean(), "1着の比": x.is1.mean() / x.p1.mean() if x.p1.mean() > 0 else np.nan,
         "3着内の比": x.in3.mean() / x.p3.mean() if x.p3.mean() > 0 else np.nan,
         "3連単1着流し%": 100 * x.tri_ret.sum() / x.tri_cost.sum(), "2車単1着流し%": 100 * x.ex_ret.sum() / x.ex_cost.sum()}
    for h in ["前", "後"]:
        y = x[x.half == h]; o["流し" + h] = 100 * y.tri_ret.sum() / y.tri_cost.sum() if len(y) else np.nan
    return pd.Series(o).round(2)
ntest = 0; hits = []
for ty in ["全レース", "荒れ予想"]:
    sub = D if ty == "全レース" else D[D.type == "荒れ予想"]
    for name, f in feats.items():
        t = sub.groupby(f.loc[sub.index], observed=True).apply(summ)
        t = t[t.選手数 >= (300 if ty == "荒れ予想" else 1000)]
        ntest += len(t)
        print(f"\n-- {name}（{ty}）"); print(t.to_string())
        for idx, r in t.iterrows():
            if r["流し前"] > 100 and r["流し後"] > 100: hits.append((ty, name, idx, r.選手数, r["3連単1着流し%"], r["流し前"], r["流し後"]))
print("\n試した区分の数", ntest)
print("前半・後半とも100%超え:"); [print(h) for h in hits]

print("\n=== レースの型：一番人気のオッズ帯の中で、B・Sの形が100倍以上の割合を変えるか ===")
rc = D.groupby("race_id").agg(B_max=("n_back", "max"), B_n10=("n_back", lambda x: (x >= 10).sum()), S_sum=("n_standing", "sum"), ag_spread=("agari_avg", lambda x: x.max() - x.min()),
                               pt_spread=("race_point", lambda x: x.max() - x.min()), ro_mean=("ro5", "mean")).join(RT[["fav", "pay", "half", "nlines", "n"]])
rc["big"] = rc.pay >= 10000
rc["fav_band"] = pd.cut(rc.fav, [0, 5, 10, 15, 1e9], labels=["〜5倍", "5〜10倍", "10〜15倍", "15倍超"])
for col, bins in [("B_n10", [-1, 0, 1, 2, 9]), ("B_max", [-1, 5, 10, 20, 99]), ("S_sum", [-1, 5, 10, 20, 999]), ("ag_spread", [0, .3, .5, .8, 9]), ("pt_spread", [0, 5, 10, 15, 99])]:
    t = rc.groupby(["fav_band", pd.cut(rc[col], bins)], observed=True).agg(レース=("big", "size"), 百倍以上=("big", "mean"))
    t["百倍以上"] = (100 * t.百倍以上).round(1)
    print(f"\n-- {col}"); print(t.unstack(0).to_string())
