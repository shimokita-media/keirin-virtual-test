"""過去の確定データで「実際の的中率より倍率が高い（市場が過小評価する）」パターンを探す。
確定オッズ（phase='POST'）と払戻を使う事後分析。95%信頼区間はレース単位のブートストラップで算出。
使い方: python history.py   -> out/history_report.md"""
import json
import os
import sqlite3

import numpy as np
import pandas as pd

import kr

OUT = os.path.join(kr.BASE, "out")
RNG = np.random.default_rng(0)


def load():
    con = kr.db()
    races = pd.read_sql("SELECT * FROM races WHERE race_id IN (SELECT DISTINCT race_id FROM payouts)", con)
    odds = pd.read_sql("SELECT race_id, bet_type, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket'", con)
    odds = odds.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo"], keep="last")
    odds = odds[odds.race_id.isin(races.race_id)]
    pay = pd.read_sql("SELECT race_id, bet_type, combo, payout FROM payouts", con)
    res = pd.read_sql("SELECT race_id, rank, number FROM results", con)
    ent = pd.read_sql("SELECT * FROM entries WHERE absent=0", con)
    return con, races, odds, pay, res, ent


def boot_ratio(df, num, den, key="race_id", B=1000):
    """レース単位で再標本化して、sum(num)/sum(den) の95%区間を求める"""
    g = df.groupby(key)[[num, den]].sum()
    if len(g) < 5:
        return np.nan, np.nan
    a, b = g[num].to_numpy(), g[den].to_numpy()
    idx = RNG.integers(0, len(g), (B, len(g)))
    r = a[idx].sum(1) / np.maximum(b[idx].sum(1), 1e-9)
    return np.percentile(r, 2.5), np.percentile(r, 97.5)


def venue_pref():
    try:
        q = json.load(open(os.path.join(kr.BASE, "tomorrow.json"), encoding="utf-8"))
        return {v["id"]: v["prefecture"] for v in q["FETCH_KEIRIN_VENUE_LIST"]["venues"]}
    except Exception:
        return {}


def main():
    con, races, odds, pay, res, ent = load()
    L = []
    A = L.append
    n_r = races.race_id.nunique()
    A(f"# 過去レース分析（確定オッズ × 確定結果）\n\n生成 {kr.now():%Y-%m-%d %H:%M} ／ 対象 {n_r} レース"
      f"（{races.date.min()}〜{races.date.max()}、{races.date.nunique()} 日）\n")
    A("確定オッズは締切後に確定する値で、実際に買える価格は締切前の値（今日の観測では確定までに下がる傾向）。"
      "ここで回収率100%を超えるパターンでも、締切前の価格で買えば下回る可能性がある。\n")
    A("**読み方**: 回収率の95%区間の下限が100%を超えていれば、統計的に「実際の的中率より倍率が高い」と言える。"
      "区間が100%をまたぐ場合は判定不能。\n")

    # ---- 1. 倍率帯 × 券種
    o = odds.merge(pay, how="left", on=["race_id", "bet_type", "combo"])
    o["ret"] = o.payout.fillna(0) / 100
    o["one"] = 1.0
    o = o[o.odds < 9999]
    bands = [0, 2, 3, 5, 10, 20, 50, 100, 300, 1000, 1e6]
    o["band"] = pd.cut(o.odds, bands)
    A("## 1. 倍率帯ごとの回収率（各組番に100円ずつ買った場合）\n")
    rows = []
    for (bt, band), g in o.groupby(["bet_type", "band"], observed=True):
        lo, hi = boot_ratio(g, "ret", "one")
        rows.append({"券種": bt, "倍率帯": str(band), "点数": len(g), "的中": int((g.ret > 0).sum()),
                     "回収率": g.ret.sum() / len(g), "95%下限": lo, "95%上限": hi})
    t1 = pd.DataFrame(rows)
    fmt = lambda df: df.assign(**{c: df[c].map(lambda x: f"{x:.0%}" if pd.notna(x) else "-") for c in ["回収率", "95%下限", "95%上限"]})
    A(fmt(t1).to_markdown(index=False))

    # ---- 2. 選手属性 × 市場評価
    pref = venue_pref()
    recs = []
    for rid, g in o.groupby("race_id"):
        tri = g[g.bet_type == "3連単"]
        if tri.empty:
            continue
        q = 1 / tri.odds.to_numpy()
        p = q / q.sum()
        w, t2, t3 = {}, {}, {}
        for c, pp in zip(tri.combo, p):
            i, j, k = map(int, c.split("-"))
            w[i] = w.get(i, 0) + pp
            for x in (i, j):
                t2[x] = t2.get(x, 0) + pp
            for x in (i, j, k):
                t3[x] = t3.get(x, 0) + pp
        recs.append((rid, w, t2, t3))
    rk = {(r.race_id, r.number): (r.rank if r.rank >= 1 else 99) for r in res.itertuples()}  # 0=落車・失格等は着外扱い
    rinfo = races.set_index("race_id")
    E = []
    for rid, w, t2, t3 in recs:
        e = ent[ent.race_id == rid]
        if e.empty:
            continue
        ri = rinfo.loc[rid]
        lines = json.loads(ri.line_json or "[]")
        pos, llen = {}, {}
        for li, l in enumerate(lines):
            nums = [n for x in l["entries"] for n in x["numbers"]]
            for k, n in enumerate(nums):
                pos[n] = (li, k, len(nums))
        e = e.copy()
        e["pt_rank"] = e.race_point.rank(ascending=False, method="min")
        e["fr_rank"] = e.first_rate.rank(ascending=False, method="min")
        n_car = len(e)
        leaders = {}
        for n, (li, k, ln) in pos.items():
            if k == 0:
                leaders[li] = float(e.loc[e.number == n, "race_point"].iloc[0]) if (e.number == n).any() else np.nan
        for x in e.itertuples():
            li, k, ln = pos.get(x.number, (None, None, None))
            if li is None:
                ps = "不明"
            elif ln == 1:
                ps = "単騎"
            else:
                ps = ["先頭", "番手", "3番手", "4番手以降"][min(k, 3)]
            lead_pt = leaders.get(li, np.nan) if li is not None else np.nan
            E.append({"race_id": rid, "number": x.number, "grade": ri.grade, "class": ri["class"],
                      "n_car": f"{n_car}車", "line_type": ri.line_type or "不明", "pos": ps, "line_len": ln,
                      "style": x.style, "local": "地元" if pref.get(ri.venue_id) == x.prefecture else "地元外",
                      "pt_gap": x.pt_rank - x.fr_rank,
                      "leader_gap": (lead_pt - x.race_point) if ps in ("番手", "3番手", "4番手以降") else np.nan,
                      "m_win": w.get(x.number, 0), "m_top2": t2.get(x.number, 0), "m_top3": t3.get(x.number, 0),
                      "win": int(rk.get((rid, x.number), 9) == 1), "top2": int(rk.get((rid, x.number), 9) <= 2),
                      "top3": int(rk.get((rid, x.number), 9) <= 3)})
    E = pd.DataFrame(E)
    E["得点と1着率"] = pd.cut(E.pt_gap, [-99, -3, 2, 99], labels=["1着率の順位が得点より3以上下", "ほぼ同じ",
                                                              "1着率の順位が得点より3以上上（得点が低いのによく勝つ）"])
    E["先頭との得点差"] = pd.cut(E.leader_gap, [-99, -5, 0, 5, 99],
                          labels=["先頭が自分より5点以上弱い", "先頭がやや弱い", "先頭がやや強い", "先頭が5点以上強い"])
    E["市場1着率帯"] = pd.cut(E.m_win, [0, .02, .05, .1, .2, .4, 1], include_lowest=True)
    A(f"\n## 2. 選手の属性別：市場の見込み vs 実際（{len(E)} 選手・{E.race_id.nunique()} レース）\n")
    A("比率 = 実際の回数 ÷ 市場が見込んだ回数（3連単の確定オッズから算出）。1.0より大きいほど市場の過小評価"
      "（倍率が実力より高い）。95%区間はレース単位のブートストラップ。\n")
    sig = []
    for col, name in [("pos", "ライン内の位置"), ("style", "脚質"), ("local", "地元"), ("n_car", "車立て"),
                      ("grade", "グレード"), ("class", "級班"), ("line_type", "並びの型"), ("得点と1着率", "得点と1着率の乖離"),
                      ("先頭との得点差", "番手以降：先頭選手との得点差"), ("市場1着率帯", "市場の1着評価帯（人気薄〜本命）")]:
        rows = []
        for v, g in E.groupby(col, observed=True):
            if len(g) < 30:
                continue
            r = {"区分": str(v), "人数": len(g)}
            for tgt, m in [("win", "m_win"), ("top2", "m_top2"), ("top3", "m_top3")]:
                lo, hi = boot_ratio(g, tgt, m)
                ratio = g[tgt].sum() / g[m].sum()
                r[{"win": "1着", "top2": "連対", "top3": "3着内"}[tgt]] = f"{ratio:.2f} [{lo:.2f}-{hi:.2f}]"
                if lo > 1.0 or hi < 1.0:
                    sig.append((name, str(v), {"win": "1着", "top2": "連対", "top3": "3着内"}[tgt], ratio, lo, hi, len(g)))
            rows.append(r)
        if rows:
            A(f"\n### {name}\n")
            A(pd.DataFrame(rows).to_markdown(index=False))
    A("\n## 3. 95%区間が1.0をまたがなかった（統計的に偏りがある）パターン\n")
    if sig:
        s = pd.DataFrame(sig, columns=["観点", "区分", "対象", "比率", "下限", "上限", "人数"]).sort_values("比率", ascending=False)
        s["判定"] = np.where(s.下限 > 1, "過小評価（倍率が実力より高い）", "過大評価（倍率が実力より低い）")
        A(s.round(2).to_markdown(index=False))
    else:
        A("なし")
    A("\n注意: 多数の区分を同時に検定しているため、5%程度は偶然でも有意に見える。データ期間を変えて再現するか確認が必要。")
    # ---- 4. 傾向を買い目に落とした戦略の回収率（前半/後半で再現性確認）
    A("\n## 4. 戦略バックテスト（確定オッズ、各100円。前半・後半の期間で再現するか）\n")
    dates = sorted(races.date.unique())
    half = dates[len(dates) // 2]
    ri2 = races.set_index("race_id")
    pos_of = {}
    for rid, g in E.groupby("race_id"):
        pos_of[rid] = g.set_index("number")
    od = {k: v for k, v in o.groupby(["race_id", "bet_type"])}
    strat = []
    for rid, g in pos_of.items():
        fav = g.m_win.idxmax()
        lines = json.loads(ri2.loc[rid].line_json or "[]")
        bets = {}
        ex = od.get((rid, "2車単"))
        tri = od.get((rid, "3連単"))
        if ex is None or tri is None:
            continue
        exd = ex.set_index("combo")
        trd = tri.set_index("combo")
        def add(name, table, combos):
            for c in combos:
                if c in table.index:
                    bets.setdefault(name, []).append(table.loc[c, "ret"])
        add("本命1着流し 2車単", exd, [f"{fav}-{n}" for n in g.index if n != fav])
        fav_s = g.loc[fav]
        if fav_s.pos == "先頭":
            add("本命が先頭(自力)のとき 本命1着流し 2車単", exd, [f"{fav}-{n}" for n in g.index if n != fav])
        if fav_s.style == "追":
            add("本命が追込のとき 本命1着流し 2車単", exd, [f"{fav}-{n}" for n in g.index if n != fav])
        for l in lines:
            nums = [n for x in l["entries"] for n in x["numbers"]]
            if len(nums) >= 2 and nums[0] in g.index and g.loc[nums[0]].style in ("逃", "両"):
                add("自力先頭→番手 2車単（全ライン）", exd, [f"{nums[0]}-{nums[1]}"])
                add("番手→自力先頭 2車単（全ライン）", exd, [f"{nums[1]}-{nums[0]}"])
            if len(nums) >= 3 and nums[0] in g.index:
                add("ライン3車 先頭-番手-3番手 3連単", trd, ["-".join(map(str, nums[:3]))])
        for name, rets in bets.items():
            strat.append({"race_id": rid, "期": "前半" if ri2.loc[rid].date < half else "後半", "戦略": name,
                          "ret": float(np.sum(rets)), "one": float(len(rets))})
    S = pd.DataFrame(strat)
    rows = []
    for (name,), g in S.groupby(["戦略"]):
        r = {"戦略": name, "点数": int(g.one.sum()), "回収率": g.ret.sum() / g.one.sum()}
        r["95%下限"], r["95%上限"] = boot_ratio(g, "ret", "one")
        for p in ("前半", "後半"):
            gg = g[g.期 == p]
            r[p] = gg.ret.sum() / gg.one.sum() if len(gg) else np.nan
        rows.append(r)
    t4 = pd.DataFrame(rows).sort_values("回収率", ascending=False)
    A(t4.assign(**{c: t4[c].map(lambda x: f"{x:.0%}" if pd.notna(x) else "-") for c in ["回収率", "95%下限", "95%上限", "前半", "後半"]}).to_markdown(index=False))
    A(f"\n前半 = {dates[0]}〜{half} の前日、後半 = {half}〜{dates[-1]}")

    os.makedirs(OUT, exist_ok=True)
    E.to_csv(os.path.join(OUT, "history_players.csv"), index=False, encoding="utf-8-sig")
    t1.to_csv(os.path.join(OUT, "history_odds_bands.csv"), index=False, encoding="utf-8-sig")
    open(os.path.join(OUT, "history_report.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
