"""新しく入った未使用期間（2025/5/30〜7/5）で、事前登録した A〜E と機械を答え合わせ。さらに3期間を足して学び直し"""
import numpy as np, pandas as pd, lightgbm as lgb
T0 = "20250706"; T1 = "20250911"
W = pd.read_pickle("wide_all4.pkl"); W = W[(W.odds >= 1.5) & (W.odds <= 50) & (W["class"] != "L級")].copy()
W["same"] = ((W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)).astype(float)
W["fin"] = W.race_type.astype(str).str.contains("決勝|準決").astype(float)
W["lpw"] = np.log(W.pw.clip(1e-4, 0.999) / (1 - W.pw.clip(1e-4, 0.999))); W["lodds"] = np.log(W.odds); W["mkt_gap"] = np.log(W.odds * W.pw)
W["y"] = (W.ret > 0).astype(int); W["ev0"] = W.pw * W.odds; W["fav_pw"] = W.groupby("race_id").pw.transform("max")
def s(g, D):
    if len(g) < 20: return f"{len(g)}点 {g.ret.mean():.0%}" if len(g) else "0点"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    return f"{len(g)}点（1日{len(g)/D.date.nunique():.1f}） {g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 当たり{int((g.ret>0).sum())} 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby(g.date.str[2:6]))
NEW = W[W.date.between(T0, T1)]
print(f"## 未使用期間 {T0}〜{T1}（{NEW.date.nunique()}日・{NEW.race_id.nunique()}レース）全体 {NEW.ret.mean():.0%}")
C = NEW[NEW.ev0 >= 1.0]; u20 = C.odds < 20
for k, m in {"C 割安×20倍未満": u20, "B 割安×20倍未満×1〜3R": u20 & (C.race_no <= 3),
             "A 割安×20倍未満×同じライン×本命が強くない": u20 & (C.same == 1) & (C.fav_pw < 0.6),
             "（参考）同じライン3番手 3〜20倍・割安0.85以上": None}.items():
    if m is None:
        g = NEW[(NEW.ev0 >= 0.85) & NEW.odds.between(3, 20) & (NEW.same == 1) & ((NEW.a_pos == 2) | (NEW.b_pos == 2))]
    else: g = C[m]
    print(f"- {k}: {s(g, NEW)}")
# E: 固定した機械 v1
wm = lgb.Booster(model_file="C:/Users/take0/.claude/keirin/research/wide_model.txt")
V = NEW.copy(); V["pp"] = V.a_pos.astype(int).astype(str) + V.b_pos.astype(int).astype(str)
for f in wm.feature_name():
    if f in {"a_style", "b_style", "grade", "class", "pp", "venue"}: V[f] = V[f].astype("category")
    elif V[f].dtype == bool or V[f].dtype == object: V[f] = V[f].astype(float)
V["ev"] = 1 / (1 + np.exp(-(wm.predict(V[wm.feature_name()], raw_score=True) + V.lpw))) * V.odds
for th in (1.1, 1.2, 1.3): print(f"- E 固定した機械(2026/2〜6で学習)≥{th}: {s(V[V.ev >= th], V)}")
# 学び直し（F1）：2025/2〜5/29 + 2026/2〜6 で学習（7〜8で止める）→ 未使用期間で確認。さらに未使用期間も足した版を保存
W["pp"] = (W.a_pos.astype(int) * 10 + W.b_pos.astype(int)).astype(float)
W["S"] = (W["class"] == "S級").astype(float); W["G"] = W.grade.astype(str).str.startswith("G").astype(float)
for c in "ab": W[f"{c}_style"] = W[f"{c}_style"].map({"逃": 0, "両": 1, "追": 2})
base = ["pos", "ls", "single", "style", "pt_rank", "mk_rank", "age", "prediction_mark", "third_rate", "first_rate", "lead_rank", "gear", "n_front"]
F1 = ["lodds", "mkt_gap", "same", "pp", "fin", "day_index", "race_no", "entries_number", "nlines", "n_strong_nige", "S", "G"] + [f"{c}_{x}" for c in "ab" for x in base]
for f in F1: W[f] = W[f].astype(np.float32)
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=400, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1)
va = W[(W.date >= "20260701") & (W.date < "20260901")]
for nm, tr in {"2025/2〜7/5＋2026/2〜6": W[(W.date < T0) | W.date.between("20260201", "20260630")],
               "2025/2〜9/11＋2026/2〜6（全部）": W[W.date < "20260701"]}.items():
    m = lgb.train(P, lgb.Dataset(tr[F1], tr.y, init_score=tr.lpw), 3000, valid_sets=[lgb.Dataset(va[F1], va.y, init_score=va.lpw)], callbacks=[lgb.early_stopping(100, verbose=False)])
    print(f"\n### 学習 {nm}（{tr.date.nunique()}日）木{m.best_iteration} 検証の損失{m.best_score['valid_0']['binary_logloss']:.5f}")
    for lab, D in (("未使用 25/5/30〜7/5", W[W.date.between(T0, T1)]), ("検証 26/7〜8", va)):
        if nm.endswith("（全部）") and lab.startswith("未使用"): continue
        D = D.copy(); D["ev"] = 1 / (1 + np.exp(-(m.predict(D[F1], raw_score=True) + D.lpw))) * D.odds
        for th in (1.1, 1.2, 1.3): print(f"  {lab} 機械≥{th}: {s(D[D.ev >= th], D)}")
    if nm.endswith("（全部）"): m.save_model("wide_model_v3cand.txt")
