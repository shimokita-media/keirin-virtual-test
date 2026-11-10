"""★事前登録「券種の先行」の判定（KNOWLEDGE.md 2026-11-11 3:25 の登録どおり。結果を見てから変えない）。
本番DBのコピー out/live_db/keirin.sqlite。開催日（race_id の末尾8桁）20261110 以降、3連単・2車単・3連複の T5・T1 がそろい、確定の払戻があるレース。1分前の3連単30倍以下の目。
lead＝mean(log 2車単の同じ1-2着の見込み T1/T5, log 3連複の同じ3人の見込み T1/T5) − log 3連単の目の見込み T1/T5。当てはまる目＝lead≧0.08。
**1,000レースたまるまでは件数だけを出し、成績は出さない**。
使い方: python -I -X utf8 research/prereg_leadlag.py reports/prereg_leadlag.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10); FIRST, CAP, CAP3, CUT, NEED = "20261110", 30, 200, 0.08, 1000
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
def load(bt):
    o = pd.read_sql(f"SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='{bt}' AND phase IN ('T5','T1') AND odds > 0 ORDER BY fetched_at", con)
    o = o[o.race_id.str[-8:] >= FIRST]
    w = o.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").reset_index().dropna(subset=["T5", "T1"])
    if bt == "3連単": w = w[w.T1 <= CAP3].copy()
    for p in ("T5", "T1"): q = 1 / w[p]; w["p_" + p] = q / q.groupby(w.race_id).transform("sum")
    return w
T = load("3連単"); EX = load("2車単"); TF = load("3連複")
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con); PY = PY[PY.race_id.str[-8:] >= FIRST]
ok_r = set(PY.race_id) & set(EX.race_id) & set(TF.race_id); T = T[T.race_id.isin(ok_r)]
nr = T.race_id.nunique(); days = sorted(T.race_id.str[-8:].unique())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# ★事前登録「券種の先行」の判定" + NL)
P(f"条件に合うレース：**{nr:,}R**（{days[0] if days else '−'}〜{days[-1] if days else '−'}、{len(days)}日）。判定は {NEED:,}R たまってから。" + NL)
if nr < NEED:
    P(f"まだ {NEED - nr:,}R 足りない。**成績は出さない**（登録どおり、判定前に結果を見ない）。"); print("races", nr, "（判定前・成績は出さない）"); sys.exit(0)
T = T.merge(PY, on=["race_id", "combo"], how="left"); T["ret"] = T.payout.fillna(0) / 100; T["hit"] = (T.ret > 0).astype(float)
cb = T.combo.str.split("-", expand=True).astype(int)
T["ex_key"] = cb[0].astype(str) + "-" + cb[1].astype(str); T["tf_key"] = ["-".join(map(str, sorted(r))) for r in cb.to_numpy()]
EX["d_ex"] = np.log(EX.p_T1 / EX.p_T5); TF["d_tf"] = np.log(TF.p_T1 / TF.p_T5)
T = T.merge(EX[["race_id", "combo", "d_ex"]].rename(columns={"combo": "ex_key"}), on=["race_id", "ex_key"], how="left")
T = T.merge(TF[["race_id", "combo", "d_tf"]].rename(columns={"combo": "tf_key"}), on=["race_id", "tf_key"], how="left")
T["lead"] = T[["d_ex", "d_tf"]].mean(axis=1) - np.log(T.p_T1 / T.p_T5)
q1 = 1 / T.T1; T["p1"] = q1 / q1.groupby(T.race_id).transform("sum")
T = T[T.lead.notna()].copy(); T["on"] = T.lead >= CUT
rng = np.random.default_rng(0)
def judge(X):
    by = X.groupby(["race_id", "on"]).agg(h=("hit", "sum"), e=("p1", "sum")).unstack("on", fill_value=0)
    h1, e1, h0, e0 = (by[(c, s)].to_numpy() for c, s in (("h", True), ("e", True), ("h", False), ("e", False)))
    ii = rng.integers(0, len(by), (4000, len(by))); ratio = (h1[ii].sum(1) / e1[ii].sum(1)) / (h0[ii].sum(1) / e0[ii].sum(1))
    return (h1.sum() / e1.sum()) / (h0.sum() / e0.sum()), np.percentile(ratio, 2.5), np.percentile(ratio, 97.5)
X = T[T.T1 <= CAP]; est, lo, hi = judge(X); s, r = X[X.on], X[~X.on]
ok = (lo > 1.0) and (s.ret.mean() > r.ret.mean())
P(f"## 判定：{'**合格**' if ok else '不合格'}" + NL + "| | 当てはまる目（lead≧0.08） | 残り |" + NL + "|---|---|---|")
P(f"| 点数・当たり | {len(s):,}点・{int(s.hit.sum())}本 | {len(r):,}点・{int(r.hit.sum())}本 |")
P(f"| 当たり÷見込み | {s.hit.sum() / s.p1.sum():.2f} | {r.hit.sum() / r.p1.sum():.2f} |")
P(f"| 回収率 | {s.ret.mean():.0%} | {r.ret.mean():.0%} |")
P(NL + f"比＝ **{est:.2f}**（95%の範囲 {lo:.2f}〜{hi:.2f}）。合格＝①範囲の下限が1.0より大きい かつ ②当てはまる目の回収率が残りより高い" + NL)
e2, l2, h2 = judge(T); P(f"参考：200倍以下での比 {e2:.2f}（{l2:.2f}〜{h2:.2f}）")
print("races", nr, "judged", ok)
