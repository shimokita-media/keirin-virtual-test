exec(open("tri_boost.py", encoding="utf-8").read().split("base_s, base_u")[0])
X["P"] = np.select([X.date.between("20250530", "20250705"), X.date.between("20250706", "20250803"), X.date.between("20250804", "20250822")], ["未①", "未②", "未③"], "探す")
nd = T.date.nunique()
def show(lab, g, w=None):
    w = pd.Series(1.0, index=g.index) if w is None else w
    r = lambda d: (d.ret * w[d.index]).sum() / w[d.index].sum()
    print(f"- {lab}: " + " ｜ ".join(f"{p} {r(g[g.P == p]):.0%}" for p in ("探す", "未①", "未②", "未③")) + f" ｜ 通し **{r(g):.0%}** 1日{w.sum()/nd:.1f}点（100円単位） 収支{((g.ret - 1) * w).sum()*100:+,.0f}円")
show("今の3連単枠", X)
ex1 = (X.nr == 1) & (X.r0_mk_rank == 1)
show("外す：法則1つだけ×1着が一番人気の選手", X[~ex1])
show("2日目だけ", X[X.day_index == 2])
show("2日目以外", X[X.day_index != 2])
show("2日目は2倍買う", X, pd.Series(np.where(X.day_index == 2, 2.0, 1.0), index=X.index))
show("外す＋2日目は2倍", X[~ex1], pd.Series(np.where(X[~ex1].day_index == 2, 2.0, 1.0), index=X[~ex1].index))
show("30倍→25倍（ずらし検証で良かった）", X[(X.odds <= 25) | (X.nr_rule6 if 'nr_rule6' in X else False)]) if False else None
print("\n日目別（今の3連単枠）:", " ".join(f"{d}日目 {g.ret.mean():.0%}({len(g)}点)" for d, g in X.groupby(X.day_index.clip(upper=4))))
print("2日目の期間別:", " ".join(f"{p} {g.ret.mean():.0%}({len(g)}点)" for p, g in X[X.day_index == 2].groupby("P")))
print("2日目の年別:", " ".join(f"{y} {g.ret.mean():.0%}" for y, g in X[X.day_index == 2].groupby(X.date.str[:4])))
print("2日目の月別:", " ".join(f"{m[2:]}:{g.ret.mean():.0%}" for m, g in X[X.day_index == 2].groupby(X.date.str[:6])))
# 開催の日数（3日開催/4日開催）で2日目の意味が違うか
mx = T.groupby("race_id").day_index.first(); 
