"""切り口（構造の違う③）：選手×バンク。その選手が特定のバンクで（その選手のふだんの癖を除いても）よく来る／来ないか、それが続くか。
見込み＝3連単の最終倍率（300倍以下）から出した「3着以内に来る見込み」。癖＝実際÷見込み。選手×バンクの癖 ÷ 選手全体の癖 を、探す期間と③⑥で比べる。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
from scipy.stats import spearmanr
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T)
L = pd.concat([pd.DataFrame({"race_id": T.race_id, "number": n, "pm": T.pm}) for n in (a, b, c)])
p3 = L.groupby(["race_id", "number"]).pm.sum().rename("p3").reset_index()
R = pd.read_pickle(K + "out/side_results.pkl")[["race_id", "number", "rank"]]  # 取り込み中のDBは読まない（research/angle_side.py で作った写し）
E = pd.read_pickle(K + "out/side_entries.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id"]]
D = p3.merge(E, on=["race_id", "number"]).merge(R, on=["race_id", "number"])
D["top3"] = (pd.to_numeric(D["rank"], errors="coerce") <= 3).astype(float)
meta = T.drop_duplicates("race_id").set_index("race_id")
D["date"] = D.race_id.map(meta.date); D["venue"] = D.race_id.map(meta.venue); D["per"] = per(D.date)
D["hold"] = np.where(D.per == "探す", "探す", "確認")
pl = D.groupby(["player_id", "hold"]).agg(a=("top3", "sum"), e=("p3", "sum")).reset_index(); pl["pr"] = pl.a / pl.e
pv = D.groupby(["player_id", "venue", "hold"]).agg(n=("top3", "size"), a=("top3", "sum"), e=("p3", "sum")).reset_index()
pv = pv.merge(pl[["player_id", "hold", "pr"]], on=["player_id", "hold"]); pv["r"] = (pv.a / pv.e) / pv.pr
X = pv.pivot_table(index=["player_id", "venue"], columns="hold", values=["n", "r", "a", "e"]).dropna()
P("# 切り口：選手×バンク（その選手のふだんの癖を除いた、バンクごとの得意・苦手）\n")
for nmin, hmin in ((5, 3), (8, 4), (12, 5)):
    Y = X[(X[("n", "探す")] >= nmin) & (X[("n", "確認")] >= hmin)]
    if len(Y) < 30: continue
    rho, p = spearmanr(Y[("r", "探す")], Y[("r", "確認")])
    P(f"- 探す{nmin}レース以上・確認（③⑥）{hmin}レース以上の組 {len(Y):,}組：探すと確認の順位相関 **{rho:.3f}**（p={p:.3g}）")
Y = X[(X[("n", "探す")] >= 8) & (X[("n", "確認")] >= 4)].copy()
Y["qq"] = pd.qcut(Y[("r", "探す")], 5, labels=["苦手20%", "20〜40", "40〜60", "60〜80", "得意20%"])
P("\n| 探す期間のバンク相性 | 組数 | 探す 癖の比 | 確認（③⑥）癖の比 |\n|---|---|---|---|")
for k, x in Y.groupby("qq", observed=True):
    P(f"| {k} | {len(x)} | {x[('r','探す')].median():.2f} | {x[('r','確認')].median():.2f}（平均 {x[('r','確認')].mean():.2f}） |")
P("\n癖の比＝（その選手のそのバンクでの 実際÷見込み）÷（その選手の全体の 実際÷見込み）。1.0＝ふだんどおり。")
print("done")
