exec(open("robust_sel.py", encoding="utf-8").read().split("# 月ごとの")[0])
rng = np.random.default_rng(0)
for nm, g in (("一番の目×法則3つ以上", c[c.nr >= 3]), ("一番の目", c), ("3連単枠ぜんぶ", B)):
    r = g.ret.to_numpy(); per_m = len(g) / 15
    for months in (1, 3, 6, 12):
        n = int(per_m * months); sims = r[rng.integers(0, len(r), (20000, n))].mean(1)
        print(f"{nm}（本当の回収率{r.mean():.0%}・1か月{per_m:.0f}点）: {months}か月で100%未満になる確率 {np.mean(sims < 1):.0%}")
