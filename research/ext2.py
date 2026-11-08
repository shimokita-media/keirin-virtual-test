"""相性・大会中の調子・同じ先頭の後ろでの成績を足す（すべて、そのレースより前の情報だけ）"""
import sys, sqlite3, numpy as np, pandas as pd
F = pd.read_pickle(sys.argv[1])
c = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
cup = dict(c.execute("SELECT race_id, cup_id FROM races"))
F["cup_id"] = F.race_id.map(cup); F["rk"] = F["rank"].fillna(9).clip(upper=9)
F["t"] = F.start.astype(float)
# 1) 同じ大会の前の日の着順
F = F.sort_values(["cup_id", "player_id", "day_index"])
g = F.groupby(["cup_id", "player_id"])
F["cup_prev_rank"] = g.rk.shift(); F["cup_prev_top3"] = g.top3.shift().astype(float); F["cup_n"] = g.cumcount()
F["cup_prev_surp"] = g.surp.shift()
# 2) 相性：過去に同じレースを走った相手に先着した割合
E = F[["race_id", "t", "player_id", "rk"]]
P = E.merge(E, on=["race_id", "t"], suffixes=("", "_o")); P = P[P.player_id != P.player_id_o]
P["ahead"] = (P.rk < P.rk_o).astype(float)
P = P.sort_values("t"); P["pair"] = P.player_id + "_" + P.player_id_o
P["cum_n"] = P.groupby("pair").cumcount(); P["cum_a"] = P.groupby("pair").ahead.cumsum() - P.ahead  # その対戦より前
h = P.groupby(["race_id", "player_id"]).agg(h2h_n=("cum_n", "sum"), h2h_a=("cum_a", "sum")).reset_index()
F = F.merge(h, on=["race_id", "player_id"], how="left"); F["h2h_rate"] = F.h2h_a / F.h2h_n.where(F.h2h_n > 0)
F["h2h_edge"] = F.h2h_a - F.h2h_n * 0.5  # 五分より何回多く先着したか
# 3) 同じ先頭の後ろを走ったときの成績（2番手以降）
lead = F[F.pos == 0][["race_id", "line_idx", "player_id"]].rename(columns={"player_id": "lead_pid"})
F = F.merge(lead, on=["race_id", "line_idx"], how="left")
F.loc[F.pos == 0, "lead_pid"] = None
B = F[F.lead_pid.notna()].sort_values("t").copy(); B["k"] = B.player_id + "_" + B.lead_pid
gb = B.groupby("k")
B["beh_n"] = gb.cumcount(); B["beh_t3"] = gb.top3.cumsum() - B.top3; B["beh_surp"] = gb.surp.cumsum() - B.surp
F = F.merge(B[["race_id", "player_id", "beh_n", "beh_t3", "beh_surp"]], on=["race_id", "player_id"], how="left")
F["beh_rate"] = F.beh_t3 / F.beh_n.where(F.beh_n > 0)
F.to_pickle(sys.argv[2])
print(len(F), F[["cup_prev_rank", "h2h_n", "beh_n"]].describe().loc[["count", "mean"]].round(2).to_string())
