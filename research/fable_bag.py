"""探す段階（Fable、2026-11-12 夜。ユーザーの案「ランダムにレースを選んで学習させたら機械の精度が上がらないか」）。
ライン順×30倍以下（out/sh_all_*.pkl）で、4年の1年抜き（y6 は見ない）。学ぶ3年の中で「レースをランダムに選んで学ぶ」を何回も繰り返し、できた機械の平均を使う（バギング）。
 R1 いまの機械（リッジ、全部のレースで1回）
 R2 リッジ×ランダム（レースの7割をランダムに選んで30回学び、平均）
 G1 木の機械（LightGBM、市場の見込みを出発点、全部のレースで1回、木の本数は学ぶ年の中のランダムな2割で決める）
 G2 木の機械×ランダム（レースの7割をランダムに選んで20回学び、平均）
 M  R1 と G2 の平均（logit の平均）
見るもの：学ばない年の対数損失の改善×1万（市場比、マイナスが良い）、期待値≥1.1・≥1.2 の点数と回収率（年別）。
使い方: python -I -X utf8 research/fable_bag.py reports/fable_bag.md"""
import sys, numpy as np, pandas as pd, lightgbm as lgb
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
FS = {"y4": "out/sh_all_y4.pkl", "2024年": "out/sh_all_2024年.pkl", "2025/2〜": "out/sh_all_20252.pkl", "y5": "out/sh_all_y5.pkl"}
P = {}
for k, f in FS.items():
    d = pd.read_pickle(K + f); d = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2)].reset_index(drop=True); d["yr"] = k; P[k] = d
def gfeats(d):   # 木の機械の材料：リッジと同じ24個＋もとの数字（木が自分で切り方を決められるように）
    X = lo_feats(d).copy()
    for c in ("r0_pt_rank", "r1_pt_rank", "r2_pt_rank", "nlines", "r0_ls", "day_index", "entries_number", "n_prev", "n_strong_nige", "popularity"): X["raw_" + c] = pd.to_numeric(d[c], errors="coerce")
    X["raw_flow"] = d.flow; X["raw_lodds"] = np.log(d.odds); X["raw_age"] = pd.to_numeric(d.r2_age, errors="coerce"); X["raw_t3"] = pd.to_numeric(d.r2_third_rate, errors="coerce")
    return X
PRM = dict(objective="binary", learning_rate=0.03, num_leaves=6, min_data_in_leaf=300, feature_fraction=0.7, lambda_l2=20.0, verbose=-1, num_threads=4)
def gfit(X, y, off, seed, n=None):
    if n is None:   # 木の本数を、学ぶ年の中のランダムな2割のレースで決める
        r = np.random.default_rng(seed); va = r.random(len(X)) < 0.2
        m = lgb.train(dict(PRM, seed=seed), lgb.Dataset(X[~va], y[~va], init_score=off[~va]), 600,
                      valid_sets=[lgb.Dataset(X[va], y[va], init_score=off[va])], callbacks=[lgb.early_stopping(40, verbose=False)])
        n = max(m.best_iteration, 20)
    return lgb.train(dict(PRM, seed=seed), lgb.Dataset(X, y, init_score=off), n), n
sg = lambda z: 1 / (1 + np.exp(-z))
OUTS = {k: [] for k in ("R1", "R2", "G1", "G2", "M")}
for k in P:
    tr = pd.concat([P[j] for j in P if j != k], ignore_index=True); te = P[k]
    Xr, yr, of = lo_feats(tr), tr.hit.to_numpy(), lo_lg(tr.pn).to_numpy(); Xt = lo_feats(te); ot = lo_lg(te.pn).to_numpy()
    At = np.column_stack([np.ones(len(Xt)), Xt.to_numpy(float)])
    z = {"R1": At @ lo_fit(Xr, yr, of, 20.0)}
    races = tr.race_id.unique(); rng = np.random.default_rng(0); zz = []
    for i in range(30):
        m = tr.race_id.isin(rng.choice(races, int(len(races) * 0.7), replace=False)).to_numpy()
        zz.append(At @ lo_fit(Xr[m], yr[m], of[m], 20.0))
    z["R2"] = np.mean(zz, 0)
    Gr, Gt = gfeats(tr).to_numpy(float), gfeats(te).to_numpy(float)
    g1, n1 = gfit(Gr, yr, of, 0); z["G1"] = g1.predict(Gt, raw_score=True); zz = []
    for i in range(20):
        m = tr.race_id.isin(rng.choice(races, int(len(races) * 0.7), replace=False)).to_numpy()
        zz.append(gfit(Gr[m], yr[m], of[m], i + 1, n1)[0].predict(Gt, raw_score=True))
    z["G2"] = np.mean(zz, 0); z["M"] = (z["R1"] + z["G2"]) / 2
    for nm, v in z.items():
        h = te[["race_id", "odds", "pn", "ret", "hit", "yr"]].copy(); h["p"] = sg(ot + v); OUTS[nm].append(h)
    print(k, "木の本数", n1, flush=True)
rng = np.random.default_rng(0)
def cell(g):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (1000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    return f"{len(g):,}点・**{g.ret.mean():.0%}**（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}／" + "/".join(f"{g[g.yr == y].ret.mean():.0%}" for y in P) + "）"
NAME = {"R1": "R1 いまの機械（リッジ1回）", "R2": "R2 リッジ×ランダム30回の平均", "G1": "G1 木の機械1回", "G2": "G2 木の機械×ランダム20回の平均", "M": "M いまの機械と G2 の平均"}
L = ["# ランダムにレースを選んで学ぶ（バギング）と木の機械（ライン順×30倍以下・4年の1年抜き。y6 は見ていない）", "",
     "かっこ内＝95%の範囲／年別 y4/2024年/2025〜/y5", "", "| 機械 | 対数損失の改善×1万（市場比） | 期待値≥1.1 | 期待値≥1.2 |", "|---|---|---|---|"]
for nm, hs in OUTS.items():
    H = pd.concat(hs, ignore_index=True); H["ev"] = H.p * H.odds; pm = np.clip(H.pn, 1e-6, 1 - 1e-6)
    dl = (-(H.hit * np.log(H.p) + (1 - H.hit) * np.log(1 - H.p)).mean() + (H.hit * np.log(pm) + (1 - H.hit) * np.log(1 - pm)).mean()) * 1e4
    L.append(f"| {NAME[nm]} | {dl:+.1f} | {cell(H[H.ev >= 1.1])} | {cell(H[H.ev >= 1.2])} |")
    if nm == "R1": base = H
    else: L[-1] += f" R1 と選ぶ目の重なり（期待値≥1.1）{len(set(zip(H[H.ev >= 1.1].race_id, H[H.ev >= 1.1].odds)) & set(zip(base[base.ev >= 1.1].race_id, base[base.ev >= 1.1].odds))) / max((H.ev >= 1.1).sum(), 1):.0%} |"
open(sys.argv[1], "w", encoding="utf-8").write(NL.join(L) + NL); print("done")
