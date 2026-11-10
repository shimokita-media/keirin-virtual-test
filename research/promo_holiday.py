"""A 特別昇級がかかった決勝（その開催の前の日までを全部1着）／D 祝日・連休・年末年始・お盆（探す段階・確定オッズ）。
見込みは new_angles と同じく「同じ見込みの高さの選手全体」で直す。使い方: python -I -X utf8 research/promo_holiday.py 出力.md"""
import sys, datetime as dt, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); Q = pd.read_pickle(K + "out/rider_q.pkl"); T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date", "cup_id", "day_index", "race_type", "close_at", "entries_number"]].rename(columns={}), on="race_id")
E = E[E.race_id.isin(set(R.race_id))]
rk = R.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])["rank"]
E["rank"] = rk.reindex(list(zip(E.race_id, E.number))).to_numpy()
E["day_index"] = pd.to_numeric(E.day_index, errors="coerce")
E = E.sort_values(["player_id", "close_at"])
g = E.groupby(["player_id", "cup_id"])
E["n_prev"] = g.cumcount(); E["wins_prev"] = g["rank"].transform(lambda s: (s == 1).astype(int).shift(1).fillna(0).cumsum())
E["sweep"] = (E.n_prev >= 2) & (E.wins_prev == E.n_prev)
E = E.merge(Q, on=["race_id", "number"])
E["y1"] = (E["rank"] == 1).astype(int); E["y3"] = (E["rank"] <= 3).astype(int)
for k, y in (("q1", "y1"), ("q3", "y3")):
    b = pd.qcut(E[k], 30, duplicates="drop"); f = E.groupby(b, observed=True)[y].sum() / E.groupby(b, observed=True)[k].sum()
    E[k] = E[k] * b.map(f).astype(float)
E["half"] = np.where(E.date < "20260101", "〜2025", "2026")
rt = E.race_type.fillna("")
def row(lab, d):
    if len(d) < 30: P(f"| {lab} | {len(d)} | （少ない） | | | | |"); return
    r1 = d.y1.sum() / d.q1.sum(); t1 = (d.y1.sum() - d.q1.sum()) / np.sqrt((d.q1.clip(0, 1) * (1 - d.q1.clip(0, 1))).sum())
    r3 = d.y3.sum() / d.q3.sum(); t3 = (d.y3.sum() - d.q3.sum()) / np.sqrt((d.q3.clip(0, 1) * (1 - d.q3.clip(0, 1))).sum())
    hh = "・".join(f"{h} {x.y1.sum() / x.q1.sum():.2f}" for h, x in d.groupby("half"))
    P(f"| {lab} | {len(d):,} | {r1:.3f} | {t1:+.1f} | {r3:.3f} | {t3:+.1f} | {hh} |")
HDR = "| 区分 | 人数 | 1着 実際÷見込み | t | 3着以内 実際÷見込み | t | 前半・後半（1着） |" + NL + "|---|---|---|---|---|---|---|"
P(f"# 特別昇級がかかった決勝・祝日（探す段階・確定オッズ、{E.date.min()}〜{E.date.max()}）" + NL)
P("## A 前の日までを全部1着で決勝に来た選手（チャレンジ＝A級3班は完全優勝で特別昇級）" + NL + HDR)
for lab, m in [("チャレンジ決勝×全部1着（特別昇級がかかる）", rt.str.contains("チャレンジ決勝") & E.sweep),
               ("A級の決勝（1・2班）×全部1着", (rt == "決勝") & (E["class"] == 2) & E.sweep),
               ("S級の決勝×全部1着", (rt == "決勝") & (E["class"] == 1) & E.sweep),
               ("ガールズの決勝×全部1着", (rt.str.contains("決勝")) & (E["class"] == 4) & E.sweep),
               ("参考：チャレンジ決勝×全部1着ではない", rt.str.contains("チャレンジ決勝") & ~E.sweep),
               ("参考：決勝以外×前の日まで全部1着", ~rt.str.contains("決勝") & E.sweep)]:
    row(lab, E[m])
# 回収率（その選手が1着の3連単300倍以下）
TT = T.merge(E[["race_id", "number", "sweep", "class", "race_type", "half"]].rename(columns={"number": "a"}), on=["race_id", "a"])
P(NL + "その選手が1着の3連単（300倍以下・全部100円）、全体 " + f"{T.ret.mean():.0%}" + NL + "| 区分 | 点数 | 回収率 | 前半・後半 |" + NL + "|---|---|---|---|")
r2 = TT.race_type.fillna("")
for lab, m in [("チャレンジ決勝×全部1着", r2.str.contains("チャレンジ決勝") & TT.sweep), ("A級1・2班の決勝×全部1着", (r2 == "決勝") & (TT["class"] == 2) & TT.sweep),
               ("S級の決勝×全部1着", (r2 == "決勝") & (TT["class"] == 1) & TT.sweep)]:
    d = TT[m]; P(f"| {lab} | {len(d):,} | {d.ret.mean():.0%} | " + "・".join(f"{h} {x.ret.mean():.0%}" for h, x in d.groupby("half")) + " |")
# D 祝日
HOL = set("""20240101 20240108 20240211 20240212 20240223 20240320 20240429 20240503 20240504 20240505 20240506 20240715 20240811 20240812 20240916 20240922 20240923 20241014 20241103 20241104 20241123
20250101 20250113 20250211 20250223 20250224 20250320 20250429 20250503 20250504 20250505 20250506 20250721 20250811 20250915 20250923 20251013 20251103 20251123 20251124
20260101 20260112 20260211 20260223 20260320 20260429 20260503 20260504 20260505 20260506 20260720 20260811 20260921 20260922 20260923 20261012 20261103""".split())
def kind(d):
    md = d[4:]
    if md >= "1228" or md <= "0103": return "年末年始"
    if "0813" <= md <= "0816": return "お盆"
    if d in HOL: return "祝日"
    return "土日" if dt.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday() >= 5 else "平日"
RD = RA[["race_id", "date"]].copy(); RD["kind"] = RD.date.map(kind)
T2 = T.merge(RD, on="race_id")
T2["ob"] = pd.cut(T2.odds, [0, 20, 60, 150, 300], labels=["20倍以下", "20〜60", "60〜150", "150〜300"])
P(NL + "## D 祝日・連休（3連単300倍以下を全部100円、倍率の帯ごとの回収率）" + NL + "| 日の種類 | レース | 20倍以下 | 20〜60 | 60〜150 | 150〜300 | 全部 | 前半・後半 |" + NL + "|---|---|---|---|---|---|---|---|")
T2["half"] = np.where(T2.date < "20260101", "〜2025", "2026")
for k in ("平日", "土日", "祝日", "年末年始", "お盆"):
    d = T2[T2.kind == k]
    if not len(d): continue
    v = d.groupby("ob", observed=True).ret.mean()
    P(f"| {k} | {d.race_id.nunique():,} | " + " | ".join(f"{v.get(b, np.nan):.0%}" for b in ("20倍以下", "20〜60", "60〜150", "150〜300")) + f" | {d.ret.mean():.0%} | " + "・".join(f"{h} {x.ret.mean():.0%}" for h, x in d.groupby("half")) + " |")
# 祝日の人気の偏り：1番人気の組の 実際÷見込み
E2 = E.merge(RD[["race_id", "kind"]], on="race_id")
P(NL + "### 日の種類 × 選手の 1着 実際÷見込み（人気の選手＝見込み上位2人／それ以外）" + NL + HDR)
E2["top2"] = E2.groupby("race_id").q1.rank(ascending=False, method="first") <= 2
for k in ("平日", "土日", "祝日", "年末年始", "お盆"):
    row(f"{k}×人気の2人", E2[(E2.kind == k) & E2.top2]); row(f"{k}×それ以外", E2[(E2.kind == k) & ~E2.top2])
print("done")
