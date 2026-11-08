import numpy as np, pandas as pd
c = pd.read_pickle("com_top.pkl"); B = pd.read_pickle("com_B.pkl")
def sc(D):
    s = (D.topB == 1).astype(int) + (D["先頭の年齢"] >= 34).astype(int) + (D["3番手のコメント"] == "その他").astype(int) + (D["得点の差"] < 0).astype(int) + (D.a3 <= 2).astype(int) - (D["人数"] >= 4).astype(int)
    return s.clip(lower=0)
def st(g, nd):
    if not len(g): return "0点"
    by = g.groupby("race_id").agg(i=("ret", "size"), x=("ret", "sum")); i = np.random.default_rng(0).integers(0, len(by), (2000, len(by))); bs = by.x.to_numpy()[i].sum(1) / by.i.to_numpy()[i].sum(1)
    mr = g.groupby(g.date.str[:6]).ret.mean()
    return f"{g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 1日{len(g)/nd:.1f}点 当たり{int((g.ret>0).sum())} 100%超えの月{(mr>=1).sum()}/{len(mr)} 最悪の月{mr.min():.0%}"
nd = c.date.nunique()
for nm, D in (("一番の目", c), ("3連単枠", B)):
    D["sc"] = sc(D); print(f"\n## {nm}")
    for k in range(0, 6):
        g = D[D.sc == k]
        if len(g) >= 30: print(f"- 点数{k}: 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}（{len(g)}点）")
    for th in (2, 3, 4):
        g = D[D.sc >= th]; print(f"- ★点数{th}以上: {st(g, nd)} ｜ 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}")
    g = D; print(f"- （比較）ぜんぶ: {st(g, nd)}")
c.to_pickle("score_top.pkl")
