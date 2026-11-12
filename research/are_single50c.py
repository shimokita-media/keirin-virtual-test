"""的中率50%を保ったまま回収率を上げられるか：レースの絞り込み（9車・ライン数・単騎の脚質・グレード）×「単騎1着の総流し＋人気上位N点」。N とレースの絞り込みは探索期間で決め、2024年でそのまま確かめる"""
import numpy as np, pandas as pd, itertools
exec(open("research/are_single50b.py", encoding="utf-8").read().split("pay1 = t1")[0])
race1 = race.set_index("race_id")[["n", "nlines", "grade"]]
a24r = a24.drop_duplicates("race_id").set_index("race_id")[["entries_number", "nlines", "grade"]].rename(columns={"entries_number": "n"})
st1 = R[R.single == True].groupby("race_id")["style"].apply(lambda s: "追" if (s == "追").any() else "他")
st2 = a24[a24.single == True].groupby("race_id")["style"].apply(lambda s: "追" if (s == "追").any() else "他")
for t, rr, st in [(t1, race1, st1), (t2, a24r, st2)]:
    t[["n", "nlines", "grade"]] = rr.reindex(t.race_id).values; t["sst"] = st.reindex(t.race_id).values
filters = {"全部": lambda t: t.race_id.notna(), "9車": lambda t: t.n == 9, "4ライン以上": lambda t: t.nlines >= 4, "9車×4ライン以上": lambda t: (t.n == 9) & (t.nlines >= 4),
           "単騎が追込": lambda t: t.sst == "追", "単騎が追込×4ライン以上": lambda t: (t.sst == "追") & (t.nlines >= 4), "単騎が追込×9車": lambda t: (t.sst == "追") & (t.n == 9),
           "F1・F2": lambda t: t.grade.isin(["FI", "FII"]), "G3以上": lambda t: ~t.grade.isin(["FI", "FII"])}
rows = []
for name, f in filters.items():
    a, b = t1[f(t1)], t2[f(t2)]
    if len(a) < 100: continue
    Xa, Xb = X1[X1.race_id.isin(a.race_id)], X2[X2.race_id.isin(b.race_id)]
    for N in range(0, 80, 2):
        fa = flat(Xa[Xa.s1 | (Xa.rk <= N)], a)
        if fa["的中率"] >= 50: break
    fb = flat(Xb[Xb.s1 | (Xb.rk <= N)], b)
    rows.append((name, N, len(a), fa["的中率"], fa["回収率"], len(b), fb["的中率"], fb["回収率"]))
print(pd.DataFrame(rows, columns=["レースの絞り込み", "人気上位N点", "探索R", "探索的中%", "探索回収%", "2024R", "2024的中%", "2024回収%"]).to_string())
print("試した絞り込み", len(rows))
