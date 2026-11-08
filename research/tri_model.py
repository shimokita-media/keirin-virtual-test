import numpy as np, pandas as pd, lightgbm as lgb
T = pd.read_pickle("tri_2026.pkl"); T = T[(T["class"] != "L級") & (T.odds <= 2000)].copy()
T["p"] = 1 / T.odds; T["p"] /= T.groupby("race_id").p.transform("sum")
T["lp"] = np.log(T.p / (1 - T.p)); T["lodds"] = np.log(T.odds); T["y"] = (T.ret > 0).astype(np.int8)
T["s12"] = ((T.x_line_idx == T.y_line_idx) & (T.x_line_idx >= 0)).astype(np.int8)
T["s23"] = ((T.y_line_idx == T.z_line_idx) & (T.y_line_idx >= 0)).astype(np.int8)
T["s13"] = ((T.x_line_idx == T.z_line_idx) & (T.x_line_idx >= 0)).astype(np.int8)
T["is7"] = (T.entries_number <= 7).astype(np.int8); T["S"] = (T["class"] == "S級").astype(np.int8)
feats = ["lodds", "popularity", "s12", "s23", "s13", "x_pos", "y_pos", "z_pos", "x_ls", "y_ls", "z_ls", "x_single", "y_single", "z_single",
         "x_mk_rank", "y_mk_rank", "z_mk_rank", "x_pt_rank", "y_pt_rank", "z_pt_rank", "nlines", "is7", "S"]
for f in feats: T[f] = T[f].astype(np.float32)
tr, te = T[T.date < "20260701"], T[T.date >= "20260701"]
cut = sorted(tr.date.unique())[int(tr.date.nunique() * 0.8)]; a, v = tr[tr.date < cut], tr[tr.date >= cut]
P = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=2000, feature_fraction=0.8, bagging_fraction=0.5, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(a[feats], a.y, init_score=a.lp), 1000, valid_sets=[lgb.Dataset(v[feats], v.y, init_score=v.lp)], callbacks=[lgb.early_stopping(50, verbose=False)])
nb = max(m.best_iteration, 1); print("木", nb)
m = lgb.train(P, lgb.Dataset(tr[feats], tr.y, init_score=tr.lp), nb)
te = te.copy(); te["pm"] = 1 / (1 + np.exp(-(m.predict(te[feats], raw_score=True) + te.lp))); te["ev"] = te.pm * te.odds
def s(g): return f"{len(g)}点 1日{len(g)/te.date.nunique():.1f} 回収{g.ret.mean():.0%} 当たり{int((g.ret>0).sum())}本 月:" + " ".join(f"{mm}:{x.ret.mean():.0%}" for mm, x in g.groupby(g.date.str[4:6]))
for lo, hi in ((1, 100), (1, 300), (1, 2000)):
    print(f"--- {lo}〜{hi}倍 ---")
    for th in (0.9, 1.0, 1.1, 1.2, 1.3, 1.5):
        g = te[te.odds.between(lo, hi) & (te.ev >= th)]
        if len(g): print(f" 見込み×倍率≥{th}", s(g))
te[te.ev >= 0.9][["race_id", "date", "combo", "odds", "ev", "ret"]].to_pickle("tri_te.pkl"); m.save_model("tri_model.txt")
imp = pd.Series(m.feature_importance("gain"), feats).sort_values(ascending=False); print((imp/imp.sum()).head(8).round(3).to_string())
