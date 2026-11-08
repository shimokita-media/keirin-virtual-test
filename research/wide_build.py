"""全ワイドの組み合わせ × 2人の特徴 × 市場の見込み（3連単から）× 結果。使い方: python wide_build.py 選手表.pkl 出力.pkl"""
import sys, sqlite3, itertools, numpy as np, pandas as pd
F = pd.read_pickle(sys.argv[1]); OUT = sys.argv[2]
c = sqlite3.connect("file:" + __import__("os").environ.get("KDB", "C:/Users/take0/.claude/keirin/keirin.sqlite") + "?mode=ro", uri=True)
ids_all = F.race_id.unique(); out = []
cols = ["pos", "ls", "single", "style", "pt_rank", "mk_rank", "age", "prediction_mark", "third_rate", "first_rate", "lead_rank", "line_idx", "p3", "p1", "gear", "n_front", "n_marker"]
for i0 in range(0, len(ids_all), 1500):
    ids = tuple(ids_all[i0:i0 + 1500]); q = ",".join("?" * len(ids))
    o = pd.read_sql(f"SELECT race_id, bet_type, combo, odds, fetched_at FROM odds WHERE phase='" + __import__("os").environ.get("KPH", "POST") + f"' AND source='winticket' AND bet_type IN ('3連単','ワイド') AND odds>0 AND race_id IN ({q})", c, params=ids)
    o = o[o.fetched_at == o.groupby("race_id").fetched_at.transform("max")]
    t = o[o.bet_type == "3連単"].copy(); t["p"] = 1 / t.odds; t["p"] /= t.groupby("race_id").p.transform("sum")
    cb = t.combo.str.split("-", expand=True).astype(int)
    # 2人が両方3着以内に入る見込み
    parts = []
    for i, j in ((0, 1), (0, 2), (1, 2)):
        a, b = np.minimum(cb[i], cb[j]), np.maximum(cb[i], cb[j])
        parts.append(pd.DataFrame({"race_id": t.race_id.values, "combo": a.astype(str).values + "-" + b.astype(str).values, "p": t.p.values}))
    pw = pd.concat(parts).groupby(["race_id", "combo"]).p.sum().rename("pw")
    w = o[o.bet_type == "ワイド"][["race_id", "combo", "odds"]].merge(pw.reset_index(), on=["race_id", "combo"])
    pay = pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='ワイド' AND race_id IN ({q})", c, params=ids)
    w = w.merge(pay, on=["race_id", "combo"], how="left"); w["ret"] = w.payout.fillna(0) / 100
    ab = w.combo.str.split("-", expand=True).astype(int); w["na"], w["nb"] = ab[0], ab[1]
    Fi = F[F.race_id.isin(ids)].set_index(["race_id", "number"])
    for s, n in (("a", "na"), ("b", "nb")):
        X = Fi[cols].reindex(list(zip(w.race_id, w[n]))); X.columns = [f"{s}_{x}" for x in cols]
        w = pd.concat([w.reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    R = F[F.race_id.isin(ids)].drop_duplicates("race_id").set_index("race_id")[["date", "venue", "grade", "class", "race_type", "day_index", "race_no", "entries_number", "nlines", "n_strong_nige"]]
    w = w.merge(R, left_on="race_id", right_index=True)
    out.append(w); print(i0, len(ids_all), flush=True)
W = pd.concat(out); W = W[W.a_pos.notna() & W.b_pos.notna()]
W.to_pickle(OUT); print(len(W))
