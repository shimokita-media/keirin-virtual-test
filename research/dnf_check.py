"""直近の落車・失格など（完走しなかった）レースの後、市場の見込みからずれるか（探す段階・確定オッズ）。
完走しなかった＝出走表で欠場でないのに着順がない（自分のデータ）、または recent_orders の 0。見込みは new_angles と同じく直す。
使い方: python -I -X utf8 research/dnf_check.py 出力.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); Q = pd.read_pickle(K + "out/rider_q.pkl"); T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date", "cup_id", "day_index", "close_at"]], on="race_id")
E = E[E.race_id.isin(set(R.race_id))]
rk = R.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])["rank"]
E["rank"] = rk.reindex(list(zip(E.race_id, E.number))).to_numpy()
E["dnf"] = E["rank"].isna()
E = E.sort_values(["player_id", "close_at"])
g = E.groupby("player_id")
E["prev_dnf"] = g.dnf.shift(1); E["prev_date"] = g.date.shift(1); E["prev_cup"] = g.cup_id.shift(1)
E["dnf_last3"] = g.dnf.transform(lambda s: s.shift(1).rolling(3, min_periods=1).max())
def z_last(s, k):
    try: v = json.loads(s) if isinstance(s, str) else list(s)
    except Exception: return np.nan
    return float(0 in v[-k:]) if len(v) else np.nan
E["ro0_1"] = E.recent_orders.map(lambda s: z_last(s, 1)); E["ro0_3"] = E.recent_orders.map(lambda s: z_last(s, 3))
E = E.merge(Q, on=["race_id", "number"])
E["y1"] = (E["rank"] == 1).astype(int); E["y3"] = (E["rank"] <= 3).astype(int)
for k, y in (("q1", "y1"), ("q3", "y3")):
    b = pd.qcut(E[k], 30, duplicates="drop"); f = E.groupby(b, observed=True)[y].sum() / E.groupby(b, observed=True)[k].sum()
    E[k] = E[k] * b.map(f).astype(float)
E["pt_rank"] = E.groupby("race_id").race_point.rank(ascending=False, method="min")
E["half"] = np.where(E.date < "20260101", "〜2025", "2026")
E["same_cup"] = E.prev_cup == E.cup_id
def row(lab, d):
    if len(d) < 50: return
    r1 = d.y1.sum() / d.q1.sum(); t1 = (d.y1.sum() - d.q1.sum()) / np.sqrt((d.q1.clip(0, 1) * (1 - d.q1.clip(0, 1))).sum())
    r3 = d.y3.sum() / d.q3.sum(); t3 = (d.y3.sum() - d.q3.sum()) / np.sqrt((d.q3.clip(0, 1) * (1 - d.q3.clip(0, 1))).sum())
    hh = "・".join(f"{h} {x.y3.sum() / x.q3.sum():.2f}" for h, x in d.groupby("half"))
    P(f"| {lab} | {len(d):,} | {r1:.3f} | {t1:+.1f} | {r3:.3f} | {t3:+.1f} | {hh} |")
P(f"# 直近の落車・失格など（完走しなかった）の後（探す段階・確定オッズ、{E.date.min()}〜{E.date.max()}）" + NL)
P(f"完走しなかったレース：{int(E.dnf.sum()):,}（出走の {E.dnf.mean():.1%}）。見込みは同じ見込みの高さの選手全体で直してある" + NL)
P("| 区分 | 人数 | 1着 実際÷見込み | t | 3着以内 実際÷見込み | t | 前半・後半（3着以内） |" + NL + "|---|---|---|---|---|---|---|")
pd_ = E.prev_dnf == True
for lab, m in [("前のレースで完走しなかった", pd_), ("　うち同じ開催の中（前の日）", pd_ & E.same_cup), ("　うち前の開催", pd_ & ~E.same_cup),
               ("　×得点1〜3位", pd_ & (E.pt_rank <= 3)), ("　×得点4位以下", pd_ & (E.pt_rank >= 4)),
               ("最近3走に完走しなかったレースあり", E.dnf_last3 == 1), ("出走表の直近の着順の最後が0", E.ro0_1 == 1), ("出走表の直近3走に0", E.ro0_3 == 1),
               ("参考：前のレースは完走", E.prev_dnf == False)]:
    row(lab, E[m])
T = T.merge(E[["race_id", "number", "prev_dnf", "same_cup", "pt_rank", "half"]].rename(columns={"number": "a"}), on=["race_id", "a"])
P(NL + "### その選手が1着の3連単（300倍以下・全部100円）" + NL + f"全部の平均 {T.ret.mean():.0%}" + NL + "| 区分 | 点数 | 回収率 | 前半・後半 |" + NL + "|---|---|---|---|")
for lab, m in [("前のレースで完走しなかった", T.prev_dnf == True), ("　同じ開催の中", (T.prev_dnf == True) & T.same_cup), ("　前の開催", (T.prev_dnf == True) & ~T.same_cup)]:
    d = T[m]; P(f"| {lab} | {len(d):,} | {d.ret.mean():.0%} | " + "・".join(f"{h} {x.ret.mean():.0%}" for h, x in d.groupby("half")) + " |")
print("done")
