"""3連単の「方程式」探し：logit(本当の確率) = logit(市場の確率) + Σ 係数×項目。
項目は締切前でも崩れにくいもの（形・出走表・レース条件）だけ。前向き選択（止めどころ 26/7〜8 の当てる力で1個ずつ追加、最大10個）。
学習 25/2〜10/11＋26/2〜6、未使用① 25/10/12〜11/21、未使用② 25/11/22〜26/1/14。2026/9〜11 は使わない。"""
import json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
src = open(K + "research/sd_study.py", encoding="utf-8").read()
exec(src.split("B_in = pd.read_pickle")[0])  # prep・picks
IS = pd.read_pickle(SP + "tri3_all.pkl"); IS = IS[(IS.date < "20260901") & ~IS.date.between("20251012", "20260114")]
OS = pd.concat([pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh6", "fresh7")]); OS = OS[OS.date <= "20260114"]
IS, OS = prep(IS), prep(OS); IS, OS = IS[IS["class"] != "L級"].copy(), OS[OS["class"] != "L級"].copy()


def feats(D):
    s01, s12, s02 = D.s01 == 1, D.s12 == 1, D.s02 == 1; same3 = s01 & s12
    order = same3 & (D.r0_pos == 0) & (D.r1_pos == 1) & (D.r2_pos == 2)
    X = {"形：ライン3人が並び順": order, "形：ライン3人": same3, "形：1-2着が同ライン": s01, "形：2-3着が同ライン": s12, "形：1-3着が同ライン": s02,
         "3着が3番手": D.r2_pos == 2, "1着が先頭": D.r0_pos == 0, "1着が番手": D.r0_pos == 1, "1着が単騎": D.r0_single == 1,
         "9車": D.entries_number >= 9, "2日目以降": D.day_index >= 2, "G戦": D.G == 1, "S級": D.S == 1, "強い逃げ2人以上": D.n_strong_nige >= 2, "4分戦以上": D.nlines >= 4,
         "log倍率": D.lodds, "1着の1着率": D.r0_first_rate, "2着の2連対率": D.r1_second_rate, "3着の3着内率": D.r2_third_rate,
         "1着の勝つ見込み(p1)": D.r0_p1, "2着の3着内見込み(p3)": D.r1_p3, "3着の3着内見込み(p3)": D.r2_p3, "3着の勝つ見込み(p1)": D.r2_p1,
         "1着の印順位": D.r0_mk_rank, "3着の印順位": D.r2_mk_rank, "1着の得点順位": D.r0_pt_rank, "3着の得点順位": D.r2_pt_rank,
         "1着の年齢": D.r0_age, "3着の年齢": D.r2_age, "1着の予想印": D.r0_prediction_mark,
         "1着が逃げ": D.r0_style == "逃", "3着が追込": D.r2_style == "追"}
    return pd.DataFrame({k: np.asarray(v, dtype=float) for k, v in X.items()}, index=D.index).fillna(0)


XI, XO = feats(IS), feats(OS)
mu, sd = XI.mean(), XI.std().replace(0, 1)
ZI, ZO = (XI - mu) / sd, (XO - mu) / sd
y_I, y_O = (IS.ret > 0).to_numpy(float), (OS.ret > 0).to_numpy(float); off_I, off_O = IS.lp.to_numpy(), OS.lp.to_numpy()
tr = ((IS.date < "20251012") | IS.date.between("20260201", "20260630")).to_numpy(); va = IS.date.between("20260701", "20260831").to_numpy()


def fit(cols, mask):
    X = np.column_stack([np.ones(mask.sum())] + [ZI[c].to_numpy()[mask] for c in cols]); y, o = y_I[mask], off_I[mask]; b = np.zeros(X.shape[1])
    for _ in range(30):
        p = 1 / (1 + np.exp(-(X @ b + o))); H = X.T @ (X * (p * (1 - p))[:, None]) + np.eye(len(b)) * 1.0; g = X.T @ (y - p) - b * 1.0
        step = np.linalg.solve(H, g); b += step
        if np.abs(step).max() < 1e-7: break
    return b, np.sqrt(np.diag(np.linalg.inv(H)))


def ll(b, cols, Z, y, o):
    X = np.column_stack([np.ones(len(Z))] + [Z[c].to_numpy() for c in cols]); p = 1 / (1 + np.exp(-(X @ b + o))); p = p.clip(1e-9, 1 - 1e-9)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


Zv, yv, ov = ZI[va], y_I[va], off_I[va]
base = ll(np.zeros(1), [], Zv, yv, ov); chosen = []; cur = base
print(f"止めどころの当てる力（市場だけ）: {base:.6f}")
for step in range(10):
    best = None
    for c in ZI.columns:
        if c in chosen: continue
        b, _ = fit(chosen + [c], tr); v = ll(b, chosen + [c], Zv, yv, ov)
        if best is None or v < best[1]: best = (c, v)
    if best[1] > cur - 2e-6: break
    chosen.append(best[0]); cur = best[1]; print(f"  +{best[0]} → {cur:.6f}")
b, se = fit(chosen, tr | va)  # 最終の係数は 学習＋止めどころ で
print("\n## 方程式（項目は標準化：平均0・ばらつき1にそろえた値）\nlogit(本当の確率) = logit(市場の確率) " + f"{b[0]:+.3f}")
for c, bb, s in zip(chosen, b[1:], se[1:]): print(f"   {bb:+.3f} × [{c}]（平均{mu[c]:.2f}・ばらつき{sd[c]:.2f}）  t値{bb/s:+.1f}")
json.dump({"cols": chosen, "b": b.tolist(), "mu": mu[chosen].tolist(), "sd": sd[chosen].tolist()}, open(K + "research/tri_equation_v1.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
rng = np.random.default_rng(0)


def st(g):
    if not len(g): return "0点"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); i = rng.integers(0, len(by), (1000, len(by))); bs = by["sum"].to_numpy()[i].sum(1) / by["size"].to_numpy()[i].sum(1)
    return f"{g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］（{len(g)}点・当たり{int((g.ret>0).sum())}）"


def score(D, Z):
    X = np.column_stack([np.ones(len(Z))] + [Z[c].to_numpy() for c in chosen]); D = D.copy(); D["pe"] = 1 / (1 + np.exp(-(X @ b + D.lp.to_numpy()))); D["ev"] = D.pe * D.odds; return D


VA, O = score(IS[va], ZI[va]), score(OS, ZO)
for nm, D in (("止めどころ 26/7〜8（係数づくりに使用）", VA), ("未使用① 25/10/12〜11/21", O[O.date <= "20251121"]), ("未使用② 25/11/22〜26/1/14", O[O.date > "20251121"])):
    Bk, top = picks(D); key = ["race_id", "combo"]; Bk = Bk.merge(D[key + ["ev"]], on=key); top = top.merge(D[key + ["ev"]], on=key)
    e2 = Bk.sort_values("ev").groupby("race_id").tail(1)
    print(f"\n## {nm}（当てる力 市場{ll(np.zeros(1), [], pd.DataFrame(index=D.index), (D.ret>0).to_numpy(float), D.lp.to_numpy()):.5f} → 方程式 {-np.mean((D.ret>0)*np.log(D.pe)+(D.ret<=0)*np.log(1-D.pe)):.5f}）")
    print(f"- 全部の目で期待値≥1.0（60倍以下）: {st(D[(D.odds <= 60) & (D.ev >= 1.0)])}")
    print(f"- 1レース1点（60倍以下・期待値≥1.0で一番）: {st(D[(D.odds <= 60) & (D.ev >= 1.0)].sort_values('ev').groupby('race_id').tail(1))}")
    print(f"- 3連単枠 全部 {st(Bk)} ／ 今の一番の目 {st(top)}")
    print(f"- 3連単枠の中で方程式の期待値が一番の目: {st(e2)} ／ そのうち期待値≥0.9: {st(e2[e2.ev >= 0.9])}")
