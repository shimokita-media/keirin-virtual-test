import numpy as np, pandas as pd, lightgbm as lgb
W = pd.read_pickle("wide_all2.pkl"); W = W[(W.odds >= 1.5) & (W.odds <= 50) & (W["class"] != "L級")].copy()
W["same"] = ((W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)).astype(float)
W["pp"] = (W.a_pos.astype(int) * 10 + W.b_pos.astype(int)).astype(float)
W["fin"] = W.race_type.astype(str).str.contains("決勝|準決").astype(float)
W["lpw"] = np.log(W.pw.clip(1e-4, 0.999) / (1 - W.pw.clip(1e-4, 0.999))); W["lodds"] = np.log(W.odds); W["mkt_gap"] = np.log(W.odds * W.pw)
W["y"] = (W.ret > 0).astype(int); W["S"] = (W["class"] == "S級").astype(float); W["G"] = W.grade.astype(str).str.startswith("G").astype(float)
for s in "ab": W[f"{s}_style"] = W[f"{s}_style"].map({"逃": 0, "両": 1, "追": 2})
base = ["pos", "ls", "single", "style", "pt_rank", "mk_rank", "age", "prediction_mark", "third_rate", "first_rate", "lead_rank", "gear", "n_front"]
new = ["n_marker", "second_rate", "ro_first5", "ro_last5", "ro_mean", "ro_top3", "h_surp_rate", "h_t3_rate", "h_n", "cup_prev_rank", "cup_prev_surp", "cup_n", "h2h_rate", "h2h_edge", "beh_rate", "beh_n"]
F1 = ["lodds", "mkt_gap", "same", "pp", "fin", "day_index", "race_no", "entries_number", "nlines", "n_strong_nige", "S", "G"] + [f"{s}_{c}" for s in "ab" for c in base]
F2 = F1 + [f"{s}_{c}" for s in "ab" for c in new] + ["hour", "wind", "venue_c"]
for f in F2: W[f] = W[f].astype(np.float32)
va = W[(W.date >= "20260701") & (W.date < "20260901")]
TR = {"2026年2〜6月だけ": W[(W.date >= "20260201") & (W.date < "20260701")], "2025年2〜5月＋2026年2〜6月": W[W.date < "20260701"]}
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=400, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1)
def s(g, D):
    if len(g) < 30: return f"{len(g)}点"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    return f"{len(g)}点 1日{len(g)/D.date.nunique():.1f} {g.ret.mean():.0%}[{np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}] 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby(g.date.str[2:6]))
for nm, tr in TR.items():
    feats = F1
    m = lgb.train(P, lgb.Dataset(tr[feats], tr.y, init_score=tr.lpw), 3000, valid_sets=[lgb.Dataset(va[feats], va.y, init_score=va.lpw)], callbacks=[lgb.early_stopping(100, verbose=False)])
    print(f"### 学習:{nm}（{tr.date.nunique()}日） 木{m.best_iteration} 検証の損失{m.best_score['valid_0']['binary_logloss']:.5f}")
    D = va.copy(); D["ev"] = 1 / (1 + np.exp(-(m.predict(D[feats], raw_score=True) + D.lpw))) * D.odds
    for th in (1.1, 1.2, 1.3): print(f"  検証26/7-8 機械≥{th}", s(D[D.ev >= th], D))
