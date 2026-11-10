"""★事前登録「直前に縮んだ目」の判定（KNOWLEDGE.md 2026-11-11 1:50 の登録どおり。結果を見てから変えない）。
データ：本番DBのコピー out/live_db/keirin.sqlite（先に `gh release download db -p keirin.sqlite.gz -D out/live_db --clobber` → gunzip、または research/daily_forward.py）。
開催日（race_id の末尾8桁）が 20261110 以降・T10 と T1 がそろい・確定の払戻があるレース。1分前の倍率 200倍以下の3連単。
**1,000レースたまるまでは件数だけを出し、成績は出さない**（途中で結果を見ないため）。
使い方: python -I -X utf8 research/prereg_late_money.py reports/prereg_late_money.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10)
FIRST, CAP, CUT, NEED = "20261110", 200, 0.95, 1000
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
O = pd.read_sql("SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='3連単' AND phase IN ('T10','T1') AND odds > 0", con)
O = O[O.race_id.str[-8:] >= FIRST]
W = O.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").dropna().reset_index()
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con)
PY = PY[PY.race_id.str[-8:] >= FIRST]
W = W[W.race_id.isin(set(PY.race_id))]
nr = W.race_id.nunique()
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# ★事前登録「直前に縮んだ目」の判定" + NL)
days = sorted(W.race_id.str[-8:].unique())
P(f"条件に合うレース：**{nr:,}R**（{days[0] if days else '−'}〜{days[-1] if days else '−'}、{len(days)}日）。判定は {NEED:,}R たまってから。" + NL)
if nr < NEED:
    P(f"まだ {NEED - nr:,}R 足りない。**成績は出さない**（登録どおり、判定前に結果を見ない）。")
    print("races", nr, "（判定前・成績は出さない）"); sys.exit(0)
W = W.merge(PY, on=["race_id", "combo"], how="left"); W["ret"] = W.payout.fillna(0) / 100; W["hit"] = (W.ret > 0).astype(float)
rng = np.random.default_rng(0)
def judge(cap, out_main):
    X = W[W.T1 <= cap].copy(); q = 1 / X.T1; X["p1"] = q / q.groupby(X.race_id).transform("sum"); X["sh"] = (X.T1 / X.T10) < CUT
    by = X.groupby(["race_id", "sh"]).agg(h=("hit", "sum"), e=("p1", "sum"), r=("ret", "sum"), n=("ret", "size")).unstack("sh", fill_value=0)
    h1, e1, h0, e0 = (by[(c, s)].to_numpy() for c, s in (("h", True), ("e", True), ("h", False), ("e", False)))
    ii = rng.integers(0, len(by), (4000, len(by)))
    ratio = (h1[ii].sum(1) / e1[ii].sum(1)) / (h0[ii].sum(1) / e0[ii].sum(1))
    est = (h1.sum() / e1.sum()) / (h0.sum() / e0.sum())
    s, r = X[X.sh], X[~X.sh]
    return dict(cap=cap, est=est, lo=np.percentile(ratio, 2.5), hi=np.percentile(ratio, 97.5), ns=len(s), nr_=len(r),
                hs=int(s.hit.sum()), hr=int(r.hit.sum()), aes=s.hit.sum() / s.p1.sum(), aer=r.hit.sum() / r.p1.sum(), rois=s.ret.mean(), roir=r.ret.mean())
m = judge(CAP, True)
ok = (m["hi"] < 1.0) and (m["rois"] < m["roir"])
P(f"## 判定：{'**合格**' if ok else '不合格'}" + NL)
P("| | 縮んだ目（0.95未満） | 残り（0.95以上） |" + NL + "|---|---|---|")
P(f"| 点数・当たり | {m['ns']:,}点・{m['hs']}本 | {m['nr_']:,}点・{m['hr']}本 |")
P(f"| 当たり÷見込み | {m['aes']:.2f} | {m['aer']:.2f} |")
P(f"| 回収率 | {m['rois']:.0%} | {m['roir']:.0%} |")
P(NL + f"比（縮んだ÷残り）＝ **{m['est']:.2f}**（95%の範囲 {m['lo']:.2f}〜{m['hi']:.2f}）。合格＝①範囲の上限が1.0未満 かつ ②縮んだ目の回収率が残りより低い" + NL)
P("## 参考（合否に使わない）：倍率の上限ごと" + NL + "| 上限 | 比 | 95%の範囲 | 縮んだ目の回収率 | 残りの回収率 |" + NL + "|---|---|---|---|---|")
for cap in (30, 50, 100, 300):
    x = judge(cap, False); P(f"| {cap}倍以下 | {x['est']:.2f} | {x['lo']:.2f}〜{x['hi']:.2f} | {x['rois']:.0%} | {x['roir']:.0%} |")
print("races", nr, "judged", ok)
