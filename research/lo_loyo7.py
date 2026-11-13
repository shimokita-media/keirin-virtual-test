"""ライン順の機械を7年で1年抜きに学び直したとき、E1（期待値≥1.2）の弱い年が上がるか（2026-11-13 夜、9年の確かめの後）。
年：y4・y5・y6・y7・y8・2024年・2025/2〜（y9・y10 は表を消したので入れない）。ライン順×15倍以下。固定係数（4年版）との比較。
使い方: python -I -X utf8 research/lo_loyo7.py reports/lo_loyo7.md"""
import sys, os, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8"))
SRC = {"y4": ("out/y4/cache.pkl", "20221108", "20231107", "20230508"), "y5": ("out/y5/cache.pkl", "20211108", "20221107", "20220508"),
       "y6": ("out/y6/cache.pkl", "20201108", "20211107", "20210508"), "y7": ("out/y7/cache.pkl", "20191108", "20201107", "20200508"),
       "y8": ("out/y8/cache.pkl", "20181108", "20191107", "20190508"), "2024年": ("out/y2024full/cache.pkl", "20231108", "20250131", "20240615"),
       "2025/2〜": ("out/angle_base.pkl", "20250201", "20261105", "20251231")}
src = open(K + "research/prereg_eval_y5_lo.py", encoding="utf-8").read().split("base = d[")[0]
OUT = K + "out/lo15_feat7.pkl"
if not os.path.exists(OUT):
    P = []
    for yr, (f, d0, d1, h) in SRC.items():
        ns = {"__name__": "x"}; keep = sys.argv; sys.argv = ["x", K + f, d0, d1, h, "NUL"]
        try: exec(src, ns)
        finally: sys.argv = keep
        d = ns["d"]; q_ = 1 / d.odds; d["pn"] = q_ / q_.groupby(d.race_id).transform("sum")
        lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy(); del d, ns
        lo["hit"] = (lo.ret > 0).astype(float); lo["yr"] = yr; P.append(lo); print(yr, len(lo), flush=True)
    A = pd.concat(P, ignore_index=True); A.to_pickle(OUT)
A = pd.read_pickle(OUT); X = lo_feats(A); off = lo_lg(A.pn).to_numpy(); y = A.hit.to_numpy()
A["ev_fix"] = lo_ratio(C["coef"], A) * A.pn * A.odds; A["ev_new"] = np.nan
Am = np.column_stack([np.ones(len(X)), X.to_numpy(float)])
for k in SRC:
    tr = (A.yr != k).to_numpy(); b = lo_fit(X[tr], y[tr], off[tr], 20.0)
    p = 1 / (1 + np.exp(-(off[~tr] + Am[~tr] @ b))); A.loc[~tr, "ev_new"] = p * A.odds[~tr]
def row(nm, c, th):
    g = A[A[c] >= th]; yrs = [g[g.yr == k].ret.mean() for k in SRC]
    return f"| {nm} | {len(g):,} | **{g.ret.mean():.0%}** | " + " / ".join(f"{v:.0%}" for v in yrs) + f" | {min(yrs):.0%} |"
L = ["# 7年で1年抜きに学び直した機械と、固定の4年版の比べ（ライン順×15倍以下）", "", "年別の順：" + " / ".join(SRC), "",
     "注意：固定の4年版は y4・2024年・2025〜・y5 で学んでいるので、その4年の数字は甘い（学んだ年で測っている）。学び直し版はどの年も抜いた年で測っている", "",
     "| 機械・線 | 点数 | 回収率 | 年別 | 一番悪い年 |", "|---|---|---|---|---|"]
for th in (1.15, 1.2, 1.25):
    L.append(row(f"固定4年版・期待値≥{th}", "ev_fix", th)); L.append(row(f"7年1年抜き・期待値≥{th}", "ev_new", th))
open(sys.argv[1], "w", encoding="utf-8").write(NL.join(L) + NL); print("done")
