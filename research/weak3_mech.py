"""本命3連単×弱い3着の仕組み（2023/11〜2026/11、確定オッズ。y5・y4 は見ない）。
3連単10倍以下×（G戦か9車）の中で、3着の得点順位ごと・1-2着の形ごと・倍率の帯ごとに、当たり÷見込みと回収率を、2024年（〜2025/1）と2025/2〜で並べる。
見込み＝確定オッズをレースの中で合計1にそろえたもの（300倍以下の中で）。新しい条件は登録しない（y5 の登録案の材料）。
使い方: python -I -X utf8 research/weak3_mech.py reports/weak3_mech.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
A = pd.read_pickle(K + "out/y2024full/cache.pkl")[["race_id", "combo", "date", "odds", "ret", "G", "entries_number", "r2_pt_rank", "s01", "s12", "r0_pos", "r2_pos"]]
B = duckdb.sql(f"SELECT race_id, combo, date, odds, ret, entries_number, s01, s12, r0_pos, r2_pos FROM '{K}out/tri_base.parquet' WHERE date > '20250131'").df()
E = pd.read_pickle(K + "out/side_entries_full.pkl"); R = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id").set_index("race_id")
EA = E[E.absent != 1].copy(); EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
look = EA.set_index(["race_id", "number"]).ptr
B["r2_pt_rank"] = look.reindex(list(zip(B.race_id, B.combo.str.split("-").str[2].astype(int)))).to_numpy()
B["G"] = B.race_id.map(R.grade).fillna("").astype(str).str.startswith("G").astype(int)
A["era"], B["era"] = "2024年", "2025/2〜"
T = pd.concat([A, B]).reset_index(drop=True); del A, B
q = 1 / T.odds; T["p"] = q / q.groupby(T.race_id).transform("sum"); T["hit"] = (T.ret > 0).astype(float)
X = T[(T.odds <= 10) & ((T.G == 1) | (T.entries_number >= 9))].copy()
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
def row(g): return f"{len(g)}点・{g.hit.sum() / g.p.sum():.2f}・**{g.ret.mean():.0%}**" if len(g) else "−"
P("# 本命3連単×弱い3着の仕組み（10倍以下×(G戦か9車)、確定オッズ）" + NL + "各セル：点数・当たり÷見込み・回収率" + NL)
P("## 3着の得点順位ごと" + NL + "| 3着の得点順位 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|")
for k in range(1, 10):
    P(f"| {k}位 | {row(X[(X.r2_pt_rank == k) & (X.era == '2024年')])} | {row(X[(X.r2_pt_rank == k) & (X.era == '2025/2〜')])} |")
W = X[X.r2_pt_rank >= 5]
P(NL + "## 3着5位以下の中で：3着の選手の位置" + NL + "| 3着の選手 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|")
for nm, m in (("1-2着と同じライン（s12=1）", W.s12 == 1), ("1-2着と別ライン", W.s12 == 0)):
    P(f"| {nm} | {row(W[m & (W.era == '2024年')])} | {row(W[m & (W.era == '2025/2〜')])} |")
P(NL + "## 3着5位以下の中で：倍率の帯" + NL + "| 倍率 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|")
for lo, hi in ((0, 4), (4, 6), (6, 8), (8, 10)):
    m = (W.odds > lo) & (W.odds <= hi); P(f"| {lo}〜{hi}倍 | {row(W[m & (W.era == '2024年')])} | {row(W[m & (W.era == '2025/2〜')])} |")
P(NL + "## 比べる：10倍以下を全部（G戦・9車の条件なし）で3着の得点順位5位以下" + NL)
Y = T[(T.odds <= 10) & (T.r2_pt_rank >= 5)]
for e in ("2024年", "2025/2〜"):
    P(f"- {e}：G戦か9車 {row(W[W.era == e])}／それ以外（F戦の7車以下） {row(Y[(Y.era == e) & ~((Y.G == 1) | (Y.entries_number >= 9))])}")
print("done")
