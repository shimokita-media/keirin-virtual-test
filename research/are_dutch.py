"""「当たれば必ず元が取れる」買い方（合成オッズ・BOXの金額配分）を、探索期間の全部の3連単の最終オッズで調べる。
- 合成オッズ S = 1 / Σ(1/オッズ)。各目に (1/オッズ)/Σ(1/オッズ) の割合で賭けると、どの目が当たっても 払戻 = 賭け金×S。S≥1 なら当たれば必ず元が取れる。
- 市場が正しければ 当たる確率 ≈ Σ(見込み) ≈ 0.75×Σ(1/オッズ) = 0.75/S。だから「元が取れる確率」と「回収率」はトレードオフ。
DBは取り込み中なので mode=ro・100レースずつ・1秒休みで読む（ana_build_small と同じ流儀）。"""
import sqlite3, time, os, itertools, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; S = K + "out/are_work/"
race, _ = pd.read_pickle(S + "are_cache.pkl")
race["type"] = np.where((race.fav >= 15) & (race.nlines >= 4), "荒れ予想", "その他")
race["half"] = np.where(race.date < "20251226", "前", "後")
if not os.path.exists(S + "tri_odds.pkl"):
    c = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    ids = list(race.race_id); O = []
    for i in range(0, len(ids), 100):
        q = ids[i:i + 100]
        o = pd.read_sql(f"SELECT race_id, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND bet_type='3連単' AND odds>0 AND race_id IN ({','.join('?'*len(q))})", c, params=q)
        o = o[o.fetched_at == o.groupby("race_id").fetched_at.transform("max")].drop(columns="fetched_at")
        O.append(o); time.sleep(1.0)
        if i % 5000 == 0: print("read", i, flush=True)
    c.close(); O = pd.concat(O); O.to_pickle(S + "tri_odds.pkl")
O = pd.read_pickle(S + "tri_odds.pkl")
O = O.merge(race[["race_id", "win", "pay", "type", "half", "n"]], on="race_id")
O["inv"] = 1 / O.odds
O["hit"] = O.combo == O.win
print("目", len(O), "レース", O.race_id.nunique(), "1レースの平均の目", round(len(O) / O.race_id.nunique(), 1), "Σ(1/オッズ)の平均", round(O.groupby("race_id").inv.sum().mean(), 3))
pd.set_option("display.width", 250)
res = []
def settle(sel, label):
    # sel: 買う目（race_id, inv, hit）。賭け金合計1、配分∝inv。払戻＝当たり目の配分×実際の払戻/100
    g = sel.assign(hv=sel.inv * sel.hit).groupby("race_id").agg(sinv=("inv", "sum"), hinv=("hv", "sum"), npt=("inv", "size"))
    g = g.join(race.set_index("race_id")[["pay", "type", "half"]])
    g["ret"] = (g.hinv / g.sinv) * (g.pay / 100)  # 賭け金1あたりの払戻
    g["Sx"] = 1 / g.sinv
    for ty in ["全部", "荒れ予想", "その他"]:
        x = g if ty == "全部" else g[g.type == ty]
        if not len(x): continue
        r = lambda y: round(100 * y.ret.mean(), 1) if len(y) else None
        res.append((label, ty, len(x), round(x.npt.mean(), 1), round(x.Sx.mean(), 2), round(100 * (x.ret > 0).mean(), 1), round(100 * (x.ret >= 1).mean(), 1), r(x), r(x[x.half == "前"]), r(x[x.half == "後"])))
# A. 人気順に足していき、合成オッズが T 以上の範囲で一番広く買う
O = O.sort_values(["race_id", "odds"])
O["cum"] = O.groupby("race_id").inv.cumsum()
for T in [1.0, 1.1, 1.25, 1.5, 2.0, 3.0]:
    settle(O[1 / O.cum >= T], f"人気順に合成オッズ{T}倍まで")
# B. BOX（選手は3連単から出した3着内の見込みの順）、金額は∝1/オッズ、合成オッズ≥1のレースだけ
cb = O.combo.str.split("-", expand=True).astype(int)
pp = O.inv / O.groupby("race_id").inv.transform("sum")
p3 = pd.concat([pd.DataFrame({"race_id": O.race_id, "num": cb[k], "p": pp}) for k in range(3)]).groupby(["race_id", "num"]).p.sum().reset_index()
p3["rk"] = p3.groupby("race_id").p.rank(ascending=False, method="first")
rk = {k: dict(zip(g.num, g.rk)) for k, g in p3.groupby("race_id")}
O["r0"] = [rk[r].get(a, 99) for r, a in zip(O.race_id, cb[0])]; O["r1"] = [rk[r].get(a, 99) for r, a in zip(O.race_id, cb[1])]; O["r2"] = [rk[r].get(a, 99) for r, a in zip(O.race_id, cb[2])]
O["mx"] = O[["r0", "r1", "r2"]].max(axis=1); O["mn"] = O[["r0", "r1", "r2"]].min(axis=1)
for lo, hi in [(1, 3), (1, 4), (1, 5), (1, 6), (2, 5), (2, 6), (2, 7)]:
    sel = O[(O.mn >= lo) & (O.mx <= hi)]
    sinv = sel.groupby("race_id").inv.transform("sum")
    k = hi - lo + 1
    settle(sel, f"{lo}〜{hi}番手の{k}人BOX・金額配分（全部のレース）")
    settle(sel[1 / sinv >= 1.0], f"{lo}〜{hi}番手の{k}人BOX・金額配分（合成1倍以上のレースだけ）")
    settle(sel[1 / sinv >= 1.5], f"{lo}〜{hi}番手の{k}人BOX・金額配分（合成1.5倍以上のレースだけ）")
R = pd.DataFrame(res, columns=["買い方", "レース", "レース数", "1レースの点数", "合成オッズ平均", "当たり%", "元が取れた%", "回収率%", "前", "後"])
print(R.to_string())
R.to_pickle(S + "dutch_res.pkl")
