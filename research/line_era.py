"""市場の変化か、法則の合わせ込みかを分ける：一番の目に選ばれていない目も含めた「ラインの形」全体の 当たり÷見込み を、2024年（〜2025/1）と 2025/2〜 で比べる。新しい条件は探さない。
形：同じライン3人（s01=1 かつ s12=1）／そのうちライン順（先頭→番手→3番手）／1-2着が同じライン（s01=1）／別ライン。各40倍以下と全部（300倍以下）。
データ：〜2025/1 は out/y2024full/cache.pkl、2025/2〜 は out/tri_base.parquet。見込み＝確定オッズをレースの中で合計1にそろえたもの（300倍以下の中で）。
使い方: python -I -X utf8 research/line_era.py reports/line_era.md"""
import sys, duckdb, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
cols = ["race_id", "date", "odds", "ret", "s01", "s12", "r0_pos", "r1_pos", "r2_pos", "is_top"]
A = pd.read_pickle(K + "out/y2024full/cache.pkl")[cols]
B = duckdb.sql(f"SELECT {', '.join(cols)} FROM '{K}out/tri_base.parquet' WHERE date > '20250131'").df()
A["era"], B["era"] = "2024年（〜2025/1）", "2025/2〜"
T = pd.concat([A, B]).reset_index(drop=True); del A, B
q = 1 / T.odds; T["p"] = q / q.groupby(T.race_id).transform("sum"); T["hit"] = (T.ret > 0).astype(float)
same3 = (T.s01 == 1) & (T.s12 == 1)
order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
shapes = [("同じライン3人", same3), ("　うちライン順（先頭→番手→3番手）", order), ("1-2着が同じライン", T.s01 == 1), ("1-2着が別ライン", T.s01 == 0), ("全部", T.s01.notna())]
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# ラインの形全体の割安さは、2025年から変わったか（確定オッズ・新しい条件は探していない）" + NL)
P("当たり÷見込み（1より大きい＝市場の見込みより当たる）と回収率。一番の目を**除いた**目でも出す（法則で選んだ目の影響を外すため）。" + NL)
for cap in (40, 300):
    P(f"## {cap}倍以下" + NL + "| 形 | 時期 | 点数 | 当たり | 当たり÷見込み | 回収率 | 一番の目を除くと：当たり÷見込み | 回収率 |" + NL + "|---|---|---|---|---|---|---|---|")
    for nm, m in shapes:
        for e in ("2024年（〜2025/1）", "2025/2〜"):
            x = T[m & (T.odds <= cap) & (T.era == e)]; y = x[~x.is_top]
            P(f"| {nm} | {e} | {len(x):,} | {int(x.hit.sum()):,} | **{x.hit.sum() / x.p.sum():.3f}** | {x.ret.mean():.0%} | **{y.hit.sum() / y.p.sum():.3f}** | {y.ret.mean():.0%} |")
    P("")
print("done")
