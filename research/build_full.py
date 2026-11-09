"""学習用の表を「全部」まとめる（2026-11-09 21:00）：angle_base（2025/2〜2026/11/5）＋ fresh8（2026/11/6〜8、本番DBから）＋ y2024a（2024/2/1〜7/8）
→ out/angle_base_full.pkl と、side も out/side_*_full.pkl にまとめる。3連単枠・一番の目の印も同じ法則で付ける。"""
import os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
T0 = pd.read_pickle(K + "out/angle_base.pkl")
SR = pd.concat([pd.read_pickle(K + f"out/side_races{s}.pkl") for s in ("", "_live", "_y2024a")]).drop_duplicates("race_id")
for nm in ("races", "entries", "results"):
    keys = {"races": ["race_id"], "entries": ["race_id", "number"], "results": ["race_id", "rank", "number"]}[nm]
    pd.concat([pd.read_pickle(K + f"out/side_{nm}{s}.pkl") for s in ("", "_live", "_y2024a")]).drop_duplicates(keys).to_pickle(K + f"out/side_{nm}_full.pkl")
parts = []
for f in ("out/fresh8/tri.pkl", "out/y2024a/tri.pkl"):
    X = prep(pd.read_pickle(K + f)); X = X[(X["class"] != "L級") & (X.odds <= 300)].copy()
    meta = SR.set_index("race_id")
    for c in ("race_type", "venue", "venue_id", "cup_id", "close_at", "start_at"): X[c] = X.race_id.map(meta[c])
    s01, s12 = X.s01 == 1, X.s12 == 1; third = (X.r2_pos == 2) & s12; same3 = s01 & s12
    order = same3 & (X.r0_pos == 0) & (X.r1_pos == 1) & (X.r2_pos == 2); nine, d2 = X.entries_number >= 9, X.day_index >= 2
    RL = [third & (X.odds <= 30) & nine & d2, same3 & (X.odds <= 30) & nine & d2, same3 & (X.odds <= 30) & nine & (X.g_tf > 0),
          order & (X.odds <= 60) & (X.r0_prediction_mark >= 3) & (X.g_tf > 0) & (X.g_ex > 0), third & (X.odds <= 10) & (X.G == 1) & (X.r0_mk_rank == 1)]
    X["nr"] = sum(r.astype(int) for r in RL)
    Y = X[X.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
    X["in_B"] = False; X.loc[Y.groupby("race_id").head(6).index, "in_B"] = True
    X["is_top"] = False; X.loc[Y.groupby("race_id").head(1).index, "is_top"] = True
    parts.append(X.reindex(columns=T0.columns))
F = pd.concat([T0] + parts, ignore_index=True).drop_duplicates(["race_id", "combo"])
F.to_pickle(K + "out/angle_base_full.pkl")
print(len(F), F.date.min(), F.date.max(), F.race_id.nunique())
