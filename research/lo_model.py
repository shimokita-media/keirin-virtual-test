"""探す段階（Fable）：ライン順の本命の目（15倍以下）だけで、締切前に分かる情報だけの小さな機械。1つの年で学び、ほかの2つの年で確かめる（選ぶ年と確かめる年を分ける）。
対象：out/lo_all_<期間>.pkl（同じライン3人で先頭→番手→3番手・確定オッズ15倍以下）。市場の見込み pn を出発点（offset）にしたロジスティック回帰（リッジつきニュートン法）。
特徴量（どれもレースの前に決まっている）：3着・1着・2着の得点順位、当日の流れ（前のレースで先頭が勝った割合・前のレースがあるか）、ラインの数・人数、何日目、G戦、9車、1着が逃げ、2着が追込、3着の年齢・3連対率、強い逃げの人数。g_tf などの確定オッズの割安さは使わない。
使い方: python -I -X utf8 research/lo_model.py reports/lo_model.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
PER = {"y4": "out/lo_all_y4.pkl", "2024年": "out/lo_all_2024年.pkl", "2025/2〜": "out/lo_all_20252.pkl"}
def feats(d):
    X = pd.DataFrame(index=d.index)
    X["c7"] = (d.r2_pt_rank >= 7).astype(float); X["c56"] = d.r2_pt_rank.between(5, 6).astype(float)
    X["a1"] = (d.r0_pt_rank == 1).astype(float); X["a4"] = (d.r0_pt_rank >= 4).astype(float)
    X["b1"] = (d.r1_pt_rank == 1).astype(float); X["b4"] = (d.r1_pt_rank >= 4).astype(float)
    fl = d.flow.fillna(0.5); X["flow"] = fl - 0.5; X["lowf"] = ((d.n_prev >= 1) & (d.flow <= 0.3)).astype(float); X["first"] = (d.n_prev == 0).astype(float)
    X["c7_lowf"] = X.c7 * X.lowf; X["c7_flow"] = X.c7 * X.flow
    X["n3"] = (d.nlines == 3).astype(float); X["n4"] = (d.nlines >= 4).astype(float); X["ls4"] = (d.r0_ls >= 4).astype(float)
    X["d2"] = (d.day_index == 2).astype(float); X["d3"] = (d.day_index >= 3).astype(float); X["G"] = (d.G == 1).astype(float); X["nine"] = (d.entries_number >= 9).astype(float)
    X["a_nige"] = (d.r0_style == "逃").astype(float); X["b_oi"] = (d.r1_style == "追").astype(float)
    X["c_age"] = (pd.to_numeric(d.r2_age, errors="coerce").fillna(38) - 38) / 10; X["c_t3"] = (pd.to_numeric(d.r2_third_rate, errors="coerce").fillna(30) - 30) / 20
    X["nige2"] = (d.n_strong_nige >= 2).astype(float); X["lp"] = np.log(d.pn) - np.log(0.15)
    return X
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
def fit(X, y, off, lam=20.0):
    A = np.column_stack([np.ones(len(X)), X.to_numpy(float)]); b = np.zeros(A.shape[1]); R = np.eye(A.shape[1]) * lam; R[0, 0] = 0
    for _ in range(50):
        mu = 1 / (1 + np.exp(-(off + A @ b))); w = mu * (1 - mu); H = (A * w[:, None]).T @ A + R; s = np.linalg.solve(H, A.T @ (y - mu) - R @ b); b += s
        if np.abs(s).max() < 1e-8: break
    return b
def pred(b, X, off): return 1 / (1 + np.exp(-(off + np.column_stack([np.ones(len(X)), X.to_numpy(float)]) @ b)))
D = {k: pd.read_pickle(K + f) for k, f in PER.items()}
Xs = {k: feats(d) for k, d in D.items()}
rng = np.random.default_rng(0)
def cell(g):
    if len(g) < 40: return f"{len(g)}（少）"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (2000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    return f"{len(g):,}点・{int(g.hit.sum())}本・**{g.ret.mean():.0%}**（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
P("# 探す段階：ライン順の本命の目（15倍以下）だけの小さな機械（締切前に分かる情報だけ・1つの年で学びほかの年で確かめる）" + NL)
P("全部（ライン順×15倍以下）： " + " ／ ".join(f"{k} {len(d):,}点・{d.ret.mean():.0%}" for k, d in D.items()) + NL)
for tr in PER:
    b = fit(Xs[tr], D[tr].hit.to_numpy(), lg(D[tr].pn).to_numpy())
    P(f"## {tr} で学ぶ" + NL)
    names = ["const"] + list(Xs[tr].columns); top = sorted(zip(names[1:], b[1:]), key=lambda t: -abs(t[1]))[:8]
    P("係数の大きい順： " + "、".join(f"{n} {v:+.2f}" for n, v in top) + NL)
    P("| 期待値（機械の見込み÷市場の見込み） | " + " | ".join(f"{k}{'（学んだ年）' if k == tr else '（確かめ）'}" for k in PER) + " |" + NL + "|---|---|---|---|")
    ratio = {k: pred(b, Xs[k], lg(D[k].pn).to_numpy()) / D[k].pn for k in PER}
    for th in (1.1, 1.2, 1.3, 1.4):
        P(f"| {th}倍以上 | " + " | ".join(cell(D[k][ratio[k] >= th]) for k in PER) + " |")
    P(f"| 1.1倍未満（残り） | " + " | ".join(cell(D[k][ratio[k] < 1.1]) for k in PER) + " |")
    # 当てる力：確かめの年で、機械の見込みが市場より良いか（対数損失の差。レースをまたいだ行ごと）
    for k in PER:
        if k == tr: continue
        pm = np.clip(ratio[k] * D[k].pn, 1e-6, 1 - 1e-6); y = D[k].hit.to_numpy(); pn = D[k].pn.to_numpy()
        ll = (y * np.log(pm) + (1 - y) * np.log(1 - pm)) - (y * np.log(pn) + (1 - y) * np.log(1 - pn))
        P(f"- {k} で当てる力（行ごとの対数損失の改善）：平均 {ll.mean():+.4f}、t={ll.mean() / (ll.std() / np.sqrt(len(ll))):+.2f}")
    P("")
print("done")
