"""選手単位で「1着の確率」を学習（市場の1着見込みを出発点に補正）→ 3連単の確率を組み立て直す"""
import sys, numpy as np, pandas as pd, lightgbm as lgb
F = pd.read_pickle(sys.argv[2] if len(sys.argv) > 2 else "ana_all.pkl"); F = F[F["class"] != "L級"].copy()
F["style_c"] = F["style"].map({"逃": 0, "両": 1, "追": 2}); F["S"] = (F["class"] == "S級").astype(float)
F["p1"] = F.p1.clip(1e-4, 0.99); F["lp1"] = np.log(F.p1 / (1 - F.p1)); F["win"] = (F["rank"] == 1).astype(int)
feats = ["lp1", "p3", "pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark", "style_c",
         "ro_first5", "ro_last5", "ro_mean", "ro_top3", "ro_top3_10", "h_surp", "h_n", "h_surp_ewm", "h_surp_rate", "h_t3_rate", "gear", "n_front", "n_marker",
         "entries_number", "nlines", "n_strong_nige", "S", "day_index", "hour", "wind", "venue_c"] + (sys.argv[3].split(",") if len(sys.argv) > 3 else [])
for f in feats: F[f] = F[f].astype(np.float32)
tr = F[F.date < "20260701"]; va = F[(F.date >= "20260701") & (F.date < "20260901")]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=300, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(tr[feats], tr.win, init_score=tr.lp1), 3000, valid_sets=[lgb.Dataset(va[feats], va.win, init_score=va.lp1)], callbacks=[lgb.early_stopping(100, verbose=False)])
nb = max(m.best_iteration, 1)
def ll(y, p): return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
pv = 1 / (1 + np.exp(-(m.predict(va[feats], raw_score=True) + va.lp1)))
print("木", nb, "検証の損失 市場", round(ll(va.win, va.p1), 5), "→ 機械", round(ll(va.win, pv), 5))
mode = sys.argv[1]
if mode == "test":
    tv = F[F.date < "20260901"]; m = lgb.train(P, lgb.Dataset(tv[feats], tv.win, init_score=tv.lp1), nb); D = F[F.date >= "20260901"].copy()
else:
    D = va.copy()
D["q"] = 1 / (1 + np.exp(-(m.predict(D[feats], raw_score=True) + D.lp1))); D["q"] /= D.groupby("race_id").q.transform("sum")
D["pm"] = D.p1 / D.groupby("race_id").p1.transform("sum")
D[["race_id", "number", "q", "pm"]].to_pickle(f"rider_q_{mode}.pkl")
imp = pd.Series(m.feature_importance("gain"), feats).sort_values(ascending=False); print("効いた手がかり:", ", ".join(imp.head(12).index))
