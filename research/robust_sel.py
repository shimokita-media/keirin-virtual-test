"""1か月を隠して残り14か月で「平均が高く・月ごとのブレが小さい」買い方を選び、隠した月で答え合わせ（15回）。最終オッズ"""
import numpy as np, pandas as pd
exec(open("top1.py", encoding="utf-8").read().split("blk = lambda")[0])
top["m"] = top.date.str[:6]; B["m"] = B.date.str[:6]
c = top
two = []  # 一番の目＋1-2着入替
sw = c.combo.str.split("-").map(lambda a: f"{a[1]}-{a[0]}-{a[2]}")
S = T.set_index(["race_id", "combo"]).ret
sw_ret = pd.Series([S.get((r, x), 0.0) for r, x in zip(c.race_id, sw)], index=c.index)
lineord = (c.r0_pos == 0) & (c.r1_pos == 1) & (c.r2_pos == 2); notfav = c.r0_mk_rank != 1
CAND = {
 "3連単枠ぜんぶ": ("B", None), "一番の目": ("T", c.index == c.index), "一番の目×ライン順": ("T", lineord), "一番の目×1着が一番人気以外": ("T", notfav),
 "一番の目×(ライン順 または 1着が一番人気以外)": ("T", lineord | notfav), "一番の目×ライン順×1着が一番人気以外": ("T", lineord & notfav),
 "一番の目×法則2つ以上": ("T", c.nr >= 2), "一番の目×法則3つ以上": ("T", c.nr >= 3), "一番の目×9車": ("T", c.entries_number >= 9), "一番の目×2日目以降": ("T", c.day_index >= 2),
 "一番の目×20倍以下": ("T", c.odds <= 20), "一番の目×10〜30倍": ("T", c.odds.between(10, 30)), "一番の目×S級": ("T", c.S == 1), "一番の目×G戦": ("T", c.G == 1),
 "一番の目＋1-2着入替(2点)": ("T2", c.index == c.index),
}
# 月ごとの 投資・払戻 の表
M = {}
for k, (kind, mask) in CAND.items():
    if kind == "B": g = B.groupby("m").ret.agg(["sum", "size"])
    elif kind == "T": g = c[mask].groupby("m").ret.agg(["sum", "size"])
    else:
        x = c[mask].assign(r2=c.ret + sw_ret); g = x.groupby("m").agg(sum=("r2", "sum"), size=("r2", lambda v: 2 * len(v)))
    M[k] = g
months = sorted(set(B.m))
def score(k, ms):
    g = M[k].reindex(ms).fillna(0); roi = g["sum"].sum() / g["size"].sum(); mr = (g["sum"] / g["size"].replace(0, np.nan)).dropna()
    return roi - 0.5 * mr.std(), roi
print("## 全期間での各買い方（参考）：回収率・100%超えの月")
for k in CAND:
    g = M[k].reindex(months).fillna(0); mr = g["sum"] / g["size"].replace(0, np.nan)
    print(f"- {k}: {g['sum'].sum()/g['size'].sum():.0%}（1日{g['size'].sum()/T.date.nunique():.1f}点） 100%超えの月 {(mr>=1).sum()}/{mr.notna().sum()} 最低の月 {mr.min():.0%}")
print("\n## 1か月を隠して選ぶ → 隠した月の成績")
rows = []
for h in months:
    rest = [x for x in months if x != h]
    best = max(CAND, key=lambda k: score(k, rest)[0])
    g = M[best].reindex([h]).fillna(0); inv, ret = g["size"].sum(), g["sum"].sum()
    rows.append((h, best, inv, ret)); print(f"- {h[2:4]}/{h[4:]}: 選ばれた買い方「{best}」→ {ret/inv if inv else 0:.0%}（{int(inv)}点）")
R = pd.DataFrame(rows, columns=["月", "買い方", "inv", "ret"])
print(f"\n隠した月の通し: {R.ret.sum()/R.inv.sum():.0%}（{int(R.inv.sum())}点） 100%超えの月 {((R.ret/R.inv)>=1).sum()}/{len(R)}  払戻5%減なら {R.ret.sum()*0.95/R.inv.sum():.0%}")
print("選ばれた回数:", R.買い方.value_counts().to_dict())
