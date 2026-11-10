"""【小分け読み込み版の ext.py】選手表に「直近の着順（ro_*）」「市場の見込みより多く3着以内に来た履歴（h_*）」を足す。計算は research/ext.py と同じ。
2026-11-11 追加：判定の段取り（prereg_full_2024.py）がこの工程を飛ばしていて、2024年・y4 の表で機械（v1・v2・D）の特徴量の重み16〜25%が空（NaN）になっていた。
- 取り込み中のDBを固めないよう、300レースずつ・0.5秒休みながら entries.recent_orders と races.start_at を読む
- 機械が使わない hour・wind・venue_c は、ext.py と同じ名前の列だけ作る（wind は天気ファイルがないので NaN。機械の重みは0%）
使い方: python -I -X utf8 research/ext_small.py 入力の選手表.pkl 出力.pkl"""
import sys, os, json, time, sqlite3, numpy as np, pandas as pd
src, dst = sys.argv[1:3]
F = pd.read_pickle(src).drop_duplicates(["race_id", "number"])
c = sqlite3.connect("file:" + os.environ.get("KDB", "C:/Users/take0/.claude/keirin/keirin.sqlite") + "?mode=ro", uri=True, timeout=30)
ids = F.race_id.unique(); ro, st = {}, {}
for i0 in range(0, len(ids), 300):
    part = tuple(ids[i0:i0 + 300]); q = ",".join("?" * len(part)); time.sleep(0.5)
    for r, n, s in c.execute(f"SELECT race_id, number, recent_orders FROM entries WHERE race_id IN ({q})", part): ro[(r, n)] = s
    for r, s_ in c.execute(f"SELECT race_id, start_at FROM races WHERE race_id IN ({q})", part): st[r] = s_
    if i0 % 6000 == 0: print(i0, len(ids), flush=True)
def stats(s):
    try: a = [x for x in json.loads(s) if x > 0]
    except Exception: return (np.nan,) * 5
    if not a: return (np.nan,) * 5
    a = np.array(a, float)
    return a[:5].mean(), a[-5:].mean(), a.mean(), (a <= 3).mean(), (a[:10] <= 3).mean()
S = np.array([stats(ro.get(k)) for k in zip(F.race_id, F.number)])
F["ro_first5"], F["ro_last5"], F["ro_mean"], F["ro_top3"], F["ro_top3_10"] = S.T
F["start"] = F.race_id.map(st)
F["hour"] = pd.to_datetime(F.start, unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.hour
F["wind"] = np.nan
F["venue_c"] = F.venue.astype("category").cat.codes
F["surp"] = F.top3.astype(float) - F.p3
d = F.groupby(["player_id", "date"]).agg(s=("surp", "sum"), n=("surp", "size"), t3=("top3", "sum")).reset_index().sort_values(["player_id", "date"])
g = d.groupby("player_id")
d["h_surp"] = g.s.cumsum() - d.s; d["h_n"] = g.n.cumsum() - d.n; d["h_t3"] = g.t3.cumsum() - d.t3
d["h_surp_ewm"] = g.s.transform(lambda x: x.shift().ewm(halflife=20, min_periods=1).mean())
F = F.merge(d[["player_id", "date", "h_surp", "h_n", "h_t3", "h_surp_ewm"]], on=["player_id", "date"], how="left")
F["h_surp_rate"] = F.h_surp / F.h_n.where(F.h_n > 0); F["h_t3_rate"] = F.h_t3 / F.h_n.where(F.h_n > 0)
F.to_pickle(dst); print(len(F), F.date.min(), F.date.max(), F[["ro_mean", "h_n"]].notna().mean().round(2).to_dict())
