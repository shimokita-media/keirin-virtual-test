"""ベンター方式（2026-11-09 20:00〜）：①オッズを見ない「実力モデル」を着順（1着→2着→3着）のモデル（Plackett-Luce）で学ぶ
②市場（3連単から出した1着の見込み）と混ぜる：v = a×実力 + b×log(市場の1着見込み)、2着・3着は v を s2・s3 倍（ベンターの割引）
③3人の順番の確率 P(i→j→k) を作り、3連単の最終倍率と比べて期待値で選ぶ
学習：①は 2025/2〜2026/6/15（③を除く）、②の a,b,s2,s3 は止めどころ 2026/6/16〜8/31 だけで決める。確認：③・⑥・2024/2〜7/8（どれも①②に使わない）
使い方: python -I -X utf8 research/benter.py 出力.md"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize
K = "C:/Users/take0/.claude/keirin/"; SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
cols = ["race_id", "number", "player_id", "age", "style", "race_point", "prediction_mark", "first_rate", "second_rate", "third_rate", "n_front", "n_marker",
        "gear", "rank", "p1", "pos", "ls", "nlines", "lead_rank", "line_idx", "single", "date", "class", "n_strong_nige", "entries_number"]
A = pd.concat([pd.read_pickle(SP + "ana_all3.pkl")[cols]] + [pd.read_pickle(K + f"out/fresh{x}/ana.pkl")[cols] for x in ("", "2", "3", "4", "5", "6", "7")] +
              [pd.read_pickle(K + "out/y2024a/ana.pkl")[cols]]).drop_duplicates(["race_id", "number"])
A = A[A["class"] != "L級"].copy()
for c in ("age", "race_point", "prediction_mark", "first_rate", "second_rate", "third_rate", "n_front", "n_marker", "gear", "rank", "p1", "pos", "ls", "lead_rank", "n_strong_nige"):
    A[c] = pd.to_numeric(A[c], errors="coerce")
g = A.groupby("race_id")
def z(c): return ((A[c] - g[c].transform("mean")) / g[c].transform("std").replace(0, np.nan)).fillna(0)
A["lstr"] = A.groupby(["race_id", "line_idx"]).race_point.transform("sum")
F = pd.DataFrame({"z_rp": z("race_point"), "z_r1": z("first_rate"), "z_r2": z("second_rate"), "z_r3": z("third_rate"), "mark": A.prediction_mark.fillna(0),
                  "pos0": (A.pos == 0).astype(float), "pos1": (A.pos == 1).astype(float), "pos2": (A.pos == 2).astype(float), "single": A.single.astype(float),
                  "ls": A.ls.fillna(1), "z_lstr": z("lstr"), "lead_rank": A.lead_rank.fillna(9), "nige": (A["style"] == "逃").astype(float),
                  "oi": (A["style"] == "追").astype(float), "z_age": z("age"), "z_front": z("n_front"), "z_marker": z("n_marker"), "z_gear": z("gear"),
                  "nsn": A.n_strong_nige.fillna(0)}, index=A.index)
F["pos0_nige"] = F.pos0 * F.nige; F["pos1_rp"] = F.pos1 * F.z_rp; F["pos0_rp"] = F.pos0 * F.z_rp; F["single_rp"] = F.single * F.z_rp
FEATS = list(F.columns)
A = pd.concat([A.drop(columns=[c for c in F.columns if c in A.columns]), F], axis=1).sort_values(["race_id", "number"])
def per(d): return np.select([d.between("20251012", "20260114"), d >= "20260901", d < "20250201", (d > "20260615") & (d <= "20260831")], ["③", "⑥", "2024", "止"], "学習")
A["per"] = per(A.date)
# --- 箱詰め（レース×最大9人）
def pack(D):
    rids = D.race_id.unique(); idx = {r: i for i, r in enumerate(rids)}; R = len(rids)
    D = D.assign(ri=D.race_id.map(idx)); D["slot"] = D.groupby("race_id").cumcount()
    D = D[D.slot < 9]
    X = np.zeros((R, 9, len(FEATS))); M = np.zeros((R, 9), bool); MK = np.full((R, 9), np.nan); RK = np.full((R, 9), np.nan); NUM = np.zeros((R, 9), int)
    X[D.ri, D.slot] = D[FEATS].to_numpy(); M[D.ri, D.slot] = True; MK[D.ri, D.slot] = D.p1.to_numpy(); RK[D.ri, D.slot] = D["rank"].to_numpy(); NUM[D.ri, D.slot] = D.number.to_numpy()
    O = np.full((R, 3), -1)
    for k in range(3):
        hit = (RK == k + 1); has = hit.any(1); O[has, k] = hit[has].argmax(1)
    ok = (O >= 0).all(1)
    return dict(X=X, M=M, MK=MK, O=O, ok=ok, rids=rids, NUM=NUM)
def pl_ll(U, M, O, ok, scales=(1, 1, 1)):
    """Plackett-Luce の対数尤度（上位3着）と、U に対する勾配"""
    R = U.shape[0]; ar = np.arange(R); rem = M.copy(); ll = np.zeros(R); G = np.zeros_like(U)
    for k in range(3):
        s = scales[k]; Uk = np.where(rem, s * U, -np.inf); mx = Uk.max(1, keepdims=True); e = np.exp(Uk - mx); Z = e.sum(1, keepdims=True); p = e / Z
        o = O[:, k].clip(0); ll += np.where(ok, s * U[ar, o] - (np.log(Z[:, 0]) + mx[:, 0]), 0)
        G -= np.where(ok[:, None], s * p, 0); G[ar, o] += np.where(ok, s, 0)
        rem[ar, o] = False
    return ll, G
TR = pack(A[A.per == "学習"]); VA = pack(A[A.per == "止"])
P("# ベンター方式：実力モデル（着順モデル）＋市場の混ぜ合わせ" + NL)
P(f"選手表 {len(A):,}行。学習 {TR['ok'].sum():,}R・止めどころ {VA['ok'].sum():,}R。実力モデルの特徴量 {len(FEATS)} 個（オッズは使わない）。" + NL)
# --- ① 実力モデル
def f_obj(w, D, lam=1.0):
    U = D["X"] @ w; ll, G = pl_ll(U, D["M"], D["O"], D["ok"])
    grad = np.einsum("rn,rnf->f", G, D["X"])
    return -(ll.sum()) + lam * (w ** 2).sum(), -grad + 2 * lam * w
res = minimize(f_obj, np.zeros(len(FEATS)), args=(TR,), jac=True, method="L-BFGS-B", options={"maxiter": 500})
w = res.x
# 標準誤差（ヘッセ行列の数値近似は重いので、勾配の外積で近似）
P("## ① 実力モデルの係数（着順モデル。正＝上位に来やすい）" + NL + NL + "| 特徴量 | 係数 |" + NL + "|---|---|")
for f_, b_ in sorted(zip(FEATS, w), key=lambda t: -abs(t[1])): P(f"| {f_} | {b_:+.3f} |")
# --- ② 市場と混ぜる（止めどころだけで a,b,s2,s3 を決める）
def blend_U(D, a, b): return a * (D["X"] @ w) + b * np.log(np.clip(np.nan_to_num(D["MK"], nan=1e-4), 1e-4, 1))
def b_obj(th, D):
    a, b, s2, s3 = th; ll, _ = pl_ll(blend_U(D, a, b), D["M"], D["O"], D["ok"], (1, s2, s3)); return -ll.sum()
r2 = minimize(b_obj, np.array([0.3, 1.0, 0.8, 0.7]), args=(VA,), method="Nelder-Mead", options={"maxiter": 600, "xatol": 1e-4, "fatol": 1e-3})
a, b, s2, s3 = r2.x
P(NL + f"## ② 混ぜ合わせ（止めどころで決定）：v = {a:.3f}×実力 + {b:.3f}×log(市場の1着見込み)、2着は v×{s2:.3f}、3着は v×{s3:.3f}" + NL)
_mk = minimize(lambda th: b_obj([0, 1, th[0], th[1]], VA), np.array([0.8, 0.7]), method="Nelder-Mead"); mk_only = _mk.fun; s2m, s3m = _mk.x
P(f"止めどころの対数尤度：市場だけ（割引あり）{-mk_only:.1f} → 混ぜ合わせ {-r2.fun:.1f}（差 {mk_only - r2.fun:+.1f}）" + NL)
# --- ③ 3連単の確率と期待値
def tri_prob(D, rid_to_combo, a=a, b=b, s2=s2, s3=s3):
    U = blend_U(D, a, b); out = {}
    for i, rid in enumerate(D["rids"]):
        if rid not in rid_to_combo: continue
        m = D["M"][i]; u = U[i]; nums = D["NUM"][i]; pos = {n: j for j, n in enumerate(nums) if m[j]}
        e1 = np.exp(u - u[m].max()) * m
        for combo in rid_to_combo[rid]:
            x, y, zz = combo
            if x not in pos or y not in pos or zz not in pos: continue
            ix, iy, iz = pos[x], pos[y], pos[zz]
            p1 = e1[ix] / e1.sum()
            e2 = np.exp(s2 * (u - u[m].max())) * m; e2[ix] = 0; p2 = e2[iy] / e2.sum()
            e3 = np.exp(s3 * (u - u[m].max())) * m; e3[ix] = 0; e3[iy] = 0; p3 = e3[iz] / e3.sum()
            out[(rid, combo)] = p1 * p2 * p3
    return out
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
T1 = pd.read_pickle(K + "out/angle_base.pkl")[["race_id", "combo", "date", "odds", "ret", "is_top", "in_B"]]
T2 = prep(pd.read_pickle(K + "out/y2024a/tri.pkl")); T2 = T2[(T2["class"] != "L級") & (T2.odds <= 300)][["race_id", "combo", "date", "odds", "ret"]]
TT = pd.concat([T1, T2.assign(is_top=False, in_B=False)], ignore_index=True)
TT["per"] = per(TT.date); TT = TT[TT.per.isin(["止", "③", "⑥", "2024"])].copy()
q = 1 / TT.odds; TT["pm"] = q / q.groupby(TT.race_id).transform("sum")
cb = TT.combo.str.split("-", expand=True).astype(int); TT["cb"] = list(zip(cb[0], cb[1], cb[2]))
rc = TT.groupby("race_id").cb.apply(list).to_dict()
probs = {}; pm_pl = {}
for k in ("止", "③", "⑥", "2024"):
    D = pack(A[A.per == k]); probs.update(tri_prob(D, rc)); pm_pl.update(tri_prob(D, rc, a=0.0, b=1.0, s2=s2m, s3=s3m))
TT["pb"] = [probs.get((r, c), np.nan) for r, c in zip(TT.race_id, TT.cb)]
TT["pmpl"] = [pm_pl.get((r, c), np.nan) for r, c in zip(TT.race_id, TT.cb)]
TT = TT.dropna(subset=["pb", "pmpl"])
# ベンターの補正の比：実力を混ぜた着順モデル ÷ 市場だけの着順モデル。着順モデルそのもののくせ（3連単の配り方の下手さ）は打ち消し、実力の分だけ3連単の市場を動かす
TT["adj"] = TT.pb / TT.pmpl
TT["pa"] = TT.pm * TT.adj; TT["pa"] = TT.pa / TT.groupby("race_id").pa.transform("sum")
base_roi = TT.ret.mean()  # 市場どおりなら回収率はこの程度（控除後）
TT["ev"] = 0.75 * TT.pa / TT.pm  # 期待回収率 ≒ 控除後の0.75 ×（補正後の見込み ÷ 市場の見込み）
TT["pb_raw_norm"] = TT.pb / TT.groupby("race_id").pb.transform("sum")
y = (TT.ret > 0).astype(float)
def lli(p): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
TT["d"] = lli(TT.pm) - lli(TT.pa)  # 補正した3連単の見込み（pa）と市場（pm）を比べる
P("## ③ 当てる力（3連単の目ごとの対数損失の差：市場−ベンター、レースごとに合計。平均・標準偏差・t値）" + NL + NL + "| 期間 | レース数 | 差の平均 | 標準偏差 | t値 |" + NL + "|---|---|---|---|---|")
for k in ("止", "③", "⑥", "2024"):
    dd = TT[TT.per == k].groupby("race_id").d.sum(); P(f"| {k} | {len(dd):,} | {dd.mean():+.4f} | {dd.std():.3f} | {dd.mean() / (dd.std() / np.sqrt(len(dd))):+.1f} |")
rng = np.random.default_rng(0)
def cell(x):
    if len(x) < 20: return f"−（{len(x)}点）"
    by = x.groupby("race_id").ret.agg(["sum", "size"]); wts = rng.dirichlet(np.ones(len(by)), 3000); post = (wts @ by["sum"].to_numpy()) / (wts @ by["size"].to_numpy())
    r = x.ret; t_ = (r.mean() - 1) / (r.std() / np.sqrt(len(r)))
    return f"**{r.mean():.0%}**（{len(x)}点・{int((r > 0).sum())}本・t={t_:+.1f}・P>100% {(post > 1).mean():.0%}）"
P(NL + "## ④ ベンター確率で選んだ回収率（最終オッズ・各100円。期待回収率≒0.75×（実力を混ぜた着順モデル÷市場だけの着順モデル の比を、レース内の平均で割ったもの））" + NL + NL + "| 選び方 | 止めどころ | ③ | ⑥ | 2024/2〜7/8 |" + NL + "|---|---|---|---|---|")
sel = {f"期待回収率≥{t}": (lambda x, t=t: x[x.ev >= t]) for t in (0.85, 0.9, 1.0, 1.1)}
sel["期待回収率≥0.9×30倍以下"] = lambda x: x[(x.ev >= 0.9) & (x.odds <= 30)]
sel["期待回収率≥1.0×60倍以下"] = lambda x: x[(x.ev >= 1.0) & (x.odds <= 60)]
sel["1レース1点（期待回収率最大・≥0.9・60倍以下）"] = lambda x: x[(x.ev >= 0.9) & (x.odds <= 60)].sort_values("ev", ascending=False).groupby("race_id").head(1)
sel["一番の目×期待回収率≥1.0（2024は一番の目の印なし）"] = lambda x: x[x.is_top & (x.ev >= 1.0)]
for nm, fn in sel.items():
    P(f"| {nm} | " + " | ".join(cell(fn(TT[TT.per == k])) for k in ("止", "③", "⑥", "2024")) + " |")
np.save(K + "research/benter_w.npy", np.r_[w, a, b, s2, s3])
TT[["race_id", "combo", "date", "odds", "ret", "pm", "pb", "pmpl", "adj", "pa", "ev", "per", "is_top", "in_B"]].to_pickle(K + "out/benter_pred.pkl")
print("done", a, b, s2, s3)
