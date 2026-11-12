"""探す段階（Fable、2026-11-12 夜）：ライン順の機械に「新しい材料」を足すと、学ばない年での当てる力・回収率が上がるか（4年の1年抜き。y6 は見ない）。
土台＝research/lo_feats.py の24個。足す材料の組（どれも締切前に分かる。ほかの券種の確定オッズ由来の列は使わない）：
 A 控除の大きさ logS（S＝Σ1/odds＝1/(pn×odds)）／B 倍率の形（log odds・その2乗）／C 3連単の人気順（1番人気・3番人気以下）
 D 直近の成績（3人の直近着順の平均・番狂わせの履歴・3着内率）／E 予想印（1着が◎・3着が無印）／F 時間帯・級・格
 G ギア・先行の順位・過去の位置取りの回数
見るもの：学ばない年の対数損失の改善（土台との差×1万、マイナスが良い）、比≥1.2・期待値≥1.1・期待値≥1.2 の点数と回収率（年別）。
使い方: python -I -X utf8 research/fable_lo2.py reports/fable_lo2.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
P = {"y4": pd.read_pickle(K + "out/lo_all_y4.pkl"), "2024年": pd.read_pickle(K + "out/lo_all_2024年.pkl"),
     "2025/2〜": pd.read_pickle(K + "out/lo_all_20252.pkl"), "y5": pd.read_pickle(K + "out/lo_all_y5.pkl")}
P["2025/2〜"] = P["2025/2〜"][P["2025/2〜"].date <= "20261105"]
P = {k: d.reset_index(drop=True) for k, d in P.items()}
num = lambda s, f: pd.to_numeric(s, errors="coerce").fillna(f)
def extra(d):
    E = {}
    S = 1 / (d.pn * d.odds); lo = np.log(d.odds)
    E["A"] = pd.DataFrame({"logS": np.log(S) - 0.1})
    E["B"] = pd.DataFrame({"lod": lo - 2.0, "lod2": (lo - 2.0) ** 2})
    E["C"] = pd.DataFrame({"pop1": (d.popularity == 1).astype(float), "pop3": (d.popularity >= 3).astype(float)})
    E["D"] = pd.DataFrame({f"{r}_{c}": (num(d[f"{r}_{c}"], m) - m) / s for r in ("r0", "r1", "r2")
                           for c, m, s in (("ro_mean", 4.3, 1.0), ("h_surp_ewm", 0.0, 0.1), ("h_t3_rate", 0.33, 0.1))})
    E["E"] = pd.DataFrame({"a_hon": (d.r0_prediction_mark == 1).astype(float), "c_nomark": (d.r2_prediction_mark == 0).astype(float),
                           "b_nomark": (d.r1_prediction_mark == 0).astype(float)})
    E["F"] = pd.DataFrame({"night": (d.hour >= 19).astype(float), "morn": (d.hour <= 10).astype(float), "S": (d["class"] == "S級").astype(float),
                           "g3": (d.grade == "GIII").astype(float), "f1": (d.grade == "FI").astype(float)})
    E["G"] = pd.DataFrame({"a_gear": (num(d.r0_gear, 3.92) - 3.92) * 10, "a_lead1": (d.r0_lead_rank == 1).astype(float), "a_lead4": (d.r0_lead_rank >= 4).astype(float),
                           "c_mark": np.log1p(num(d.r2_n_marker, 1)) - 0.7, "a_front": np.log1p(num(d.r0_n_front, 3)) - 1.4})
    return E
BASE = {k: lo_feats(d) for k, d in P.items()}; EX = {k: extra(d) for k, d in P.items()}
OFF = {k: lo_lg(d.pn).to_numpy() for k, d in P.items()}
def mat(k, groups): return pd.concat([BASE[k]] + [EX[k][g].set_axis(P[k].index) for g in groups], axis=1)
def loyo(groups, lam=20.0):
    out = []
    for k in P:
        Xtr = pd.concat([mat(j, groups) for j in P if j != k], ignore_index=True)
        ytr = np.concatenate([P[j].hit.to_numpy() for j in P if j != k]); otr = np.concatenate([OFF[j] for j in P if j != k])
        b = lo_fit(Xtr, ytr, otr, lam); X = mat(k, groups)
        p = 1 / (1 + np.exp(-(OFF[k] + np.column_stack([np.ones(len(X)), X.to_numpy(float)]) @ b)))
        d = P[k][["race_id", "odds", "pn", "ret", "hit"]].copy(); d["p"] = p; d["yr"] = k; out.append(d)
    H = pd.concat(out, ignore_index=True); H["ratio"] = H.p / H.pn; H["ev"] = H.p * H.odds; return H
def ll(H): return -(H.hit * np.log(H.p) + (1 - H.hit) * np.log(1 - H.p)).mean()
def cell(g):
    if len(g) < 30: return f"{len(g)}点"
    return f"{len(g):,}点・**{g.ret.mean():.0%}**（" + "/".join(f"{g[g.yr == y].ret.mean():.0%}" for y in P) + "）"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def W(*a): print(*a, file=OUT, flush=True)
W("# ライン順の機械に新しい材料を足す（4年の1年抜き＝学ばない年だけ。y6 は見ていない）" + NL)
W("年別の並び：y4/2024年/2025〜/y5。対数損失の差は土台との差×1万（マイナスが良い。市場だけ→土台の改善も同じ単位で1行目に）" + NL)
H0 = loyo([]); l0 = ll(H0); lm = -(H0.hit * np.log(H0.pn) + (1 - H0.hit) * np.log(1 - H0.pn)).mean()
W("| 足した材料 | 対数損失の差 | 比≥1.2 | 期待値≥1.1 | 期待値≥1.2 |" + NL + "|---|---|---|---|---|")
W(f"| （土台。市場だけとの差 {1e4 * (l0 - lm):+.1f}） | 0 | {cell(H0[H0.ratio >= 1.2])} | {cell(H0[H0.ev >= 1.1])} | {cell(H0[H0.ev >= 1.2])} |")
RES = {}
for gs in (["A"], ["B"], ["C"], ["D"], ["E"], ["F"], ["G"], ["A", "B", "C"], ["D", "E"], ["A", "B", "C", "D", "E", "F", "G"]):
    H = loyo(gs); RES["".join(gs)] = H
    W(f"| {'+'.join(gs)} | {1e4 * (ll(H) - l0):+.1f} | {cell(H[H.ratio >= 1.2])} | {cell(H[H.ev >= 1.1])} | {cell(H[H.ev >= 1.2])} |")
H = loyo(["A", "B", "C", "D", "E", "F", "G"], 80.0)
W(f"| 全部（リッジ強め λ=80） | {1e4 * (ll(H) - l0):+.1f} | {cell(H[H.ratio >= 1.2])} | {cell(H[H.ev >= 1.1])} | {cell(H[H.ev >= 1.2])} |")
# 全部入りの係数（4年すべてで学ぶ。大きい順）
gs = ["A", "B", "C", "D", "E", "F", "G"]; X = pd.concat([mat(j, gs) for j in P], ignore_index=True)
b = lo_fit(X, np.concatenate([P[j].hit.to_numpy() for j in P]), np.concatenate([OFF[j] for j in P]), 20.0)
sd = X.std().to_numpy()
W(NL + "## 全部入りの係数×その材料のばらつき（効き目の大きい順、上位20）" + NL)
W("、".join(f"{n} {v:+.3f}" for n, v in sorted(zip(X.columns, b[1:] * sd), key=lambda t: -abs(t[1]))[:20]))
print("done")
