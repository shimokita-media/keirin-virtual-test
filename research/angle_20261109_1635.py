"""切り口（構造の違う⑤）：同じ開催の前日の走り。市場は「昨日の着順」に引っ張られすぎていないか（昨日勝った選手を買いすぎ、昨日大敗した選手を軽く見すぎ）。
選手ごとに、今日の「3着以内に来る見込み」（3連単の最終倍率から）に対する実際を、昨日の着順・決まり手で分ける。取り込み中のDBは読まず side_*.pkl を使う。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T)
L = pd.concat([pd.DataFrame({"race_id": T.race_id, "number": n, "pm": T.pm}) for n in (a, b, c)])
p3 = L.groupby(["race_id", "number"]).pm.sum().rename("p3").reset_index()
RA = pd.read_pickle(K + "out/side_races.pkl")[["race_id", "date", "cup_id", "day_index"]]
E = pd.read_pickle(K + "out/side_entries.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id"]]
S = pd.read_pickle(K + "out/side_results.pkl")[["race_id", "player_id", "rank", "factor"]]
X = E.merge(RA, on="race_id").merge(S, on=["race_id", "player_id"], how="left")
X["rank"] = pd.to_numeric(X["rank"], errors="coerce")
prev = X[["player_id", "cup_id", "day_index", "rank", "factor"]].rename(columns={"rank": "prank", "factor": "pfactor"}); prev["day_index"] += 1
X = X.merge(prev, on=["player_id", "cup_id", "day_index"], how="left")
D = p3.merge(X, on=["race_id", "number"])
D["top3"] = (D["rank"] <= 3).astype(float); D["per"] = per(D.date)
D = D[D.day_index >= 2]
def grp(lab, m):
    out = []
    for k in ("探す", "③", "⑥"):
        x = D[m & (D.per == k)]
        out.append(f"{x.top3.sum() / x.p3.sum():.3f}（{len(x):,}）" if len(x) else "−")
    P(f"| {lab} | " + " | ".join(out) + " |")
P("# 切り口：同じ開催の前日の走り（昨日の着順に市場が引っ張られるか）\n")
P("2日目以降の選手。値＝実際の3着以内 ÷ 今日の見込み（3連単の最終倍率から、300倍以下の目で作るので全体は1.03前後）。\n")
P("| 昨日 | 探す | ③ | ⑥ |\n|---|---|---|---|")
grp("全体（2日目以降）", D.prank.notna() | D.prank.isna())
for lab, m in (("昨日1着", D.prank == 1), ("昨日2着", D.prank == 2), ("昨日3着", D.prank == 3), ("昨日4〜5着", D.prank.between(4, 5)),
               ("昨日6〜7着", D.prank.between(6, 7)), ("昨日8〜9着（大敗）", D.prank >= 8), ("昨日の記録なし（失格・欠場など）", D.prank.isna())):
    grp(lab, m)
P("\n## 昨日の決まり手（1着・2着の選手）\n\n| 昨日の決まり手 | 探す | ③ | ⑥ |\n|---|---|---|---|")
for f in ("逃", "捲", "差", "マ"):
    grp(f"昨日 {f}（1〜2着）", (D.pfactor.astype(str).str.contains(f)) & (D.prank <= 2))
# 買い方：昨日大敗の選手を含む目・昨日1着の選手を1着に買う目
pr = dict(zip(zip(X.race_id, X.number), X.prank))
for i, n in enumerate((a, b, c)): T[f"pr{i}"] = pd.Series([pr.get((r, x)) for r, x in zip(T.race_id, n)], index=T.index, dtype="float")
OUT.close()
conds = {"1着が昨日1着": T.pr0 == 1, "1着が昨日大敗（8着以下）": T.pr0 >= 8, "3着が昨日大敗": T.pr2 >= 8, "昨日大敗を含む": (T.pr0 >= 8) | (T.pr1 >= 8) | (T.pr2 >= 8),
         "3人とも昨日3着以内": (T.pr0 <= 3) & (T.pr1 <= 3) & (T.pr2 <= 3), "3人とも昨日4着以下": (T.pr0 >= 4) & (T.pr1 >= 4) & (T.pr2 >= 4)}
tmp = sys.argv[1] + ".tmp"; cand, c2 = report(tmp, "（続き）昨日の着順で切った目の回収率", "", conds)
with open(sys.argv[1], "a", encoding="utf-8") as f, open(tmp, encoding="utf-8") as g2: f.write("\n" + g2.read())
import os; os.remove(tmp); print("候補", len(cand))
