"""探す段階（Fable）：lo_factors.py で3期間とも110%超だった3条件（当日の流れが弱い・3連複から見て割安・3日目以降）が本物かを確かめる。
①段階があるか（当日の流れを細かく）②ライン順の本命の目全体（3着の順位を問わない）でも同じ向きか ③条件を重ねたときの回収率と95%の範囲。
ライン順×15倍以下の全部を out/lo_all_<期間>.pkl に保存して使う。見た3期間だけ（y5・y6 は見ない）。
使い方: python -I -X utf8 research/lo_drill2.py reports/lo_drill2.md"""
import sys, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SRC = {"y4": "out/y4/cache.pkl", "2024年": "out/y2024full/cache.pkl", "2025/2〜": "out/angle_base.pkl"}
def build(nm):
    f = K + f"out/lo_all_{nm.replace('/', '').replace('〜', '')}.pkl"
    if os.path.exists(f): return pd.read_pickle(f)
    d = pd.read_pickle(K + SRC[nm]); d = d[d.odds <= 300]
    if nm == "2025/2〜": d = d[d.date <= "20261105"]
    q = 1 / d.odds; d = d.assign(pn=q / q.groupby(d.race_id).transform("sum"), hit=(d.ret > 0).astype(float))
    W = d[d.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
    R = d.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
    R["lw"] = R.race_id.map(W).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
    R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan)
    d["flow"] = d.race_id.map(R.set_index("race_id").flow); d["n_prev"] = d.race_id.map(R.set_index("race_id").n_prev)
    s = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy()
    s.to_pickle(f); return s
PER = {nm: build(nm) for nm in SRC}
ALL = pd.concat(PER.values())
rng = np.random.default_rng(0)
def ci(g):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (2000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1); return np.percentile(bs, 2.5), np.percentile(bs, 97.5)
def cell(g, with_ci=False):
    if len(g) < 40: return f"{len(g)}（少）"
    t = f"{len(g):,}・{int(g.hit.sum())}本・{g.hit.sum() / g.pn.sum():.2f}・**{g.ret.mean():.0%}**"
    if with_ci: lo, hi = ci(g); t += f"（{lo:.0%}〜{hi:.0%}）"
    return t
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
def table(title, rows, with_ci=False):
    P(f"## {title}" + NL + "| 区分 | " + " | ".join(PER) + " | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    for nm, m in rows: P(f"| {nm} | " + " | ".join(cell(d[m(d)], False) for d in PER.values()) + f" | {cell(ALL[m(ALL)], True)} |")
    P("")
P("# 探す段階：ライン順の本命の目で効く条件の確かめ（各セル：点数・当たり・当たり÷見込み・回収率）" + NL)
w7 = lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 10)
fl = lambda d, lo, hi: (d.n_prev >= 1) & (d.flow >= lo) & (d.flow < hi)
table("① 当日の流れを細かく（ライン順×3着7位以下×10倍以下。その日のそれまでのレースで先頭が勝った割合）", [
    ("その日の最初のレース（流れなし）", lambda d: w7(d) & (d.n_prev == 0)),
    ("0%（先頭が1回も勝っていない）", lambda d: w7(d) & (d.n_prev >= 1) & (d.flow == 0)),
    ("0%超〜30%", lambda d: w7(d) & (d.n_prev >= 1) & (d.flow > 0) & (d.flow <= 0.3)),
    ("30%超〜50%", lambda d: w7(d) & (d.n_prev >= 1) & (d.flow > 0.3) & (d.flow <= 0.5)),
    ("50%超〜70%", lambda d: w7(d) & (d.n_prev >= 1) & (d.flow > 0.5) & (d.flow <= 0.7)),
    ("70%超", lambda d: w7(d) & (d.n_prev >= 1) & (d.flow > 0.7)),
    ("30%以下 × 前のレースが3つ以上", lambda d: w7(d) & (d.n_prev >= 3) & (d.flow <= 0.3)),
    ("30%以下 × 前のレースが1〜2つ", lambda d: w7(d) & (d.n_prev.between(1, 2)) & (d.flow <= 0.3)),
])
lowf = lambda d: (d.n_prev >= 1) & (d.flow <= 0.3)
table("② ライン順×10倍以下の全体でも同じ向きか（3着の得点順位ごと）", [
    ("3着1〜4位 × 流れ30%以下", lambda d: (d.r2_pt_rank <= 4) & (d.odds <= 10) & lowf(d)),
    ("3着1〜4位 × それ以外", lambda d: (d.r2_pt_rank <= 4) & (d.odds <= 10) & ~lowf(d)),
    ("3着5〜6位 × 流れ30%以下", lambda d: d.r2_pt_rank.between(5, 6) & (d.odds <= 10) & lowf(d)),
    ("3着5〜6位 × それ以外", lambda d: d.r2_pt_rank.between(5, 6) & (d.odds <= 10) & ~lowf(d)),
    ("3着7位以下 × 流れ30%以下", lambda d: w7(d) & lowf(d)),
    ("3着7位以下 × それ以外", lambda d: w7(d) & ~lowf(d)),
    ("3着1〜4位 × 3連複から見て割安", lambda d: (d.r2_pt_rank <= 4) & (d.odds <= 10) & (d.g_tf > 0)),
    ("3着1〜4位 × それ以外", lambda d: (d.r2_pt_rank <= 4) & (d.odds <= 10) & ~(d.g_tf > 0)),
    ("3着5〜6位 × 3連複から見て割安", lambda d: d.r2_pt_rank.between(5, 6) & (d.odds <= 10) & (d.g_tf > 0)),
    ("3着5〜6位 × それ以外", lambda d: d.r2_pt_rank.between(5, 6) & (d.odds <= 10) & ~(d.g_tf > 0)),
    ("3着7位以下 × 3連複から見て割安", lambda d: w7(d) & (d.g_tf > 0)),
    ("3着7位以下 × それ以外", lambda d: w7(d) & ~(d.g_tf > 0)),
])
table("③ 3連複から見た割安さの段階（ライン順×3着7位以下×10倍以下。g_tf＝3連複の見込み÷3連単の同じ3人の見込み−1）", [
    ("g_tf −5%未満", lambda d: w7(d) & (d.g_tf < -0.05)), ("−5%〜0%", lambda d: w7(d) & (d.g_tf >= -0.05) & (d.g_tf <= 0)),
    ("0%〜+5%", lambda d: w7(d) & (d.g_tf > 0) & (d.g_tf <= 0.05)), ("+5%〜+10%", lambda d: w7(d) & (d.g_tf > 0.05) & (d.g_tf <= 0.10)), ("+10%超", lambda d: w7(d) & (d.g_tf > 0.10)),
])
A, B_, C = (lambda d: d.g_tf > 0), lowf, (lambda d: d.day_index >= 3)
table("④ 条件を重ねる（ライン順×3着7位以下×10倍以下）", [
    ("全部", w7), ("3連複から見て割安", lambda d: w7(d) & A(d)), ("流れ30%以下", lambda d: w7(d) & B_(d)), ("3日目以降", lambda d: w7(d) & C(d)),
    ("割安 かつ 流れ30%以下", lambda d: w7(d) & A(d) & B_(d)), ("割安 または 流れ30%以下", lambda d: w7(d) & (A(d) | B_(d))),
    ("3つのうち1つ以上", lambda d: w7(d) & (A(d) | B_(d) | C(d))), ("3つのうち2つ以上", lambda d: w7(d) & ((A(d).astype(int) + B_(d).astype(int) + C(d).astype(int)) >= 2)),
    ("どれにも当たらない", lambda d: w7(d) & ~(A(d) | B_(d) | C(d))),
    ("15倍以下に広げて：割安 または 流れ30%以下", lambda d: (d.r2_pt_rank >= 7) & (A(d) | B_(d))),
])
print("done")
