"""探す段階（Fable）：9車立てのライン順×最下位級の3着（Codex が見つけた候補の確かめ）。見た3期間だけ（y4・2024年＝2023/11/8〜2025/1/31・2025/2〜2026/11/5）。
ライン順（同じライン3人で先頭→番手→3番手）の全部（300倍以下）を out/lo_wide_<期間>.pkl に保存して使う（当日の流れ flow・n_prev、見込み pn つき）。
使い方: python -I -X utf8 research/lo_nine.py reports/lo_nine.md"""
import sys, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SRC = {"y4": "out/y4/cache.pkl", "2024年": "out/y2024full/cache.pkl", "2025/2〜": "out/angle_base.pkl"}
def build(nm):
    f = K + f"out/lo_wide_{nm.replace('/', '').replace('〜', '')}.pkl"
    if os.path.exists(f): return pd.read_pickle(f)
    d = pd.read_pickle(K + SRC[nm]); d = d[d.odds <= 300]
    if nm == "2025/2〜": d = d[d.date <= "20261105"]
    q = 1 / d.odds; d = d.assign(pn=q / q.groupby(d.race_id).transform("sum"), hit=(d.ret > 0).astype(float))
    W = d[d.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
    R = d.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
    R["lw"] = R.race_id.map(W).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
    R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan)
    d["flow"] = d.race_id.map(R.set_index("race_id").flow); d["n_prev"] = d.race_id.map(R.set_index("race_id").n_prev)
    s = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2)].copy(); s.to_pickle(f); return s
PER = {nm: build(nm) for nm in SRC}; ALL = pd.concat(PER.values())
rng = np.random.default_rng(0)
def cell(g, ci=False):
    if len(g) < 30: return f"{len(g)}（少）"
    t = f"{len(g):,}・{int(g.hit.sum())}本・{g.hit.sum() / g.pn.sum():.2f}・**{g.ret.mean():.0%}**"
    if ci:
        by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
        ii = rng.integers(0, len(by), (2000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1); t += f"（{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）"
    return t
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
def table(title, rows):
    P(f"## {title}" + NL + "| 区分 | " + " | ".join(PER) + " | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    for nm, m in rows: P(f"| {nm} | " + " | ".join(cell(d[m(d)]) for d in PER.values()) + f" | {cell(ALL[m(ALL)], True)} |")
    P("")
P("# 探す段階：9車立てのライン順×最下位級の3着（各セル：点数・当たり・当たり÷見込み・回収率）" + NL)
nine = lambda d: d.entries_number >= 9
bands = [("〜10倍", 0, 10), ("10〜20倍", 10, 20), ("20〜30倍", 20, 30), ("30〜50倍", 30, 50), ("50〜100倍", 50, 100)]
table("9車 × 3着の得点順位7位以下 × 倍率の帯", [(b, (lambda d, lo=lo, hi=hi: nine(d) & (d.r2_pt_rank >= 7) & (d.odds > lo) & (d.odds <= hi))) for b, lo, hi in bands])
table("9車 × 3着の得点順位5〜6位 × 倍率の帯（比べる）", [(b, (lambda d, lo=lo, hi=hi: nine(d) & d.r2_pt_rank.between(5, 6) & (d.odds > lo) & (d.odds <= hi))) for b, lo, hi in bands])
table("9車 × 3着の得点順位1〜4位 × 倍率の帯（比べる）", [(b, (lambda d, lo=lo, hi=hi: nine(d) & (d.r2_pt_rank <= 4) & (d.odds > lo) & (d.odds <= hi))) for b, lo, hi in bands])
table("9車 × 20倍以下 × 3着の得点順位ごと", [(f"{k}位", (lambda d, k=k: nine(d) & (d.r2_pt_rank == k) & (d.odds <= 20))) for k in range(3, 10)])
table("7車以下 × 3着7位以下 × 倍率の帯（比べる）", [(b, (lambda d, lo=lo, hi=hi: ~nine(d) & (d.r2_pt_rank >= 7) & (d.odds > lo) & (d.odds <= hi))) for b, lo, hi in bands])
table("まとめの形", [
    ("9車 × 3着7位以下 × 20倍以下", lambda d: nine(d) & (d.r2_pt_rank >= 7) & (d.odds <= 20)),
    ("9車 × 3着7位以下 × 30倍以下", lambda d: nine(d) & (d.r2_pt_rank >= 7) & (d.odds <= 30)),
    ("9車 × 3着7位以下 × 20倍以下 × 一番の目を除く", lambda d: nine(d) & (d.r2_pt_rank >= 7) & (d.odds <= 20) & ~d.is_top),
    ("9車 × 3着7位以下 × 20倍以下 × G戦", lambda d: nine(d) & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.G == 1)),
    ("9車 × 3着7位以下 × 20倍以下 × F戦", lambda d: nine(d) & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.G != 1)),
    ("9車 × 3着7位以下 × 20倍以下 × 前半（各期間の日付で2等分）", lambda d: nine(d) & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.date <= d.date.sort_values().iloc[len(d) // 2])),
    ("L1（全部の車立て・10倍以下）＋9車の10〜20倍", lambda d: (d.r2_pt_rank >= 7) & ((d.odds <= 10) | (nine(d) & (d.odds <= 20)))),
])
print("done")
