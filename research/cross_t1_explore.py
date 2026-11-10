"""探す段階：締切1分前（T1）の時点での券種どうしの食い違い（水準）。**11/9 までのレースだけ**。
3連単の目の見込み（1/倍率をレースの中で合計1）を、同じ3人の3連複の見込みに占める割合と、同じ1-2着の2車単の見込みに占める割合で見る：
  g_tf1 ＝ 3連複の同じ3人の見込み ÷ 3連単でその3人の6通りの見込みの合計 −1   （＋＝3連複の方が3人を高く見ている＝3連単のその3人が割安）
  g_ex1 ＝ 2車単の同じ1-2着の見込み ÷ 3連単でその1-2着の見込みの合計 −1     （＋＝3連単のその1-2着が割安）
目的：＋の目ほど 1分前の見込みより当たるか、最後の1分に縮むか（確定オッズでの g_tf・g_ex と同じ考えを1分前で）。
使い方: python -I -X utf8 research/cross_t1_explore.py reports/cross_t1_explore.md"""
import sys, sqlite3, numpy as np, pandas as pd
NL = chr(10); LAST = "20261109"
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro", uri=True)
def load(bt, phases):
    o = pd.read_sql(f"SELECT race_id, combo, phase, odds FROM odds WHERE bet_type='{bt}' AND phase IN ({','.join(repr(p) for p in phases)}) AND odds > 0 ORDER BY fetched_at", con)
    o = o[o.race_id.str[-8:].between("20261107", LAST)]
    w = o.pivot_table(index=["race_id", "combo"], columns="phase", values="odds", aggfunc="last").reset_index()
    for p in phases:
        q = 1 / w[p]; w["p_" + p] = q / q.groupby(w.race_id).transform("sum")
    return w
T = load("3連単", ["T1", "POST"]).dropna(subset=["T1", "POST"]); EX = load("2車単", ["T1"]).dropna(); TF = load("3連複", ["T1"]).dropna()
PY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連単'", con)
T = T[T.race_id.isin(set(PY.race_id))].merge(PY, on=["race_id", "combo"], how="left"); T["ret"] = T.payout.fillna(0) / 100; T["hit"] = (T.ret > 0).astype(float)
cb = T.combo.str.split("-", expand=True).astype(int)
T["ex_key"] = cb[0].astype(str) + "-" + cb[1].astype(str); T["tf_key"] = ["-".join(map(str, sorted(r))) for r in cb.to_numpy()]
T["tri_set"] = T.groupby(["race_id", "tf_key"]).p_T1.transform("sum"); T["tri_ex"] = T.groupby(["race_id", "ex_key"]).p_T1.transform("sum")
T = T.merge(TF[["race_id", "combo", "p_T1"]].rename(columns={"combo": "tf_key", "p_T1": "tf1"}), on=["race_id", "tf_key"], how="left")
T = T.merge(EX[["race_id", "combo", "p_T1"]].rename(columns={"combo": "ex_key", "p_T1": "ex1"}), on=["race_id", "ex_key"], how="left")
T["g_tf1"] = T.tf1 / T.tri_set - 1; T["g_ex1"] = T.ex1 / T.tri_ex - 1
T["last"] = np.log(T.p_POST / T.p_T1)
T = T[(T.T1 <= 200) & T.g_tf1.notna() & T.g_ex1.notna()].copy()
q1 = 1 / T.T1; T["p1"] = q1 / q1.groupby(T.race_id).transform("sum")
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT)
P("# 探す段階：締切1分前の券種どうしの食い違い（11/9 までのレースだけ）" + NL)
P(f"{T.race_id.nunique()}R・{len(T):,}点（1分前で200倍以下）。当たり {int(T.hit.sum())}本。" + NL)
for col, nm in (("g_tf1", "3連複との食い違い"), ("g_ex1", "2車単との食い違い")):
    P(f"## {nm}（{col}）" + NL + f"- 最後の1分の変化との相関 {np.corrcoef(T[col].clip(-1, 3), T['last'])[0, 1]:+.3f}" + NL)
    T["b"] = pd.qcut(T[col], 5, labels=["1（3連単が割高）", "2", "3", "4", "5（3連単が割安）"], duplicates="drop")
    P("| 段階 | 点数 | 最後の1分の変化 | 当たり | 当たり÷1分前の見込み | 回収率 | 30倍以下：点数・当たり÷見込み・回収率 |" + NL + "|---|---|---|---|---|---|---|")
    for k, g in T.groupby("b", observed=True):
        g30 = g[g.T1 <= 30]
        P(f"| {k} | {len(g):,} | {g['last'].mean():+.3f} | {int(g.hit.sum())} | {g.hit.sum() / g.p1.sum():.2f} | {g.ret.mean():.0%} | {len(g30)}点・{g30.hit.sum() / max(g30.p1.sum(), 1e-9):.2f}・{g30.ret.mean():.0%} |")
    P("")
print("done")
