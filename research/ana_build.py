"""選手単位の表：市場が見込む3着以内の確率（3連単の最終オッズから） vs 実際の3着以内。使い方: python ana_build.py 開始日 終了日 出力.pkl"""
import sys, json, re, sqlite3, numpy as np, pandas as pd
D0, D1, OUT = sys.argv[1:4]
c = sqlite3.connect("file:" + __import__("os").environ.get("KDB", "C:/Users/take0/.claude/keirin/keirin.sqlite") + "?mode=ro", uri=True)
races = pd.read_sql(f"""SELECT race_id, date, venue, grade, class, race_type, day_index, race_no, entries_number, line_json, cup_id FROM races
    WHERE class!='L級' AND date BETWEEN '{D0}' AND '{D1}' AND race_id IN (SELECT race_id FROM results)""", c)
out = []
for i0 in range(0, len(races), 2000):
    R = races.iloc[i0:i0 + 2000]; ids = tuple(R.race_id); q = ",".join("?" * len(ids))
    o = pd.read_sql(f"SELECT race_id, combo, odds, fetched_at FROM odds WHERE phase='" + __import__("os").environ.get("KPH", "POST") + f"' AND source='winticket' AND bet_type='3連単' AND odds>0 AND race_id IN ({q})", c, params=ids)
    o = o[o.fetched_at == o.groupby("race_id").fetched_at.transform("max")]
    o["p"] = 1 / o.odds; o["p"] /= o.groupby("race_id").p.transform("sum")
    cb = o.combo.str.split("-", expand=True).astype(int)
    pm = pd.concat([pd.DataFrame({"race_id": o.race_id, "number": cb[k], "p": o.p}) for k in range(3)]).groupby(["race_id", "number"]).p.sum()
    p1 = pd.DataFrame({"race_id": o.race_id, "number": cb[0], "p": o.p}).groupby(["race_id", "number"]).p.sum()
    E = pd.read_sql(f"""SELECT race_id, number, player_id, name, prefecture, age, class AS pcls, style, race_point, comment, prediction_mark,
        first_rate, second_rate, third_rate, n_front, n_stalker, n_closer, n_marker, gear FROM entries WHERE absent=0 AND race_id IN ({q})""", c, params=ids)
    res = pd.read_sql(f"SELECT race_id, number, rank, factor FROM results WHERE race_id IN ({q})", c, params=ids).drop_duplicates(["race_id", "number"])
    E = E.merge(res, on=["race_id", "number"], how="left")
    E["p3"] = [pm.get((r, n), np.nan) for r, n in zip(E.race_id, E.number)]
    E["p1"] = [p1.get((r, n), np.nan) for r, n in zip(E.race_id, E.number)]
    E["pt_rank"] = E.groupby("race_id").race_point.rank(ascending=False, method="min")
    E["mk_rank"] = E.groupby("race_id").p3.rank(ascending=False, method="min")
    E["n"] = E.groupby("race_id").number.transform("size")
    Ri = R.set_index("race_id")
    pos, ls, nl, lead_rank, lead_style, lead_id, n_strong_nige, lid = [], [], [], [], [], [], [], []
    Eg = {k: g for k, g in E.groupby("race_id")}
    for r, num in zip(E.race_id, E.number):
        lj = Ri.line_json[r]
        lines = [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(lj)] if isinstance(lj, str) else []
        g = Eg[r].set_index("number")
        L = next((l for l in lines if num in l), [num])
        pos.append(L.index(num)); ls.append(len(L)); nl.append(len(lines)); lid.append(lines.index(L) if L in lines else -1)
        ld = L[0]; lead_rank.append(g.pt_rank.get(ld, np.nan)); lead_style.append(g["style"].get(ld)); lead_id.append(ld)
        # 先行タイプ（逃）で得点上位3位以内の先頭がいくつのラインにいるか
        n_strong_nige.append(sum(1 for l in lines if len(l) >= 1 and g["style"].get(l[0]) == "逃" and g.pt_rank.get(l[0], 9) <= 3))
    E["pos"], E["ls"], E["nlines"], E["lead_rank"], E["lead_style"], E["n_strong_nige"], E["line_idx"] = pos, ls, nl, lead_rank, lead_style, n_strong_nige, lid
    E["single"] = (E.ls == 1) | E.comment.fillna("").str.contains("単騎|１人|一人|1人")
    E = E.merge(R[["race_id", "date", "venue", "grade", "class", "race_type", "day_index", "race_no", "entries_number"]], on="race_id")
    E["top3"] = E["rank"].between(1, 3); out.append(E)
    print(i0, len(races), flush=True)
F = pd.concat(out); F = F[F.p3.notna()]
F.to_pickle(OUT); print(len(F), F.race_id.nunique())
