"""月ごとに100%を割りにくくする組み方の比較（16か月・最終オッズ）。各買い方の 月ごとの投資・払戻 を重みで足す"""
import sqlite3
exec(open("robust_sel2.py", encoding="utf-8").read().split("def run(")[0])
t3 = TRI["一番の目×法則3つ以上"].copy(); t1 = TRI["一番の目"].copy()
# 一番の目と同じ3人の3連複1点
c_ = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = t1.race_id.unique().tolist(); pay = []
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900])); pay.append(pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連複' AND race_id IN ({q})", c_, params=ids[i:i+900]))
pay = pd.concat(pay).drop_duplicates(["race_id", "combo"]).set_index(["race_id", "combo"]).payout
trio = t1.copy(); trio["combo"] = trio.combo.str.split("-").map(lambda a: "-".join(sorted(a, key=int)))
trio["ret"] = [pay.get((r, x), 0) / 100 for r, x in zip(trio.race_id, trio.combo)]
LEG = {"3連単(法則3つ以上)": t3, "3連単(一番の目)": t1, "3連単(10〜30倍)": TRI["一番の目×10〜30倍"], "3連複(一番の目の3人)": trio,
       "ワイドA×10倍未満": WID["ワイドA×10倍未満"], "ワイドA": WID["ワイドA"], "形のワイド": WID["形のワイド"], "同ライン先頭-3番手×割安": WID["同ライン先頭-3番手×割安×20倍未満"]}
months = sorted(set(t1.m) | set(WID["ワイドA"].m))
MS = {k: g.groupby("m").ret.agg(["sum", "size"]).reindex(months).fillna(0) for k, g in LEG.items()}
for k in LEG:
    g = MS[k]; mr = (g["sum"] / g["size"].replace(0, np.nan)).dropna(); print(f"  単独 {k}: {g['sum'].sum()/g['size'].sum():.0%} 最悪の月{mr.min():.0%} 100%超え{(mr>=1).sum()}/{len(mr)} 1か月{g['size'].sum()/len(mr):.0f}点")
def mix(w):
    s = sum(MS[k]["sum"] * v for k, v in w.items()); n = sum(MS[k]["size"] * v for k, v in w.items())
    mr = (s / n.replace(0, np.nan)).dropna(); net = (s - n) * 100
    return s.sum() / n.sum(), mr.min(), (mr >= 1).sum(), len(mr), net.sum(), n.sum() / len(mr) * 100
print("\n| 組み方（1点あたりの単位） | 通し | 一番悪い月 | 100%超えの月 | 1か月の投資 | 16か月の収支 |\n|---|---|---|---|---|---|")
W8 = {
 "3連単(法則3つ以上)1 ＋ ワイドA×10倍未満1": {"3連単(法則3つ以上)": 1, "ワイドA×10倍未満": 1},
 "3連単(法則3つ以上)1 ＋ ワイドA×10倍未満2": {"3連単(法則3つ以上)": 1, "ワイドA×10倍未満": 2},
 "3連単(法則3つ以上)1 ＋ ワイドA1": {"3連単(法則3つ以上)": 1, "ワイドA": 1},
 "3連単(法則3つ以上)1 ＋ ワイドA×10倍未満1 ＋ 形のワイド1": {"3連単(法則3つ以上)": 1, "ワイドA×10倍未満": 1, "形のワイド": 1},
 "3連単(法則3つ以上)1 ＋ 3連複1 ＋ ワイドA×10倍未満1": {"3連単(法則3つ以上)": 1, "3連複(一番の目の3人)": 1, "ワイドA×10倍未満": 1},
 "3連単(一番の目)1 ＋ 3連複(同じ3人)1": {"3連単(一番の目)": 1, "3連複(一番の目の3人)": 1},
 "3連単(一番の目)1 ＋ ワイドA×10倍未満1": {"3連単(一番の目)": 1, "ワイドA×10倍未満": 1},
 "3連単(法則3つ以上)1 ＋ 同ライン先頭-3番手×割安1 ＋ ワイドA×10倍未満1": {"3連単(法則3つ以上)": 1, "同ライン先頭-3番手×割安": 1, "ワイドA×10倍未満": 1},
 "【締切前に崩れにくい形だけ】3連単(法則3つ以上)1 ＋ 形のワイド1": {"3連単(法則3つ以上)": 1, "形のワイド": 1},
 "【締切前に崩れにくい形だけ】3連単(一番の目)1 ＋ 3連複1 ＋ 形のワイド1": {"3連単(一番の目)": 1, "3連複(一番の目の3人)": 1, "形のワイド": 1},
}
for k, w in W8.items():
    r, lo_, ok, n, net, inv = mix(w); print(f"| {k} | {r:.0%} | {lo_:.0%} | {ok}/{n} | 約{inv:,.0f}円 | {net:+,.0f}円 |")
