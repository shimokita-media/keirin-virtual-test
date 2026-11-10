"""探す段階：券種どうしの動きの時間差（先に2車単・3連複にお金が入った目は、最後の1分に3連単でも縮むか・当たるか）。
**11/9 までのレースだけ**（race_id の末尾8桁）。本番DBのコピー out/live_db/keirin.sqlite の T5・T1・POST。確定の払戻。
合図 lead＝（2車単の同じ1-2着の見込みの変化）＋（3連複の同じ3人の見込みの変化）の平均 − 3連単の目自体の見込みの変化。変化＝log(T1の見込み ÷ T5の見込み)。見込み＝1/倍率をレースの中で合計1にそろえたもの。
目的：lead が大きい目ほど、最後の1分（T1→POST）に3連単が縮むか、1分前の見込みより当たるか。
使い方: python -I -X utf8 research/leadlag_explore.py reports/leadlag_explore.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10); LAST = "20261109"
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
def load(bt, phases):
    o = pd.read_sql(f"SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='{bt}' AND phase IN ({','.join(repr(p) for p in phases)}) AND odds > 0 ORDER BY fetched_at", con)
    o = o[o.race_id.str[-8:].between("20261107", LAST)]
    w = o.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").reset_index()
    for p in phases:
        if p in w: q = 1 / w[p]; w["p_" + p] = q / q.groupby(w.race_id).transform("sum")
    return w
T = load("3連単", ["T5", "T1", "POST"]).dropna(subset=["T5", "T1", "POST"])
EX = load("2車単", ["T5", "T1"]).dropna(subset=["T5", "T1"]); TF = load("3連複", ["T5", "T1"]).dropna(subset=["T5", "T1"])
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con)
T = T[T.race_id.isin(set(PY.race_id))].merge(PY, on=["race_id", "combo"], how="left"); T["ret"] = T.payout.fillna(0) / 100; T["hit"] = (T.ret > 0).astype(float)
cb = T.combo.str.split("-", expand=True).astype(int)
T["ex_key"] = cb[0].astype(str) + "-" + cb[1].astype(str)
T["tf_key"] = ["-".join(map(str, sorted(r))) for r in cb.to_numpy()]
EX["d_ex"] = np.log(EX.p_T1 / EX.p_T5); TF["d_tf"] = np.log(TF.p_T1 / TF.p_T5)
T = T.merge(EX[["race_id", "combo", "d_ex"]].rename(columns={"combo": "ex_key"}), on=["race_id", "ex_key"], how="left")
T = T.merge(TF[["race_id", "combo", "d_tf"]].rename(columns={"combo": "tf_key"}), on=["race_id", "tf_key"], how="left")
T["d_tri"] = np.log(T.p_T1 / T.p_T5); T["last"] = np.log(T.p_POST / T.p_T1)  # 最後の1分の見込みの変化（＋＝縮んだ＝買われた）
T["lead"] = T[["d_ex", "d_tf"]].mean(axis=1) - T.d_tri
T = T[(T.T1 <= 200) & T.lead.notna()].copy()
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 探す段階：券種どうしの動きの時間差（11/9 までのレースだけ）" + NL)
P(f"{T.race_id.str[-8:].min()}〜{T.race_id.str[-8:].max()}・{T.race_id.nunique()}R・{len(T):,}点（1分前で200倍以下）。当たり {int(T.hit.sum())}本。" + NL)
r_last = np.corrcoef(T.lead, T["last"])[0, 1]
P(f"- 合図 lead と「最後の1分の見込みの変化」の相関：**{r_last:+.3f}**（{len(T):,}点。＋なら、先に他の券種が買われた目は最後の1分に3連単でも買われる）")
# レースをまとめた t（レースごとの相関の平均）
rc = T.groupby("race_id").apply(lambda g: np.corrcoef(g.lead, g["last"])[0, 1] if len(g) > 5 and g.lead.std() > 0 else np.nan, include_groups=False).dropna()
P(f"- レースごとの相関の平均 {rc.mean():+.3f}（{len(rc)}R、t={rc.mean() / (rc.std() / np.sqrt(len(rc))):+.2f}）" + NL)
q1 = 1 / T.T1; T["p1"] = q1 / q1.groupby(T.race_id).transform("sum")
T["b"] = pd.qcut(T.lead, 5, labels=["1（他の券種が売れた）", "2", "3", "4", "5（他の券種が先に買われた）"])
P("## 合図の5段階" + NL + "| lead の段階 | 点数 | 最後の1分の見込みの変化（平均） | 当たり | 当たり÷1分前の見込み | 回収率 |" + NL + "|---|---|---|---|---|---|")
for k, g in T.groupby("b", observed=True):
    P(f"| {k} | {len(g):,} | {g['last'].mean():+.3f} | {int(g.hit.sum())} | {g.hit.sum() / g.p1.sum():.2f} | {g.ret.mean():.0%} |")
P(NL + "## 30倍以下だけ" + NL + "| lead の段階 | 点数 | 最後の1分の変化 | 当たり | 当たり÷見込み | 回収率 |" + NL + "|---|---|---|---|---|---|")
for k, g in T[T.T1 <= 30].groupby("b", observed=True):
    P(f"| {k} | {len(g):,} | {g['last'].mean():+.3f} | {int(g.hit.sum())} | {g.hit.sum() / max(g.p1.sum(), 1e-9):.2f} | {g.ret.mean():.0%} |")
print("done", r_last)
