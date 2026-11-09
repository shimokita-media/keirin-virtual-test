"""締切1分前（T1）の倍率で作った3連単の表（out/live_t1/tri.pkl）を、angle_base と同じ形の表 out/angle_base_t1.pkl にする。払戻は確定のもの。"""
import pandas as pd
K = "C:/Users/take0/.claude/keirin/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
T0cols = pd.read_pickle(K + "out/angle_base.pkl").columns
SR = pd.read_pickle(K + "out/side_races_full.pkl").set_index("race_id")
X = prep(pd.read_pickle(K + "out/live_t1/tri.pkl")); X = X[(X["class"] != "L級") & (X.odds <= 300)].copy()
for c in ("race_type", "venue", "venue_id", "cup_id", "close_at", "start_at"): X[c] = X.race_id.map(SR[c])
s01, s12 = X.s01 == 1, X.s12 == 1; third = (X.r2_pos == 2) & s12; same3 = s01 & s12
order = same3 & (X.r0_pos == 0) & (X.r1_pos == 1) & (X.r2_pos == 2); nine, d2 = X.entries_number >= 9, X.day_index >= 2
RL = [third & (X.odds <= 30) & nine & d2, same3 & (X.odds <= 30) & nine & d2, same3 & (X.odds <= 30) & nine & (X.g_tf > 0),
      order & (X.odds <= 60) & (X.r0_prediction_mark >= 3) & (X.g_tf > 0) & (X.g_ex > 0), third & (X.odds <= 10) & (X.G == 1) & (X.r0_mk_rank == 1)]
X["nr"] = sum(r.astype(int) for r in RL)
Y = X[X.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
X["in_B"] = False; X.loc[Y.groupby("race_id").head(6).index, "in_B"] = True
X["is_top"] = False; X.loc[Y.groupby("race_id").head(1).index, "is_top"] = True
X.reindex(columns=T0cols).to_pickle(K + "out/angle_base_t1.pkl"); print(len(X), X.race_id.nunique())
