import numpy as np, pandas as pd, lightgbm as lgb
exec(open("pre_eval.py", encoding="utf-8").read().split("fin = prep")[0])  # prep(): 機械の見込み pm, ev
fin = prep(pd.read_pickle("d_wide_POST.pkl")).set_index(["race_id", "combo"])
MIN = {"T10": 10, "T5": 5, "B1R": 2.7, "T1": 1}
rows = []
for ph in MIN:
    W = prep(pd.read_pickle(f"d_wide_{ph}.pkl")); W["ph"] = ph; W["mins"] = MIN[ph]
    W["fodds"] = fin.odds.reindex(list(zip(W.race_id, W.combo))).to_numpy(); rows.append(W)
D = pd.concat(rows); D = D[D.fodds.notna()].copy()
D["drift"] = np.log(D.fodds / D.odds); D["day"] = D.race_id.str[-8:]
D["sameF"] = D.same.astype(float); D["S"] = (D["class"].astype(str) == "S級").astype(float)
D["pop_w"] = D.groupby(["race_id", "ph"]).odds.rank()
feats = ["lodds", "mkt_gap", "ev", "pm", "mins", "sameF", "pop_w", "S", "entries_number", "a_pos", "b_pos", "a_mk_rank", "b_mk_rank", "lpw"]
for f in feats: D[f] = D[f].astype(float)
print("行数", len(D), "日", D.day.unique(), "倍率変化の中央", f"{np.exp(D.drift.median())-1:+.0%}")
print("割安(ev≥1.15)だけの倍率変化", f"{np.exp(D[D.ev>=1.15].drift.median())-1:+.0%}", "| 割高(ev<0.9)", f"{np.exp(D[D.ev<0.9].drift.median())-1:+.0%}")
P = dict(objective="regression", learning_rate=0.03, num_leaves=7, min_data_in_leaf=100, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1)
D["pred"] = np.nan
for d in D.day.unique():   # その日を除いた日で学習して、その日を予測
    tr = D[D.day != d]; m = lgb.train(P, lgb.Dataset(tr[feats], tr.drift), 300)
    D.loc[D.day == d, "pred"] = m.predict(D.loc[D.day == d, feats])
print("倍率変化の予測の当たり具合（相関）", round(np.corrcoef(D.pred, D.drift)[0, 1], 3), "| 何もしない（平均だけ）より誤差が", f"{1 - ((D.pred - D.drift) ** 2).mean() / D.drift.var():.0%}", "減った")
D["ev_adj"] = D.pm * D.odds * np.exp(D.pred)   # 最終の倍率を見込んだ割安さ
def s(g):
    if len(g) < 20: return f"{len(g)}点 回収{g.ret.mean():.0%}"
    return f"{len(g)}点 回収{g.ret.mean():.0%} 的中{(g.ret>0).mean():.0%} 日別:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby("day"))
for ph in ("T5", "B1R", "T1"):
    X = D[D.ph == ph]; print(f"--- {ph}（{X.race_id.nunique()}レース）---")
    for th in (1.0, 1.1, 1.2):
        print(f"  締切前のev≥{th}", s(X[X.ev >= th]), " | 下がりを見込んだev≥{th}", s(X[X.ev_adj >= th]))
m = lgb.train(P, lgb.Dataset(D[feats], D.drift), 300); imp = pd.Series(m.feature_importance("gain"), feats).sort_values(ascending=False)
print("倍率の下がりに効く:", ", ".join(imp.head(8).index))
D.to_pickle("drift_D.pkl")
