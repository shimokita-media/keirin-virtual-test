"""3連単の表（tri3_build の出力）を、angle_base と同じ形の表にする（期間を問わない版。build_t1.py の一般化）。
3連単枠・一番の目の印も tri_rule.py（commit 18adc39）と同じ5法則で付ける。レースの情報（種類・場・発走時刻など）は side の races から。
使い方: python -I -X utf8 research/build_cache_period.py 3連単の表.pkl sideの接尾辞 出力.pkl
例:     ... out/y2024full/tri.pkl _y2024full out/angle_base_y2024full.pkl"""
import sys, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
src, suf, dst = sys.argv[1:4]
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
T0cols = pd.read_pickle(K + "out/angle_base.pkl").columns  # 列をそろえる（機械が同じ特徴量を使えるように）
SR = pd.read_pickle(K + f"out/side_races{suf}.pkl").drop_duplicates("race_id").set_index("race_id")
X = prep(pd.read_pickle(K + src if not src.startswith(("C:", "/")) else src))
X = X[(X["class"] != "L級") & (X.odds <= 300)].copy().reset_index(drop=True)  # 小分けで作った表は行番号が重複するので振り直す（重複したまま印を付けると、同じ番号の行すべてに印が付く。2026-11-10 に実際に起きた）
for c in ("race_type", "venue", "venue_id", "cup_id", "close_at", "start_at"): X[c] = X.race_id.map(SR[c])
s01, s12 = X.s01 == 1, X.s12 == 1; third = (X.r2_pos == 2) & s12; same3 = s01 & s12
order = same3 & (X.r0_pos == 0) & (X.r1_pos == 1) & (X.r2_pos == 2); nine, d2 = X.entries_number >= 9, X.day_index >= 2
RL = [third & (X.odds <= 30) & nine & d2, same3 & (X.odds <= 30) & nine & d2, same3 & (X.odds <= 30) & nine & (X.g_tf > 0),
      order & (X.odds <= 60) & (X.r0_prediction_mark >= 3) & (X.g_tf > 0) & (X.g_ex > 0), third & (X.odds <= 10) & (X.G == 1) & (X.r0_mk_rank == 1)]
X["nr"] = sum(r.astype(int) for r in RL)
Y = X[X.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
X["in_B"] = False; X.loc[Y.groupby("race_id").head(6).index, "in_B"] = True
X["is_top"] = False; X.loc[Y.groupby("race_id").head(1).index, "is_top"] = True
miss = [c for c in T0cols if c not in X.columns]
X.reindex(columns=T0cols).to_pickle(K + dst if not dst.startswith(("C:", "/")) else dst)
print(len(X), X.race_id.nunique(), X.date.min(), X.date.max(), "（angle_base にあってこの表にない列＝NaN：", len(miss), "個）")
