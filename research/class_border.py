"""C 級班が決まる成績の期間の終わり（1〜6月の成績→10月から、7〜12月の成績→4月から。終わりの5〜6月・11〜12月）に、
級班の中で得点が下の方の選手（降級・代謝が近い）や上の方の選手（昇級が近い）が、市場の見込みからずれるか（探す段階・確定オッズ）。
級班の中の位置＝その日に走った同じ級・班の選手の中での得点の順位（％）。使い方: python -I -X utf8 research/class_border.py 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); Q = pd.read_pickle(K + "out/rider_q.pkl"); T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date"]], on="race_id"); E = E[E.race_id.isin(set(R.race_id)) & E["class"].isin([1, 2])]
rk = R.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])["rank"]
E["rank"] = rk.reindex(list(zip(E.race_id, E.number))).to_numpy()
E = E.merge(Q, on=["race_id", "number"])
E["y1"] = (E["rank"] == 1).astype(int); E["y3"] = (E["rank"] <= 3).astype(int)
for k, y in (("q1", "y1"), ("q3", "y3")):
    b = pd.qcut(E[k], 30, duplicates="drop"); f = E.groupby(b, observed=True)[y].sum() / E.groupby(b, observed=True)[k].sum()
    E[k] = E[k] * b.map(f).astype(float)
E["ym"] = E.date.str[:6]
E["pct"] = E.groupby(["ym", "class", "grp"]).race_point.rank(pct=True)
E["m"] = E.date.str[4:6].astype(int)
E["endp"] = E.m.isin([5, 6, 11, 12])
E["half"] = np.where(E.date < "20260101", "〜2025", "2026")
E["cg"] = np.where(E["class"] == 1, "S", "A") + E.grp.astype(str) + "班"
def row(lab, d):
    if len(d) < 100: return
    r1 = d.y1.sum() / d.q1.sum(); t1 = (d.y1.sum() - d.q1.sum()) / np.sqrt((d.q1.clip(0, 1) * (1 - d.q1.clip(0, 1))).sum())
    r3 = d.y3.sum() / d.q3.sum(); t3 = (d.y3.sum() - d.q3.sum()) / np.sqrt((d.q3.clip(0, 1) * (1 - d.q3.clip(0, 1))).sum())
    hh = "・".join(f"{h} {x.y3.sum() / x.q3.sum():.2f}" for h, x in d.groupby("half"))
    P(f"| {lab} | {len(d):,} | {r1:.3f} | {t1:+.1f} | {r3:.3f} | {t3:+.1f} | {hh} |")
HDR = "| 区分 | 人数 | 1着 実際÷見込み | t | 3着以内 実際÷見込み | t | 前半・後半（3着以内） |" + NL + "|---|---|---|---|---|---|---|"
P(f"# 級班が決まる期間の終わり（探す段階・確定オッズ、{E.date.min()}〜{E.date.max()}、S級・A級の男子）" + NL)
P("期間の終わり＝5〜6月・11〜12月。下の方＝同じ級班の中で得点が下から20%、上の方＝上から20%" + NL + HDR)
for cg in ["S1班", "S2班", "A1班", "A2班", "A3班"]:
    for lab, m in (("下の方", E.pct <= 0.2), ("上の方", E.pct >= 0.8)):
        row(f"{cg}×{lab}×期間の終わり", E[(E.cg == cg) & m & E.endp]); row(f"{cg}×{lab}×それ以外の月", E[(E.cg == cg) & m & ~E.endp])
P(NL + "### まとめ（全部の級班）" + NL + HDR)
for lab, m in (("下の方", E.pct <= 0.2), ("上の方", E.pct >= 0.8), ("真ん中", E.pct.between(0.2, 0.8, inclusive="neither"))):
    row(f"{lab}×期間の終わり", E[m & E.endp]); row(f"{lab}×それ以外の月", E[m & ~E.endp])
P(NL + "### 月ごと（A3班の下の方＝代謝が近い）" + NL + HDR)
for mm in range(1, 13): row(f"{mm}月", E[(E.cg == "A3班") & (E.pct <= 0.2) & (E.m == mm)])
print("done")
# 追加：A3班の下の方は新人のせいか（年齢・期で分ける）、その選手を含む3連単の回収率
A = E[(E.cg == "A3班")].copy()
A["low"] = A.pct <= 0.2
A["young"] = A.age <= 25
P(NL + "### A3班の下の方 × 年齢" + NL + HDR)
for lab, m in (("下の方×25歳以下", A.low & A.young), ("下の方×26〜39歳", A.low & A.age.between(26, 39)), ("下の方×40歳以上", A.low & (A.age >= 40)),
               ("それ以外×25歳以下", ~A.low & A.young), ("それ以外×40歳以上", ~A.low & (A.age >= 40))):
    row(lab, A[m])
TT = T.merge(A[["race_id", "number", "low", "age", "half"]], left_on=["race_id", "c"], right_on=["race_id", "number"])
P(NL + "その選手が3着の3連単（300倍以下・全部100円）、全体 " + f"{T.ret.mean():.0%}" + NL + "| 区分 | 点数 | 回収率 | 前半・後半 |" + NL + "|---|---|---|---|")
for lab, m in (("A3下の方が3着", TT.low), ("A3下の方×40歳以上が3着", TT.low & (TT.age >= 40)), ("A3それ以外が3着", ~TT.low)):
    d = TT[m]; P(f"| {lab} | {len(d):,} | {d.ret.mean():.0%} | " + "・".join(f"{h} {x.ret.mean():.0%}" for h, x in d.groupby("half")) + " |")
TA = T.merge(A[["race_id", "number", "low", "half"]], left_on=["race_id", "a"], right_on=["race_id", "number"])
d = TA[TA.low]; P(f"| A3下の方が1着 | {len(d):,} | {d.ret.mean():.0%} | " + "・".join(f"{h} {x.ret.mean():.0%}" for h, x in d.groupby("half")) + " |")
print("done2")
