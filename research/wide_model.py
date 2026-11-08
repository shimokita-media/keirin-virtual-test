import sys, numpy as np, pandas as pd, lightgbm as lgb
W = pd.read_pickle(sys.argv[1]); SPLIT = sys.argv[2]
W = W[(W.odds >= 1.5) & (W.odds <= 50)].copy()
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)
W["pp"] = W.a_pos.astype(int).astype(str) + W.b_pos.astype(int).astype(str)
for c in ["a_style", "b_style", "grade", "class", "pp", "venue"]: W[c] = W[c].astype("category")
W["fin"] = W.race_type.astype(str).str.contains("決勝|準決").astype(int)
W["lpw"] = np.log(W.pw.clip(1e-4, 0.999) / (1 - W.pw.clip(1e-4, 0.999)))
W["lodds"] = np.log(W.odds); W["mkt_gap"] = np.log(W.odds * W.pw)  # 3連単から見た割安さ
W["y"] = (W.ret > 0).astype(int)
feats = ["lodds", "mkt_gap", "same", "pp", "a_ls", "b_ls", "a_single", "b_single", "a_style", "b_style", "a_pt_rank", "b_pt_rank", "a_mk_rank", "b_mk_rank",
         "a_age", "b_age", "a_prediction_mark", "b_prediction_mark", "a_third_rate", "b_third_rate", "a_first_rate", "b_first_rate", "a_lead_rank", "b_lead_rank",
         "grade", "class", "fin", "day_index", "race_no", "entries_number", "nlines", "n_strong_nige", "a_gear", "b_gear", "a_n_front", "b_n_front"]
for f in feats:
    if W[f].dtype == object or W[f].dtype == bool: W[f] = W[f].astype(float) if W[f].dtype == bool else W[f].astype("category")
tr, te = W[W.date < SPLIT], W[W.date >= SPLIT]
# 学習データの中でさらに検証用を分けて木の数を決める
cut = sorted(tr.date.unique())[int(tr.date.nunique() * 0.8)]
a, v = tr[tr.date < cut], tr[tr.date >= cut]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=400, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(a[feats], a.y, init_score=a.lpw), 2000, valid_sets=[lgb.Dataset(v[feats], v.y, init_score=v.lpw)],
              callbacks=[lgb.early_stopping(100, verbose=False)])
nb = m.best_iteration; print("木の数", nb)
m = lgb.train(P, lgb.Dataset(tr[feats], tr.y, init_score=tr.lpw), max(nb, 1))
te = te.copy(); te["pm"] = 1 / (1 + np.exp(-(m.predict(te[feats], raw_score=True) + te.lpw)))
te["ev"] = te.pm * te.odds; te["ev0"] = te.pw * te.odds
def s(g): return f"{len(g)}点 1日{len(g)/te.date.nunique():.1f} {g.ret.mean():.0%} 的中{g.y.mean():.0%}"
print("学習", tr.date.min(), "〜", tr.date.max(), "/ 確認", te.date.min(), "〜", te.date.max())
for lo, hi in ((3, 20), (1.5, 50)):
    T = te[te.odds.between(lo, hi)]
    print(f"--- {lo}〜{hi}倍 ---")
    for th in (1.0, 1.05, 1.1, 1.15, 1.2, 1.3):
        print(f"機械の見込み×倍率≥{th}", s(T[T.ev >= th]), "| 3連単だけ(今の方式)", s(T[T.ev0 >= th]))
imp = pd.Series(m.feature_importance("gain"), feats).sort_values(ascending=False)
print((imp / imp.sum()).head(12).round(3).to_string())
te.to_pickle("wide_te.pkl"); m.save_model("wide_model.txt")
