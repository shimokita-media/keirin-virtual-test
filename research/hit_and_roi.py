"""的中率と回収率を「両方ほどほど」に保つ選び方（機械v2）。当たる確率（pmod）の下限 × 期待値（pmod×倍率）の下限 の格子で調べる。
選ぶのは止めどころ（2026/6/16〜8/31）だけ。③・⑥は最後に見る。T（10倍以下×G戦か9車×3着得点5位以下）も並べる。
使い方: python -I -X utf8 research/hit_and_roi.py 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
D = pd.read_pickle(K + "out/meta_pred_v2.pkl")
D["per"] = np.select([D.date.between("20251012", "20260114"), D.date >= "20260901", (D.date > "20260615") & (D.date <= "20260831")], ["③", "⑥", "止"], "学習")
D = D[D.per != "学習"].copy()
B = pd.read_pickle(K + "out/angle_base.pkl")[["race_id", "combo", "G", "entries_number", "r2_pt_rank"]]
D = D.merge(B, on=["race_id", "combo"], how="left")
D["T"] = (D.odds <= 10) & ((D.G == 1) | (D.entries_number >= 9)) & (D.r2_pt_rank >= 5)
rng = np.random.default_rng(0)
def stats(x):
    if len(x) < 30: return None
    by = x.groupby("race_id").ret.agg(["sum", "size"]); w = rng.dirichlet(np.ones(len(by)), 2000); post = (w @ by["sum"].to_numpy()) / (w @ by["size"].to_numpy())
    r = x.ret; return dict(n=len(x), hit=(r > 0).mean(), roi=r.mean(), t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))), pp=(post > 1).mean(), sd=r.std(), days=x.date.nunique())
grid = []
for pmin in (0.0, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20):
    for emin in (0.9, 1.0, 1.05, 1.1, 1.2):
        s = stats(D[(D.per == "止") & (D.pmod >= pmin) & (D.ev >= emin)])
        if s: grid.append((pmin, emin, s))
P("# 的中率と回収率を両方ほどほどに保つ選び方（機械v2）" + NL)
P("当たる確率＝機械v2の見込み（pmod）、期待値＝pmod×最終倍率。各100円・最終オッズ。" + NL)
P("## 1. 止めどころでの格子（ここで選ぶ）" + NL + NL + "| 当たる確率の下限 | 期待値の下限 | 点数 | 1日あたり | 的中率 | 回収率 | 標準偏差 | t | P>100% |" + NL + "|---|---|---|---|---|---|---|---|---|")
for pmin, emin, s in grid:
    P(f"| {pmin:.0%} | {emin} | {s['n']} | {s['n'] / s['days']:.1f} | {s['hit']:.1%} | {s['roi']:.0%} | {s['sd']:.2f} | {s['t']:+.1f} | {s['pp']:.0%} |")
# 止めどころで「的中率10%以上・回収率100%以上・P>100% 60%以上」を満たす中で点数が最も多いもの
ok = [(p, e, s) for p, e, s in grid if s["hit"] >= 0.10 and s["roi"] >= 1.0 and s["pp"] >= 0.6]
P(NL + "## 2. 止めどころで「的中率10%以上・回収率100%以上・P>100% 60%以上」を満たした組み合わせを、③・⑥で確認" + NL)
if ok:
    P("| 当たる確率の下限 | 期待値の下限 | 止めどころ | ③ | ⑥ |" + NL + "|---|---|---|---|---|")
    fmt = lambda s: f"的中{s['hit']:.0%}・回収{s['roi']:.0%}（{s['n']}点・1日{s['n'] / s['days']:.1f}点・t={s['t']:+.1f}・P>100% {s['pp']:.0%}）" if s else "−"
    for p, e, s in ok:
        P(f"| {p:.0%} | {e} | {fmt(s)} | {fmt(stats(D[(D.per == '③') & (D.pmod >= p) & (D.ev >= e)]))} | {fmt(stats(D[(D.per == '⑥') & (D.pmod >= p) & (D.ev >= e)]))} |")
else:
    P("- 満たす組み合わせなし")
fmt2 = lambda s: f"的中{s['hit']:.0%}・回収{s['roi']:.0%}（{s['n']}点・1日{s['n'] / s['days']:.1f}点・t={s['t']:+.1f}・P>100% {s['pp']:.0%}）" if s else "−"
P(NL + "## 3. 比べるもの" + NL + NL + "| 買い方 | 止めどころ | ③ | ⑥ |" + NL + "|---|---|---|---|")
for nm, m in (("T", D["T"]), ("T×期待値≥1.0", D["T"] & (D.ev >= 1.0)), ("一番の目", D.is_top), ("10倍以下×期待値≥1.0", (D.odds <= 10) & (D.ev >= 1.0)), ("20倍以下×期待値≥1.05", (D.odds <= 20) & (D.ev >= 1.05))):
    P(f"| {nm} | " + " | ".join(fmt2(stats(D[(D.per == k) & m])) for k in ("止", "③", "⑥")) + " |")
print("done")
