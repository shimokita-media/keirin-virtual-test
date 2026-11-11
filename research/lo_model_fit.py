"""ライン順の機械を、見た3期間（y4・2024年・2025/2〜2026/11/5）まとめて学ばせて係数を固定する → research/lo_model_coef.json（★事前登録 L4 用。y5 を見る前に作る）。
使い方: python -I -X utf8 research/lo_model_fit.py"""
import json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
D = pd.concat([pd.read_pickle(K + f) for f in ("out/lo_all_y4.pkl", "out/lo_all_2024年.pkl", "out/lo_all_20252.pkl")], ignore_index=True)
b = lo_fit(lo_feats(D), D.hit.to_numpy(), lo_lg(D.pn).to_numpy())
json.dump({"cols": ["const"] + LO_COLS, "coef": [float(x) for x in b], "lam": 20.0, "rows": int(len(D)), "trained_on": "y4+2024+2025/2-2026/11/5, line-order & odds<=15"},
          open(K + "research/lo_model_coef.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
r = lo_ratio(b, D)
for th in (1.2, 1.3, 1.4):
    g = D[r >= th]; print(f"学んだ3期間の中（参考）: 比 {th} 以上 {len(g):,}点・{g.ret.mean():.0%}")
print("saved", dict(zip(["const"] + LO_COLS, np.round(b, 3))))
