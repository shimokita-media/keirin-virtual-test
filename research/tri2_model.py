import sys, numpy as np, pandas as pd, lightgbm as lgb
def prep(T):
    T = T.copy(); lg = lambda v: np.log(np.clip(v, 1e-6, None))
    T["lp"] = np.log(T.p.clip(1e-6, 0.99) / (1 - T.p.clip(1e-6, 0.99))); T["lodds"] = lg(T.odds)
    T["g_ex"] = lg(T.ex_q) - lg(T.xy_p)            # 2車単から見た1-2着の割安さ
    T["g_tf"] = lg(T.tf_q) - lg(T.set_p)           # 3連複から見た3人セットの割安さ
    T["g_qn"] = lg(T.qn_q) - lg(T.xy_p)
    T["cond"] = lg(T.p) - lg(T.xy_p)               # 1-2着が決まった時の3着の売れ方
    for w in ("w12", "w13", "w23"): T["l" + w] = lg(T[w])
    T["s01"] = ((T.r0_line_idx == T.r1_line_idx) & (T.r0_line_idx >= 0)).astype(float)
    T["s12"] = ((T.r1_line_idx == T.r2_line_idx) & (T.r1_line_idx >= 0)).astype(float)
    T["s02"] = ((T.r0_line_idx == T.r2_line_idx) & (T.r0_line_idx >= 0)).astype(float)
    T["S"] = (T["class"] == "S級").astype(float); T["G"] = T.grade.astype(str).str.startswith("G").astype(float)
    T["y"] = (T.ret > 0).astype(int); return T
cols = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark", "p1", "p3"]
feats = ["lodds", "popularity", "g_ex", "g_tf", "g_qn", "cond", "lw12", "lw13", "lw23", "s01", "s12", "s02"] + [f"r{j}_{c}" for j in range(3) for c in cols] + ["entries_number", "nlines", "n_strong_nige", "S", "G", "day_index"]
A = prep(pd.read_pickle("tri2_2026.pkl")); B = prep(pd.read_pickle("tri2_2025a.pkl"))
for f in feats: A[f] = A[f].astype(np.float32); B[f] = B[f].astype(np.float32)
tr = A[A.date < "20260901"]; cut = "20260701"; a, v = tr[tr.date < cut], tr[tr.date >= cut]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=1000, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(a[feats], a.y, init_score=a.lp), 3000, valid_sets=[lgb.Dataset(v[feats], v.y, init_score=v.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
nb = max(m.best_iteration, 1); print("木", nb)
# まず7〜8月（検証）での成績
v = v.copy(); v["ev"] = 1 / (1 + np.exp(-(m.predict(v[feats], raw_score=True) + v.lp))) * v.odds
m2 = lgb.train(P, lgb.Dataset(tr[feats], tr.y, init_score=tr.lp), nb)
B["ev"] = 1 / (1 + np.exp(-(m2.predict(B[feats], raw_score=True) + B.lp))) * B.odds
def s(g, D):
    if len(g) < 30: return f"{len(g)}点 当たり{int((g.ret>0).sum())}"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    return f"{len(g)}点 1日{len(g)/D.date.nunique():.1f} {g.ret.mean():.0%}[{np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}] 当たり{int((g.ret>0).sum())} 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby(g.date.str[2:6]))
for nm, D in (("検証 2026/7-8", v), ("未使用 2025/2-4", B)):
    print("===", nm, "===")
    for hi in (50, 300):
        for th in (1.0, 1.1, 1.2, 1.3, 1.5):
            g = D[(D.odds <= hi) & (D.ev >= th)]; print(f" {hi}倍以下 機械≥{th}", s(g, D))
B[B.ev >= 1.0][["race_id", "date", "combo", "odds", "ev", "ret"]].to_pickle("tri2_B.pkl"); m2.save_model("tri2_model.txt")
imp = pd.Series(m2.feature_importance("gain"), feats).sort_values(ascending=False); print((imp / imp.sum()).head(10).round(3).to_string())
