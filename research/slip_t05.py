"""締切直前（T05）で判断すると、1分前（T1）より目のずれ（最後の倍率の動き）がどれだけ減るか。
本番DBの写し out/live_local/keirin.sqlite（このPCの本番DBを sqlite の backup で写したもの）を読む。記録には触らない。
使い方：python -X utf8 research/slip_t05.py reports/slip_t05.md"""
import sqlite3, sys, numpy as np, pandas as pd

DB = "out/live_local/keirin.sqlite"
out = sys.argv[1] if len(sys.argv) > 1 else "reports/slip_t05.md"
con = sqlite3.connect(DB)
TRI = "3連単"
races = pd.read_sql("select race_id, close_at from races", con)
o = pd.read_sql(f"""select race_id, combo, phase, odds, fetched_at from odds
                   where bet_type='{TRI}' and phase in ('T1','T05','POST') and odds>0""", con)
o = o.drop_duplicates(["race_id", "combo", "phase"], keep="last")
w = o.pivot_table(index=["race_id", "combo"], columns="phase", values="odds").dropna().reset_index()
o["ts"] = pd.to_datetime(o.fetched_at, utc=True, format="ISO8601").map(lambda x: x.timestamp())
ft = o.groupby(["race_id", "phase"]).ts.max().unstack()
ft = ft.join(races.set_index("race_id"))
pay = pd.read_sql(f"select race_id, combo, payout from payouts where bet_type='{TRI}'", con)
hit = set(zip(pay.race_id, pay.combo))
w["hit"] = [(r, c) in hit for r, c in zip(w.race_id, w.combo)]
w = w[w.race_id.isin(pay.race_id)]

L = []
p = L.append
p("# 締切直前（T05）で判断したら目のずれは減るか（本番DB・3連単）\n")
p(f"- 3連単の名前: {TRI}。T1・T05・確定（POST）の3つがそろったレース: **{w.race_id.nunique()}R**・{len(w):,}通り")
for ph in ("T1", "T05"):
    s_ = (ft["close_at"].astype(float) - ft[ph]).dropna()
    p(f"- {ph} を取った時刻：締切の {s_.quantile(.1):.0f}〜{s_.quantile(.9):.0f} 秒前（中央値 {s_.median():.0f} 秒）")
p("")
# 1) 倍率の動きの大きさ
for lim in (30, 300):
    s = w[w.T1 <= lim]
    a = np.log(s.POST / s.T1); b = np.log(s.POST / s.T05)
    p(f"## {lim}倍以下（T1の倍率で）: {len(s):,}通り")
    p(f"| | T1→確定 | T05→確定 |\n|---|---|---|")
    p(f"| 倍率の動きの大きさ（対数の平均絶対値） | {a.abs().mean():.3f} | {b.abs().mean():.3f} |")
    p(f"| 20%以上縮んだ目の割合 | {(s.POST/s.T1<0.8).mean():.1%} | {(s.POST/s.T05<0.8).mean():.1%} |")
    p(f"| 20%以上伸びた目の割合 | {(s.POST/s.T1>1.2).mean():.1%} | {(s.POST/s.T05>1.2).mean():.1%} |")
    p(f"| 最後の動きのうち T05 までに済んだ割合 | − | {1 - b.abs().mean()/a.abs().mean():.0%} |")
    p("")
# 2) 一番人気の目（レース内で一番低い倍率）がそろうか
def top(col):
    return w.loc[w.groupby("race_id")[col].idxmin(), ["race_id", "combo"]].set_index("race_id").combo
t1, t05, po = top("T1"), top("T05"), top("POST")
p("## 一番人気の目は確定と同じか")
p(f"- T1 の一番人気＝確定の一番人気: {(t1 == po).mean():.1%}　／　T05: {(t05 == po).mean():.1%}")
# 3) 「しきい値で選ぶ」ときのずれ：T1/T05 で 10倍以下・30倍以下・見込み比 などを満たすか
p("\n## しきい値で選ぶとき、確定の倍率で選んだ目と食い違う割合")
p("| 決まり | T1で選んだ点数 | T1の食い違い | T05の食い違い |\n|---|---|---|---|")
for lim in (10, 15, 30):
    fin = w.POST <= lim
    for ph in ("T1", "T05"):
        pass
    a = w.T1 <= lim; b = w.T05 <= lim
    mis1 = (a ^ fin).sum() / max(fin.sum(), 1); mis5 = (b ^ fin).sum() / max(fin.sum(), 1)
    p(f"| {lim}倍以下 | {a.sum():,} | {mis1:.1%} | {mis5:.1%} |")
# 4) 縮んだ目の当たり方（研究の「遅いお金」と同じ見方）と、T1で選んで確定で払われる損
p("\n## 判断してから確定までの倍率の動きと当たり（30倍以下）")
s = w[w.T1 <= 30].copy()
s["r"] = s.POST / s.T1
s["g"] = pd.cut(s.r, [0, 0.8, 0.95, 1.05, 1.2, 99], labels=["20%以上縮む", "5〜20%縮む", "ほぼ同じ", "5〜20%伸びる", "20%以上伸びる"])
g = s.groupby("g", observed=True).agg(n=("hit", "size"), h=("hit", "sum"), ret=("POST", lambda x: (x[s.loc[x.index, "hit"]]).sum()))
g["回収率"] = g.ret / g.n
g["当たり÷T1の見込み"] = g.h / s.groupby("g", observed=True).apply(lambda d: (0.75 / d.T1).sum())
p(g[["n", "h", "回収率", "当たり÷T1の見込み"]].to_markdown(floatfmt=".2f"))
# 5) 本番の記録（通知した2つ・一番の目）の目減り：判断時の倍率→確定
pr = pd.read_sql(f"""select race_id, phase, combo, ref_odds from predictions
                    where phase in ('B3E','B3V','B3T') and ref_odds>0""", con)
pr = pr.merge(w[["race_id", "combo", "T05", "POST", "hit"]], on=["race_id", "combo"], how="inner")
p("\n## 本番で記録した目：判断時（約1分前）の倍率 → 確定の倍率")
p("| 種類 | 点数 | 確定÷判断時（中央値） | 確定÷T05（中央値） | 当たり | 回収率（確定） |\n|---|---|---|---|---|---|")
for k, d in pr.groupby("phase"):
    p(f"| {k} | {len(d)} | {np.median(d.POST/d.ref_odds):.3f} | {np.median(d.POST/d.T05):.3f} | {int(d.hit.sum())} | {(d.POST*d.hit).sum()/len(d):.0%} |")
p("\n※ T05 は締切3〜42秒前の写し。T1 は締切56〜89秒前。確定は払戻の倍率。点数が少ないので傾向だけ")
open(out, "w", encoding="utf-8").write("\n".join(L))
print("\n".join(L))
