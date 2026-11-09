"""切り口：ライン人数の組み合わせ（3-3-1、4-3、3-2-2 など）と、1着の選手のラインの人数。大きいラインが有利すぎ／不利すぎに買われていないか。
あわせて、今日の候補 U（級班2種類以上）・V（最終日の前日）・W（400m）を「残りとの差」の基準で見直す（判定は y4 で行う。ここでは参考）。"""
import sys, json
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro&immutable=1", uri=True)
L = pd.read_sql("SELECT race_id, line_json FROM races WHERE date >= '20250201'", con)
def comp(s):
    try:
        ls = [sum(len(x["numbers"]) for x in l["entries"]) for l in json.loads(s or "[]")]
        return "-".join(str(v) for v in sorted(ls, reverse=True)), max(ls) if ls else np.nan
    except Exception:
        return "", np.nan
cc = L.line_json.map(comp); L["comp"] = cc.str[0]; L["maxl"] = cc.str[1]
T["comp"] = T.race_id.map(L.set_index("race_id").comp); T["maxl"] = T.race_id.map(L.set_index("race_id").maxl)
r0ls = pd.to_numeric(T.r0_ls, errors="coerce")
top_comps = T.drop_duplicates("race_id").comp.value_counts().head(8).index.tolist()
conds = {f"並び {k}": T.comp == k for k in top_comps}
conds.update({"4人以上のラインがある": T.maxl >= 4, "1着のラインが4人以上": r0ls >= 4, "1着のラインが3人": r0ls == 3, "1着のラインが2人": r0ls == 2, "1着が1人（単騎）": r0ls == 1})
c, c2 = report(sys.argv[1], "ライン人数の組み合わせ", "並び＝各ラインの人数を大きい順（例 3-3-1）。r0_ls＝1着の選手のラインの人数。", conds)
# 今日の候補の見直し（参考）
con2 = con
E = pd.read_sql("SELECT e.race_id, e.class AS c, e.grp AS g FROM entries e JOIN races r USING(race_id) WHERE r.date >= '20250201' AND e.absent = 0", con2)
E["rk"] = pd.to_numeric(E.c, errors="coerce") * 10 + pd.to_numeric(E.g, errors="coerce")
nk = E.groupby("race_id").rk.nunique(); ND = pd.read_sql("SELECT cup_id, MAX(day_index) nd FROM races GROUP BY cup_id", con2).set_index("cup_id").nd
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
tx = T[T.is_top]
chk = {"U 級班2種類以上": tx.race_id.map(nk) >= 2, "V 最終日の前日": (tx.day_index == tx.cup_id.map(ND) - 1) & (tx.cup_id.map(ND) >= 3), "W 400m": ~tx.venue.isin(S333 | S500)}
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 参考：今日の事前登録U・V・Wを「残りとの差」で見直し（一番の目）\n")
    for nm, m in chk.items():
        a_, b_ = summ(tx[m]), summ(tx[~m])
        x, y = tx[m & (per(tx.date) == "探す")].ret, tx[~m & (per(tx.date) == "探す")].ret
        t_ = (x.mean() - y.mean()) / np.sqrt(x.var(ddof=1) / len(x) + y.var(ddof=1) / len(y))
        f.write(f"- {nm}: 当てはまる {fmt(a_)} ／ 当てはまらない {fmt(b_)} ／ 差のt={t_:.1f}\n")
print("候補", len(c), "参考", len(c2))
