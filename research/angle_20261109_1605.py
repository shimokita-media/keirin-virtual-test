"""切り口：ギア倍数。重いギアの選手（先行・捲りでスピードを持続）と軽いギアの選手の差を、市場が織り込んでいるか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True)
E = pd.read_sql("SELECT e.race_id, e.gear FROM entries e JOIN races r USING(race_id) WHERE r.date >= '20250201' AND e.absent = 0", con)
E["gear"] = pd.to_numeric(E.gear, errors="coerce")
gmax, gmin = E.groupby("race_id").gear.max(), E.groupby("race_id").gear.min()
g0, g1, g2 = (pd.to_numeric(T[f"r{i}_gear"], errors="coerce") for i in range(3))
mx, mn = T.race_id.map(gmax), T.race_id.map(gmin)
q_hi = E.gear.quantile(0.8); q_lo = E.gear.quantile(0.2)
conds = {f"1着のギアが重い（上位20%・{q_hi:.2f}以上）": g0 >= q_hi, f"1着のギアが軽い（下位20%・{q_lo:.2f}以下）": g0 <= q_lo,
         "1着のギアがレースで一番重い": g0 >= mx, "1着のギアがレースで一番軽い": g0 <= mn,
         "3着のギアが重い": g2 >= q_hi, "3着のギアが軽い": g2 <= q_lo, "3人ともギアが重い": (g0 >= q_hi) & (g1 >= q_hi) & (g2 >= q_hi),
         "ギアがレース全員同じ": mx == mn, "レースのギアの差が大きい（0.15以上）": (mx - mn) >= 0.15}
c, c2 = report(sys.argv[1], "ギア倍数", f"entries.gear。重い＝全出走の上位20%（{q_hi:.2f}以上）、軽い＝下位20%（{q_lo:.2f}以下）。", conds)
x = T[(T.odds <= 30) & (per(T.date) == "探す")].copy(); x["hit"] = (x.ret > 0).astype(float); x["imp"] = 0.75 / x.odds
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 市場の見立てとのズレ（30倍以下・探す期間）\n")
    for nm, m in (("1着が重いギア", g0 >= q_hi), ("1着が軽いギア", g0 <= q_lo), ("1着がレースで一番重い", g0 >= mx)):
        g = x[m.reindex(x.index)]; f.write(f"- {nm}: 実際の当たり {g.hit.mean():.2%} ÷ 見込み {g.imp.mean():.2%} = {g.hit.mean() / g.imp.mean():.2f}（{len(g)}点）\n")
print("候補", len(c), "参考", len(c2))
