exec(open("year_sim.py", encoding="utf-8").read().split("pct = lambda")[0])
f = 0.95; Rr = Rr * f
prof = (Rr - I).sum(1); roi = Rr.sum(1) / I.sum(1)
cum = np.cumsum(Rr - I, 1); dd = (np.maximum.accumulate(np.concatenate([np.zeros((N, 1)), cum], 1), 1)[:, 1:] - cum).max(1)
low = cum.min(1)  # 始めてから一番下まで沈んだ額（元手がいくら要るか）
m = np.array([(Rr[:, i:i+30] - I[:, i:i+30]).sum(1) for i in range(0, 360, 30)]).T
q = lambda a, p: np.percentile(a, p)
# 連敗（レース単位）：実データの日ごとではなくレース順で
by = TB.groupby(["date", "race_id"]).ret.sum().reset_index().sort_values(["date"])
st = cur = 0; streaks = []
for v in by.ret.to_numpy():
    cur = 0 if v > 0 else cur + 1; st = max(st, cur)
print(f"回収率 中央{q(roi,50):.0%}（悪い年{q(roi,5):.0%}・良い年{q(roi,95):.0%}） マイナスの確率 {np.mean(prof<0):.1%}")
print(f"1か月がマイナスの確率 {np.mean(m<0):.0%}、12か月中マイナスの月 中央{np.median((m<0).sum(1)):.0f} 多い年{q((m<0).sum(1),95):.0f}")
print(f"3か月続けてマイナスになる年の割合 {np.mean([(np.convolve((mm<0).astype(int), np.ones(3), 'valid') >= 3).any() for mm in m]):.0%}")
print(f"過去データの最大連敗 {st}レース")
for stake in (100, 300, 500, 1000):
    k = stake / 100
    print(f"1点{stake}円: 1年の投資{np.median(I.sum(1))*k:,.0f}円 収支 中央{q(prof,50)*k:+,.0f}（悪い年{q(prof,5)*k:+,.0f}・良い年{q(prof,95)*k:+,.0f}） 最大のへこみ 中央{q(dd,50)*k:,.0f}・悪い年{q(dd,95)*k:,.0f} 元手から一番沈む額 悪い年{-q(low,5)*k:,.0f}")
