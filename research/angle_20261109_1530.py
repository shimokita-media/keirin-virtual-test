"""切り口：中何日（前の開催からの間隔）。連闘気味（中3日以内）の疲れ、休み明け（21日以上）の調整不足を市場が織り込んでいるか。
間隔の計算は2025/1以降の開催だけを使う（2024年のデータは事前登録R・S・Tのため使わない）。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro&immutable=1", uri=True)
E = pd.read_sql("SELECT e.race_id, e.number, e.player_id, r.date, r.cup_id FROM entries e JOIN races r USING(race_id) WHERE r.date >= '20250101' AND e.absent = 0", con)
E["d"] = pd.to_datetime(E.date)
cup = E.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
cup["prev_end"] = cup.groupby("player_id")["max"].shift()
cup["rest"] = (cup["min"] - cup.prev_end).dt.days - 1
E = E.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
E = E[E.date >= "20250201"]
rest = dict(zip(zip(E.race_id, E.number), E.rest))
a, b, c = combo_parts(T)
for i, n in enumerate((a, b, c)): T[f"rest{i}"] = [rest.get((r, x)) for r, x in zip(T.race_id, n)]
R = {i: pd.to_numeric(T[f"rest{i}"], errors="coerce") for i in range(3)}
anyshort = (R[0] <= 3) | (R[1] <= 3) | (R[2] <= 3); anylong = (R[0] >= 21) | (R[1] >= 21) | (R[2] >= 21)
conds = {"1着が中3日以内": R[0] <= 3, "1着が中4〜9日": R[0].between(4, 9), "1着が中10〜20日": R[0].between(10, 20), "1着が中21日以上（休み明け）": R[0] >= 21,
         "2着が中3日以内": R[1] <= 3, "2着が休み明け": R[1] >= 21, "3着が中3日以内": R[2] <= 3, "3着が休み明け": R[2] >= 21,
         "3人とも中4〜20日（普通）": R[0].between(4, 20) & R[1].between(4, 20) & R[2].between(4, 20), "誰かが中3日以内": anyshort, "誰かが休み明け": anylong}
c, c2 = report(sys.argv[1], "中何日（前の開催からの間隔）", f"間隔が分かる割合：{R[0].notna().mean():.0%}（2025/2初めは前の開催が分からないので空欄）。中3日以内＝前の開催の最終日から3日以内に次の開催が始まる。", conds)
print("候補", len(c), "参考", len(c2))
