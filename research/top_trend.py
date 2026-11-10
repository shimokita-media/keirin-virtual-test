"""一番の目の回収率を月ごと・四半期ごとに並べる（2023/11〜2026/11、確定オッズ）。新しい条件は探さない＝時期による変化の確認だけ。
2023/11〜2025/1 は out/y2024full/cache.pkl（使い終わった年）、2025/2〜は out/tri_base.parquet。
使い方: python -I -X utf8 research/top_trend.py reports/top_trend.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
A = pd.read_pickle(K + "out/y2024full/cache.pkl")
A = A.loc[A.is_top, ["race_id", "date", "odds", "ret", "venue", "race_type", "entries_number"]]
B = duckdb.sql(f"SELECT race_id, date, odds, ret, venue, race_type, entries_number FROM '{K}out/tri_base.parquet' WHERE is_top").df()
T = pd.concat([A, B[B.date > A.date.max()]]).reset_index(drop=True)
T["q"] = T.date.str[:4] + "Q" + ((T.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
rng = np.random.default_rng(0)
def ci(g):
    r = g.ret.to_numpy(); ii = rng.integers(0, len(r), (2000, len(r))); b = r[ii].mean(1)
    return np.percentile(b, 2.5), np.percentile(b, 97.5)
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 一番の目の回収率の時期による変化（確定オッズ・各100円）" + NL)
P(f"{T.date.min()}〜{T.date.max()}・{len(T):,}点。新しい条件は探していない。" + NL)
P("## 四半期ごと" + NL + "| 四半期 | 点数 | 当たり | 的中率 | 回収率 | 95%の範囲 | 平均倍率 | 当たりの平均倍率 |" + NL + "|---|---|---|---|---|---|---|---|")
for q, g in T.groupby("q"):
    lo, hi = ci(g); h = g[g.ret > 0]
    P(f"| {q} | {len(g)} | {len(h)} | {len(h) / len(g):.1%} | **{g.ret.mean():.0%}** | {lo:.0%}〜{hi:.0%} | {g.odds.mean():.1f} | {h.odds.mean() if len(h) else float('nan'):.1f} |")
P(NL + "## 年ごと" + NL + "| 年 | 点数 | 的中率 | 回収率 | 95%の範囲 | 平均倍率 |" + NL + "|---|---|---|---|---|---|")
for y, g in T.groupby(T.date.str[:4]):
    lo, hi = ci(g); P(f"| {y} | {len(g)} | {(g.ret > 0).mean():.1%} | **{g.ret.mean():.0%}** | {lo:.0%}〜{hi:.0%} | {g.odds.mean():.1f} |")
# 的中率×平均倍率の分解：的中率が下がったのか、当たったときの倍率が下がったのか
P(NL + "## 2024年と2025年以降の違いの分解" + NL)
for nm, g in (("〜2025/1", T[T.date <= "20250131"]), ("2025/2〜", T[T.date > "20250131"])):
    h = g[g.ret > 0]
    P(f"- {nm}：{len(g)}点、的中率 {len(h) / len(g):.1%}、当たりの平均払戻 {h.ret.mean():.1f}倍、1レースの平均倍率 {g.odds.mean():.1f}、市場の見込みの合計÷点数 {(1 / g.odds).mean():.3f}（＝倍率から見た当たりやすさ）、実際の的中率÷倍率から見た当たりやすさ {len(h) / len(g) / (1 / g.odds).mean():.2f}")
print("done")
