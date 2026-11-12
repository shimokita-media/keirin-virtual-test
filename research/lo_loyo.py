"""ライン順の機械（L4）を4年分（y4・2024年・2025/2〜・y5）で「1年を抜いて学び、抜いた年で確かめる」（2026-11-12、y5 の判定の後。y6 は見ない）。
対象＝ライン順（同じライン3人で先頭→番手→3番手）×確定オッズ15倍以下。特徴量・学び方は research/lo_feats.py（L4 と同じ）。
y5 の写し out/lo_all_y5.pkl は prereg_eval_y5_lo.py と同じ作り方（pn＝300倍以下で合計1、当日の流れ flow・n_prev）で作る。
使い方: python -I -X utf8 research/lo_loyo.py reports/lo_loyo.md"""
import sys, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
def build_y5():
    f = K + "out/lo_all_y5.pkl"
    if os.path.exists(f): return pd.read_pickle(f)
    d = pd.read_pickle(K + "out/y5/cache.pkl"); d = d[d.date.between("20211108", "20221107") & (d.odds <= 300)].copy().reset_index(drop=True)
    d["hit"] = (d.ret > 0).astype(float)
    W = d[d.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
    R = d.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
    R["lw"] = R.race_id.map(W).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
    R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R = R.set_index("race_id")
    d["flow"] = d.race_id.map(R.flow); d["n_prev"] = d.race_id.map(R.n_prev)
    q = 1 / d.odds; d["pn"] = q / q.groupby(d.race_id).transform("sum")
    s = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy(); s.to_pickle(f); return s
P = {"y4": pd.read_pickle(K + "out/lo_all_y4.pkl"), "2024年": pd.read_pickle(K + "out/lo_all_2024年.pkl"),
     "2025/2〜": pd.read_pickle(K + "out/lo_all_20252.pkl"), "y5": build_y5()}
P["2025/2〜"] = P["2025/2〜"][P["2025/2〜"].date <= "20261105"]
rng = np.random.default_rng(0)
def cell(g):
    if len(g) < 30: return f"{len(g)}点（少）"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (2000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    top = g.ret.sort_values(ascending=False); ex5 = top.iloc[5:].sum() / len(g)
    return f"{len(g):,}点・**{g.ret.mean():.0%}**（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}・上位5本除き{ex5:.0%}）"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def W(*a): print(*a, file=OUT, flush=True)
W("# ライン順の機械（L4）を4年分で1年抜き（学ぶ3年 → 抜いた1年で確かめる）。y6 は見ていない" + NL)
W("全部（ライン順×15倍以下）： " + " ／ ".join(f"{k} {len(d):,}点・{d.ret.mean():.0%}" for k, d in P.items()) + NL)
TH = (1.2, 1.3, 1.4, 1.5)
for lam in (20.0, 80.0):
    W(f"## リッジの強さ λ={lam:g}" + NL)
    W("| 抜いた年 | " + " | ".join(f"比 {t} 以上" for t in TH) + " |" + NL + "|---|" + "---|" * len(TH))
    pooled = {t: [] for t in TH}
    for k in P:
        tr = pd.concat([d for j, d in P.items() if j != k], ignore_index=True)
        b = lo_fit(lo_feats(tr), tr.hit.to_numpy(), lo_lg(tr.pn).to_numpy(), lam)
        r = lo_ratio(b, P[k]); row = []
        for t in TH:
            g = P[k][r >= t]; pooled[t].append(g); row.append(cell(g))
        W(f"| {k} | " + " | ".join(row) + " |")
    W("| **4年まとめ（それぞれ学ばない年で）** | " + " | ".join(cell(pd.concat(pooled[t])) for t in TH) + " |" + NL)
# 4年すべてで学んだ係数（y6 用に固定する候補）と、学んだ年の中の成績（参考）
D = pd.concat(P.values(), ignore_index=True)
b = lo_fit(lo_feats(D), D.hit.to_numpy(), lo_lg(D.pn).to_numpy(), 20.0)
W("## 4年すべてで学んだ係数（λ=20、大きい順）" + NL)
W("、".join(f"{n} {v:+.2f}" for n, v in sorted(zip(LO_COLS, b[1:]), key=lambda t: -abs(t[1]))) + NL)
np.save(K + "out/lo_coef_4yr.npy", b)
print("done")
