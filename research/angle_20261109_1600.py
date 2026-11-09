"""切り口：選手の期（デビューの新しさ）。新人（直近の期）は成長が速く、成績表（得点・印）が実力に追いついていない＝市場が軽く見ている可能性。逆にベテランは名前で買われすぎていないか。
新人＝その月に走った選手の中で一番新しい期から2期以内。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro&immutable=1", uri=True)
E = pd.read_sql("SELECT e.race_id, e.number, e.term, r.date FROM entries e JOIN races r USING(race_id) WHERE r.date >= '20250201' AND e.absent = 0", con)
E["term"] = pd.to_numeric(E.term, errors="coerce"); E["ym"] = E.date.str[:6]
E["newest"] = E.groupby("ym").term.transform("max"); E["gap"] = E.newest - E.term
gap = dict(zip(zip(E.race_id, E.number), E.gap))
a, b, c = combo_parts(T)
G = {i: pd.Series([gap.get((r, x)) for r, x in zip(T.race_id, n)], index=T.index, dtype="float") for i, n in enumerate((a, b, c))}
rook = {i: G[i] <= 2 for i in range(3)}; vet = {i: G[i] >= 30 for i in range(3)}
nrook = rook[0].astype(int) + rook[1].astype(int) + rook[2].astype(int)
conds = {"1着が新人": rook[0], "2着が新人": rook[1], "3着が新人": rook[2], "新人を含む": nrook >= 1, "新人を含まない": nrook == 0,
         "1着がベテラン（30期以上前）": vet[0], "3着がベテラン": vet[2], "1着が新人×2〜3着がベテラン": rook[0] & (vet[1] | vet[2])}
c, c2 = report(sys.argv[1], "選手の期（新人・ベテラン）", "新人＝その月に走った選手の一番新しい期から2期以内、ベテラン＝30期以上前。", conds)
x = T[(T.odds <= 30) & (per(T.date) == "探す")].copy(); x["hit"] = (x.ret > 0).astype(float); x["imp"] = 0.75 / x.odds
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 市場の見立てとのズレ（30倍以下・探す期間）\n")
    for nm, m in (("1着が新人", rook[0]), ("新人を含む", nrook >= 1), ("新人を含まない", nrook == 0), ("1着がベテラン", vet[0])):
        g = x[m.reindex(x.index)]; f.write(f"- {nm}: 実際の当たり {g.hit.mean():.2%} ÷ 見込み {g.imp.mean():.2%} = {g.hit.mean() / g.imp.mean():.2f}（{len(g)}点）\n")
print("候補", len(c), "参考", len(c2))
