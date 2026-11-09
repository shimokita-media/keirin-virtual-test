"""切り口（構造の違う⑧）：当日の流れ。同じ場・同じ日の前のレースで「先頭（逃げ・先行）が勝ち続けている」「荒れ続いている」とき、
後のレースで市場がその流れを追いかけすぎる（または追いつけない）か。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
W = T[T.ret > 0][["race_id", "r0_pos", "popularity"]].drop_duplicates("race_id").set_index("race_id")
R = T.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].copy()
R["lead_win"] = R.race_id.map(W.r0_pos).eq(0).astype(float)
R["upset"] = (R.race_id.map(W.popularity).fillna(999) >= 20).astype(float)  # 当たり目が300倍超（表にない）も荒れ扱い
R = R.sort_values(["venue", "date", "race_no"])
g = R.groupby(["venue", "date"])
R["n_prev"] = g.cumcount()
R["lead_prev"] = (g.lead_win.cumsum() - R.lead_win) / R.n_prev.replace(0, np.nan)
R["upset_prev"] = (g.upset.cumsum() - R.upset) / R.n_prev.replace(0, np.nan)
for col in ("n_prev", "lead_prev", "upset_prev"): T[col] = T.race_id.map(R.set_index("race_id")[col])
enough = T.n_prev >= 4
lp, up = T.lead_prev, T.upset_prev
band_lo, band_hi = T.odds <= 30, T.odds >= 100
conds = {"先頭が勝ち続け（前のレースの60%以上）×1着が先頭": enough & (lp >= 0.6) & (T.r0_pos == 0),
         "先頭が勝ち続け×1着が番手": enough & (lp >= 0.6) & (T.r0_pos == 1),
         "先頭が勝てていない（30%以下）×1着が先頭": enough & (lp <= 0.3) & (T.r0_pos == 0),
         "先頭が勝てていない×1着が番手": enough & (lp <= 0.3) & (T.r0_pos == 1),
         "荒れ続き（前の50%以上が20番人気以下）×100倍以上": enough & (up >= 0.5) & band_hi,
         "荒れ続き×30倍以下": enough & (up >= 0.5) & band_lo,
         "固く決まり続き（荒れ10%以下）×100倍以上": enough & (up <= 0.1) & band_hi,
         "固く決まり続き×30倍以下": enough & (up <= 0.1) & band_lo,
         "前のレースが4つ以上（後半のレース）": enough, "前のレースが3つ以下（前半のレース）": T.n_prev <= 3}
c, c2 = report(sys.argv[1], "当日の流れ（同じ場・同じ日の前のレースの決まり方）",
               "先頭が勝った＝当たり目の1着がラインの先頭。荒れ＝当たり目が20番人気以下（300倍超を含む）。前のレースが4つ以上あるレースだけで比べる。", conds)
x = T[enough & (T.odds <= 30) & (per(T.date) == "探す")].copy(); x["hit"] = (x.ret > 0).astype(float); x["imp"] = 0.75 / x.odds
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 市場の見立てとのズレ（30倍以下・探す期間・前のレース4つ以上）\n")
    for nm, m in (("先頭勝ち続け×1着先頭", (lp >= 0.6) & (T.r0_pos == 0)), ("先頭勝てず×1着先頭", (lp <= 0.3) & (T.r0_pos == 0)), ("先頭勝ち続け×1着番手", (lp >= 0.6) & (T.r0_pos == 1)), ("先頭勝てず×1着番手", (lp <= 0.3) & (T.r0_pos == 1))):
        gg = x[m.reindex(x.index)]; f.write(f"- {nm}: 実際の当たり {gg.hit.mean():.2%} ÷ 見込み {gg.imp.mean():.2%} = {gg.hit.mean() / gg.imp.mean():.2f}（{len(gg)}点）\n")
print("候補", len(c), "参考", len(c2))
