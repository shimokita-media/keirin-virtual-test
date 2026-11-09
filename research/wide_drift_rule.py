"""ワイド枠（6〜10倍×割安度0.85以上、最大5点）を「最後の1分の下がり」を見込んで選んだら回収率は変わるか（本番DB 11/7〜）。
1分前（T1、無ければ B1R）の倍率で kr.evaluate を回し、割安度と倍率を「人気帯ごとの1分前→最終の平均の動き」で直してから同じ基準で選ぶ。
動きの平均は、その日を除いた日から求める（1日ずつ外して当てはめる＝答えを見ない）。払戻は最終オッズの確定払戻。
使い方: python -I -X utf8 research/wide_drift_rule.py 出力.md"""
import sys, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
sys.path.insert(0, K[:-1])
import kr
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
c = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True)
O = pd.read_sql("""SELECT race_id, bet_type, combo, odds, odds_max, popularity, phase, fetched_at FROM odds
  WHERE source='winticket' AND phase IN ('T1','B1R','POST') AND substr(race_id,5) >= '20261107'""", c)
PAY = pd.read_sql("SELECT race_id, combo, payout FROM payouts WHERE bet_type='ワイド'", c)
c.close()
O = O.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo", "phase"], keep="last")
rows = []
for rid, g in O[O.phase.isin(["T1", "B1R"])].groupby("race_id"):
    ph = "T1" if (g.phase == "T1").any() else "B1R"; g = g[g.phase == ph]
    od = {bt: {} for bt in kr.BET_TYPES}
    for x in g.itertuples():
        od[x.bet_type][x.combo] = (x.odds, x.odds_max, x.popularity)
    if not od["3連単"] or not od["ワイド"]: continue
    for r in kr.evaluate(od):
        if r["bet_type"] == "ワイド":
            rows.append((rid, r["combo"], r["odds"], r["evc"], od["ワイド"][r["combo"]][2]))
W = pd.DataFrame(rows, columns=["race_id", "combo", "o1", "evc", "pop1"])
F = O[(O.phase == "POST") & (O.bet_type == "ワイド")][["race_id", "combo", "odds"]].rename(columns={"odds": "of"})
W = W.merge(F, on=["race_id", "combo"]).merge(PAY, on=["race_id", "combo"], how="left")
W = W[W.race_id.isin(set(PAY.race_id)) & (W.of > 0)]
W["ret"] = W.payout.fillna(0) / 100; W["date"] = W.race_id.str[4:]
W["mv"] = np.log(W.of / W.o1)
W["pb"] = pd.cut(W.pop1, [0, 1, 3, 6, 10, 15, 1e9], labels=False)
def pick(df, ocol, ecol):
    s = df[(df[ocol] >= 6) & (df[ocol] <= 10) & (df[ecol] >= 0.85)].sort_values(ecol, ascending=False)
    return s.groupby("race_id").head(5)
res = {k: [] for k in ("今のまま（1分前の倍率）", "下がりを見込んで直す", "参考：最終の倍率で選べたら（できない）")}
for d in sorted(W.date.unique()):
    tr, te = W[W.date != d], W[W.date == d].copy()
    f = tr.groupby("pb").mv.mean()
    te["fac"] = np.exp(te.pb.map(f).fillna(0))
    te["o_adj"] = te.o1 * te.fac; te["e_adj"] = te.evc * te.fac
    te["e_fin"] = te.evc * te.of / te.o1
    res["今のまま（1分前の倍率）"].append(pick(te, "o1", "evc"))
    res["下がりを見込んで直す"].append(pick(te, "o_adj", "e_adj"))
    res["参考：最終の倍率で選べたら（できない）"].append(pick(te, "of", "e_fin"))
P(f"# ワイド枠を「最後の1分の下がり」込みで選んだら（本番 {W.date.min()}〜{W.date.max()}、{W.race_id.nunique()}R）" + NL)
P("| 選び方 | 点数 | 当たり | 回収率 | 選んだ目の 1分前→最終 | 1日ごと |" + NL + "|---|---|---|---|---|---|")
for k, v in res.items():
    s = pd.concat(v)
    per = "・".join(f"{dd[4:6]}/{dd[6:]} {g.ret.mean():.0%}" for dd, g in s.groupby("date"))
    P(f"| {k} | {len(s)} | {(s.ret > 0).sum()} | **{s.ret.mean():.0%}** | {s.mv.mean():+.1%} | {per} |")
a, b = pd.concat(res["今のまま（1分前の倍率）"]), pd.concat(res["下がりを見込んで直す"])
ka, kb = set(zip(a.race_id, a.combo)), set(zip(b.race_id, b.combo))
P(NL + f"- 入れ替わり：今のままだけで選ばれる目 {len(ka - kb)}点（回収率 {a[[k not in kb for k in zip(a.race_id, a.combo)]].ret.mean():.0%}）、直した方だけで選ばれる目 {len(kb - ka)}点（回収率 {b[[k not in ka for k in zip(b.race_id, b.combo)]].ret.mean():.0%}）")
P("- 点数が数百点なので、回収率の差は偶然の範囲（ワイド6〜10倍の1点あたりの標準偏差は約2.5、200点で±35%ほどぶれる）")
print("done")
