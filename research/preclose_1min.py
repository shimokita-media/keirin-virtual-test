"""締切1分前（T1）で深く分析（2026-11-09〜、毎日やり直せる）。本番DBのコピー out/live_db/keirin.sqlite を使う
（最新にするには: gh release download db -p keirin.sqlite.gz -D out/live_db --clobber → gunzip -kf）。
1) 1分前→最終の倍率の動き（倍率帯・人気順位ごと）と、1分前に全部買ったときの回収率（市場の正確さ）
2) 買い方ごと（一番の目・3連単枠・T）を「1分前の倍率で選んで、確定の払戻で精算」したときの成績。同じ買い方を判断時点（B1R）で選んだ場合と比べる
使い方: python -I -X utf8 research/preclose_1min.py 出力.md"""
import sys, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; sys.path.insert(0, K)
import tri_rule
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
con = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True); con.row_factory = sqlite3.Row
O = pd.read_sql("SELECT race_id, bet_type, combo, phase, odds, odds_max, popularity, fetched_at FROM odds WHERE phase IN ('B1R','T1','POST') AND substr(race_id,-8) >= '20261107'", con)
O = O.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo", "phase"], keep="last")
PY = pd.read_sql("SELECT race_id, bet_type, combo, payout FROM payouts WHERE substr(race_id,-8) >= '20261107'", con)
done = set(PY.race_id)
tri = O[O.bet_type == "3連単"].pivot_table(index=["race_id", "combo"], columns="phase", values="odds").reset_index()
pop = O[(O.bet_type == "3連単") & (O.phase == "T1")].set_index(["race_id", "combo"]).popularity
tri = tri[tri.race_id.isin(done) & tri.T1.notna() & tri.POST.notna()].copy()
tri = tri.merge(PY[PY.bet_type == "3連単"][["race_id", "combo", "payout"]], on=["race_id", "combo"], how="left"); tri["ret"] = tri.payout.fillna(0) / 100
tri["pop"] = [pop.get((r, c)) for r, c in zip(tri.race_id, tri.combo)]
tri["mv"] = tri.POST / tri.T1
P("# 締切1分前（T1）の深い分析" + NL)
P(f"本番DBの {tri.race_id.nunique()} レース（11/7〜、1分前と最終の両方の倍率と確定の払戻があるもの）。1分前→最終の倍率の動き＝最終÷1分前（1.00＝変わらず）。" + NL)
P("## 1. 1分前→最終の倍率の動き（3連単）" + NL + NL + "| 1分前の倍率帯 | 点数 | 動きの中央値 | 平均 | 下がった割合 | 1分前に全部買った回収率 |" + NL + "|---|---|---|---|---|---|")
for lo, hi in ((0, 10), (10, 30), (30, 60), (60, 100), (100, 300), (300, 1e9)):
    x = tri[(tri.T1 > lo) & (tri.T1 <= hi)]
    if len(x): P(f"| {lo:g}〜{hi:g}倍 | {len(x):,} | {x.mv.median():.3f} | {x.mv.mean():.3f} | {(x.mv < 1).mean():.0%} | {x.ret.mean():.0%} |")
P(NL + "| 1分前の人気順位 | 点数 | 動きの中央値 | 下がった割合 | 回収率 |" + NL + "|---|---|---|---|---|")
for lo, hi in ((1, 3), (4, 10), (11, 30), (31, 100), (101, 999)):
    x = tri[tri["pop"].between(lo, hi)]
    if len(x): P(f"| {lo}〜{hi}番人気 | {len(x):,} | {x.mv.median():.3f} | {(x.mv < 1).mean():.0%} | {x.ret.mean():.0%} |")
# --- 2. 買い方ごと：1分前の倍率で選ぶ vs 判断時点（B1R）で選ぶ
def odds_dict(rid, ph):
    d = {bt: {} for bt in ("3連単", "3連複", "2車単", "2車複", "ワイド")}
    for r in O[(O.race_id == rid) & (O.phase == ph)].itertuples():
        if r.bet_type in d: d[r.bet_type][r.combo] = (r.odds, r.odds_max, r.popularity)
    return d
rows = []
races = con.execute(f"SELECT * FROM races WHERE race_id IN ({','.join('?' * len(done))})", list(done)).fetchall()
pay = PY[PY.bet_type == "3連単"].set_index(["race_id", "combo"]).payout
fin = O[(O.bet_type == "3連単") & (O.phase == "POST")].set_index(["race_id", "combo"]).odds
for row in races:
    rid = row["race_id"]
    for ph in ("B1R", "T1"):
        od = odds_dict(rid, ph)
        if not od["3連単"]: continue
        try: pk = tri_rule.picks(con, row, od)
        except Exception: pk = []
        for i, p in enumerate(pk):
            rows.append((rid, ph, "3連単枠", p["combo"], p["odds"], pay.get((rid, p["combo"]), 0) / 100, fin.get((rid, p["combo"]))))
            if i == 0: rows.append((rid, ph, "一番の目", p["combo"], p["odds"], pay.get((rid, p["combo"]), 0) / 100, fin.get((rid, p["combo"]))))
        if (row["class"] or "") != "L級" and (str(row["grade"] or "").startswith("G") or (row["entries_number"] or 0) >= 9):
            pts = con.execute("SELECT number, race_point FROM entries WHERE race_id=? AND absent=0", (rid,)).fetchall()
            vals = sorted([v for _, v in pts if v is not None], reverse=True); rank = {n: 1 + sum(1 for v in vals if v > p_) for n, p_ in pts if p_ is not None}
            for c, (o, _m, _p) in od["3連単"].items():
                if o and o <= 10 and rank.get(int(c.split("-")[2]), 0) >= 5:
                    rows.append((rid, ph, "T", c, o, pay.get((rid, c), 0) / 100, fin.get((rid, c))))
S = pd.DataFrame(rows, columns=["race_id", "ph", "kind", "combo", "odds", "ret", "fin"])
rng = np.random.default_rng(0)
def cell(x):
    if not len(x): return "−"
    by = x.groupby("race_id").ret.agg(["sum", "size"]); w = rng.dirichlet(np.ones(len(by)), 3000); post = (w @ by["sum"].to_numpy()) / (w @ by["size"].to_numpy())
    mv = (x.fin / x.odds).median()
    return f"**{x.ret.mean():.0%}**（{len(x)}点・{int((x.ret > 0).sum())}本・倍率の動き {mv - 1:+.1%}・P>100% {(post > 1).mean():.0%}）"
P(NL + "## 2. 買い方ごと：どの時点の倍率で選ぶか（確定の払戻で精算・各100円）" + NL + NL + "| 買い方 | 判断時点（11/7〜9は2〜3分前）で選ぶ | 1分前で選ぶ |" + NL + "|---|---|---|")
for k in ("一番の目", "3連単枠", "T"):
    P(f"| {k} | {cell(S[(S.kind == k) & (S.ph == 'B1R')])} | {cell(S[(S.kind == k) & (S.ph == 'T1')])} |")
P(NL + "※ レース数が少ないうちは傾向だけ。本番の記録（11/10〜は判断が1分前、T枠＝B3X も記録）がたまったらやり直す。")
S.to_pickle(K + "out/preclose_1min_picks.pkl")
print("done", tri.race_id.nunique())
