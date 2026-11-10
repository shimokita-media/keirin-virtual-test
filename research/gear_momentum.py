"""ギアの変更・直近の勢いで、市場の見込みからずれるか（探す段階・確定オッズ）。new_angles.py と同じく見込みは「同じ見込みの高さの選手全体」で直す。
ギアの変更：同じ選手の前の開催（別の cup）での最後のギアとの差。勢い：直近の着順（recent_orders の後ろが新しい）の最近5走の平均と、それより前の平均の差。
使い方: python -I -X utf8 research/gear_momentum.py 出力.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); Q = pd.read_pickle(K + "out/rider_q.pkl"); T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date", "cup_id", "day_index", "class", "close_at"]].rename(columns={"class": "rclass"}), on="race_id").merge(Q, on=["race_id", "number"])
rk = R.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])["rank"]
E["rank"] = rk.reindex(list(zip(E.race_id, E.number))).to_numpy(); E = E[E.race_id.isin(set(R.race_id))]
E["y1"] = (E["rank"] == 1).astype(int); E["y3"] = (E["rank"] <= 3).astype(int)
for k, y in (("q1", "y1"), ("q3", "y3")):
    b = pd.qcut(E[k], 30, duplicates="drop"); f = E.groupby(b, observed=True)[y].sum() / E.groupby(b, observed=True)[k].sum()
    E[k] = E[k] * b.map(f).astype(float)
E["half"] = np.where(E.date < "20260101", "〜2025", "2026")
E["pt_rank"] = E.groupby("race_id").race_point.rank(ascending=False, method="min")
E["day_index"] = pd.to_numeric(E.day_index, errors="coerce")
# ギアの変更（前の開催の最後のレースのギア）
E = E.sort_values(["player_id", "date", "close_at"])
cg = E.groupby(["player_id", "cup_id"], sort=False).agg(first_date=("date", "min"), last_gear=("gear", "last")).reset_index().sort_values(["player_id", "first_date"])
cg["prev_gear"] = cg.groupby("player_id").last_gear.shift()
E = E.merge(cg[["player_id", "cup_id", "prev_gear"]], on=["player_id", "cup_id"], how="left")
E["dg"] = (pd.to_numeric(E.gear, errors="coerce") - pd.to_numeric(E.prev_gear, errors="coerce")).round(2)
# 開催の中でのギアの変更（前の日より）
E = E.sort_values(["player_id", "date", "close_at"]); E["dg_in"] = E.groupby(["player_id", "cup_id"]).gear.diff().round(2)
# 勢い
def mom(s):
    try: v = [x for x in json.loads(s) if isinstance(x, (int, float)) and 1 <= x <= 9] if isinstance(s, str) else [x for x in s if 1 <= x <= 9]
    except Exception: return np.nan, np.nan
    if len(v) < 10: return np.nan, np.nan
    return np.mean(v[-5:]), np.mean(v[:-5])
mm = E.recent_orders.map(mom); E["r5"] = [m[0] for m in mm]; E["rold"] = [m[1] for m in mm]; E["dm"] = E.rold - E.r5  # ＋なら最近良くなっている（着順が小さくなった）
def row(lab, g):
    if len(g) < 50: return
    r1 = g.y1.sum() / g.q1.sum(); t1 = (g.y1.sum() - g.q1.sum()) / np.sqrt((g.q1.clip(0, 1) * (1 - g.q1.clip(0, 1))).sum())
    r3 = g.y3.sum() / g.q3.sum(); t3 = (g.y3.sum() - g.q3.sum()) / np.sqrt((g.q3.clip(0, 1) * (1 - g.q3.clip(0, 1))).sum())
    hh = "・".join(f"{h} {x.y1.sum() / x.q1.sum():.2f}" for h, x in g.groupby("half"))
    P(f"| {lab} | {len(g):,} | {r1:.3f} | {t1:+.1f} | {r3:.3f} | {t3:+.1f} | {hh} |")
def tab(title, groups):
    P(NL + f"### {title}" + NL + "| 区分 | 人数 | 1着 実際÷見込み | t | 3着以内 実際÷見込み | t | 前半・後半（1着） |" + NL + "|---|---|---|---|---|---|---|")
    for lab, m in groups: row(lab, E[m])
P(f"# ギアの変更・直近の勢い（探す段階・確定オッズ、{E.date.min()}〜{E.date.max()}、選手 {len(E):,}）" + NL)
P("見込みは同じ見込みの高さの選手全体で直してある（全体で1.00）。1を超えると市場が軽く見ている。たくさん見ているので t は ±3 以上を目安に")
d1 = E.day_index == 1
tab("ギアの変更（開催1日目、前の開催の最後のギアとの差）", [("上げた（+0.05以上）", d1 & (E.dg >= 0.05)), ("同じ", d1 & (E.dg.abs() < 0.005)), ("下げた（−0.05以下）", d1 & (E.dg <= -0.05)),
    ("上げた×得点1〜3位", d1 & (E.dg >= 0.05) & (E.pt_rank <= 3)), ("上げた×得点4位以下", d1 & (E.dg >= 0.05) & (E.pt_rank >= 4)),
    ("下げた×得点1〜3位", d1 & (E.dg <= -0.05) & (E.pt_rank <= 3)), ("下げた×得点4位以下", d1 & (E.dg <= -0.05) & (E.pt_rank >= 4))])
tab("開催の途中でギアを変えた（前の日より）", [("上げた", E.dg_in >= 0.05), ("下げた", E.dg_in <= -0.05), ("同じ", E.dg_in.abs() < 0.005)])
E["dmb"] = pd.cut(E.dm, [-9, -1.5, -0.7, 0.7, 1.5, 9], labels=["かなり悪化（1.5着以上）", "悪化", "変わらず", "良化", "かなり良化（1.5着以上）"])
tab("直近の勢い（最近5走の平均着順 − それより前の平均。良化＝最近の方が着順が良い）", [(k, E.dmb == k) for k in E.dmb.cat.categories] +
    [("かなり良化×得点4位以下", (E.dmb == "かなり良化（1.5着以上）") & (E.pt_rank >= 4)), ("かなり悪化×得点1〜3位", (E.dmb == "かなり悪化（1.5着以上）") & (E.pt_rank <= 3))])
E["r5b"] = pd.cut(E.r5, [0, 2, 3, 4, 5, 10], labels=["最近5走 平均2着以内", "2〜3着", "3〜4着", "4〜5着", "5着より下"])
tab("最近5走の平均着順そのもの", [(k, E.r5b == k) for k in E.r5b.cat.categories])
# 回収率（その選手が1着の3連単300倍以下）
T = T.merge(E[["race_id", "number", "dg", "dmb", "pt_rank", "day_index", "half"]].rename(columns={"number": "a"}), on=["race_id", "a"])
P(NL + "### その選手が1着の3連単（300倍以下・全部100円）の回収率" + NL + f"全部の平均 {T.ret.mean():.0%}" + NL)
P("| 区分 | 点数 | レース | 回収率 | t（全体との差） | 前半・後半 |" + NL + "|---|---|---|---|---|---|")
for lab, m in [("ギア上げた（1日目）", (T.day_index == 1) & (T.dg >= 0.05)), ("ギア下げた（1日目）", (T.day_index == 1) & (T.dg <= -0.05)),
               ("かなり良化", T.dmb == "かなり良化（1.5着以上）"), ("かなり良化×得点4位以下", (T.dmb == "かなり良化（1.5着以上）") & (T.pt_rank >= 4)),
               ("かなり悪化", T.dmb == "かなり悪化（1.5着以上）"), ("かなり悪化×得点1〜3位", (T.dmb == "かなり悪化（1.5着以上）") & (T.pt_rank <= 3))]:
    g = T[m]
    if len(g) < 100: continue
    rr = g.groupby("race_id").ret.mean(); t = (rr.mean() - T.ret.mean()) / (rr.std() / np.sqrt(len(rr)))
    P(f"| {lab} | {len(g):,} | {g.race_id.nunique():,} | **{g.ret.mean():.0%}** | {t:+.1f} | " + "・".join(f"{h} {x.ret.mean():.0%}" for h, x in g.groupby("half")) + " |")
print("done")
