import sys, json, sqlite3, numpy as np, pandas as pd
c = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
F = pd.read_pickle("ana_2026.pkl"); ids_all = F.race_id.unique()
Fi = F.set_index(["race_id", "number"])
out = []
for i0 in range(0, len(ids_all), 1500):
    ids = tuple(ids_all[i0:i0+1500]); q = ",".join("?"*len(ids))
    t = pd.read_sql(f"SELECT race_id, combo, odds, popularity, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND bet_type='3連単' AND odds>0 AND race_id IN ({q})", c, params=ids)
    t = t[t.fetched_at == t.groupby("race_id").fetched_at.transform("max")].drop(columns="fetched_at")
    pay = pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単' AND race_id IN ({q})", c, params=ids)
    t = t.merge(pay, on=["race_id","combo"], how="left"); t["ret"] = t.payout.fillna(0)/100
    cb = t.combo.str.split("-", expand=True).astype(int)
    for k, s in enumerate("xyz"):
        key = list(zip(t.race_id, cb[k]))
        for col in ("pos", "line_idx", "ls", "single", "mk_rank", "pt_rank"):
            t[f"{s}_{col}"] = Fi[col].reindex(key).to_numpy()
    out.append(t); print(i0, flush=True)
T = pd.concat(out); T = T.merge(F.drop_duplicates("race_id")[["race_id","date","entries_number","class","nlines"]], on="race_id")
T.to_pickle("tri_2026.pkl"); print(len(T))
