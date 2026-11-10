"""探す段階：締切10分前→1分前に倍率が「伸びた」3連単（直前に売れなかった目）を、1分前の倍率の上限ごとに見る。
**使うのは 11/9 までのレースだけ**（race_id の末尾8桁＝開催日で絞る。11/10 以降は事前登録の判定用に見ない）。
データ：本番DBのコピー out/live_db/keirin.sqlite（T10・T1 のスナップショット、確定の払戻）。回収率は確定の払戻、各100円。
使い方: python -I -X utf8 research/late_money_explore.py reports/late_money_explore.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10)
LAST = "20261109"
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
O = pd.read_sql("SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='3連単' AND phase IN ('T10','T1') AND odds > 0", con)
O = O[O.race_id.str[-8:] <= LAST]
W = O.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").dropna().reset_index()
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con)
PY = PY[PY.race_id.str[-8:] <= LAST]
W = W[W.race_id.isin(set(PY.race_id))].merge(PY, on=["race_id", "combo"], how="left")
W["ret"] = W.payout.fillna(0) / 100; W["hit"] = (W.ret > 0).astype(float)
W = W[W.T1 <= 300].copy()
q = 1 / W.T1; W["p1"] = q / q.groupby(W.race_id).transform("sum")
W["mv"] = W.T1 / W.T10
rng = np.random.default_rng(0)
def st(g):
    if len(g) < 2: return None
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    w = rng.dirichlet(np.ones(len(by)), 4000); post = (w @ s) / (w @ n)
    sd = g.ret.std()
    return dict(n=len(g), r=g.race_id.nunique(), h=int(g.hit.sum()), roi=g.ret.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5),
                sd=sd, t=(g.ret.mean() - 1) / (sd / np.sqrt(len(g))) if sd > 0 else np.nan, ae=g.hit.sum() / g.p1.sum(), pp=(post > 1).mean())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 探す段階：締切10分前→1分前に倍率が伸びた3連単（11/9 までのレースだけ）" + NL)
P(f"{W.race_id.str[-8:].min()}〜{W.race_id.str[-8:].max()}・{W.race_id.nunique()}レース・{len(W):,}点（1分前で300倍以下）。当たり {int(W.hit.sum())}本。"
  "動き＝1分前の倍率÷10分前の倍率（1.05以上＝5%以上伸びた）。見込み＝1分前の倍率から。確定の払戻・各100円。**11/10 以降は見ていない**" + NL)
moves = [("縮んだ（0.95未満）", W.mv < 0.95), ("ほぼ変わらず（0.95〜1.05）", W.mv.between(0.95, 1.05, inclusive="left")),
         ("5%以上伸びた（1.05以上）", W.mv >= 1.05), ("10%以上伸びた（1.10以上）", W.mv >= 1.10), ("20%以上伸びた（1.20以上）", W.mv >= 1.20)]
P("| 1分前の倍率 | 10分前→1分前 | レース | 点数 | 当たり | 回収率 | 95%の範囲 | t | 当たり÷見込み | P(>100%) |" + NL + "|---|---|---|---|---|---|---|---|---|---|")
for cap in (30, 50, 100, 200, 300):
    for nm, m in moves:
        s = st(W[(W.T1 <= cap) & m])
        if s is None: continue
        P(f"| {cap}倍以下 | {nm} | {s['r']} | {s['n']:,} | {s['h']} | **{s['roi']:.0%}** | {s['lo']:.0%}〜{s['hi']:.0%} | {s['t']:+.2f} | {s['ae']:.2f} | {s['pp']:.0%} |")
P(NL + "## 日ごと（200倍以下 × 5%以上伸びた）" + NL)
g = W[(W.T1 <= 200) & (W.mv >= 1.05)]
P("| 日 | レース | 点数 | 当たり | 回収率 |" + NL + "|---|---|---|---|---|")
for d, x in g.groupby(g.race_id.str[-8:]):
    P(f"| {d} | {x.race_id.nunique()} | {len(x):,} | {int(x.hit.sum())} | {x.ret.mean():.0%} |")
P(NL + "## 1レースあたりの点数（200倍以下 × 5%以上伸びた）" + NL)
c = g.groupby("race_id").size()
P(f"平均 {c.mean():.1f}点、中央値 {c.median():.0f}点、最大 {c.max()}点（各100円なら1レース平均 {c.mean() * 100:,.0f}円）")
print("races", W.race_id.nunique(), "rows", len(W))
