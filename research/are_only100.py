"""100倍以上になりやすいレースだけを買う場合の比較（are_100x・are_multi・are_bs のキャッシュを使う）"""
import numpy as np, pandas as pd, itertools
S = "C:/Users/take0/.claude/keirin/out/are_work/"
race, _ = pd.read_pickle(S + "are_cache.pkl"); A, R, P = pd.read_pickle(S + "multi_cache.pkl")
race["half"] = np.where(race.date < "20251226", "前", "後")
filt = {"一番人気15倍以上×4ライン以上": (race.fav >= 15) & (race.nlines >= 4),
        "一番人気15倍以上×4ライン以上×9車": (race.fav >= 15) & (race.nlines >= 4) & (race.n == 9),
        "一番人気20倍以上": race.fav >= 20, "一番人気30倍以上": race.fav >= 30}
win = race.set_index("race_id").win.str.split("-", expand=True).astype(int)
mk = R[["race_id", "num", "mk_rank", "style", "single"]].dropna(subset=["mk_rank"])
mkm = {k: g.sort_values("mk_rank") for k, g in mk.groupby("race_id")}
A = A.merge(race[["race_id", "half"]], on="race_id")
out = []
for fname, m in filt.items():
    rs = race[m]; ids = set(rs.race_id)
    out.append((fname, "（参考）100倍以上になった割合", len(rs), round(100 * (rs.pay >= 10000).mean(), 1), None, None, None))
    a = A[A.race_id.isin(ids) & (A.odds >= 100)]
    for h in [None]:
        out.append((fname, "3連単 100倍以上の目を全部（表にある目）", len(rs), round(100 * a.ret.mean(), 1), round(100 * a[a.half == "前"].ret.mean(), 1), round(100 * a[a.half == "後"].ret.mean(), 1), round(len(a) / len(rs), 1)))
    a = A[A.race_id.isin(ids) & (A.odds >= 100) & (A.odds < 300)]
    out.append((fname, "3連単 100〜300倍の目（表にある目）", len(rs), round(100 * a.ret.mean(), 1), round(100 * a[a.half == "前"].ret.mean(), 1), round(100 * a[a.half == "後"].ret.mean(), 1), round(len(a) / len(rs), 1)))
    rows = []
    for r in rs.itertuples():
        g = mkm.get(r.race_id)
        if g is None: continue
        w = [int(x) for x in r.win.split("-")]; L = g.num.tolist()
        for name, s, k in [("3連単 2〜5番人気4人BOX", L[1:5], 4), ("3連単 上位5人BOX", L[:5], 5)]:
            if len(s) == k: rows.append((name, k * (k - 1) * (k - 2) * 100, r.pay if set(w) <= set(s) else 0, r.half))
        for num in g[(g["style"] == "追") & (g.single == True)].num:
            rows.append(("3連単 追込の単騎を1着に総流し", (r.n - 1) * (r.n - 2) * 100, r.pay if w[0] == num else 0, r.half))
    B = pd.DataFrame(rows, columns=["s", "cost", "ret", "half"])
    for s, g in B.groupby("s"):
        f = lambda x: round(100 * x.ret.sum() / x.cost.sum(), 1) if len(x) else None
        out.append((fname, s, len(rs), f(g), f(g[g.half == "前"]), f(g[g.half == "後"]), round(g.cost.sum() / 100 / len(rs), 1)))
pd.set_option("display.width", 250)
print(pd.DataFrame(out, columns=["レースの選び方", "買い方", "レース数", "回収率%", "前", "後", "1レースの点数"]).to_string())
