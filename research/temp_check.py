"""気温（発走の時刻、Open-Meteo）×脚質・ライン内の位置で、市場の見込みからずれるか（探す段階・確定オッズ）。屋根のある前橋・小倉は除く。
使い方: python -I -X utf8 research/temp_check.py 出力.md"""
import sys, json, glob, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
W = []
for f in glob.glob(K + "out/wx_temp/*.json"):
    h = json.load(open(f, encoding="utf-8")); W.append(pd.DataFrame({"venue": os.path.basename(f)[:-5], "t": h["time"], "temp": h["temperature_2m"], "rain": h["precipitation"]}))
W = pd.concat(W); W["key"] = W.venue + W.t.str[:13]
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
RA = RA[~RA.venue.isin(["前橋", "小倉"])].copy()
RA["key"] = RA.venue + pd.to_datetime(pd.to_numeric(RA.start_at), unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.strftime("%Y-%m-%dT%H")
RA = RA.merge(W[["key", "temp", "rain"]], on="key", how="left")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
R = pd.read_pickle(K + "out/side_results_full.pkl"); Q = pd.read_pickle(K + "out/rider_q.pkl"); T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date", "temp", "rain", "line_json"]], on="race_id"); E = E[E.race_id.isin(set(R.race_id))]
rk = R.drop_duplicates(["race_id", "number"]).set_index(["race_id", "number"])["rank"]
E["rank"] = rk.reindex(list(zip(E.race_id, E.number))).to_numpy()
E = E.merge(Q, on=["race_id", "number"])
E["y1"] = (E["rank"] == 1).astype(int); E["y3"] = (E["rank"] <= 3).astype(int)
for k, y in (("q1", "y1"), ("q3", "y3")):
    b = pd.qcut(E[k], 30, duplicates="drop"); f = E.groupby(b, observed=True)[y].sum() / E.groupby(b, observed=True)[k].sum()
    E[k] = E[k] * b.map(f).astype(float)
def pos(lj, n):
    try:
        for l in json.loads(lj or "[]"):
            ns = [m for x in l["entries"] for m in x["numbers"]]
            if n in ns: return "単騎" if len(ns) == 1 else ["先頭", "番手", "3番手"][min(ns.index(n), 2)]
    except Exception: pass
    return "不明"
E["lpos"] = [pos(a, b) for a, b in zip(E.line_json, E.number)]
E["half"] = np.where(E.date < "20260101", "〜2025", "2026")
E["tb"] = pd.cut(E.temp, [-30, 5, 10, 20, 28, 50], labels=["5℃未満", "5〜10℃", "10〜20℃", "20〜28℃", "28℃以上"])
def row(lab, d):
    if len(d) < 100: return
    r1 = d.y1.sum() / d.q1.sum(); t1 = (d.y1.sum() - d.q1.sum()) / np.sqrt((d.q1.clip(0, 1) * (1 - d.q1.clip(0, 1))).sum())
    r3 = d.y3.sum() / d.q3.sum(); t3 = (d.y3.sum() - d.q3.sum()) / np.sqrt((d.q3.clip(0, 1) * (1 - d.q3.clip(0, 1))).sum())
    hh = "・".join(f"{h} {x.y1.sum() / x.q1.sum():.2f}" for h, x in d.groupby("half"))
    P(f"| {lab} | {len(d):,} | {r1:.3f} | {t1:+.1f} | {r3:.3f} | {t3:+.1f} | {hh} |")
HDR = "| 区分 | 人数 | 1着 実際÷見込み | t | 3着以内 実際÷見込み | t | 前半・後半（1着） |" + NL + "|---|---|---|---|---|---|---|"
P(f"# 気温×脚質・位置（探す段階・確定オッズ、{E.date.min()}〜{E.date.max()}、前橋・小倉を除く、気温が取れた {E.temp.notna().mean():.0%}）" + NL)
for col, keys, lab in (("style", ["逃", "両", "追"], "脚質"), ("lpos", ["先頭", "番手", "3番手", "単騎"], "ライン内の位置")):
    P(NL + f"### 気温×{lab}" + NL + HDR)
    for tb in E.tb.cat.categories:
        for k in keys: row(f"{tb}×{k}", E[(E.tb == tb) & (E[col] == k)])
P(NL + "### 雨（発走の時刻に降水あり）×位置" + NL + HDR)
for k in ["先頭", "番手", "3番手", "単騎"]:
    row(f"雨×{k}", E[(E.rain > 0.5) & (E.lpos == k)]); row(f"雨なし×{k}", E[(E.rain == 0) & (E.lpos == k)])
print("done", E.temp.notna().mean())
