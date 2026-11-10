"""★事前登録「直前に縮んだ目」の判定（KNOWLEDGE.md 2026-11-11 1:50 の登録どおり。結果を見てから変えない）。
データ：本番DBのコピー out/live_db/keirin.sqlite（先に `gh release download db -p keirin.sqlite.gz -D out/live_db --clobber` → gunzip、または research/daily_forward.py）。
開催日（race_id の末尾8桁）が 20261110 以降・T10 と T1 がそろい・確定の払戻があるレース。1分前の倍率 200倍以下の3連単。
**1,000レースたまるまでは件数だけを出し、成績は出さない**（途中で結果を見ないため）。
使い方: python -I -X utf8 research/prereg_late_money.py reports/prereg_late_money.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10)
FIRST, CAP, CUT, NEED = "20261110", 200, 0.95, 1000
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
O = pd.read_sql("SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='3連単' AND phase IN ('T10','T1') AND odds > 0 ORDER BY fetched_at", con)  # 同じ組が何回か記録されても最後（新しい方）を取る
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
# 参考：縮み方の強さ別（200倍以下）
X2 = W[W.T1 <= CAP].copy(); q2 = 1 / X2.T1; X2["p1"] = q2 / q2.groupby(X2.race_id).transform("sum"); X2["mv"] = X2.T1 / X2.T10
P(NL + "## 参考：縮み方の強さ別（200倍以下）" + NL + "| 10分前→1分前 | 点数 | 当たり | 当たり÷見込み | 回収率 |" + NL + "|---|---|---|---|---|")
for nm, mm in (("15%以上縮んだ（0.85未満）", X2.mv < 0.85), ("5〜15%縮んだ（0.85〜0.95）", X2.mv.between(0.85, CUT, inclusive="left")), ("残り（0.95以上）", X2.mv >= CUT)):
    x = X2[mm]; P(f"| {nm} | {len(x):,} | {int(x.hit.sum())} | {x.hit.sum() / max(x.p1.sum(), 1e-9):.2f} | {x.ret.mean():.0%} |")
# 参考：本番の3連単の買い方（predictions の B3T 3連単枠・B3T のうち一番の目・B3X T枠）から縮んだ目を外すと
PR = pd.read_sql("SELECT race_id, phase, combo, reason FROM predictions WHERE bet_type='3連単' AND phase IN ('B3T','B3X')", con)
PR = PR[PR.race_id.str[-8:] >= FIRST].merge(W[["race_id", "combo", "T10", "T1", "ret"]], on=["race_id", "combo"], how="inner")
PR["sh"] = (PR.T1 / PR.T10) < CUT
P(NL + "## 参考：本番の3連単の買い方から縮んだ目を外すと（記録の目・確定の払戻）" + NL + "| 買い方 | 全部 | 縮んだ目 | 縮んだ目を外した残り |" + NL + "|---|---|---|---|")
for nm, g in (("3連単枠（B3T）", PR[PR.phase == "B3T"]), ("一番の目", PR[(PR.phase == "B3T") & PR.reason.fillna("").str.contains("一番の目")]), ("T枠（B3X）", PR[PR.phase == "B3X"])):
    f = lambda x: f"{x.ret.mean():.0%}（{len(x)}点・{int((x.ret > 0).sum())}本）" if len(x) else "−"
    P(f"| {nm} | {f(g)} | {f(g[g.sh])} | {f(g[~g.sh])} |")
print("races", nr, "judged", ok)
