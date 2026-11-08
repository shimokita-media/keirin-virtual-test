"""最新データ（〜2025/10/11）で、1か月を隠して選ぶ学習をやり直す（3連単とワイド）。最終オッズ。基準＝平均の回収率−0.5×月ごとのブレ"""
import numpy as np, pandas as pd
exec(open("top1.py", encoding="utf-8").read().split("blk = lambda")[0].replace('("fresh", "fresh2", "fresh3", "fresh4")', '("fresh", "fresh2", "fresh3", "fresh4", "fresh5")').replace('(T.date >= "20250928")', '(T.date >= "20251012")'))
c = top.copy(); c["m"] = c.date.str[:6]; B["m"] = B.date.str[:6]
lo_ = (c.r0_pos == 0) & (c.r1_pos == 1) & (c.r2_pos == 2); bs_ = (c.r0_pos == 1) & (c.r1_pos == 0) & (c.r2_pos == 2); nf = c.r0_mk_rank != 1
TRI = {"3連単枠ぜんぶ": B, "一番の目": c, "一番の目×ライン順": c[lo_], "一番の目×番→先→3": c[bs_], "一番の目×(ライン順か番→先→3)": c[lo_ | bs_],
       "一番の目×1着が一番人気以外": c[nf], "一番の目×ライン順×1着が一番人気以外": c[lo_ & nf], "一番の目×法則2つ以上": c[c.nr >= 2], "一番の目×法則3つ以上": c[c.nr >= 3],
       "一番の目×10〜30倍": c[c.odds.between(10, 30)], "一番の目×ライン順×10〜30倍": c[lo_ & c.odds.between(10, 30)], "一番の目×2日目以降": c[c.day_index >= 2],
       "一番の目×9車": c[c.entries_number >= 9], "一番の目×G戦": c[c.G == 1], "一番の目×S級": c[c.S == 1]}
K = "C:/Users/take0/.claude/keirin/out/"
W = pd.concat([pd.read_pickle("wide_all3.pkl")] + [pd.read_pickle(K + f + "/wide.pkl") for f in ("fresh", "fresh2", "fresh3", "fresh4", "fresh5")]).drop_duplicates(["race_id", "combo"])
W = W[(W["class"] != "L級") & (W.odds <= 50) & (W.date <= "20260831") & ~((W.date >= "20251012") & (W.date < "20260101"))].copy(); W["m"] = W.date.str[:6]
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0); W["ev0"] = W.pw * W.odds; W["fav_pw"] = W.groupby("race_id").pw.transform("max")
lo, hi = W[["a_pos", "b_pos"]].min(axis=1), W[["a_pos", "b_pos"]].max(axis=1); G = W.grade.astype(str).str.startswith("G")
WID = {"形のワイド": W[W.same & (lo == 0) & (hi == 2) & W.odds.between(3, 20) & ((W.entries_number >= 9) | G)],
       "ワイドA": W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (W.fav_pw < 0.6)],
       "ワイドA×10倍未満": W[(W.ev0 >= 1.0) & (W.odds < 10) & W.same & (W.fav_pw < 0.6)],
       "同ライン先頭-番手×割安×20倍未満": W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (lo == 0) & (hi == 1)],
       "同ライン番手-3番手×割安×20倍未満": W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (lo == 1) & (hi == 2)],
       "同ライン先頭-3番手×割安×20倍未満": W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (lo == 0) & (hi == 2)],
       "割安×20倍未満（形なし）": W[(W.ev0 >= 1.0) & (W.odds < 20)]}
def run(CAND, title):
    M = {k: g.groupby("m").ret.agg(["sum", "size"]) for k, g in CAND.items()}
    months = sorted(set().union(*[set(g.index) for g in M.values()]))
    print(f"\n# {title}（{len(months)}か月）\n## 全期間の参考")
    for k, g in M.items():
        g = g.reindex(months).fillna(0); mr = g["sum"] / g["size"].replace(0, np.nan)
        print(f"- {k}: {g['sum'].sum()/g['size'].sum():.0%}（{int(g['size'].sum())}点） 100%超えの月 {(mr>=1).sum()}/{mr.notna().sum()}")
    def score(k, ms):
        g = M[k].reindex(ms).fillna(0); mr = (g["sum"] / g["size"].replace(0, np.nan)).dropna()
        return g["sum"].sum() / max(g["size"].sum(), 1) - 0.5 * mr.std()
    rows = []
    for h in months:
        rest = [x for x in months if x != h]; best = max(CAND, key=lambda k: score(k, rest))
        g = M[best].reindex([h]).fillna(0); rows.append((h, best, g["size"].sum(), g["sum"].sum()))
    R = pd.DataFrame(rows, columns=["月", "買い方", "inv", "ret"]); mr = R.ret / R.inv.replace(0, np.nan)
    print(f"## 1か月を隠して選んだ場合 → 隠した月の通し **{R.ret.sum()/R.inv.sum():.0%}**、100%超えの月 {(mr>=1).sum()}/{mr.notna().sum()}、払戻5%減なら {R.ret.sum()*0.95/R.inv.sum():.0%}")
    print("   月ごと:", " ".join(f"{h[2:4]}/{h[4:]}:{v:.0%}" for h, v in zip(R.月, mr)))
    print("   選ばれた回数:", R.買い方.value_counts().to_dict())
run(TRI, "3連単"); run(WID, "ワイド")
