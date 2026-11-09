"""② 買うレースの絞り込み：機械v2が「市場とはっきり違う」と言うレースだけを買う（ポーカーの「勝てる卓だけに座る」）。
自信の測り方：レースの中で、機械の見込み（pmod）と市場の見込み（pm）がどれだけ違うか（KL距離）と、そのレースの最大の期待値。
境目は止めどころ（2026/6/16〜8/31）だけで決め、③・⑥は最後に1回だけ見る。使い方: python -I -X utf8 research/race_select.py 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
D = pd.read_pickle(K + "out/meta_pred_v2.pkl")
per = np.select([D.date.between("20251012", "20260114"), D.date >= "20260901", (D.date > "20260615") & (D.date <= "20260831")], ["③", "⑥", "止"], "学習")
D["per"] = per; D = D[D.per != "学習"].copy()
D["pmn"] = D.pmod / D.groupby("race_id").pmod.transform("sum")
D["kl_i"] = D.pmn * np.log(D.pmn / D.pm)
R = D.groupby("race_id").agg(kl=("kl_i", "sum"), evmax=("ev", "max"), per=("per", "first"))
D = D.join(R[["kl", "evmax"]], on="race_id")
rng = np.random.default_rng(0)
def cell(x):
    if len(x) < 20: return f"−（{len(x)}点）"
    by = x.groupby("race_id").ret.agg(["sum", "size"]); w = rng.dirichlet(np.ones(len(by)), 3000); post = (w @ by["sum"].to_numpy()) / (w @ by["size"].to_numpy())
    r = x.ret; t_ = (r.mean() - 1) / (r.std() / np.sqrt(len(r)))
    return f"**{r.mean():.0%}**（{len(x)}点・{x.race_id.nunique()}R・t={t_:+.1f}・P>100% {(post > 1).mean():.0%}）"
P("# ② 買うレースの絞り込み（機械v2の自信が高いレースだけ）" + NL)
P("自信＝レース内で機械と市場の見込みがどれだけ違うか（KL距離）。上位◯%＝止めどころのレースで測った境目。" + NL)
va = R[R.per == "止"]
P("| 絞り方 | 買う目 | 止めどころ | ③ | ⑥ |" + NL + "|---|---|---|---|---|")
for q_ in (1.0, 0.5, 0.3, 0.2, 0.1):
    th = va.kl.quantile(1 - q_) if q_ < 1 else -1
    for lab, fn in (("期待値≥1.0", lambda x: x[x.ev >= 1.0]), ("期待値≥1.1", lambda x: x[x.ev >= 1.1]), ("レースで期待値最大の1点（≥1.0）", lambda x: x[x.ev >= 1.0].sort_values("ev", ascending=False).groupby("race_id").head(1)),
                    ("一番の目", lambda x: x[x.is_top]), ("一番の目×期待値≥1.0", lambda x: x[x.is_top & (x.ev >= 1.0)])):
        cells = [cell(fn(D[(D.per == k) & (D.kl >= th)])) for k in ("止", "③", "⑥")]
        P(f"| 自信 上位{int(q_ * 100)}% | {lab} | " + " | ".join(cells) + " |")
P(NL + "## 期待値の最大で絞る（レースの最大期待値が◯以上のレースだけ）" + NL + NL + "| 絞り方 | 買う目 | 止めどころ | ③ | ⑥ |" + NL + "|---|---|---|---|---|")
for th in (1.2, 1.4, 1.6):
    for lab, fn in (("期待値≥1.1", lambda x: x[x.ev >= 1.1]), ("一番の目", lambda x: x[x.is_top])):
        P(f"| レースの最大期待値≥{th} | {lab} | " + " | ".join(cell(fn(D[(D.per == k) & (D.evmax >= th)])) for k in ("止", "③", "⑥")) + " |")
print("done")
