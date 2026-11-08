"""3連単枠の買い目を、ラインの先頭の S（主導権）・B（バック）で分けて比べる。最終オッズ。探す期間と未使用期間（25/5/30〜10/11）で別々に"""
import json, sqlite3
exec(open("robust_sel2.py", encoding="utf-8").read().split("lo_ = (c.r0_pos")[0])
c_ = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = B.race_id.unique().tolist(); E = []; L = {}
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900]))
    E.append(pd.read_sql(f"SELECT race_id, number, n_standing S, n_back B, style FROM entries WHERE absent=0 AND race_id IN ({q})", c_, params=ids[i:i+900]))
    L.update(dict(c_.execute(f"SELECT race_id, line_json FROM races WHERE race_id IN ({q})", ids[i:i+900])))
E = pd.concat(E); SB = {(r, n): (s, b) for r, n, s, b, _ in E.itertuples(index=False)}
def feats(row):
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(L.get(row.race_id) or "[]")]
    third = int(row.combo.split("-")[2]); main = next((l for l in lines if third in l), None)
    if not main: return pd.Series([np.nan] * 5)
    lead = main[0]; others = [l[0] for l in lines if l is not main and len(l) >= 2]
    ls, lb = SB.get((row.race_id, lead), (np.nan, np.nan)); ob = [SB.get((row.race_id, o), (0, 0))[1] for o in others]; os_ = [SB.get((row.race_id, o), (0, 0))[0] for o in others]
    allb = [SB.get((row.race_id, l[0]), (0, 0))[1] for l in lines]
    return pd.Series([lb, ls, max(ob) if ob else 0, max(os_) if os_ else 0, float(lb >= max(allb)) if allb else np.nan])
for nm, D in (("3連単枠", B), ("一番の目", c)):
    D[["lB", "lS", "oB", "oS", "topB"]] = D.apply(feats, axis=1)
    D["per"] = np.where(D.date.between("20250530", "20251011"), "未使用", "探す")
    print(f"\n## {nm}（探す {(D.per=='探す').sum()}点・未使用 {(D.per=='未使用').sum()}点）")
    cuts = {"ラインの先頭のB": ("lB", [-1, 0, 4, 10, 999], ["0回", "1〜4回", "5〜10回", "11回以上"]),
            "ラインの先頭のS": ("lS", [-1, 0, 3, 8, 999], ["0回", "1〜3回", "4〜8回", "9回以上"]),
            "ほかのラインの先頭のB（一番多い人）": ("oB", [-1, 0, 4, 10, 999], ["0回", "1〜4回", "5〜10回", "11回以上"]),
            "ほかのラインの先頭のS（一番多い人）": ("oS", [-1, 0, 3, 8, 999], ["0回", "1〜3回", "4〜8回", "9回以上"])}
    for lab, (col, bins, names) in cuts.items():
        b = pd.cut(D[col], bins, labels=names)
        print(f"- {lab}: " + " ｜ ".join(f"{k} 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}({len(g)})" for k, g in D.groupby(b, observed=True)))
    print(f"- 先頭のBがレースで一番多い: " + " ｜ ".join(f"{'はい' if k else 'いいえ'} 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}({len(g)})" for k, g in D.groupby(D.topB == 1)))
    D["adv"] = D.lB - D.oB
    b = pd.cut(D.adv, [-999, -5, -1, 0, 4, 999], labels=["ほかの先頭のほうが5回以上多い", "1〜4回多い", "同じ", "自分の先頭が1〜4回多い", "5回以上多い"])
    print(f"- 先頭のB − ほかの先頭のB: " + " ｜ ".join(f"{k} 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}({len(g)})" for k, g in D.groupby(b, observed=True)))
c.to_pickle("sb_top.pkl"); B.to_pickle("sb_B.pkl")
