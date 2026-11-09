"""切り口：地元選手（開催場と同じ都道府県の選手）。地元の選手は人気を集めやすい（買われすぎ）か、地元で頑張る（実力以上に来る）か。
使い方: python -I -X utf8 research/angle_20261109_1545.py 出力.md"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
VP = {"函館": "北海道", "青森": "青森", "いわき平": "福島", "弥彦": "新潟", "前橋": "群馬", "取手": "茨城", "宇都宮": "栃木", "大宮": "埼玉", "西武園": "埼玉",
      "京王閣": "東京", "立川": "東京", "松戸": "千葉", "千葉": "千葉", "川崎": "神奈川", "平塚": "神奈川", "小田原": "神奈川", "伊東": "静岡", "静岡": "静岡",
      "名古屋": "愛知", "豊橋": "愛知", "岐阜": "岐阜", "大垣": "岐阜", "富山": "富山", "松阪": "三重", "四日市": "三重", "福井": "福井", "奈良": "奈良",
      "向日町": "京都", "和歌山": "和歌山", "岸和田": "大阪", "玉野": "岡山", "広島": "広島", "防府": "山口", "高松": "香川", "小松島": "徳島", "高知": "高知",
      "松山": "愛媛", "小倉": "福岡", "久留米": "福岡", "武雄": "佐賀", "佐世保": "長崎", "別府": "大分", "熊本": "熊本"}
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro&immutable=1", uri=True)
ids = T.race_id.unique()
E = pd.read_sql("SELECT race_id, number, prefecture FROM entries", con)
E = E[E.race_id.isin(set(ids))]
pref = dict(zip(zip(E.race_id, E.number), E.prefecture))
vp = T.venue.map(VP)
parts = T.combo.str.split("-", expand=True).astype(int)
for i in range(3):
    T[f"h{i}"] = [pref.get((r, n)) == v for r, n, v in zip(T.race_id, parts[i], vp)]
T["nh"] = T.h0.astype(int) + T.h1.astype(int) + T.h2.astype(int)
nh_race = E.assign(v=E.race_id.map(T.drop_duplicates("race_id").set_index("race_id").venue.map(VP))).assign(h=lambda d: d.prefecture == d.v).groupby("race_id").h.sum()
T["home_in_race"] = T.race_id.map(nh_race).fillna(0)
B2, top2 = T[T.in_B], T[T.is_top]
lo = T.odds <= 30
P("# 切り口：地元選手（開催場と同じ都道府県）\n")
P(f"地元選手がいるレースの割合：{(T.drop_duplicates('race_id').home_in_race > 0).mean():.0%}。回収率（点数）は 探す / ③ / ⑥。最終オッズ・各100円。\n")
P("| 条件 | 3連単全部 | 30倍以下 | 3連単枠 | 一番の目 |")
P("|---|---|---|---|---|")
rows = []
conds = {"1着が地元": T.h0, "2着が地元": T.h1, "3着が地元": T.h2, "地元0人": T.nh == 0, "地元1人": T.nh == 1, "地元2人以上": T.nh >= 2,
         "1着が地元×地元のいるレース": T.h0, "地元がいるレースで地元を含まない": (T.home_in_race > 0) & (T.nh == 0), "地元がいないレース": T.home_in_race == 0}
for nm, m in conds.items():
    gs = [T[m], T[m & lo], B2[m[B2.index]], top2[m[top2.index]]]
    P(f"| {nm} | " + " | ".join(fmt(summ(g)) for g in gs) + " |")
    for lab, g in zip(("全部", "30倍以下", "3連単枠", "一番の目"), gs): rows.append((nm, lab, summ(g)))
P("\n## 候補（探す t≥2.5 かつ 3期間とも100%超）")
c = [(a, b, s) for a, b, s in rows if s["探す"][2] >= 2.5 and all(s[k][1] > 1 for k in ("探す", "③", "⑥"))]
P("\n".join(f"- {a} × {b}: {fmt(s)}（t={s['探す'][2]:.1f}）" for a, b, s in c) or "- なし")
P("\n## 参考：3期間とも100%超（tは問わない）")
c2 = [(a, b, s) for a, b, s in rows if all(s[k][1] > 1 for k in ("探す", "③", "⑥"))]
P("\n".join(f"- {a} × {b}: {fmt(s)}（t={s['探す'][2]:.1f}）" for a, b, s in c2) or "- なし")
P("\n## 市場の見立てとのズレ（30倍以下・探す期間）：地元を含む目は、倍率から見込む当たり率に比べて実際どうか")
x = T[lo & (per(T.date) == "探す")].copy(); x["imp"] = 0.75 / x.odds; x["hit"] = (x.ret > 0).astype(float)
for nm, m in (("地元0人", x.nh == 0), ("地元1人", x.nh == 1), ("地元2人以上", x.nh >= 2), ("1着が地元", x.h0)):
    g = x[m]; P(f"- {nm}: 実際の当たり {g.hit.mean():.2%} ÷ 見込み {g.imp.mean():.2%} = {g.hit.mean() / g.imp.mean():.2f}（{len(g)}点）")
