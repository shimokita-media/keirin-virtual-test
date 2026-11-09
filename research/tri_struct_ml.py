"""3連単の「形と出走表だけ」の機械（他の賭け式との差＝割安さは使わない＝締切前でも崩れにくい）。
LightGBM・初期値＝市場の確率のlogit（市場からのズレだけを学ぶ）。
学習 2025/2〜10/11＋2026/2〜6、止めどころ 2026/7〜8、未使用 2025/10/12〜2026/1/14。2026/9〜11は使わない。最終オッズ（3連単は締切前→最終の下がりが小さい）"""
import numpy as np, pandas as pd, lightgbm as lgb
K = "C:/Users/take0/.claude/keirin/"; SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
OOS0, OOS1 = "20251012", "20260114"
IS = pd.read_pickle(SP + "tri3_all.pkl"); IS = IS[(IS.date < "20260901") & ~IS.date.between(OOS0, OOS1)]
OS = pd.concat([pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh6", "fresh7")]); OS = OS[OS.date <= OOS1]
IS, OS = prep(IS), prep(OS); IS, OS = IS[IS["class"] != "L級"].copy(), OS[OS["class"] != "L級"].copy()
RIDER = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark", "p1", "p3", "gear", "n_front", "n_marker"]
F = ["lodds", "s01", "s12", "s02", "entries_number", "nlines", "n_strong_nige", "S", "G", "day_index", "race_no"] + [f"r{i}_{c}" for i in range(3) for c in RIDER] + ["r0_sty", "r1_sty", "r2_sty"]
for D in (IS, OS):
    for i in range(3): D[f"r{i}_sty"] = D[f"r{i}_style"].map({"逃": 0, "両": 1, "追": 2}).astype(float)
    D["y"] = (D.ret > 0).astype(int)
    for f in F: D[f] = D[f].astype(np.float32)
tr = IS[(IS.date < OOS0) | IS.date.between("20260201", "20260630")]; va = IS[IS.date.between("20260701", "20260831")]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=2000, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=20, verbose=-1, seed=1)
m = lgb.train(P, lgb.Dataset(tr[F], tr.y, init_score=tr.lp), 3000, valid_sets=[lgb.Dataset(va[F], va.y, init_score=va.lp)], callbacks=[lgb.early_stopping(150, verbose=False)])
base_ll = lambda D: -np.mean(D.y * np.log(1 / (1 + np.exp(-D.lp))) + (1 - D.y) * np.log(1 - 1 / (1 + np.exp(-D.lp))))
print(f"木{m.best_iteration}本・学習{tr.date.nunique()}日／止めどころ{va.date.nunique()}日／未使用{OS.date.nunique()}日")
rng = np.random.default_rng(0)
def ci(g):
    if len(g) < 30: return ""
    by = g.groupby("race_id").ret.agg(["sum", "size"]); i = rng.integers(0, len(by), (1000, len(by))); b = by["sum"].to_numpy()[i].sum(1) / by["size"].to_numpy()[i].sum(1)
    return f"［{np.percentile(b,2.5):.0%}〜{np.percentile(b,97.5):.0%}］"
def st(g): return f"{g.ret.mean():.0%}{ci(g)}（{len(g)}点・当たり{int((g.ret>0).sum())}）" if len(g) else "0点"
for nm, D in (("止めどころ 26/7〜8", va), ("未使用 25/10〜26/1", OS)):
    D["pm"] = 1 / (1 + np.exp(-(m.predict(D[F], raw_score=True) + D.lp))); D["ev"] = D.pm * D.odds
    ll = -np.mean(D.y * np.log(D.pm) + (1 - D.y) * np.log(1 - D.pm))
    print(f"\n## {nm}（{D.race_id.nunique()}R・全体{D.ret.mean():.0%}） 当てる力：市場だけ {base_ll(D):.5f} → 機械 {ll:.5f}（小さいほど良い）")
    for cap in (60, 300):
        X = D[D.odds <= cap]
        print(f"- {cap}倍以下: " + " ／ ".join(f"期待値≥{t}: {st(X[X.ev >= t])}" for t in (0.9, 1.0, 1.1)))
    for t in (0.9, 1.0, 1.1):
        top = D[(D.odds <= 60) & (D.ev >= t)].sort_values("ev").groupby("race_id").tail(1)
        print(f"- 1レース1点（60倍以下・期待値≥{t}で一番）: {st(top)} 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in top.groupby(top.date.str[:6])))
imp = pd.Series(m.feature_importance("gain"), index=F).sort_values(ascending=False).head(12)
print("\n効いている項目: " + " ／ ".join(f"{k}" for k in imp.index))
m.save_model(K + "research/tri_struct_v1cand.txt")
OS[["race_id", "combo", "date", "odds", "ret", "pm", "ev"]].to_pickle(SP + "tri_struct_OS.pkl")
