"""3連単を「レースを絞って少ない点数で」当てる買い方。学習・選び方決め=2025/2〜5＋2026/2〜8（9〜11月は最終確認用で使わない）、
答え合わせ=2025/5/30〜7/5（未使用）"""
import numpy as np, pandas as pd, lightgbm as lgb
exec(open("tri2_model.py", encoding="utf-8").read().split("cols = ")[0])
ALL = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl")]).drop_duplicates(["race_id", "combo"])
T = prep(ALL.reset_index(drop=True)); T = T[T.date < "20260901"].copy()
for j in range(3): T[f"r{j}_style"] = T[f"r{j}_style"].map({"逃": 0, "両": 1, "追": 2})
base_cols = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark", "p1", "p3"]
new_cols = ["ro_first5", "ro_last5", "ro_mean", "ro_top3", "ro_top3_10", "h_surp", "h_n", "h_surp_ewm", "h_surp_rate", "h_t3_rate", "gear", "n_front", "n_marker", "style"]
F = ["lodds", "popularity", "g_ex", "g_tf", "g_qn", "cond", "lw12", "lw13", "lw23", "s01", "s12", "s02"] + [f"r{j}_{c}" for j in range(3) for c in base_cols + new_cols] + ["entries_number", "nlines", "n_strong_nige", "S", "G", "day_index", "hour", "wind", "venue_c"]
for f in F: T[f] = T[f].astype(np.float32)
NEW = T.date.between("20250530", "20250705")
dev = T[~NEW]; new = T[NEW].copy()
T["order"] = (T.s01 == 1) & (T.s12 == 1) & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
T["fav_p1"] = T.groupby("race_id").r0_p1.transform("max")
def s(g, D):
    n = g.race_id.nunique()
    if len(g) < 15: return f"{len(g)}点（{n}レース） 当たり{int((g.ret>0).sum())} 回収{g.ret.mean():.0%}" if len(g) else "0点"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    return f"{len(g)}点・{n}レース（1日{n/D.date.nunique():.1f}R） {g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 当たり{int((g.ret>0).sum())}本"
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=1000, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1)
a = dev[dev.date < "20260701"]; v = dev[dev.date >= "20260701"]
m = lgb.train(P, lgb.Dataset(a[F], a.y, init_score=a.lp), 3000, valid_sets=[lgb.Dataset(v[F], v.y, init_score=v.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
nb = max(m.best_iteration, 1); m2 = lgb.train(P, lgb.Dataset(dev[F], dev.y, init_score=dev.lp), nb)
T.loc[v.index, "ev"] = 1 / (1 + np.exp(-(m.predict(v[F], raw_score=True) + v.lp))) * v.odds          # 7〜8月：学習に使っていない
T.loc[new.index, "ev"] = 1 / (1 + np.exp(-(m2.predict(new[F], raw_score=True) + new.lp))) * new.odds  # 未使用期間
print("木", nb)
T[T.ev.notna()][["race_id","date","combo","odds","ev","ret","entries_number"]].to_pickle("tri_few_ev.pkl")
for lab, D in (("検証 2026/7〜8", T[T.date >= "20260701"]), ("★未使用 2025/5/30〜7/5", T[T.date.between("20250530", "20250705")])):
    print(chr(10) + f"## {lab}（{D.date.nunique()}日）")
    for hi in (30, 60, 100):
        for th in (1.0, 1.1):
            X = D[(D.odds <= hi) & (D.ev >= th)].sort_values("ev")
            print(f"- {hi}倍以下×{th}以上: " + " ｜ ".join(f"{k if k<99 else '全部'}点まで {s(X.groupby('race_id').tail(k), D)}" for k in (1, 2, 3, 5, 99)))
