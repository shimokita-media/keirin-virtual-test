"""3連単枠の買い目を、上がりタイム（agari_avg、小さいほど速い）で分けて比べる。最終オッズ。探す期間と未使用期間（25/5/30〜10/11）"""
import json, sqlite3, numpy as np, pandas as pd
c = pd.read_pickle("sb_top.pkl"); B = pd.read_pickle("sb_B.pkl")
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = B.race_id.unique().tolist(); E = []; L = {}
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900]))
    E.append(pd.read_sql(f"SELECT race_id, number, agari_avg a, agari_best ab FROM entries WHERE absent=0 AND race_id IN ({q})", con, params=ids[i:i+900]))
    L.update(dict(con.execute(f"SELECT race_id, line_json FROM races WHERE race_id IN ({q})", ids[i:i+900])))
E = pd.concat(E); E["rk"] = E.groupby("race_id").a.rank(method="min"); AG = {(r, n): (a, k) for r, n, a, ab, k in E.itertuples(index=False)}
def feats(row):
    a, b, d = map(int, row.combo.split("-"))
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(L.get(row.race_id) or "[]")]
    main = next((l for l in lines if d in l), [])
    others = [n for l in lines if l is not main for n in l]
    rk = lambda n: AG.get((row.race_id, n), (np.nan, np.nan))[1]
    main_back = [rk(n) for n in main[1:]]  # 番手・3番手
    oth = [rk(n) for n in others]
    return pd.Series([rk(a), rk(d), np.nanmin(main_back) if main_back else np.nan, np.nanmean(main_back) if main_back else np.nan, np.nanmin(oth) if oth else np.nan,
                      AG.get((row.race_id, d), (np.nan,))[0]])
for nm, D in (("3連単枠", B), ("一番の目", c)):
    D[["a1", "a3", "mb_min", "mb_mean", "oth_min", "a3_sec"]] = D.apply(feats, axis=1)
    print(f"\n## {nm}（探す {(D.per=='探す').sum()}点・未使用 {(D.per=='未使用').sum()}点）")
    def show(lab, b):
        print(f"- {lab}: " + " ｜ ".join(f"{k} 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}({len(g)})" for k, g in D.groupby(b, observed=True)))
    show("1着の選手の上がりの速さ（レース内の順位）", pd.cut(D.a1, [0, 1, 3, 5, 99], labels=["1位", "2〜3位", "4〜5位", "6位以下"]))
    show("3着の選手の上がりの速さ", pd.cut(D.a3, [0, 2, 4, 6, 99], labels=["1〜2位", "3〜4位", "5〜6位", "7位以下"]))
    show("ラインの番手・3番手で一番速い人の順位", pd.cut(D.mb_min, [0, 1, 3, 5, 99], labels=["1位", "2〜3位", "4〜5位", "6位以下"]))
    show("ほかのラインで一番速い人の順位", pd.cut(D.oth_min, [0, 1, 2, 3, 99], labels=["1位（ほかのラインに一番速い人）", "2位", "3位", "4位以下"]))
    D["agB"] = (D.mb_min < D.oth_min)
    show("ラインの番手・3番手が、ほかのラインの誰よりも速い", D.agB.map({True: "はい", False: "いいえ"}))
    D["both"] = (D.topB == 1) & D.agB
    show("先頭のBが一番多い × 番手・3番手がほかより速い", D.both.map({True: "はい", False: "いいえ"}))
c.to_pickle("ag_top.pkl"); B.to_pickle("ag_B.pkl")
