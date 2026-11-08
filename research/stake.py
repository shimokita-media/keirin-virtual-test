"""3連単枠の賭け方（金額の配分）。重みは探す期間だけで決め、未使用①②③で確認。払戻は最終オッズ×0.95（締切前の目減り5%を想定）"""
exec(open("tri_boost.py", encoding="utf-8").read().split("base_s, base_u")[0])
X["P"] = np.where(X.per == "s", "探す", "未使用")
X["ret"] = X.ret * 0.95
X["bad"] = (X.nr == 1) & (X.r0_mk_rank == 1)
X["band"] = pd.cut(X.odds, [0, 10, 20, 30, 60], labels=["〜10倍", "10〜20倍", "20〜30倍", "30〜60倍"])
S = X[X.P == "探す"]
print("## 探す期間での目の種類ごとの回収率（払戻5%減）")
for nm, col in (("開催日", S.day_index.clip(upper=4)), ("当たった法則の数", S.nr.clip(upper=3)), ("倍率", S.band), ("外す条件", S.bad), ("1レースの点数", S.npick.clip(upper=4))):
    print(f"- {nm}: " + " ｜ ".join(f"{k} {g.ret.mean():.0%}({len(g)})" for k, g in S.groupby(col, observed=True)))
# 重みの案（探す期間の結果から決める）
def W(X, kind):
    w = pd.Series(1.0, index=X.index)
    if kind in ("外す", "外す＋2日目2倍", "外す＋法則2つ以上2倍", "外す＋2日目2倍＋法則2つ以上2倍", "外す＋20倍以下2倍"): w[X.bad] = 0
    if "2日目2倍" in kind: w[X.day_index == 2] *= 2
    if "法則2つ以上2倍" in kind: w[X.nr >= 2] *= 2
    if "20倍以下2倍" in kind: w[X.odds <= 20] *= 2
    if kind == "割合で配分":  # 探す期間の 種類ごとの回収率 から 期待のもうけ に比例（上限3倍・0倍あり）
        key = lambda D: D.day_index.clip(upper=4).astype(str) + "_" + D.nr.clip(upper=2).astype(str) + "_" + D.bad.astype(str)
        roi = S.groupby(key(S)).ret.mean(); n = S.groupby(key(S)).size()
        shrink = (roi * n + 1.0 * 200) / (n + 200)  # 少ない種類は全体寄りに縮める
        edge = (shrink - 1).clip(lower=0); w = key(X).map(edge / edge.mean()).fillna(0).clip(upper=3)
    return w
def stat(X, w):
    rows = []
    for p in ("探す", "未使用"):
        g = X[X.P == p]; ww = w[g.index]
        inv, ret = (ww).sum(), (ww * g.ret).sum()
        by = pd.DataFrame({"d": g.date, "pl": ww * (g.ret - 1)}).groupby("d").pl.sum()
        cum = by.cumsum().to_numpy(); dd = (np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum]).max()
        rows.append(f"{p} 回収率{ret/inv:.0%} もうけ{(ret-inv)*100:+,.0f}円 へこみ{dd*100:,.0f}円 もうけ÷へこみ {((ret-inv)/dd if dd else 0):.1f}")
    return " ｜ ".join(rows)
print("\n## 賭け方の比較（1単位=100円、払戻5%減）")
for k in ("同じ額", "外す", "外す＋2日目2倍", "外す＋法則2つ以上2倍", "外す＋2日目2倍＋法則2つ以上2倍", "外す＋20倍以下2倍", "割合で配分"):
    print(f"- {k}: {stat(X, W(X, k))}")
