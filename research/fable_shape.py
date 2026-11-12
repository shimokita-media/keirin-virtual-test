"""探す段階（Fable、2026-11-12 夜）：ライン順でうまくいった「小さな機械＋期待値の線」を、ほかの並びの形にも当てる（4年の1年抜き。y6 は見ない）。
ねらい：ライン順×15倍以下だけだと期待値1.2以上が1日0.6点しか出ない → 形を広げて点数を増やせるか。
対象＝確定オッズ30倍以下の全部の目。形（1着・2着・3着のラインの関係と位置）ごとに、research/lo_feats.py と同じ材料・同じ学び方（市場の見込みを出発点にしたリッジ λ=20）で別々に学ぶ。
形：LO ライン順（先頭→番手→3番手）／UR 番手→先頭→同ライン3番手／AB 先頭→番手→別線／BA 番手→先頭→別線／AxB 先頭→別線→番手（同ラインはさむ）／
    BxA 番手→別線→先頭／XAB 別線→先頭→番手（同ラインの2人が2・3着）／ALL3 3人とも別線・単騎まじり／OTH その他
使い方: python -I -X utf8 research/fable_shape.py reports/fable_shape.md"""
import sys, os, gc, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
SRC = {"y4": ("out/y4/cache.pkl", "20221108", "20231107"), "2024年": ("out/y2024full/cache.pkl", "20231108", "20250131"),
       "2025/2〜": ("out/angle_base.pkl", "20250201", "20261105"), "y5": ("out/y5/cache.pkl", "20211108", "20221107")}
KEEP = ["race_id", "date", "combo", "odds", "ret", "hit", "pn", "flow", "n_prev", "s01", "s12", "s02", "r0_pos", "r1_pos", "r2_pos", "r0_single", "r1_single", "r2_single",
        "r0_pt_rank", "r1_pt_rank", "r2_pt_rank", "nlines", "r0_ls", "day_index", "G", "entries_number", "r0_style", "r1_style", "r2_age", "r2_third_rate", "n_strong_nige", "popularity"]
def build(k):
    f = K + f"out/sh_all_{k.replace('/', '').replace('〜', '')}.pkl"
    if os.path.exists(f): return pd.read_pickle(f)
    p, d0, d1 = SRC[k]; d = pd.read_pickle(K + p); d = d[d.date.between(d0, d1) & (d.odds <= 300)].reset_index(drop=True)
    d["hit"] = (d.ret > 0).astype(float)
    Wn = d[d.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
    R = d.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
    R["lw"] = R.race_id.map(Wn).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
    R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R = R.set_index("race_id")
    d["flow"] = d.race_id.map(R.flow); d["n_prev"] = d.race_id.map(R.n_prev)
    q = 1 / d.odds; d["pn"] = q / q.groupby(d.race_id).transform("sum")
    s = d.loc[d.odds <= 30, KEEP].reset_index(drop=True); s.to_pickle(f); del d; gc.collect(); return s
def shape(d):
    a, b, c = d.r0_pos, d.r1_pos, d.r2_pos; s01, s12, s02 = d.s01 == 1, d.s12 == 1, d.s02 == 1
    sh = pd.Series("OTH", index=d.index)
    sh[s01 & s12 & (a == 0) & (b == 1) & (c == 2)] = "LO"
    sh[s01 & s12 & (a == 1) & (b == 0) & (c == 2)] = "UR"
    sh[s01 & ~s12 & ~s02 & (a == 0) & (b == 1)] = "AB"
    sh[s01 & ~s12 & ~s02 & (a == 1) & (b == 0)] = "BA"
    sh[s02 & ~s01 & ~s12 & (a == 0) & (c == 1)] = "AxB"
    sh[s02 & ~s01 & ~s12 & (a == 1) & (c == 0)] = "BxA"
    sh[s12 & ~s01 & ~s02 & (b == 0) & (c == 1)] = "XAB"
    sh[~s01 & ~s12 & ~s02] = "ALL3"
    return sh
P = {}
for k in SRC:
    P[k] = build(k); P[k]["sh"] = shape(P[k]); P[k]["yr"] = k; print(k, len(P[k]), flush=True)
rng = np.random.default_rng(0)
def cell(g):
    if len(g) < 50: return f"{len(g)}点"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (1000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    return f"{len(g):,}点・**{g.ret.mean():.0%}**（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}／" + "/".join(f"{g[g.yr == y].ret.mean():.0%}" if (g.yr == y).sum() else "—" for y in P) + "）"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def W(*a): print(*a, file=OUT, flush=True)
W("# 形ごとの小さな機械と期待値の線（確定オッズ30倍以下・4年の1年抜き＝学ばない年だけ。y6 は見ていない）" + NL)
W("かっこ内＝95%の範囲／年別 y4/2024年/2025〜/y5。期待値＝機械の見込み×倍率" + NL)
W("| 形 | 全部 | 対数損失の改善×1万 | 比≥1.2 | 期待値≥1.1 | 期待値≥1.2 | 期待値≥1.3 |" + NL + "|---|---|---|---|---|---|---|")
ALLH = []
for sh in ("LO", "UR", "AB", "BA", "AxB", "BxA", "XAB", "ALL3", "OTH"):
    Q = {k: d[d.sh == sh].reset_index(drop=True) for k, d in P.items()}; hs = []
    for k in Q:
        tr = pd.concat([Q[j] for j in Q if j != k], ignore_index=True)
        b = lo_fit(lo_feats(tr), tr.hit.to_numpy(), lo_lg(tr.pn).to_numpy(), 20.0)
        h = Q[k][["race_id", "date", "combo", "odds", "pn", "ret", "hit", "yr", "sh"]].copy(); h["ratio"] = lo_ratio(b, Q[k]); hs.append(h)
    H = pd.concat(hs, ignore_index=True); H["p"] = H.ratio * H.pn; H["ev"] = H.p * H.odds; ALLH.append(H)
    pm = np.clip(H.pn, 1e-6, 1 - 1e-6); pp = np.clip(H.p, 1e-6, 1 - 1e-6)
    dl = (-(H.hit * np.log(pp) + (1 - H.hit) * np.log(1 - pp)).mean() + (H.hit * np.log(pm) + (1 - H.hit) * np.log(1 - pm)).mean()) * 1e4
    W(f"| {sh} | {len(H):,}点・{H.ret.mean():.0%} | {dl:+.1f} | {cell(H[H.ratio >= 1.2])} | {cell(H[H.ev >= 1.1])} | {cell(H[H.ev >= 1.2])} | {cell(H[H.ev >= 1.3])} |")
A = pd.concat(ALLH, ignore_index=True); A.to_pickle(K + "out/sh_heldout.pkl")
W(f"| **全部の形まとめ** | {len(A):,}点・{A.ret.mean():.0%} | | {cell(A[A.ratio >= 1.2])} | {cell(A[A.ev >= 1.1])} | {cell(A[A.ev >= 1.2])} | {cell(A[A.ev >= 1.3])} |")
print("done")
