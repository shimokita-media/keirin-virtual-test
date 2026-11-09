"""切り口（構造の違う②）：締切前の倍率の動き（遅いお金）。締切10分前→1分前で倍率が縮んだ目（直前にお金が入った目）は、1分前の倍率から見込むより当たるか。
データ：GitHub Actions の本番DB（リリース db → out/live_db/keirin.sqlite、読み取り専用）の 11/6〜 スナップショット T10/T5/T1 と確定払戻。
1分前の倍率で買っても払戻は最終倍率なので、回収率は確定の払戻で計算。レース数が少ない（約160R）ので傾向を見るだけ。"""
import sys, sqlite3, numpy as np, pandas as pd
DB = "C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite"
con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
O = pd.read_sql("SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='3連単' AND phase IN ('T10','T5','T1') AND substr(race_id,-8) >= '20261106'", con)
W = O.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").dropna().reset_index()
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con)
W = W.merge(PY, on=["race_id", "combo"], how="left"); W["ret"] = W.payout.fillna(0) / 100
W = W[W.race_id.isin(set(PY.race_id))]
W = W[(W.T1 > 0) & (W.T1 <= 300)].copy()
W["mv"] = W.T1 / W.T10; W["mv5"] = W.T1 / W.T5
q = 1 / W.T1; W["p1"] = q / q.groupby(W.race_id).transform("sum"); W["hit"] = (W.ret > 0).astype(float)
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 切り口：締切前の倍率の動き（10分前→1分前）\n")
P(f"{W.race_id.nunique()}レース・{len(W):,}点（1分前で300倍以下の3連単）。当たり {int(W.hit.sum())}本。回収率は確定の払戻、見込みは1分前の倍率から。\n")
bins = [0, 0.7, 0.85, 0.95, 1.05, 1.2, 99]; labs = ["30%以上縮んだ", "15〜30%縮んだ", "5〜15%縮んだ", "ほぼ変わらず", "5〜20%伸びた", "20%以上伸びた"]
W["b"] = pd.cut(W.mv, bins, labels=labs)
P("| 10分前→1分前 | 点数 | 当たり | 回収率 | 実際の当たり÷1分前の見込み | 1分前→最終の倍率（当たり目の中央値） |\n|---|---|---|---|---|---|")
POST = pd.read_sql("SELECT race_id, combo, odds AS fin FROM odds WHERE bet_type='3連単' AND phase='POST' AND substr(race_id,-8) >= '20261106'", con)
POST = POST.drop_duplicates(["race_id", "combo"], keep="last")  # POST は何回か記録されているので最後の1つだけ
W = W.merge(POST, on=["race_id", "combo"], how="left")
for k, x in W.groupby("b", observed=True):
    h = x[x.hit > 0]
    P(f"| {k} | {len(x):,} | {int(x.hit.sum())} | {x.ret.mean():.0%} | {x.hit.sum() / x.p1.sum():.2f} | {(h.fin / h.T1).median():.2f} |" if len(h) else f"| {k} | {len(x):,} | 0 | {x.ret.mean():.0%} | {x.hit.sum() / x.p1.sum():.2f} | − |")
P("\n## 人気どころ（1分前30倍以下）だけ\n")
P("| 10分前→1分前 | 点数 | 当たり | 回収率 | 実際÷見込み |\n|---|---|---|---|---|")
for k, x in W[W.T1 <= 30].groupby("b", observed=True):
    P(f"| {k} | {len(x):,} | {int(x.hit.sum())} | {x.ret.mean():.0%} | {x.hit.sum() / max(x.p1.sum(), 1e-9):.2f} |")
P("\n## 5分前→1分前の動き（もっと直前）\n")
W["b5"] = pd.cut(W.mv5, [0, 0.85, 0.95, 1.05, 1.15, 99], labels=["15%以上縮んだ", "5〜15%縮んだ", "ほぼ変わらず", "5〜15%伸びた", "15%以上伸びた"])
P("| 5分前→1分前 | 点数 | 当たり | 回収率 | 実際÷見込み |\n|---|---|---|---|---|")
for k, x in W.groupby("b5", observed=True):
    P(f"| {k} | {len(x):,} | {int(x.hit.sum())} | {x.ret.mean():.0%} | {x.hit.sum() / x.p1.sum():.2f} |")
r = np.corrcoef(np.log(W.mv), W.hit - W.p1)[0, 1]
P(f"\n- 倍率の動き（log）と「当たり−見込み」の相関：{r:.4f}（負なら、縮んだ目ほど見込み以上に当たる）")
print("races", W.race_id.nunique(), "corr", r)
