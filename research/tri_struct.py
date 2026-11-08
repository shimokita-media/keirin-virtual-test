"""倍率の細かい差（他券種とのズレ・人気順）を使わず、形（ライン・位置・選手の成績）中心の3連単の機械。締切前でも選ぶ目がぶれないか確認"""
import numpy as np, pandas as pd, lightgbm as lgb, sys
sys.path.insert(0, "C:/Users/take0/.claude/keirin/research")
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0].split("lg = lambda")[1].join(["lg = lambda", ""]) if False else "")
exec(open("tri2_model.py", encoding="utf-8").read().split("cols = ")[0])
ALL = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(ALL); T = T[T.date < "20260901"].reset_index(drop=True)
rc = ["pos", "ls", "single", "pt_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark"]
FS = ["lodds", "s01", "s12", "s02"] + [f"r{j}_{c}" for j in range(3) for c in rc] + ["entries_number", "nlines", "n_strong_nige", "S", "G", "day_index", "race_no"]
for f in FS: T[f] = T[f].astype(np.float32)
NEW = T.date.between("20250530", "20250705"); tr = T[~NEW & (T.date < "20260701")]; va = T[T.date >= "20260701"]; te = T[NEW].copy()
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=1000, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(tr[FS], tr.y, init_score=tr.lp), 3000, valid_sets=[lgb.Dataset(va[FS], va.y, init_score=va.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
print("木", m.best_iteration)
R = T[["race_id", "combo", "ret"]]
def show(lab, D):
    D = D.copy(); D["ev"] = 1 / (1 + np.exp(-(m.predict(D[FS], raw_score=True) + D.lp))) * D.odds
    for hi in (30, 60, 100):
        for th in (1.0, 1.05, 1.1):
            X = D[(D.odds <= hi) & (D.ev >= th)].sort_values("ev").groupby("race_id").tail(1)
            if not len(X): continue
            sw = X.combo.str.split("-").map(lambda a: f"{a[0]}-{a[2]}-{a[1]}")
            B = pd.concat([X[["race_id", "combo"]], pd.DataFrame({"race_id": X.race_id, "combo": sw})]).merge(R, on=["race_id", "combo"], how="left").fillna({"ret": 0})
            print(f"{lab} {hi}倍以下×{th}: 1点 {X.ret.mean():.0%}（{X.race_id.nunique()/D.date.nunique():.1f}R/日 当たり{(X.ret>0).sum()}） ｜ ＋2-3着入替 {B.ret.mean():.0%}（当たり{(B.ret>0).sum()}）")
show("26/7〜8", va); show("★未使用", te)
m.save_model("tri_model_struct.txt", num_iteration=m.best_iteration)
# 締切前と最終で選ぶレース数の比較（11/7〜8 同じ106レース）
W = "C:/Users/take0/.claude/keirin/out/eval_work/"
for nm in ("tri_P", "tri_T1"):
    D = prep(pd.read_pickle(W + nm + ".pkl"))
    for f in FS: D[f] = D[f].astype(np.float32)
    D["ev"] = 1 / (1 + np.exp(-(m.predict(D[FS], raw_score=True) + D.lp))) * D.odds
    print(nm, {th: D[(D.odds <= 60) & (D.ev >= th)].race_id.nunique() for th in (1.0, 1.05, 1.1)}, "機械中央", round(D[D.odds <= 60].ev.median(), 3))
