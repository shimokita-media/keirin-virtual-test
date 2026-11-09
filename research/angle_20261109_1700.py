"""切り口（構造の違う⑩）：勝ち上がり条件とライン内の位置。準決勝・予選は「何着までに入れば次に進めるか」があるので、番手が先頭を残して2着・3着を確保しにいく（＝ラインで上位を独占）動きが増えるはず。
決勝・特選・一般戦（勝ち上がりがない）と比べて、ラインの決まり方（先頭→番手、番手→先頭、ライン3人）の歪みが違うか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
rt = T.race_type.fillna("").astype(str)
kind = np.select([rt.str.contains("準決勝"), rt.str.contains("予選"), rt.str.contains("決勝") & ~rt.str.contains("準"), rt.str.contains("特選|選抜"), rt.str.contains("一般")],
                 ["準決勝", "予選", "決勝", "特選・選抜", "一般戦"], "その他")
s01, s12 = T.s01 == 1, T.s12 == 1; same3 = s01 & s12
one_two = s01 & (T.r0_pos == 0) & (T.r1_pos == 1); two_one = s01 & (T.r0_pos == 1) & (T.r1_pos == 0)
order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
conds = {}
for k in ("準決勝", "予選", "決勝", "特選・選抜", "一般戦"):
    m = pd.Series(kind == k, index=T.index)
    conds[f"{k}×先頭→番手"] = m & one_two
    conds[f"{k}×番手→先頭"] = m & two_one
    conds[f"{k}×ライン3人が並び順"] = m & order
    conds[f"{k}×ライン3人（順不同）"] = m & same3
c, c2 = report(sys.argv[1], "勝ち上がり条件とライン内の位置（レースの種類×ラインの決まり方）",
               "準決勝・予選＝勝ち上がりあり、決勝・特選・選抜・一般戦＝勝ち上がりなし。", conds)
x = T[(T.odds <= 60) & (per(T.date) == "探す")].copy(); x["hit"] = (x.ret > 0).astype(float); x["imp"] = 0.75 / x.odds
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 市場の見立てとのズレ（60倍以下・探す期間）：実際の当たり÷見込み\n\n| レースの種類 | 先頭→番手 | 番手→先頭 | ライン3人 |\n|---|---|---|---|\n")
    for k in ("準決勝", "予選", "決勝", "特選・選抜", "一般戦"):
        m = pd.Series(kind == k, index=T.index).reindex(x.index)
        cells = []
        for s in (one_two, two_one, same3):
            g = x[m & s.reindex(x.index)]; cells.append(f"{g.hit.mean() / g.imp.mean():.2f}（{len(g)}）" if len(g) else "−")
        f.write(f"| {k} | " + " | ".join(cells) + " |\n")
print("候補", len(c), "参考", len(c2))
