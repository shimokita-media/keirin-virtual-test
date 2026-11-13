"""ライン順×30倍以下の機械（F1 期待値≥1.1・F2 期待値≥1.2。KNOWLEDGE 2026-11-12 の★事前登録 F1/F2 と同じ式・同じ係数）を、本番の締切1分前（T1）の倍率で拾い、
日ごとの目と結果を並べる（2026-11-13、ユーザー依頼「合格しなくても明日のデータがほしい」）。参考用：y6 の判定の合否や登録した条件は、この表を見て変えない。
入力：out/angle_base_t1.pkl（先に research/daily_forward.py を回す）
使い方: python -I -X utf8 research/lo30_forward_t1.py reports/lo30_forward_t1.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
C = json.load(open(K + "research/lo30_model_coef_4yr.json", encoding="utf-8")); assert C["cols"] == ["const"] + LO_COLS
T = pd.read_pickle(K + "out/angle_base_t1.pkl").reset_index(drop=True)
T["hit"] = (T.ret > 0).astype(float)
Wn = T[T.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
R = T.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
R["lw"] = R.race_id.map(Wn).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R = R.set_index("race_id")
T["flow"] = T.race_id.map(R.flow); T["n_prev"] = T.race_id.map(R.n_prev)
d = T[T.odds <= 300].copy(); q = 1 / d.odds; d["pn"] = q / q.groupby(d.race_id).transform("sum")
lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 30)].copy()
lo["ratio"] = lo_ratio(C["coef"], lo); lo["ev"] = lo.ratio * lo.pn * lo.odds
days = sorted(T.date.unique()); nR = T.groupby("date").race_id.nunique()
L = [f"# ライン順×30倍以下の機械（F1・F2）を本番の締切1分前の倍率で拾った記録（{days[0]}〜{days[-1]}・{T.race_id.nunique()}R）", "",
     "参考用。払戻は確定の値。点数が少ないうちは運で大きく動く（判断には使わない）。1分前の記録が取れたレースだけが対象", "",
     "## 日ごと", "", "| 日 | 記録できたレース | F1 期待値≥1.1 | F2 期待値≥1.2 |", "|---|---|---|---|"]
def cell(g): return f"{len(g)}点・当たり{int((g.ret > 0).sum())}・{g.ret.mean():.0%}" if len(g) else "0点"
for dy in days:
    x = lo[lo.date == dy]; L.append(f"| {dy} | {nR[dy]}R | {cell(x[x.ev >= 1.1])} | {cell(x[x.ev >= 1.2])} |")
L.append(f"| **累計** | {T.race_id.nunique()}R | {cell(lo[lo.ev >= 1.1])} | {cell(lo[lo.ev >= 1.2])} |")
L += ["", f"## 最新の日（{days[-1]}）の目", "", "| レース | 目 | 1分前の倍率 | 比 | 期待値 | 結果 |", "|---|---|---|---|---|---|"]
x = lo[(lo.date == days[-1]) & (lo.ev >= 1.1)].sort_values(["venue", "race_no"])
for r in x.itertuples(): L.append(f"| {r.venue} {r.race_no}R | {r.combo} | {r.odds:.1f} | {r.ratio:.2f} | {r.ev:.2f} | {'当たり ' + format(r.ret * 100, ',.0f') + '円' if r.ret > 0 else '外れ'} |")
open(sys.argv[1], "w", encoding="utf-8").write(NL.join(L) + NL); print("done")
