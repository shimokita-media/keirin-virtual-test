import sys, json, os, re, sqlite3, numpy as np, pandas as pd
sys.path.insert(0, r"C:\Users\take0\.claude\keirin"); import kr
S = "."; D0, D1 = sys.argv[1], sys.argv[2]
exec(open("vp.py", encoding="utf-8").read())
c = sqlite3.connect(r"file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
races = pd.read_sql(f"SELECT race_id, date, venue, start_at, line_json FROM races WHERE class!='L級' AND date BETWEEN '{D0}' AND '{D1}' AND race_id IN (SELECT race_id FROM payouts)", c)
wx = pd.concat([pd.DataFrame(json.load(open(f"{d}/{f}", encoding="utf-8")))[["time","wind_speed_10m"]].assign(venue=f[:-5]) for d in ("wx","wx2","wx3") for f in os.listdir(d)]).drop_duplicates(["venue","time"])
W = wx.set_index(wx.venue + wx.time.str[:13]).wind_speed_10m
races["w"] = (races.venue + pd.to_datetime(races.start_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.strftime("%Y-%m-%dT%H")).map(W)
ids = tuple(races.race_id)
ent = pd.read_sql("SELECT race_id, number, prefecture, comment, absent FROM entries WHERE race_id IN (%s)" % ",".join("?" * len(ids)), c, params=ids)
absr = set(ent[ent.absent == 1].race_id)
E = {(r, n): (p, cm or "") for r, n, p, cm, ab in ent.itertuples(index=False) if not ab}
pay = {(a, b): p for a, b, p in c.execute("SELECT race_id, combo, payout FROM payouts WHERE bet_type='ワイド'")}
o = pd.read_sql("SELECT race_id, bet_type, combo, odds, odds_max, popularity, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND race_id IN (%s)" % ",".join("?" * len(ids)), c, params=ids)
o = o[o.fetched_at == o.groupby("race_id").fetched_at.transform("max")]
R = races.set_index("race_id"); rows = []
for rid, g in o.groupby("race_id"):
    od = {bt: {} for bt in kr.BET_TYPES}
    for bt, cb, x, xm, p in g[["bet_type", "combo", "odds", "odds_max", "popularity"]].itertuples(index=False): od[bt][cb] = (x, xm, p)
    if not od["3連単"] or not od["ワイド"]: continue
    lj = R.line_json[rid]; ven = R.venue[rid]; wind = R.w[rid]
    lines = [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(lj)] if isinstance(lj, str) else []
    lid = {x: i for i, l in enumerate(lines) for x in l}; pos = {x: k for l in lines for k, x in enumerate(l)}; ls = {x: len(l) for l in lines for x in l}
    ev = [e for e in kr.evaluate(od) if e["bet_type"] == "ワイド" and e["evc"] >= 0.85 and 3 <= e["odds"] <= 20]
    base = set(x["combo"] for x in sorted([e for e in ev if 6 <= e["odds"] <= 10], key=lambda e: -e["evc"])[:5])
    for e in ev:
        a, b = map(int, e["combo"].split("-"))
        same = a in lid and lid.get(a) == lid.get(b)
        single = any(ls.get(n, 1) == 1 or re.search("単騎|１人|一人|1人", E.get((rid, n), ("", ""))[1]) for n in (a, b))
        third = any(pos.get(n, 0) >= 2 for n in (a, b)); lead = any(pos.get(n, -1) == 0 and ls.get(n, 1) >= 2 for n in (a, b))
        weak = pd.notna(wind) and wind < 4; strong = pd.notna(wind) and wind >= 6
        local = same and any(E.get((rid, n), ("",))[0] == VP.get(ven) for n in (a, b))
        ns = int(same) + int(not single) + int(third and weak) + int(local) + int(lead and strong) + int(same and rid in absr)
        rows.append(dict(race_id=rid, date=R.date[rid], combo=e["combo"], odds=e["odds"], evc=e["evc"], pop=e["pop"], base=e["combo"] in base,
                         same=same, third=third, third_same=same and 2 in (pos.get(a), pos.get(b)), lead=lead, weak=weak, strong=strong,
                         nlines=len(lines), ns=ns, ret=pay.get((rid, e["combo"]), 0) / 100))
df = pd.DataFrame(rows)
nb = df[df.base].groupby("race_id").size(); df["npk"] = df.race_id.map(nb).fillna(0)
df["os"] = df.same.astype(int) + df.third_same + (df.evc >= 0.913) + (df["pop"].fillna(99) <= 10) + (df.npk >= 2)
df.to_pickle(f"val_{D0}_{D1}.pkl"); print(len(df), df.date.nunique(), df.race_id.nunique())
