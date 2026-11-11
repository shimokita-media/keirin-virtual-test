"""ライン順の機械（research/lo_model.py）の特徴量と予測。exec(open(...).read()) で読み込んで使う（-I だと import できないため）。
特徴量はどれも締切前に分かる情報：得点順位、当日の流れ（flow・n_prev）、ラインの数・人数、何日目、G戦、9車、脚質、3着の年齢・3連対率、強い逃げの人数、市場の見込み pn。"""
import json, numpy as np, pandas as pd
LO_COLS = ["c7", "c56", "a1", "a4", "b1", "b4", "flow", "lowf", "first", "c7_lowf", "c7_flow", "n3", "n4", "ls4", "d2", "d3", "G", "nine", "a_nige", "b_oi", "c_age", "c_t3", "nige2", "lp"]
def lo_feats(d):
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
    return X[LO_COLS]
def lo_lg(p): p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))
def lo_fit(X, y, off, lam=20.0):
    A = np.column_stack([np.ones(len(X)), X.to_numpy(float)]); b = np.zeros(A.shape[1]); R = np.eye(A.shape[1]) * lam; R[0, 0] = 0
    for _ in range(50):
        mu = 1 / (1 + np.exp(-(off + A @ b))); w = mu * (1 - mu); H = (A * w[:, None]).T @ A + R; s = np.linalg.solve(H, A.T @ (y - mu) - R @ b); b += s
        if np.abs(s).max() < 1e-8: break
    return b
def lo_ratio(b, d):
    """機械の見込み ÷ 市場の見込み（1.3 以上＝機械が市場より3割以上当たると見た目）"""
    off = lo_lg(d.pn).to_numpy(); A = np.column_stack([np.ones(len(d)), lo_feats(d).to_numpy(float)])
    return 1 / (1 + np.exp(-(off + A @ np.asarray(b)))) / d.pn.to_numpy()
