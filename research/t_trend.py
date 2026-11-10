"""本命3連単×弱い3着（事前登録T：3連単10倍以下 ×（G戦か9車立て）× 3着の得点順位5位以下）の時期ごとの安定（2023/11〜2026/11、確定オッズ）。条件は変えない。
2023/11〜2025/1 は out/y2024full/cache.pkl（r2_pt_rank・G がある）。2025/2〜 は out/tri_base.parquet に side_entries_full（得点順位）・side_races_full（グレード）をつないで同じ定義で作る。
参考に「3着の得点順位6位以下」（登録「とても弱い3着」、y4 で判定）も並べる。
使い方: python -I -X utf8 research/t_trend.py reports/t_trend.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
A = pd.read_pickle(K + "out/y2024full/cache.pkl")
A = A.loc[(A.odds <= 10), ["race_id", "date", "odds", "ret", "G", "entries_number", "r2_pt_rank"]]
B = duckdb.sql(f"SELECT race_id, combo, date, odds, ret, entries_number FROM '{K}out/tri_base.parquet' WHERE odds <= 10 AND date > '20250131'").df()
E = pd.read_pickle(K + "out/side_entries_full.pkl"); R = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id").set_index("race_id")
EA = E[E.absent != 1].copy(); EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
look = EA.set_index(["race_id", "number"]).ptr
B["r2_pt_rank"] = look.reindex(list(zip(B.race_id, B.combo.str.split("-").str[2].astype(int)))).to_numpy()
B["G"] = B.race_id.map(R.grade).fillna("").astype(str).str.startswith("G").astype(int)
T = pd.concat([A, B.drop(columns="combo")]).reset_index(drop=True)
base = (T.G == 1) | (T.entries_number >= 9)
T5, T6 = T[base & (T.r2_pt_rank >= 5)], T[base & (T.r2_pt_rank >= 6)]
rng = np.random.default_rng(0)
def ci(g):
    if len(g) < 2: return "−"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (2000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    return f"**{g.ret.mean():.0%}**（{len(g)}点・{int((g.ret > 0).sum())}本・{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 本命3連単×弱い3着（T）の時期ごとの安定（確定オッズ・各100円・条件は登録のまま）" + NL)
P("2024年（〜2025/1）は判定に使った未使用の年。2025/2〜 は T を見つけた探す期間を含む。" + NL)
P("## 年ごと" + NL + "| 年 | T（3着5位以下） | 参考：3着6位以下 | 参考：10倍以下×(G戦か9車)全部 |" + NL + "|---|---|---|---|")
for y in sorted(T.date.str[:4].unique()):
    m = T.date.str[:4] == y
    P(f"| {y} | {ci(T5[T5.date.str[:4] == y])} | {ci(T6[T6.date.str[:4] == y])} | {ci(T[base & m])} |")
T["q"] = T.date.str[:4] + "Q" + ((T.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
T5 = T5.assign(q=T.q); T6 = T6.assign(q=T.q)
P(NL + "## 四半期ごと" + NL + "| 四半期 | T（3着5位以下） | 参考：3着6位以下 |" + NL + "|---|---|---|")
for q in sorted(T.q.unique()):
    P(f"| {q} | {ci(T5[T5.q == q])} | {ci(T6[T6.q == q])} |")
print("done")
