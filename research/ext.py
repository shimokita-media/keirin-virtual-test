"""選手表に追加の手がかりを足す。使い方: python ext.py 出力.pkl 入力1.pkl 入力2.pkl ..."""
import sys, os, json, sqlite3, numpy as np, pandas as pd
F = pd.concat([pd.read_pickle(f) for f in sys.argv[2:]]).drop_duplicates(["race_id", "number"])
c = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
ids = F.race_id.unique()
ro, st = {}, {}
for i0 in range(0, len(ids), 5000):
    part = tuple(ids[i0:i0 + 5000]); q = ",".join("?" * len(part))
    for r, n, s in c.execute(f"SELECT race_id, number, recent_orders FROM entries WHERE race_id IN ({q})", part): ro[(r, n)] = s
    for r, s_ in c.execute(f"SELECT race_id, start_at FROM races WHERE race_id IN ({q})", part): st[r] = s_
def stats(s):
    try: a = [x for x in json.loads(s) if x > 0]
    except Exception: return (np.nan,) * 5
    if not a: return (np.nan,) * 5
    a = np.array(a, float)
    return a[:5].mean(), a[-5:].mean(), a.mean(), (a <= 3).mean(), (a[:10] <= 3).mean()
S = np.array([stats(ro.get(k)) for k in zip(F.race_id, F.number)])
F["ro_first5"], F["ro_last5"], F["ro_mean"], F["ro_top3"], F["ro_top3_10"] = S.T
F["start"] = F.race_id.map(st)
t = pd.to_datetime(F.start, unit="s", utc=True).dt.tz_convert("Asia/Tokyo")
F["hour"] = t.dt.hour
wx = pd.concat([pd.DataFrame(json.load(open(f"{d}/{f}", encoding="utf-8")))[["time", "wind_speed_10m"]].assign(venue=f[:-5]) for d in ("wx", "wx2", "wx3", "wx4") for f in os.listdir(d)]).drop_duplicates(["venue", "time"])
W = wx.set_index(wx.venue + wx.time.str[:13]).wind_speed_10m
F["wind"] = (F.venue + t.dt.strftime("%Y-%m-%dT%H")).map(W)
F["venue_c"] = F.venue.astype("category").cat.codes
# 過去の「市場の見込みより多く3着以内に来た回数」（その日より前だけ）
F["surp"] = F.top3.astype(float) - F.p3
d = F.groupby(["player_id", "date"]).agg(s=("surp", "sum"), n=("surp", "size"), t3=("top3", "sum")).reset_index().sort_values(["player_id", "date"])
g = d.groupby("player_id")
d["h_surp"] = g.s.cumsum() - d.s; d["h_n"] = g.n.cumsum() - d.n; d["h_t3"] = g.t3.cumsum() - d.t3
d["h_surp_ewm"] = g.s.transform(lambda x: x.shift().ewm(halflife=20, min_periods=1).mean())
F = F.merge(d[["player_id", "date", "h_surp", "h_n", "h_t3", "h_surp_ewm"]], on=["player_id", "date"], how="left")
F["h_surp_rate"] = F.h_surp / F.h_n.where(F.h_n > 0); F["h_t3_rate"] = F.h_t3 / F.h_n.where(F.h_n > 0)
F.to_pickle(sys.argv[1]); print(len(F), F.date.min(), F.date.max(), F[["ro_mean", "wind", "h_n"]].notna().mean().round(2).to_dict())
