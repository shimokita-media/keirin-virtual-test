"""元手の増やし方：毎回同じ額 vs 元手に合わせて1単位を変える。賭け方は「外す＋2日目2倍」、払戻5%減、7日ずつのかたまりで1年を2万回"""
exec(open("stake.py", encoding="utf-8").read().split('print("\n## 賭け方の比較')[0].replace('print("## 探す期間', 'if False: print("').replace("for nm, col in", "for nm, col in [] or []:#"))
w = W(X, "外す＋2日目2倍")
days = sorted(T.date.unique())
G = pd.DataFrame({"d": X.date, "inv": w, "ret": w * X.ret}).groupby("d").sum().reindex(days, fill_value=0)
inv, ret = G.inv.to_numpy(), G.ret.to_numpy()   # 1単位あたり
print(f"1日の平均 {inv.mean():.1f}単位（多い日 {np.percentile(inv,95):.0f}単位）")
rng = np.random.default_rng(3); N, L = 20000, 365
st = rng.integers(0, len(days) - 7, (N, L // 7 + 1)); idx = (st[:, :, None] + np.arange(7)).reshape(N, -1)[:, :L]
I, R = inv[idx], ret[idx]
def run(bank0, mode, f=None, unit=100):
    b = np.full(N, float(bank0)); peak = b.copy(); mdd = np.zeros(N); low = b.copy()
    for t in range(L):
        u = np.full(N, unit, float) if mode == "flat" else np.maximum(100, np.floor(b * f / 100) * 100)
        u = np.where(b >= u * I[:, t], u, np.maximum(0, np.floor(b / np.maximum(I[:, t], 1) / 100) * 100))  # 足りなければ減らす
        b = b + u * (R[:, t] - I[:, t]); peak = np.maximum(peak, b); mdd = np.maximum(mdd, (peak - b) / peak); low = np.minimum(low, b)
    q = lambda a, p: np.percentile(a, p)
    return f"1年後の元手 中央{q(b,50):,.0f}円（悪い年{q(b,5):,.0f}・良い年{q(b,95):,.0f}） 増え方 中央{q(b,50)/bank0:.1f}倍 減った確率{np.mean(b<bank0):.1%} 半分以下まで沈んだ確率{np.mean(low<bank0/2):.1%} 最大の落ち込み(割合) 中央{q(mdd,50):.0%}・悪い年{q(mdd,95):.0%}"
B0 = 50000
print(f"\n## 元手{B0:,}円で始めた場合")
print("- 毎回1単位100円:", run(B0, "flat", unit=100))
print("- 毎回1単位300円:", run(B0, "flat", unit=300))
for f in (0.002, 0.004, 0.006, 0.01):
    print(f"- 1単位＝元手の{f:.1%}（毎日見直し、最低100円）:", run(B0, "prop", f=f))
