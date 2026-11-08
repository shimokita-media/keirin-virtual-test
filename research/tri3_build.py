"""3連単（300倍以下）× 他の券種の倍率 × 3人の特徴。使い方: python tri2_build.py 選手表.pkl 出力.pkl"""
import sys, sqlite3, numpy as np, pandas as pd
c = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
F = pd.read_pickle(sys.argv[1]); F = F[F["class"] != "L級"]; Fi = F.set_index(["race_id", "number"]); ids_all = F.race_id.unique()
cols = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "line_idx", "prediction_mark", "p1", "p3", "ro_first5", "ro_last5", "ro_mean", "ro_top3", "ro_top3_10", "h_surp", "h_n", "h_surp_ewm", "h_surp_rate", "h_t3_rate", "gear", "n_front", "n_marker", "style"]
def norm(d):
    d = d.copy(); d["q"] = 1 / d.odds; d["q"] /= d.groupby("race_id").q.transform("sum"); return d
out = []
for i0 in range(0, len(ids_all), 1000):
    ids = tuple(ids_all[i0:i0 + 1000]); q = ",".join("?" * len(ids))
    o = pd.read_sql(f"SELECT race_id, bet_type, combo, odds, popularity, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND odds>0 AND race_id IN ({q})", c, params=ids)
    o = o[o.fetched_at == o.groupby(["race_id", "bet_type"]).fetched_at.transform("max")]
    t = norm(o[o.bet_type == "3連単"]).rename(columns={"q": "p"})
    t = t[t.odds <= 300].copy()
    cb = t.combo.str.split("-", expand=True).astype(int); x, y, z = cb[0], cb[1], cb[2]
    ex = norm(o[o.bet_type == "2車単"]).set_index(["race_id", "combo"])
    tf = norm(o[o.bet_type == "3連複"]).set_index(["race_id", "combo"])
    wd = o[o.bet_type == "ワイド"].set_index(["race_id", "combo"]).odds
    qn = norm(o[o.bet_type == "2車複"]).set_index(["race_id", "combo"])
    def pk(a, b): return np.minimum(a, b).astype(str) + "-" + np.maximum(a, b).astype(str)
    t["ex_q"] = ex.q.reindex(list(zip(t.race_id, x.astype(str) + "-" + y.astype(str)))).to_numpy()
    srt = np.sort(cb.to_numpy(), axis=1); t["tf_q"] = tf.q.reindex(list(zip(t.race_id, ["-".join(map(str, r)) for r in srt]))).to_numpy()
    t["qn_q"] = qn.q.reindex(list(zip(t.race_id, pk(x, y)))).to_numpy()
    for nm, (a, b) in {"w12": (x, y), "w13": (x, z), "w23": (y, z)}.items(): t[nm] = wd.reindex(list(zip(t.race_id, pk(a, b)))).to_numpy()
    # 3連単の中での比率（同じ1-2着の中で、この3着がどれだけ売れているか）
    t["xy_p"] = t.groupby([t.race_id, x, y]).p.transform("sum"); t["set_p"] = t.groupby([t.race_id, pd.Series(["-".join(map(str, r)) for r in srt], index=t.index)]).p.transform("sum")
    pay = pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単' AND race_id IN ({q})", c, params=ids)
    t = t.merge(pay, on=["race_id", "combo"], how="left"); t["ret"] = t.payout.fillna(0) / 100
    cb = t.combo.str.split("-", expand=True).astype(int)
    for j in range(3):
        X = Fi[cols].reindex(list(zip(t.race_id, cb[j]))); X.columns = [f"r{j}_{c_}" for c_ in cols]
        t = pd.concat([t.reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    out.append(t.drop(columns=["fetched_at", "bet_type", "payout"])); print(i0, len(ids_all), flush=True)
T = pd.concat(out); R = F.drop_duplicates("race_id").set_index("race_id")
for col in ("date", "entries_number", "nlines", "n_strong_nige", "class", "grade", "day_index", "race_no", "hour", "wind", "venue_c"): T[col] = T.race_id.map(R[col])
T = T[T.r0_pos.notna()]; T.to_pickle(sys.argv[2]); print(len(T))
