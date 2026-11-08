"""出走表の項目で3連単枠・一番の目を分けて比べる（最終オッズ、探す→未使用）"""
import json, sqlite3, numpy as np, pandas as pd
c = pd.read_pickle("ag_top.pkl"); B = pd.read_pickle("ag_B.pkl")
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = B.race_id.unique().tolist(); E = []; L = {}
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900]))
    E.append(pd.read_sql(f"""SELECT race_id, number, prefecture pf, age, grp, gear, race_point rp, n_front nf, n_stalker ns, n_closer nc, n_marker nm, recent_orders ro, comment cm
        FROM entries WHERE absent=0 AND race_id IN ({q})""", con, params=ids[i:i+900]))
    L.update(dict(con.execute(f"SELECT race_id, line_json FROM races WHERE race_id IN ({q})", ids[i:i+900])))
E = pd.concat(E)
def ro_mean(s):
    try: v = [x for x in json.loads(s or "[]")[:5] if isinstance(x, (int, float)) and x > 0]; return np.mean(v) if v else np.nan
    except Exception: return np.nan
E["form"] = E.ro.map(ro_mean)
EI = E.set_index(["race_id", "number"])
def feats(row):
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(L.get(row.race_id) or "[]")]
    d = int(row.combo.split("-")[2]); main = next((l for l in lines if d in l), [])
    g = lambda n, col: EI[col].get((row.race_id, n), np.nan)
    if len(main) < 2: return pd.Series([np.nan] * 11)
    pfs = [g(n, "pf") for n in main]
    same_pf = float(len(set(pfs)) == 1)
    lead, ban = main[0], main[1]; third = main[2] if len(main) >= 3 else np.nan
    rp_main = np.nanmean([g(n, "rp") for n in main]); others = [l for l in lines if l is not main and len(l) >= 2]
    rp_oth = max([np.nanmean([g(n, "rp") for n in l]) for l in others]) if others else np.nan
    form_main = np.nanmean([g(n, "form") for n in main]); form_all = np.nanmean([g(n, "form") for l in lines for n in l])
    return pd.Series([same_pf, g(lead, "nf"), g(ban, "nm"), (g(third, "nc") + g(third, "nm")) if third == third else np.nan, form_main - form_all,
                      g(lead, "gear"), rp_main - rp_oth if rp_oth == rp_oth else np.nan, g(lead, "age"), str(g(lead, "grp")), str(g(ban, "cm"))[:6], len(main)])
cols = ["同県", "先頭の逃げ", "番手のマーク", "3番手の差し+マーク", "調子の差", "先頭のギア", "得点の差", "先頭の年齢", "先頭の級班", "番手のコメント", "ラインの人数"]
for nm, D in (("3連単枠", B), ("一番の目", c)):
    D[cols] = D.apply(feats, axis=1)
    print(f"\n## {nm}")
    def show(lab, b):
        print(f"- {lab}: " + " ｜ ".join(f"{k} 探す{g[g.per=='探す'].ret.mean():.0%}・未使用{g[g.per=='未使用'].ret.mean():.0%}({len(g)})" for k, g in D.groupby(b, observed=True) if len(g) >= 80))
    show("ラインが全員同じ県", D["同県"].map({1.0: "同じ県", 0.0: "違う県"}))
    show("先頭の逃げ回数", pd.qcut(D["先頭の逃げ"], 3, labels=["少", "中", "多"], duplicates="drop"))
    show("番手のマーク回数", pd.qcut(D["番手のマーク"].rank(method="first"), 3, labels=["少", "中", "多"]))
    show("3番手の差し+マーク回数", pd.qcut(D["3番手の差し+マーク"].rank(method="first"), 3, labels=["少", "中", "多"]))
    show("ラインの最近の着順（レース平均との差、マイナス＝好調）", pd.cut(D["調子の差"], [-9, -1, 0, 1, 9], labels=["かなり好調", "やや好調", "やや不調", "不調"]))
    show("先頭のギア", pd.cut(D["先頭のギア"], [0, 3.85, 3.93, 9], labels=["〜3.85", "3.86〜3.93", "3.94〜"]))
    show("ラインの得点 − いちばん強いほかのライン", pd.cut(D["得点の差"], [-99, -3, 0, 3, 99], labels=["3点以上弱い", "少し弱い", "少し強い", "3点以上強い"]))
    show("先頭の年齢", pd.cut(D["先頭の年齢"], [0, 27, 33, 40, 99], labels=["〜27歳", "28〜33歳", "34〜40歳", "41歳〜"]))
    show("先頭の級班", D["先頭の級班"])
    show("ラインの人数", D["ラインの人数"])
c.to_pickle("card_top.pkl"); B.to_pickle("card_B.pkl")
