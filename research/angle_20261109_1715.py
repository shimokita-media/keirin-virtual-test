"""切り口（構造の違う⑬）：選手の得点の流れ。得点（競走得点＝過去4か月の平均）は遅れて動くので、最近調子を上げている選手は得点が実力に追いついていない。
得点の変化＝今回の得点 −（約60日前の開催での得点）。市場（印・得点を見る客）がこの流れを追えているか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T)
L = pd.concat([pd.DataFrame({"race_id": T.race_id, "number": n, "pm": T.pm}) for n in (a, b, c)])
p3 = L.groupby(["race_id", "number"]).pm.sum().rename("p3").reset_index()
RA = pd.read_pickle(K + "out/side_races.pkl")[["race_id", "date"]]
E = pd.read_pickle(K + "out/side_entries.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id", "race_point"]].merge(RA, on="race_id")
E["rp"] = pd.to_numeric(E.race_point, errors="coerce"); E["d"] = pd.to_datetime(E.date)
E = E.sort_values(["player_id", "d"])
past = E[["player_id", "d", "rp"]].rename(columns={"d": "d0", "rp": "rp0"})
E["key"] = E.d - pd.Timedelta(days=60)
E = pd.merge_asof(E.sort_values("key"), past.sort_values("d0"), left_on="key", right_on="d0", by="player_id", direction="backward")
E["trend"] = E.rp - E.rp0
S = pd.read_pickle(K + "out/side_results.pkl")[["race_id", "number", "rank"]]
D = p3.merge(E[["race_id", "number", "trend", "date"]], on=["race_id", "number"]).merge(S, on=["race_id", "number"])
D["top3"] = (pd.to_numeric(D["rank"], errors="coerce") <= 3).astype(float); D["per"] = per(D.date)
D = D.dropna(subset=["trend"])
cuts = D[D.per == "探す"].trend.quantile([0.1, 0.3, 0.7, 0.9]).tolist()
D["tb"] = pd.cut(D.trend, [-99] + cuts + [99], labels=["大きく下降（下位10%）", "下降", "横ばい", "上昇", "大きく上昇（上位10%）"])
base = {k: D[D.per == k].top3.sum() / D[D.per == k].p3.sum() for k in ("探す", "③", "⑥")}
P("# 切り口：選手の得点の流れ（約60日前からの得点の変化）\n")
P(f"境目（探す期間の10/30/70/90%）：{', '.join(f'{x:+.2f}' for x in cuts)}。値＝実際の3着以内÷見込み を全体で割ったもの（1.00＝市場どおり）。\n")
P("| 得点の流れ | 探す | ③ | ⑥ |\n|---|---|---|---|")
for k, x in D.groupby("tb", observed=True):
    P(f"| {k} | " + " | ".join(f"{x[x.per==p].top3.sum() / x[x.per==p].p3.sum() / base[p]:.3f}（{(x.per==p).sum():,}）" for p in ("探す", "③", "⑥")) + " |")
tr = dict(zip(zip(E.race_id, E.number), E.trend))
for i, n in enumerate((a, b, c)): T[f"tr{i}"] = pd.Series([tr.get((r, x)) for r, x in zip(T.race_id, n)], index=T.index, dtype="float")
OUT.close()
up, dn = cuts[3], cuts[0]
conds = {"1着が大きく上昇中": T.tr0 >= up, "1着が大きく下降中": T.tr0 <= dn, "大きく上昇中を含む": (T.tr0 >= up) | (T.tr1 >= up) | (T.tr2 >= up),
         "大きく下降中を含む": (T.tr0 <= dn) | (T.tr1 <= dn) | (T.tr2 <= dn), "3人とも上昇か横ばい": (T.tr0 >= cuts[1]) & (T.tr1 >= cuts[1]) & (T.tr2 >= cuts[1])}
tmp = sys.argv[1] + ".tmp"; c1, c2 = report(tmp, "（続き）得点の流れで切った目の回収率", "", conds)
with open(sys.argv[1], "a", encoding="utf-8") as f, open(tmp, encoding="utf-8") as g2: f.write("\n" + g2.read())
import os; os.remove(tmp); print("候補", len(c1), "参考", len(c2))
