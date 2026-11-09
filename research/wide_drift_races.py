"""ワイドの倍率が締切前→最終で下がる（縮む）レース・目の特徴（本番DBの写し、11/6〜）。
動き = log(最終の倍率 / 締切前の倍率)。マイナスなら下がった。各目を同じ重さで平均し、t値はレースごとにまとめてから。
使い方: python -I -X utf8 research/wide_drift_races.py 出力.md"""
import sys, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
c = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True)
O = pd.read_sql("""SELECT race_id, combo, phase, odds, popularity, fetched_at FROM odds
  WHERE bet_type='ワイド' AND source='winticket' AND phase IN ('T10','T5','T1','B1R','POST') AND substr(race_id,5) >= '20261106'""", c)
RA = pd.read_sql("SELECT race_id, date, venue, race_no, grade, class, race_type, entries_number, close_at, line_type, day_index FROM races", c)
AB = pd.read_sql("SELECT race_id, SUM(absent) ab FROM entries GROUP BY race_id", c)
O = O.sort_values("fetched_at").drop_duplicates(["race_id", "combo", "phase"], keep="last")
W = O.pivot_table(index=["race_id", "combo"], columns="phase", values="odds").reset_index()
PO = O[O.phase == "POST"].set_index(["race_id", "combo"]).popularity
W["pop"] = PO.reindex(list(zip(W.race_id, W.combo))).to_numpy()
W = W.merge(RA, on="race_id").merge(AB, on="race_id", how="left")
W = W[(W.POST > 0) & W.T1.notna() & (W.T1 > 0)]
W["mv1"] = np.log(W.POST / W.T1); W["mv10"] = np.log(W.POST / W.T10)
W["hour"] = pd.to_datetime(W.close_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.hour
W["tod"] = pd.cut(W.hour, [0, 11, 15, 19, 24], labels=["朝（〜11時）", "昼（11〜15時）", "夕（15〜19時）", "夜（19時〜）"], right=False)
W["oband"] = pd.cut(W.T1, [0, 2, 3, 5, 10, 20, 1e9], labels=["〜2倍", "2〜3", "3〜5", "5〜10", "10〜20", "20倍〜"])
W["pband"] = pd.cut(W["pop"], [0, 1, 3, 6, 10, 1e9], labels=["1番人気", "2〜3", "4〜6", "7〜10", "11〜"])
W["fin"] = W.race_type.fillna("").str.contains("決勝|準決"); W["grd"] = W.grade.isin(["GP", "GI", "GII", "GIII"])
W["n"] = W.entries_number.astype("Int64"); W["abs"] = W.ab.fillna(0) > 0
W["fav"] = W.groupby("race_id").T1.transform("min"); W["favb"] = pd.cut(W.fav, [0, 1.3, 1.6, 2.0, 1e9], labels=["1.3倍以下", "1.3〜1.6", "1.6〜2.0", "2.0倍超"])
P(f"# ワイドの倍率が下がるレース・目の特徴（{W.date.min()}〜{W.date.max()}、{W.race_id.nunique()}R・{len(W):,}目）" + NL)
P("動き＝log(最終÷1分前)。−0.10 なら約10%下がった。全体の平均 " + f"{W.mv1.mean():+.3f}（10分前→最終 {W.mv10.mean():+.3f}）" + NL)
def tab(col, lab):
    P(f"### {lab}" + NL + "| 区分 | レース | 目 | 1分前→最終 | 10分前→最終 | 下がった目の割合 | t（1分前→最終、レースごと） |" + NL + "|---|---|---|---|---|---|---|")
    for k, g in W.groupby(col, observed=True):
        r = g.groupby("race_id").mv1.mean(); t = r.mean() / (r.std() / np.sqrt(len(r))) if len(r) > 2 else np.nan
        P(f"| {k} | {g.race_id.nunique()} | {len(g):,} | {g.mv1.mean():+.3f} | {g.mv10.mean():+.3f} | {(g.mv1 < -0.02).mean():.0%} | {t:+.1f} |")
    P("")
for col, lab in (("oband", "1分前の倍率"), ("pband", "最終の人気"), ("favb", "そのレースの1番人気のワイドの倍率（本命の強さ）"), ("n", "車立て"),
                 ("grd", "G戦（GIII以上）"), ("class", "級"), ("fin", "準決勝・決勝"), ("day_index", "開催の何日目"), ("tod", "時間帯"),
                 ("abs", "欠場者あり"), ("line_type", "並びの形"), ("venue", "場")):
    tab(col, lab)
print("done", len(W))
P(NL + "## 人気10番以内の目だけで見たレースの特徴（大穴の目の多さに左右されないように）" + NL)
W = W[W["pop"] <= 10]
for col, lab in (("favb", "本命の強さ"), ("n", "車立て"), ("grd", "G戦"), ("class", "級"), ("fin", "準決勝・決勝"), ("tod", "時間帯"), ("line_type", "並びの形"), ("day_index", "何日目")):
    tab(col, lab)
