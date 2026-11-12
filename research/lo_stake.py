"""ライン順の機械（L4）の「絞り方」と「買い方の配分」を、4年分の1年抜き（学ばない年の予測）で比べる（2026-11-12、y6 は見ない）。
目的：y6 の判定前に、120% を狙う絞り方・配分を見た年だけで決めて事前登録する。
- 絞り方：比（機械÷市場）の線、期待値 EV＝比×pn×odds（機械の見込み×倍率）の線
- 配分：一律100円、比−1 に比例、ケリー（edge/(odds−1)）
回収率＝Σ(賭け金×払戻倍率)/Σ賭け金。95%の範囲はレース単位のブートストラップ 2,000回。
使い方: python -I -X utf8 research/lo_stake.py reports/lo_stake.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
P = {"y4": pd.read_pickle(K + "out/lo_all_y4.pkl"), "2024年": pd.read_pickle(K + "out/lo_all_2024年.pkl"),
     "2025/2〜": pd.read_pickle(K + "out/lo_all_20252.pkl"), "y5": pd.read_pickle(K + "out/lo_all_y5.pkl")}
P["2025/2〜"] = P["2025/2〜"][P["2025/2〜"].date <= "20261105"]
H = []
for k in P:
    tr = pd.concat([d for j, d in P.items() if j != k], ignore_index=True)
    b = lo_fit(lo_feats(tr), tr.hit.to_numpy(), lo_lg(tr.pn).to_numpy(), 20.0)
    d = P[k][["race_id", "date", "odds", "pn", "ret", "hit"]].copy(); d["ratio"] = lo_ratio(b, P[k]); d["yr"] = k; H.append(d)
H = pd.concat(H, ignore_index=True); H["ev"] = H.ratio * H.pn * H.odds
H.to_pickle(K + "out/lo_stake_heldout.pkl")
rng = np.random.default_rng(0)
def roi(g, w):
    if len(g) < 30: return f"{len(g)}点（少）"
    x = pd.DataFrame({"r": g.race_id.to_numpy(), "a": (w * g.ret).to_numpy(), "w": w.to_numpy()}).groupby("r").sum()
    a, s = x.a.to_numpy(), x.w.to_numpy(); ii = rng.integers(0, len(x), (2000, len(x))); bs = a[ii].sum(1) / s[ii].sum(1)
    ys = " / ".join(f"{(w[g.yr == y] * g.ret[g.yr == y]).sum() / max(w[g.yr == y].sum(), 1e-9):.0%}" for y in P)
    return f"{len(g):,}点・**{a.sum() / s.sum():.0%}**（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）・年別 {ys}"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def W(*a): print(*a, file=OUT, flush=True)
W("# ライン順の機械：絞り方と配分（4年の1年抜き＝学ばない年の予測だけ。y6 は見ていない）" + NL)
W("年別の並び：y4 / 2024年 / 2025/2〜 / y5" + NL)
W("## 絞り方（一律100円）" + NL + "| 条件 | 成績 |" + NL + "|---|---|")
for t in (1.2, 1.3, 1.35, 1.4, 1.5):
    g = H[H.ratio >= t]; W(f"| 比 ≥ {t} | {roi(g, pd.Series(1.0, index=g.index))} |")
for t in (0.9, 1.0, 1.1, 1.2, 1.3):
    g = H[H.ev >= t]; W(f"| 期待値 ≥ {t} | {roi(g, pd.Series(1.0, index=g.index))} |")
for t, o in ((1.3, 10), (1.3, 7), (1.2, 10), (1.2, 7)):
    g = H[(H.ratio >= t) & (H.odds <= o)]; W(f"| 比 ≥ {t} × {o}倍以下 | {roi(g, pd.Series(1.0, index=g.index))} |")
W(NL + "## 配分（比 ≥ 1.2 の目の中で賭け金を変える）" + NL + "| 配分 | 成績 |" + NL + "|---|---|")
g = H[H.ratio >= 1.2]
W(f"| 一律 | {roi(g, pd.Series(1.0, index=g.index))} |")
W(f"| 比−1 に比例 | {roi(g, g.ratio - 1)} |")
W(f"| (比−1)² に比例 | {roi(g, (g.ratio - 1) ** 2)} |")
kel = ((g.ev - 1) / (g.odds - 1)).clip(lower=0)
gk = g[kel > 0]; W(f"| ケリー（期待値>1 の目だけ・edge/(odds−1)） | {roi(gk, kel[kel > 0])} |")
W(f"| 期待値−0.8 に比例（0 未満は0） | {roi(g[g.ev > 0.8], g.ev[g.ev > 0.8] - 0.8)} |")
print("done")
