"""切り口（構造の違う⑪）：開催の混み具合。同じ時間帯に締切が重なるレースが多いと、1レースあたりのお金と注目が減り、倍率が不正確（歪みが大きい）になるか。
重なり＝そのレースの締切の前後5分以内に締切がある他場のレース数（全場の races から数える）。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
RA = pd.read_pickle(K + "out/side_races.pkl")[["race_id", "date", "venue", "close_at"]].dropna()
RA["ca"] = pd.to_numeric(RA.close_at, errors="coerce"); RA = RA.dropna(subset=["ca"]).sort_values("ca")
ca = RA.ca.to_numpy()
lo = np.searchsorted(ca, ca - 300, "left"); hi = np.searchsorted(ca, ca + 300, "right")
RA["overlap"] = hi - lo - 1
nven = RA.groupby("date").venue.nunique()
T["overlap"] = T.race_id.map(RA.set_index("race_id").overlap); T["nven"] = T.date.map(nven)
ov = T.overlap
conds = {"締切の重なり0〜1レース": ov <= 1, "重なり2〜3": ov.between(2, 3), "重なり4〜5": ov.between(4, 5), "重なり6以上": ov >= 6,
         "その日の開催が6場以下": T.nven <= 6, "その日の開催が7〜9場": T.nven.between(7, 9), "その日の開催が10場以上": T.nven >= 10,
         "重なり6以上×30倍以下": (ov >= 6) & (T.odds <= 30), "重なり0〜1×30倍以下": (ov <= 1) & (T.odds <= 30)}
c, c2 = report(sys.argv[1], "開催の混み具合（締切の重なり・その日の開催場数）", "重なり＝締切の前後5分以内に締切がある他のレースの数。", conds)
# 歪みの大きさ：倍率帯ごとの 実際÷見込み のばらつき
x = T[per(T.date) == "探す"].copy(); x["hit"] = (x.ret > 0).astype(float); x["imp"] = 0.75 / x.odds
x["band"] = pd.cut(x.odds, [0, 5, 10, 20, 50, 100, 300]); x["ovb"] = pd.cut(x.overlap, [-1, 1, 3, 5, 99], labels=["0〜1", "2〜3", "4〜5", "6以上"])
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 重なりごとの 実際÷見込み（倍率帯別・探す期間）。1.0から離れるほど倍率が不正確\n\n")
    tb = x.groupby(["ovb", "band"], observed=True).apply(lambda d: d.hit.sum() / d.imp.sum()).unstack()
    f.write(tb.round(2).to_string() + "\n")
    f.write("\n各行の1.0からのずれの平均：" + ", ".join(f"{k} {abs(tb.loc[k] - tb.loc[k].mean()).mean():.3f}" for k in tb.index) + "\n")
print("候補", len(c), "参考", len(c2))
