exec(open("robust_sel2.py", encoding="utf-8").read().split("def run(")[0])
def mon(g): return g.groupby("m").ret.agg(["sum", "size"])
P = {"3連単 一番の目×法則3つ以上": [TRI["一番の目×法則3つ以上"]], "3連単 一番の目×10〜30倍": [TRI["一番の目×10〜30倍"]], "3連単 一番の目": [TRI["一番の目"]],
     "ワイドA×10倍未満": [WID["ワイドA×10倍未満"]],
     "組み合わせ：3連単(法則3つ以上)＋ワイドA×10倍未満": [TRI["一番の目×法則3つ以上"], WID["ワイドA×10倍未満"]],
     "組み合わせ：3連単(10〜30倍)＋ワイドA×10倍未満": [TRI["一番の目×10〜30倍"], WID["ワイドA×10倍未満"]],
     "組み合わせ：3連単(10〜30倍)＋形のワイド": [TRI["一番の目×10〜30倍"], WID["形のワイド"]]}
for k, gs in P.items():
    s = sum(mon(g)["sum"].reindex(sorted(set(TRI["一番の目"].m))).fillna(0) for g in gs); n = sum(mon(g)["size"].reindex(sorted(set(TRI["一番の目"].m))).fillna(0) for g in gs)
    mr = (s / n.replace(0, np.nan)).dropna(); inv = n.sum()
    print(f"- {k}: 通し{s.sum()/inv:.0%} 1か月の点数{inv/len(mr):.0f} 100%超えの月{(mr>=1).sum()}/{len(mr)} 一番悪い月{mr.min():.0%} 2番目{mr.nsmallest(2).iloc[-1]:.0%}")
# 法則3つ以上の61%の月の中身
g = TRI["一番の目×法則3つ以上"]; x = g[g.m == "202607"]; print("26/07 法則3つ以上:", len(x), "点 当たり", int((x.ret > 0).sum()), "本")
