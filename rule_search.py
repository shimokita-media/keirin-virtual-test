"""回収率100%超の買い方を「前半で探索 → 後半で検証」の手順で探す（確定オッズでの事後分析）。
使い方: python rule_search.py  -> out/rule_search.md, out/bets_features.parquet(csv)"""
import json
import os

import numpy as np
import pandas as pd

import kr

OUT = os.path.join(kr.BASE, "out")


def build():
    c = kr.db()
    races = pd.read_sql("SELECT race_id, cup_id, day_index, date, class, grade, line_json, race_type FROM races", c)
    pay = pd.read_sql("SELECT race_id, bet_type, combo, payout FROM payouts", c)
    races = races[races.race_id.isin(pay.race_id)]
    fin = races[races.race_type.str.contains("決勝")].groupby("cup_id").date.max()
    races["日程"] = np.where(races.date == races.cup_id.str[:8], "初日",
                          np.where(races.date == races.cup_id.map(fin), "最終日", "中日"))
    ent = pd.read_sql("SELECT race_id, number, style, race_point FROM entries WHERE absent=0", c)
    odds = pd.read_sql("SELECT race_id, bet_type, combo, odds, popularity, fetched_at FROM odds "
                       "WHERE phase='POST' AND source='winticket'", c)
    odds = odds.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo"], keep="last")
    odds = odds[odds.race_id.isin(races.race_id) & (odds.odds < 9999)]
    paymap = {(r.race_id, r.bet_type, r.combo): r.payout for r in pay.itertuples()}
    rinfo = races.set_index("race_id")
    eg = {k: g.set_index("number") for k, g in ent.groupby("race_id")}
    rows = []
    for rid, g in odds.groupby("race_id"):
        od = {bt: {} for bt in kr.BET_TYPES}
        for x in g.itertuples():
            od[x.bet_type][x.combo] = (x.odds, None, x.popularity)
        ev = kr.evaluate(od)
        ri = rinfo.loc[rid]
        lines = [[n for e in l["entries"] for n in e["numbers"]] for l in json.loads(ri.line_json or "[]")]
        pos = {}
        for li, l in enumerate(lines):
            for k, n in enumerate(l):
                pos[n] = (li, "単騎" if len(l) == 1 else ["先頭", "番手", "3番手", "4番手以降"][min(k, 3)])
        e = eg.get(rid)
        if e is None or not lines:
            continue
        top = e.race_point.idxmax()
        ncar = f"{len(e)}車"
        for r in ev:
            nums = list(map(int, r["combo"].split("-")))
            f = nums[0]
            li_f, pos_f = pos.get(f, (None, "不明"))
            same = len({pos.get(n, (None,))[0] for n in nums}) == 1 and li_f is not None
            rows.append({
                "race_id": rid, "date": ri.date, "日程": ri["日程"], "級班": ri["class"], "車立て": ncar,
                "券種": r["bet_type"], "combo": r["combo"], "倍率": r["odds"], "人気": r["pop"], "推定確率": r["p"], "見込み倍率比": r["evc"],
                "先頭車の位置": pos_f if r["bet_type"] in ("3連単", "2車単") else "対象外",
                "先頭車の脚質": (e.style.get(f) if f in e.index else None) if r["bet_type"] in ("3連単", "2車単") else "対象外",
                "先頭車が得点1位": (f == top) if r["bet_type"] in ("3連単", "2車単") else None,
                "同ライン決着": same,
                "払戻": paymap.get((rid, r["bet_type"], r["combo"]), 0) / 100})
    df = pd.DataFrame(rows)
    df["倍率帯"] = pd.cut(df.倍率, [0, 3, 6, 10, 20, 50, 100, 300, 1e6], labels=["〜3", "3〜6", "6〜10", "10〜20", "20〜50", "50〜100", "100〜300", "300〜"])
    df["見込み帯"] = pd.cut(df.見込み倍率比, [0, 0.7, 0.85, 1.0, 1.15, 99], labels=["〜0.7", "0.7〜0.85", "0.85〜1.0", "1.0〜1.15", "1.15〜"])
    df.to_pickle(os.path.join(OUT, "bets_features.pkl"))
    return df


def search(df):
    dates = sorted(df.date.unique())
    half = dates[len(dates) // 2]
    tr, te = df[df.date < half], df[df.date >= half]
    feats = ["券種", "倍率帯", "見込み帯", "日程", "級班", "車立て", "先頭車の位置", "先頭車の脚質", "先頭車が得点1位", "同ライン決着"]
    res = []
    import itertools
    for k in (1, 2, 3):
        for fs in itertools.combinations(feats, k):
            g = tr.groupby(list(fs), observed=True).agg(n=("払戻", "size"), hits=("払戻", lambda x: int((x > 0).sum())),
                                                        ret=("払戻", "sum"), races=("race_id", "nunique"))
            g = g[(g.n >= 300) & (g.hits >= 20)]
            for key, row in g.iterrows():
                key = key if isinstance(key, tuple) else (key,)
                res.append({"条件": " × ".join(f"{f}={v}" for f, v in zip(fs, key)), "fs": fs, "key": key,
                            "前半_点数": int(row.n), "前半_的中": int(row.hits), "前半_回収率": row.ret / row.n})
    R = pd.DataFrame(res).sort_values("前半_回収率", ascending=False)
    cand = R[R.前半_回収率 >= 1.05].head(40).copy()
    for i, r in cand.iterrows():
        m = np.ones(len(te), bool)
        for f, v in zip(r.fs, r.key):
            m &= (te[f] == v).to_numpy()
        t = te[m]
        cand.loc[i, "後半_点数"] = len(t)
        cand.loc[i, "後半_的中"] = int((t.払戻 > 0).sum())
        cand.loc[i, "後半_回収率"] = t.払戻.sum() / max(len(t), 1)
        # 後半の95%区間（レース単位ブートストラップ）
        if len(t):
            gg = t.groupby("race_id").agg(ret=("払戻", "sum"), n=("払戻", "size"))
            a, b = gg.ret.to_numpy(), gg.n.to_numpy()
            idx = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg)))
            rr = a[idx].sum(1) / b[idx].sum(1)
            cand.loc[i, "後半_下限"], cand.loc[i, "後半_上限"] = np.percentile(rr, 2.5), np.percentile(rr, 97.5)
    return R, cand, half


def main():
    p = os.path.join(OUT, "bets_features.pkl")
    df = pd.read_pickle(p) if os.path.exists(p) else build()
    R, cand, half = search(df)
    L = [f"# 回収率100%超の買い方の探索（確定オッズ・事後分析）\n",
         f"対象 {df.race_id.nunique()} レース・{len(df):,} 組番。前半（〜{half}の前日）で探索し、後半（{half}〜）で検証。",
         f"前半で調べた条件の数: {len(R):,}（点数300以上・的中20以上のもの）。前半で回収率105%以上だった上位40件を後半で検証。\n",
         "注意: 確定オッズは締切後に決まる値で、実際に買える締切直前の倍率とはずれる。"
         "多数の条件を調べているため、前半で良く見える条件の多くは偶然。後半でも100%を超えたかが判断の基準。\n"]
    show = cand.assign(**{c: cand[c].map(lambda x: f"{x:.0%}") for c in ["前半_回収率", "後半_回収率", "後半_下限", "後半_上限"]})
    L.append(show[["条件", "前半_点数", "前半_的中", "前半_回収率", "後半_点数", "後半_的中", "後半_回収率", "後半_下限", "後半_上限"]].to_markdown(index=False))
    ok = cand[(cand.後半_回収率 >= 1.0)]
    L.append(f"\n後半でも100%以上: {len(ok)} / {len(cand)} 件。うち後半の95%区間の下限が100%超: {int((cand.後半_下限 > 1).sum())} 件")
    open(os.path.join(OUT, "rule_search.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
