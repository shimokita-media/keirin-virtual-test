"""切り口（構造の違う⑥）：払戻の分布の形。レースごとの3連単の見込みの「散らばり（エントロピー）」で、本命〜大穴の買われ方の歪み（本命・大穴バイアス）がレースの形によって変わるか。
人気の割れ方（一番人気の倍率だけ）と違い、全部の目の並び方を使う。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
T["ent"] = -(T.pm * np.log(T.pm)).groupby(T.race_id).transform("sum")
T["top10"] = T.groupby("race_id").pm.transform(lambda s: s.nlargest(10).sum())
ents = T.drop_duplicates("race_id").ent
cuts = ents[per(T.drop_duplicates("race_id").date) == "探す"].quantile([0.2, 0.4, 0.6, 0.8]).tolist()
T["eb"] = pd.cut(T.ent, [-1] + cuts + [99], labels=["固い（散らばり小）", "やや固い", "中", "やや荒れ", "荒れ（散らばり大）"])
band = pd.cut(T.odds, [0, 10, 30, 100, 300], labels=["〜10倍", "10〜30倍", "30〜100倍", "100〜300倍"])
conds = {}
for e in T.eb.cat.categories:
    for bd in band.cat.categories:
        conds[f"{e}×{bd}"] = (T.eb == e) & (band == bd)
c, c2 = report(sys.argv[1], "払戻の分布の形（3連単の見込みの散らばり）×倍率帯",
               f"散らばり＝300倍以下の目の見込み（1/倍率を正規化）のエントロピー。5段階の境目は探す期間のレースの20%ごと（{', '.join(f'{x:.2f}' for x in cuts)}）。", conds)
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 散らばりと実際の荒れ方（当たった目の人気順位の中央値・探す / ③ / ⑥）\n")
    W = T[T.ret > 0]
    for e, x in W.groupby("eb", observed=True):
        f.write(f"- {e}: " + " / ".join(f"{x[per(x.date) == k].popularity.median():.0f}番人気（{(per(x.date) == k).sum()}R）" for k in ("探す", "③", "⑥")) + "\n")
print("候補", len(c), "参考", len(c2))
