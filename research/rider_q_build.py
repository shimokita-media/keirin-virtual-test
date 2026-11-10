"""選手ごとの市場の見込み（最終の3連単300倍以下から：1着の見込み q1・3着以内の見込み q3）と、3連単の組の軽い表を作る。
出力: out/rider_q.pkl（race_id, number, q1, q3）、out/tri_compact.pkl（race_id, a, b, c, odds, ret, p）
使い方: python -I -X utf8 research/rider_q_build.py"""
import gc, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
T = pd.read_pickle(K + "out/angle_base_full.pkl")[["race_id", "combo", "p", "odds", "ret"]]
gc.collect()
print("rows", len(T))
T = T[T.combo.str.len() == 5]
T["a"] = T.combo.str[0].astype("int8"); T["b"] = T.combo.str[2].astype("int8"); T["c"] = T.combo.str[4].astype("int8")
T = T.drop(columns="combo"); T[["p", "odds", "ret"]] = T[["p", "odds", "ret"]].astype("float32")
s = T.groupby("race_id").p.transform("sum"); T["p"] = (T.p / s).astype("float32"); del s; gc.collect()
T.reset_index(drop=True).to_pickle(K + "out/tri_compact.pkl")
q1 = T.groupby(["race_id", "a"]).p.sum().rename("q1"); q1.index.names = ["race_id", "number"]
qs = [T.groupby(["race_id", k]).p.sum().rename_axis(["race_id", "number"]) for k in "abc"]
q3 = pd.concat(qs, axis=1).fillna(0).sum(axis=1).rename("q3")
pd.concat([q1, q3], axis=1).fillna(0).reset_index().to_pickle(K + "out/rider_q.pkl")
print("done", T.race_id.nunique())
