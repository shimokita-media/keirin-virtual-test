"""選手コメントで3連単枠・一番の目を分けて比べる（最終オッズ、探す→未使用）"""
import json, re, sqlite3, numpy as np, pandas as pd
c = pd.read_pickle("card_top.pkl"); B = pd.read_pickle("card_B.pkl")
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = B.race_id.unique().tolist(); E = []; L = {}
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900]))
    E.append(pd.read_sql(f"SELECT race_id, number, name, comment cm FROM entries WHERE absent=0 AND race_id IN ({q})", con, params=ids[i:i+900]))
    L.update(dict(con.execute(f"SELECT race_id, line_json FROM races WHERE race_id IN ({q})", ids[i:i+900])))
E = pd.concat(E); EI = E.set_index(["race_id", "number"])
ATTACK = re.compile(r"先行|先手|逃げ|主導権|積極|前を取|前々|前で"); MAKURI = re.compile(r"捲り|まくり"); JIZAI = re.compile(r"自在|決めず|取れた位置|何でも|流れ"); JIRIKI = re.compile(r"自力|自分で")
def lead_type(s):
    s = s or ""
    if ATTACK.search(s): return "先行・前々"
    if MAKURI.search(s): return "捲り"
    if JIZAI.search(s): return "自在・決めず"
    if JIRIKI.search(s): return "自力だけ"
    return "その他"
def feats(row):
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(L.get(row.race_id) or "[]")]
    d = int(row.combo.split("-")[2]); main = next((l for l in lines if d in l), [])
    if len(main) < 2: return pd.Series([np.nan] * 6)
    cm = lambda n: str(EI.cm.get((row.race_id, n), "") or ""); nm = lambda n: str(EI.name.get((row.race_id, n), "") or "")
    lead, ban = main[0], main[1]
    lt = lead_type(cm(lead))
    sur = nm(lead)[:2]
    ban_follow = "先頭の名前あり" if sur and sur in cm(ban) else ("決めず・自力" if (JIZAI.search(cm(ban)) or JIRIKI.search(cm(ban))) else "その他")
    third = "3番手と明記" if len(main) >= 3 and re.search(r"[3３]番手", cm(main[2])) else ("名前あり" if len(main) >= 3 and nm(ban)[:2] and nm(ban)[:2] in cm(main[2]) else "その他")
    oth_attack = sum(1 for l in lines if l is not main and len(l) >= 2 and ATTACK.search(cm(l[0])))
    hoju = float(any("補充" in cm(n) for n in main))
    return pd.Series([lt, ban_follow, third, min(oth_attack, 2), hoju, len(main)])
for nm_, D in (("3連単枠", B), ("一番の目", c)):
    D[["先頭のコメント", "番手のコメント", "3番手のコメント", "ほかの先頭の先行宣言", "補充出走", "人数"]] = D.apply(feats, axis=1)
    print(f"\n## {nm_}")
    def show(lab, b):
        print(f"- {lab}: " + " ｜ ".join(f"{k} 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}({len(g)})" for k, g in D.groupby(b, observed=True) if len(g) >= 60))
    show("ラインの先頭のコメント", D["先頭のコメント"]); show("番手のコメント", D["番手のコメント"]); show("3番手のコメント", D["3番手のコメント"])
    show("ほかのラインの先頭で「先行・前々」と言う人の数", D["ほかの先頭の先行宣言"].map({0: "0人", 1: "1人", 2: "2人以上"}))
    show("ラインに補充出走の選手", D["補充出走"].map({1.0: "いる", 0.0: "いない"}))
    D["結束"] = (D["番手のコメント"] == "先頭の名前あり") & (D["3番手のコメント"] != "その他")
    show("番手が先頭の名前・3番手も明記（結束が固い）", D["結束"].map({True: "はい", False: "いいえ"}))
c.to_pickle("com_top.pkl"); B.to_pickle("com_B.pkl")
