"""Z の選び方の地図と、機械の見込みの正確さ（較正）を、まだ見ていない期間で確かめる（2026-11-09）。
使い方: python -I -X utf8 research/z_grid_period.py 予測.pkl 出力.md
- 予測.pkl：research/z_predict_period.py の出力（p_v2・p_D・odds・ret）
- 地図：当たる確率の下限 × 期待値の下限 ごとの 回収率・的中率・点数（v2 と D）。どこか1点だけ良いのではなく、まわりも良いか（なだらかか）を見る
- 較正：見込み（当たる確率）の帯ごとに、実際の的中率 ÷ 見込み。1.00 に近いほど見込みが正確"""
import sys, numpy as np, pandas as pd
src, outp = sys.argv[1:3]
Z = pd.read_pickle(src); OUT = open(outp, "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
P(f"# Z の選び方の地図と較正（{Z.date.min()}〜{Z.date.max()}・{Z.race_id.nunique():,}R・最終オッズ・各100円）" + NL)
for col, lab in (("p_v2", "機械 v2（事前登録Zの登録モデル）"), ("p_D", "機械 D（今使う機械）")):
    P(f"## {lab}：回収率（点数・的中率）" + NL)
    es = (0.8, 0.85, 0.9, 0.95, 1.0, 1.1); ps = (0.05, 0.08, 0.10, 0.12, 0.15, 0.20)
    P("| 当たる確率の下限＼期待値の下限 | " + " | ".join(str(e) for e in es) + " |" + NL + "|---|" + "---|" * len(es))
    for p in ps:
        cells = []
        for e in es:
            x = Z[(Z[col] >= p) & (Z[col] * Z.odds >= e)]
            cells.append(f"{x.ret.mean():.0%}（{len(x)}・{(x.ret > 0).mean():.0%}）" if len(x) >= 30 else f"−（{len(x)}）")
        P(f"| {p:.0%} | " + " | ".join(cells) + " |")
    P(NL + f"### {lab}：較正（見込みの帯ごとの 実際の的中率 ÷ 見込み）" + NL + NL + "| 見込みの帯 | 点数 | 見込みの平均 | 実際の的中率 | 実際÷見込み |" + NL + "|---|---|---|---|---|")
    bins = [0, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 1.0]
    for iv, x in Z.groupby(pd.cut(Z[col], bins), observed=True):
        P(f"| {iv.left:.0%}〜{iv.right:.0%} | {len(x):,} | {x[col].mean():.2%} | {(x.ret > 0).mean():.2%} | {(x.ret > 0).mean() / x[col].mean():.2f} |")
    P("")
print("done")
