"""倍率の影響を除いても相関が残るか（ロジスティック回帰：当たり ~ log倍率 + 項目）。残れば市場より上、残らなければ市場が織り込み済み"""
import numpy as np, pandas as pd
from scipy.stats import norm
def logit(y, X):
    X = np.column_stack([np.ones(len(X)), X]); b = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ b)); H = X.T @ (X * (p * (1 - p))[:, None]); b = b + np.linalg.solve(H, X.T @ (y - p))
    se = np.sqrt(np.diag(np.linalg.inv(H))); return b[-1], 2 * norm.sf(abs(b[-1] / se[-1]))
exec(open("C:/Users/take0/.claude/keirin/research/sd_study.py", encoding="utf-8").read().split('print("## 1)')[0])
FE = {"rp_sd": "得点の標準偏差", "line_sd": "ラインの強さの標準偏差", "z_mean": "買い目3人の偏差値", "z_min": "3人で一番低い偏差値", "z3": "3着の人の偏差値"}
for nm, Di, Do in (("一番の目", top_in, top_out), ("3連単枠", B_in, B_out)):
    print(f"## {nm}\n| 項目 | 倍率を除いた効き 探す | 未使用 | 回収との相関(実額) 探す | 未使用 |\n|---|---|---|---|---|")
    for f, lab in FE.items():
        out = []
        for D in (Di, Do):
            d = D[[f, "odds", "ret"]].dropna(); d["hit"] = (d.ret > 0).astype(int)
            x = (d[f] - Di[f].mean()) / Di[f].std()
            b, pv = logit(d.hit.to_numpy(float), np.column_stack([np.log(d.odds), x]))
            out.append(f"{b:+.2f}{'★' if pv < 0.05 else ''}（p{pv:.2f}）")
        for D in (Di, Do):
            d = D[[f, "ret"]].dropna(); r = np.corrcoef(d[f], d.ret)[0, 1]; se = 1 / np.sqrt(len(d))
            out.append(f"{r:+.3f}{'★' if abs(r) > 2 * se else ''}")
        print(f"| {lab} | " + " | ".join(out) + " |")
    print()
