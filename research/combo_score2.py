import numpy as np, pandas as pd
c = pd.read_pickle("score_top.pkl")
c["sc2"] = (c.sc + (c.nr >= 3).astype(int) + ((c.r0_pos == 0) & (c.r1_pos == 1) & (c.r2_pos == 2)).astype(int) + (c.r0_mk_rank != 1).astype(int)
            + c.odds.between(10, 30).astype(int) + (c["先頭の年齢"] >= 41).astype(int) + c.oB.between(1, 4).astype(int) + (c["同県"] == 1).astype(int)
            - (c.lS >= 9).astype(int) - c["結束"].astype(int))
nd = c.date.nunique()
def st(g):
    by = g.groupby("race_id").agg(i=("ret", "size"), x=("ret", "sum")); i = np.random.default_rng(0).integers(0, len(by), (2000, len(by))); bs = by.x.to_numpy()[i].sum(1) / by.i.to_numpy()[i].sum(1)
    mr = g.groupby(g.date.str[:6]).ret.mean()
    return f"{g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 1日{len(g)/nd:.1f}点 当たり{int((g.ret>0).sum())} 100%超えの月{(mr>=1).sum()}/{len(mr)} 最悪の月{mr.min():.0%} ｜ 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}"
print("## 新しい点数（15項目）ごと")
for k in sorted(c.sc2.unique()):
    g = c[c.sc2 == k]
    if len(g) >= 30: print(f"- 点数{k}: 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}（{len(g)}点）")
print("\n## しきい値で絞る")
for th in range(3, 9):
    g = c[c.sc2 >= th]
    if len(g) >= 40: print(f"- 新しい点数{th}以上: {st(g)}")
print(f"- （比較）元の点数3以上: {st(c[c.sc >= 3])}")
print(f"- （比較）一番の目ぜんぶ: {st(c)}")
# 月を隠してしきい値を選ぶ（いいとこ取りの度合いを見る）
months = sorted(c.date.str[:6].unique()); rows = []
for h in months:
    rest = c[c.date.str[:6] != h]; best = max(range(3, 9), key=lambda t: (rest[rest.sc2 >= t].ret.mean() - 0.5 * rest[rest.sc2 >= t].groupby(rest.date.str[:6]).ret.mean().std()) if (rest.sc2 >= t).sum() >= 100 else -9)
    g = c[(c.date.str[:6] == h) & (c.sc2 >= best)]; rows.append((h, best, len(g), g.ret.sum()))
R = pd.DataFrame(rows, columns=["m", "th", "n", "r"]); mr = R.r / R.n.replace(0, np.nan)
print(f"\n月を隠してしきい値を選んだ場合: 通し {R.r.sum()/R.n.sum():.0%}（{R.n.sum()}点） 100%超えの月 {(mr>=1).sum()}/{mr.notna().sum()} 選ばれたしきい値 {R.th.value_counts().to_dict()}")
