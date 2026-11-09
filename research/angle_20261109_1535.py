"""切り口：級班の混ざり方（S1・S2・A1…。数字が小さいほど上位）。格上・格下が混ざるレースで、市場は格上を買いすぎ／格下を軽く見ていないか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True)
E = pd.read_sql("SELECT e.race_id, e.number, e.class AS c, e.grp AS g FROM entries e JOIN races r USING(race_id) WHERE r.date >= '20250201' AND e.absent = 0", con)
E["rk"] = pd.to_numeric(E.c, errors="coerce") * 10 + pd.to_numeric(E.g, errors="coerce")
top_rk = E.groupby("race_id").rk.min(); nkind = E.groupby("race_id").rk.nunique()
rk = dict(zip(zip(E.race_id, E.number), E.rk))
a, b, c = combo_parts(T)
for i, n in enumerate((a, b, c)): T[f"rk{i}"] = [rk.get((r, x)) for r, x in zip(T.race_id, n)]
T["toprk"] = T.race_id.map(top_rk); T["nkind"] = T.race_id.map(nkind)
low = {i: pd.to_numeric(T[f"rk{i}"], errors="coerce") > T.toprk for i in range(3)}
nlow = low[0].astype(int) + low[1].astype(int) + low[2].astype(int)
mixed = T.nkind >= 2
conds = {"級班が1種類のレース": T.nkind == 1, "級班が2種類以上のレース": mixed, "級班が3種類以上のレース": T.nkind >= 3,
         "混ざるレース×1着が格下": mixed & low[0], "混ざるレース×1着が最上位の班": mixed & ~low[0],
         "混ざるレース×2着が格下": mixed & low[1], "混ざるレース×3着が格下": mixed & low[2],
         "混ざるレース×3人とも最上位の班": mixed & (nlow == 0), "混ざるレース×格下が2人以上": mixed & (nlow >= 2)}
c, c2 = report(sys.argv[1], "級班の混ざり方", "級班＝entries の class×10＋grp（小さいほど上位）。格下＝そのレースで一番上の班より下の選手。", conds)
x = T[(T.odds <= 30) & (per(T.date) == "探す") & mixed].copy(); x["hit"] = (x.ret > 0).astype(float); x["imp"] = 0.75 / x.odds
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 市場の見立てとのズレ（混ざるレース・30倍以下・探す期間）\n")
    for nm, m in (("1着が格下", low[0]), ("1着が最上位", ~low[0]), ("格下を含まない", nlow == 0), ("格下2人以上", nlow >= 2)):
        g = x[m.reindex(x.index)]; f.write(f"- {nm}: 実際の当たり {g.hit.mean():.2%} ÷ 見込み {g.imp.mean():.2%} = {g.hit.mean() / g.imp.mean():.2f}（{len(g)}点）\n")
print("候補", len(c), "参考", len(c2))
