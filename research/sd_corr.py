"""標準偏差の項目と「当たり」「回収」の相関（スピアマン順位相関＋並べ替えでp値）。sd_study.py の表を使う"""
import numpy as np, pandas as pd
from scipy.stats import spearmanr
src = open("C:/Users/take0/.claude/keirin/research/sd_study.py", encoding="utf-8").read().split('print("## 1)')[0]
exec(src)
FE = {"rp_sd": "得点の標準偏差", "rp_cv": "得点のばらつき率", "line_sd": "ラインの強さの標準偏差", "z_mean": "買い目3人の偏差値", "z_min": "3人で一番低い偏差値", "z3": "3着の人の偏差値", "lodds": "倍率（参考）"}
rng = np.random.default_rng(0)
def cor(D, f, y):
    d = D[[f, y]].dropna(); r = spearmanr(d[f], d[y])[0]
    # レース単位で並べ替えて偶然の幅
    null = [spearmanr(d[f].to_numpy(), rng.permutation(d[y].to_numpy()))[0] for _ in range(300)]
    p = (np.abs(null) >= abs(r)).mean()
    return r, p
for D in (top_in, top_out, B_in, B_out):
    D["hit"] = (D.ret > 0).astype(int); D["lodds"] = np.log(D.odds)
print("相関係数（−1〜+1。0なら無関係）。p＝偶然でこれ以上になる確率（0.05未満で「関係あり」）\n")
for nm, Di, Do in (("一番の目", top_in, top_out), ("3連単枠", B_in, B_out)):
    print(f"## {nm}（探す {len(Di)}点／未使用 {len(Do)}点）\n| 項目 | 当たりとの相関 探す | 未使用 | 回収との相関 探す | 未使用 |\n|---|---|---|---|---|")
    for f, lab in FE.items():
        a = [cor(D, f, y) for y in ("hit", "ret") for D in (Di, Do)]
        print(f"| {lab} | " + " | ".join(f"{r:+.3f}{'★' if p < 0.05 else ''}（p{p:.2f}）" for r, p in a) + " |")
    print()
