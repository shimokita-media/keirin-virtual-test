import sys, numpy as np, pandas as pd, lightgbm as lgb
exec(open("tri2_model.py", encoding="utf-8").read().split("cols = ")[0])  # prep()
T = prep(pd.read_pickle("tri3_all.pkl"))
for j in range(3): T[f"r{j}_style"] = T[f"r{j}_style"].map({"逃": 0, "両": 1, "追": 2})
base_cols = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark", "p1", "p3"]
new_cols = ["ro_first5", "ro_last5", "ro_mean", "ro_top3", "ro_top3_10", "h_surp", "h_n", "h_surp_ewm", "h_surp_rate", "h_t3_rate", "gear", "n_front", "n_marker", "style"]
F0 = ["lodds", "popularity", "g_ex", "g_tf", "g_qn", "cond", "lw12", "lw13", "lw23", "s01", "s12", "s02"] + [f"r{j}_{c}" for j in range(3) for c in base_cols] + ["entries_number", "nlines", "n_strong_nige", "S", "G", "day_index"]
F1 = F0 + [f"r{j}_{c}" for j in range(3) for c in new_cols] + ["hour", "wind", "venue_c"]
for f in F1: T[f] = T[f].astype(np.float32)
tr = T[(T.date < "20260701")]; va = T[(T.date >= "20260701") & (T.date < "20260901")]; te = T[T.date >= "20260901"]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=1000, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1)
def s(g, D):
    if len(g) < 30: return f"{len(g)}点 当たり{int((g.ret>0).sum())}"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    return f"{len(g)}点 1日{len(g)/D.date.nunique():.1f} {g.ret.mean():.0%}[{np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}] 当たり{int((g.ret>0).sum())} 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby(g.date.str[2:6]))
MODE = sys.argv[1]  # "val" か "test"
for nm, feats in (("今までの手がかり", F0), ("新しい手がかり込み", F1)):
    m = lgb.train(P, lgb.Dataset(tr[feats], tr.y, init_score=tr.lp), 3000, valid_sets=[lgb.Dataset(va[feats], va.y, init_score=va.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
    nb = max(m.best_iteration, 1); print(f"### {nm}（木{nb}、検証の損失 {m.best_score['valid_0']['binary_logloss']:.5f}）")
    if MODE == "val":
        D = va.copy(); D["ev"] = 1 / (1 + np.exp(-(m.predict(D[feats], raw_score=True) + D.lp))) * D.odds
    else:
        tv = pd.concat([tr, va]); m = lgb.train(P, lgb.Dataset(tv[feats], tv.y, init_score=tv.lp), nb)
        D = te.copy(); D["ev"] = 1 / (1 + np.exp(-(m.predict(D[feats], raw_score=True) + D.lp))) * D.odds
        D[D.ev >= 0.9][["race_id", "date", "combo", "odds", "ev", "ret", "entries_number", "s01", "s12", "r0_pos", "r1_pos", "r2_pos"]].to_pickle(f"tri3_test_{len(feats)}.pkl")
        imp = pd.Series(m.feature_importance("gain"), feats).sort_values(ascending=False); print("  効いた手がかり:", ", ".join(f"{k}" for k in imp.head(12).index))
    for hi in (30, 100, 300):
        for th in (1.0, 1.1, 1.2, 1.3):
            g = D[(D.odds <= hi) & (D.ev >= th)]; print(f"  {hi}倍以下 機械≥{th}", s(g, D))
