exec(open("robust.py", encoding="utf-8").read().split("def per(d)")[0])
X = TB
days = sorted(T.date.unique()); D = X.groupby("date").agg(inv=("ret", "size"), r=("ret", "sum")).reindex(days, fill_value=0)
inv, ret = D.inv.to_numpy() * 100, D.r.to_numpy() * 100
print(f"データ {len(days)}日: 投資 {inv.sum():,.0f}円 払戻 {ret.sum():,.0f}円 回収率 {ret.sum()/inv.sum():.0%} 1日平均 {inv.mean():.0f}円投資")
rng = np.random.default_rng(1); N = 20000; L = 365
# 7日ずつのかたまりで抜き出し（連敗のまとまりを残す）
nb = L // 7 + 1; starts = rng.integers(0, len(days) - 7, (N, nb))
idx = (starts[:, :, None] + np.arange(7)).reshape(N, -1)[:, :L]
I, Rr = inv[idx], ret[idx]; prof = (Rr - I).sum(1); roi = Rr.sum(1) / I.sum(1)
cum = np.cumsum(Rr - I, 1); dd = (np.maximum.accumulate(np.concatenate([np.zeros((N, 1)), cum], 1), 1)[:, 1:] - cum).max(1)
pct = lambda a: " / ".join(f"{q}%:{np.percentile(a, q):,.0f}" for q in (5, 25, 50, 75, 95))
print("1年の投資（中央）", f"{np.median(I.sum(1)):,.0f}円")
print("1年の収支（100円ずつ）", pct(prof)); print("1年の回収率", " / ".join(f"{q}%:{np.percentile(roi, q):.0%}" for q in (5, 25, 50, 75, 95)))
print(f"1年でマイナスになる確率 {np.mean(prof < 0):.1%}")
print("最大のへこみ", pct(dd))
m = np.array([(Rr[:, i:i+30] - I[:, i:i+30]).sum(1) for i in range(0, 360, 30)]).T
print(f"30日ごとに区切ってマイナスの月の数（12か月中） 中央 {np.median((m < 0).sum(1)):.0f}  ／ 1か月がマイナスの確率 {np.mean(m < 0):.0%}")
# 締切前で回収率が少し落ちた場合（払戻を一律で減らす）
for f in (0.95, 0.9, 0.85):
    p2 = (Rr * f - I).sum(1); print(f"払戻が{1-f:.0%}減った場合: 収支中央 {np.median(p2):,.0f}円 回収率中央 {np.median(Rr.sum(1)*f/I.sum(1)):.0%} マイナスの確率 {np.mean(p2 < 0):.0%}")
