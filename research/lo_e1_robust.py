"""E1（ライン順×15倍以下×期待値≥1.2）の頑丈さ（2026-11-13、y9・y10 の判定の後）。7年分（4年の1年抜き＋y6・y9・y10 は固定係数）をまとめ、
①線を少し動かしたとき（1分前の倍率では期待値が確定より約1.5%低く出る＝線が1.2→1.22 に動くのと近い）、②期待値に±5%のゆらぎを足して選び直したとき の回収率を見る。
使い方: python -I -X utf8 research/lo_e1_robust.py reports/lo_e1_robust.md"""
import sys, json, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8"))
OUT = K + "out/lo15_7yr.pkl"
if not os.path.exists(OUT):
    src = open(K + "research/prereg_eval_y5_lo.py", encoding="utf-8").read().split("base = d[")[0]; P = [pd.read_pickle(K + "out/lo_stake_heldout.pkl")[["race_id", "date", "odds", "ret", "ratio", "ev", "yr"]]]
    for yr, fT, d0, d1, h in (("y6", "out/y6/cache.pkl", "20201108", "20211107", "20210508"), ("y9", "out/y9/cache.pkl", "20171108", "20181107", "20180508"), ("y10", "out/y10/cache.pkl", "20161108", "20171107", "20170508")):
        ns = {"__name__": "x"}; keep = sys.argv; sys.argv = ["x", K + fT, d0, d1, h, "NUL"]
        try: exec(src, ns)
        finally: sys.argv = keep
        d = ns["d"]; q_ = 1 / d.odds; d["pn"] = q_ / q_.groupby(d.race_id).transform("sum")
        lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy(); del d, ns
        lo["ratio"] = lo_ratio(C["coef"], lo); lo["ev"] = lo.ratio * lo.pn * lo.odds; lo["yr"] = yr; P.append(lo[["race_id", "date", "odds", "ret", "ratio", "ev", "yr"]])
    pd.concat(P, ignore_index=True).to_pickle(OUT)
A = pd.read_pickle(OUT); YR = ["y10", "y9", "y6", "y5", "y4", "2024年", "2025/2〜"]; rng = np.random.default_rng(0)
def cell(g):
    x = g.groupby("race_id").ret.agg(["sum", "size"]); ii = rng.integers(0, len(x), (2000, len(x))); bs = x["sum"].to_numpy()[ii].sum(1) / x["size"].to_numpy()[ii].sum(1)
    return f"{len(g):,}点 | **{g.ret.mean():.0%}** | {np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%} | " + "/".join(f"{g[g.yr == y].ret.mean():.0%}" for y in YR)
L = ["# E1 の頑丈さ（7年分・確定オッズ）", "", "年別の順：" + "/".join(YR) + "（y4・2024年・2025/2〜・y5 は1年抜きの予測、y6・y9・y10 は固定係数）", "",
     "## ① 線を動かす", "", "| 線 | 点数 | 回収率 | 95%の範囲 | 年別 |", "|---|---|---|---|---|"]
for th in (1.1, 1.15, 1.18, 1.2, 1.22, 1.25, 1.3): L.append(f"| 期待値≥{th} | " + cell(A[A.ev >= th]) + " |")
L += ["", "## ② 期待値にゆらぎを足して選び直す（1分前の倍率のずれの代わり。対数で正規分布、20回の平均）", "", "| ゆらぎ（標準偏差） | 平均の点数 | 平均の回収率 | 20回の最小〜最大 |", "|---|---|---|---|"]
for s in (0.02, 0.05, 0.1):
    r = [];  n = []
    for i in range(20):
        e = A.ev * np.exp(rng.normal(-0.015, s, len(A))); g = A[e >= 1.2]; r.append(g.ret.mean()); n.append(len(g))
    L.append(f"| {s:.0%}（中心は−1.5%） | {np.mean(n):,.0f} | **{np.mean(r):.0%}** | {min(r):.0%}〜{max(r):.0%} |")
open(sys.argv[1], "w", encoding="utf-8").write(NL.join(L) + NL); print("done")
