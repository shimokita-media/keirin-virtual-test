"""機械つき3連単枠の締切前チェック：①倍率のブレ（11/6〜8の 判断時点÷最終 の比）を入れて選び直す ②11/6〜8の実際の判断時点の倍率で選ぶ"""
import json, os, sqlite3, subprocess, sys, numpy as np, pandas as pd, lightgbm as lgb
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
cfg = json.load(open("tri_ml_cfg.json")); F = cfg["F"]; m = lgb.Booster(model_file="tri_ml_cand.txt")
te = pd.read_pickle("tri_ml_te.pkl")
def lp_of(p): p = np.clip(p, 1e-6, 0.99); return np.log(p / (1 - p))
def frame(D):
    return D[D.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6)
def sel(D, th1=0.8, th2=1.05):
    B = frame(D); a = B[B.ev >= th1]; b = B[B.ev >= th2].sort_values("ev").groupby("race_id").tail(1); return B, a, b
c = sqlite3.connect("C:/Users/take0/.claude/keirin/out/eval_work/keirin.sqlite")
o = pd.read_sql("SELECT race_id, phase, combo, odds, fetched_at FROM odds WHERE source='winticket' AND bet_type='3連単' AND odds>0 AND phase IN ('B1R','POST')", c)
o = o[o.fetched_at == o.groupby(["race_id", "phase"]).fetched_at.transform("max")]
Pv = o.pivot_table(index=["race_id", "combo"], columns="phase", values="odds").dropna(); Pv = Pv[Pv.POST <= 80]; ratio = (Pv.B1R / Pv.POST).to_numpy()
rng = np.random.default_rng(5); out = []
for t in range(10):
    D = te.copy(); r = rng.choice(ratio, len(D))
    D["odds"] = D.odds * r; D["lodds"] = np.log(D.odds); D["lp"] = lp_of(D.p / r)  # 締切前の倍率で見えていたはずの値（目ごとにブレ）
    # 法則の倍率条件も締切前の倍率で判定し直す
    s01, s12 = D.s01 == 1, D.s12 == 1; third = (D.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (D.r0_pos == 0) & (D.r1_pos == 1) & (D.r2_pos == 2)
    nine, d2 = D.entries_number >= 9, D.day_index >= 2
    RR = [third & (D.odds <= 30) & nine & d2, same3 & (D.odds <= 30) & nine & d2, same3 & (D.odds <= 30) & nine & (D.g_tf > 0),
          order & (D.odds <= 60) & (D.r0_prediction_mark >= 3) & (D.g_tf > 0) & (D.g_ex > 0), third & (D.odds <= 10) & (D.G == 1) & (D.r0_mk_rank == 1)]
    for i, x in enumerate(RR): D[f"rule{i+1}"] = x.astype(np.float32)
    D["nr"] = sum(x.astype(int) for x in RR).astype(np.float32)
    for f in ("lodds", "lp"): D[f] = D[f].astype(np.float32)
    D["ev"] = 1 / (1 + np.exp(-(m.predict(D[F], raw_score=True) + D.lp))) * D.odds
    B, a, b = sel(D); out.append((B.ret.mean(), a.ret.mean(), b.ret.mean()))
o_ = np.array(out); print("① 締切前の倍率のブレを入れて選び直し（10回の平均、払戻は最終）:", f"枠そのまま {o_[:,0].mean():.0%}（{o_[:,0].min():.0%}〜{o_[:,0].max():.0%}） ｜ 枠×機械≥0.8 {o_[:,1].mean():.0%}（{o_[:,1].min():.0%}〜{o_[:,1].max():.0%}） ｜ 枠の上位1点≥1.05 {o_[:,2].mean():.0%}（{o_[:,2].min():.0%}〜{o_[:,2].max():.0%}）")
# ② 実際の判断時点の倍率（11/7〜8 のB1R、11/6はB1Rでも ana が無いので作る）
W = "C:/Users/take0/.claude/keirin/out/eval_work/"
env = dict(os.environ, KDB=W + "keirin.sqlite", PYTHONIOENCODING="utf-8")
pay = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", c)
for ph in ("B1R", "POST"):
    env["KPH"] = ph
    subprocess.run([sys.executable, "C:/Users/take0/.claude/keirin/research/ana_build.py", "20261106", "20261108", W + f"mlana_{ph}.pkl"], env=env, check=True, capture_output=True, cwd=W)
    subprocess.run([sys.executable, "C:/Users/take0/.claude/keirin/research/tri3_build.py", W + f"mlana_{ph}.pkl", W + f"mltri_{ph}.pkl"], env=env, check=True, capture_output=True, cwd=W)
    D = prep(pd.read_pickle(W + f"mltri_{ph}.pkl")); D = D[D["class"] != "L級"].copy()
    s01, s12 = D.s01 == 1, D.s12 == 1; third = (D.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (D.r0_pos == 0) & (D.r1_pos == 1) & (D.r2_pos == 2)
    nine, d2 = D.entries_number >= 9, D.day_index >= 2
    RR = [third & (D.odds <= 30) & nine & d2, same3 & (D.odds <= 30) & nine & d2, same3 & (D.odds <= 30) & nine & (D.g_tf > 0),
          order & (D.odds <= 60) & (D.r0_prediction_mark >= 3) & (D.g_tf > 0) & (D.g_ex > 0), third & (D.odds <= 10) & (D.G == 1) & (D.r0_mk_rank == 1)]
    for i, x in enumerate(RR): D[f"rule{i+1}"] = x.astype(float)
    D["nr"] = sum(x.astype(int) for x in RR)
    for j in range(3): D[f"r{j}_style"] = D[f"r{j}_style"].map({"逃": 0, "両": 1, "追": 2})
    for f in F: D[f] = pd.to_numeric(D[f], errors="coerce").astype(np.float32)
    D["ev"] = 1 / (1 + np.exp(-(m.predict(D[F], raw_score=True) + D.lp))) * D.odds
    D = D.drop(columns="ret").merge(pay.drop_duplicates(["race_id", "combo"]), on=["race_id", "combo"], how="left"); D["ret"] = D.payout.fillna(0) / 100
    D = D[D.race_id.isin(set(pay.race_id))]
    B, a, b = sel(D)
    f = lambda g: f"{g.ret.mean():.0%}（{len(g)}点・当たり{int((g.ret>0).sum())}）" if len(g) else "0点"
    print(f"② 11/6〜8 {'判断時点の倍率で選ぶ' if ph=='B1R' else '最終オッズで選ぶ（比較）'}: 枠そのまま {f(B)} ｜ 枠×機械≥0.8 {f(a)} ｜ 枠の上位1点≥1.05 {f(b)}")
