"""3連単枠の中で機械に順番をつけさせる。締切前でも変わりにくい手がかりだけ（他券種とのズレは使わない）。
学習=2025/2〜5/29＋2026/2〜6、選び方の基準=2026/7〜8、答え合わせ=2025/5/30〜9/11（未使用）。最終オッズ"""
import sqlite3, numpy as np, pandas as pd, lightgbm as lgb
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
K = "C:/Users/take0/.claude/keirin/out/"
A = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl")] + [pd.read_pickle(K + f + "/tri.pkl") for f in ("fresh", "fresh2", "fresh3")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(A); T = T[(T["class"] != "L級") & (T.date < "20260901") & (T.date <= "20260831")].copy()
T = T[~((T.date >= "20250912") & (T.date < "20260101"))]
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
for i, r in enumerate(R): T[f"rule{i+1}"] = r.astype(float)
T["nr"] = sum(r.astype(int) for r in R)
# 学習用の広い候補：同じラインが絡む目（3着が同ライン3番手 or 3人同ライン or 1-2着同ライン）× 60倍以下
cand = (third | same3 | s01) & (T.odds <= 60)
C = T[cand].copy(); C["y"] = (C.ret > 0).astype(int)
for j in range(3): C[f"r{j}_style"] = C[f"r{j}_style"].map({"逃": 0, "両": 1, "追": 2})
rc = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "prediction_mark", "p1", "p3", "gear", "n_front", "n_marker", "style"]
F = ["lodds", "lp", "s01", "s12", "s02"] + [f"r{j}_{c}" for j in range(3) for c in rc] + ["entries_number", "nlines", "n_strong_nige", "S", "G", "day_index", "race_no", "nr"] + [f"rule{i}" for i in range(1, 6)]
F = [f for f in F if f in C.columns]
for f in F: C[f] = pd.to_numeric(C[f], errors="coerce").astype(np.float32)
UN = C.date.between("20250530", "20250911")
tr = C[~UN & (C.date < "20260701")]; va = C[C.date >= "20260701"]; te = C[UN].copy()
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=500, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(tr[F], tr.y, init_score=tr.lp), 3000, valid_sets=[lgb.Dataset(va[F], va.y, init_score=va.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
print(f"学習 {tr.date.nunique()}日・{len(tr):,}点 → 木{m.best_iteration} 損失 市場だけ→機械: ", end="")
ll = lambda y, p: -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
pv0 = 1 / (1 + np.exp(-va.lp)); pv = 1 / (1 + np.exp(-(m.predict(va[F], raw_score=True) + va.lp)))
print(f"{ll(va.y, pv0.clip(1e-6, 1-1e-6)):.5f} → {ll(va.y, pv.clip(1e-6, 1-1e-6)):.5f}")
for D in (va, te): D["ev"] = 1 / (1 + np.exp(-(m.predict(D[F], raw_score=True) + D.lp))) * D.odds
imp = pd.Series(m.feature_importance("gain"), index=F).sort_values(ascending=False); print("効いた手がかり:", ", ".join(imp.index[:8]))
def s(g, D):
    if not len(g): return "0点"
    by = g.groupby("race_id").agg(i=("ret", "size"), x=("ret", "sum"))
    b = np.random.default_rng(0).integers(0, len(by), (1000, len(by))); bs = by.x.to_numpy()[b].sum(1) / by.i.to_numpy()[b].sum(1)
    return f"**{g.ret.mean():.0%}**［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 1日{len(g)/D.date.nunique():.1f}点 当たり{int((g.ret>0).sum())}"
def per4(g):
    P4 = np.select([g.date.between("20250530", "20250705"), g.date.between("20250706", "20250803"), g.date.between("20250804", "20250822")], ["①", "②", "③"], "④")
    return " ".join(f"{p}{x.ret.mean():.0%}" for p, x in g.groupby(P4))
def pick(D, kind, th):
    B = D[D.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6)  # 今の3連単枠
    if kind == "枠×機械": return B[B.ev >= th]
    if kind == "枠の上位1点": return B[B.ev >= th].sort_values("ev").groupby("race_id").tail(1)
    if kind == "広い候補×機械": return D[D.ev >= th].sort_values("ev").groupby("race_id").tail(2)
print("\n## 選び方の基準を 2026/7〜8 で決める")
best = {}
for kind in ("枠×機械", "枠の上位1点", "広い候補×機械"):
    rows = []
    for th in (0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1):
        g = pick(va, kind, th)
        if len(g) >= 60: rows.append((th, g.ret.mean(), len(g)))
    print(f"- {kind}: " + " ｜ ".join(f"≥{th} {r:.0%}({n})" for th, r, n in rows))
    ok = [x for x in rows if x[2] >= 100]; best[kind] = max(ok, key=lambda x: x[1])[0] if ok else None
print("\n## ★答え合わせ（未使用 2025/5/30〜9/11、基準は 2026/7〜8 で決めたものをそのまま）")
B0 = te[te.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6)
print(f"- 今の3連単枠（機械なし）: {s(B0, te)} ／ 期間別 {per4(B0)}")
for kind, th in best.items():
    if th is None: continue
    g = pick(te, kind, th); print(f"- {kind}（≥{th}）: {s(g, te)} ／ 期間別 {per4(g)}")
m.save_model("tri_ml_cand.txt", num_iteration=m.best_iteration)
te.to_pickle("tri_ml_te.pkl"); va.to_pickle("tri_ml_va.pkl")
import json; json.dump({"best": best, "F": F}, open("tri_ml_cfg.json", "w"))
