"""締切前に固定した買い目 × 確定の払戻 だけで各枠の成績を出す（条件は今のまま固定・選び方の調整はしない）。
使い方: python research/preclose_eval.py [DBのパス]  → reports/preclose_live.md
A. 実際に記録した買い目（predictions。判断した時点で固定されたもの）
B. 判断した時点（B1R）の倍率の記録から、各枠の今の条件で選び直した買い目（記録が始まる前の枠も同じ時点で比べるため）
   参考：締切1分前（T1）の記録からも同様に
C. 最終オッズで選び直した買い目（比較用。実際には買えない）
払戻：確定の払戻表のみ。買い目の選手が判断後に欠場していたら返還（100円戻し）。払戻表がまだ無いレースは「未確定」で除外"""
import os, sys, json, sqlite3
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
import kr, tri_rule, wide_rule
START = "20261106"
FRAMES = {"B1W": "🎯ワイド枠（通知中）", "B3T": "🎰3連単枠（通知中・11/9〜記録）", "B3T1": "⭐3連単枠の一番の目1点（選び直しで確認）", "B3TB": "⭐一番の目×ラインの先頭のB（バック回数）がレースで一番多い（選び直しで確認）", "B3TS": "⭐一番の目×出走表の点数3以上（選び直しで確認）", "B3K": "👀形のワイド（記録のみ・11/9〜）", "B3A": "👀ワイドA（記録のみ・11/9〜）", "B1R": "📐法則枠（記録のみ）"}


from tri_rule import card_score  # 点数の計算は tri_rule.py に一本化（2026-11-09）


def pick_all(con, row, od):
    out = {}
    ev = kr.evaluate(od)
    w = sorted([r for r in ev if r["bet_type"] == "ワイド" and 6 <= r["odds"] <= 10 and r["evc"] >= 0.85], key=lambda r: -r["evc"])[:5]
    out["B1W"] = [("ワイド", r["combo"], r["odds"]) for r in w]
    rp, _ = kr.rule_picks(con, row, od)
    out["B1R"] = [(r["bet_type"], r["combo"], r["odds"]) for r in rp]
    out["B3T"] = [("3連単", r["combo"], r["odds"]) for r in tri_rule.picks(con, row, od)]
    out["B3T1"] = out["B3T"][:1]  # 一番の目：当たった法則の数が多い順・倍率の低い順で1番目（tri_rule.picks の並び順）
    out["B3TB"] = []
    if out["B3T1"]:  # 一番の目の3着の選手がいるラインの先頭が、各ラインの先頭の中でバック回数（B）が一番多いときだけ（2026-11-09 追加）
        lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(row["line_json"] or "[]")]
        nb = dict(con.execute("SELECT number, COALESCE(n_back,0) FROM entries WHERE race_id=? AND absent=0", (row["race_id"],)).fetchall())
        third = int(out["B3T1"][0][1].split("-")[2]); main = next((l for l in lines if third in l), None)
        if main and nb.get(main[0], 0) >= max(nb.get(l[0], 0) for l in lines):
            out["B3TB"] = out["B3T1"]
    out["B3TS"] = []
    if out["B3T1"] and card_score(con, row, out["B3T1"][0][1]) >= 3:
        out["B3TS"] = out["B3T1"]
    wr = wide_rule.picks(con, row, od)
    out["B3A"] = [("ワイド", r["combo"], r["odds"]) for r in wr["B3A"]]
    out["B3K"] = [("ワイド", r["combo"], r["odds"]) for r in wr["B3K"]]
    return out


def main(db):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    races = {r["race_id"]: r for r in con.execute("SELECT * FROM races WHERE date >= ? ORDER BY close_at", (START,))}
    ids = tuple(races); q = ",".join("?" * len(ids))
    pay = pd.read_sql(f"SELECT race_id, bet_type, combo, payout FROM payouts WHERE race_id IN ({q})", con, params=ids)
    settled = set(pay.race_id); payd = {(a, b, c): p for a, b, c, p in pay.itertuples(index=False)}
    absent = {(a, n) for a, n in con.execute(f"SELECT race_id, number FROM entries WHERE absent=1 AND race_id IN ({q})", ids)}
    od_all = pd.read_sql(f"SELECT race_id, phase, bet_type, combo, odds, odds_max, popularity, fetched_at FROM odds WHERE source='winticket' AND phase IN ('B1R','T1','POST') AND race_id IN ({q})", con, params=ids)
    od_all = od_all[od_all.fetched_at == od_all.groupby(["race_id", "phase"]).fetched_at.transform("max")]
    ODS = {}
    for (rid, ph), g in od_all.groupby(["race_id", "phase"]):
        d = {bt: {} for bt in kr.BET_TYPES}
        for bt, cb, o, om, pp in zip(g.bet_type, g.combo, g.odds, g.odds_max, g.popularity):
            if bt in d: d[bt][cb] = (o, om, pp)
        ODS[(rid, ph)] = d
    fin_odds = {(r, bt, cb): o for r, bt, cb, o in od_all[od_all.phase == "POST"][["race_id", "bet_type", "combo", "odds"]].itertuples(index=False)}

    def settle(rid, bt, cb):
        if rid not in settled: return None, "未確定"
        if any((rid, int(n)) in absent for n in cb.split("-")): return 100, "返還"
        return payd.get((rid, bt, cb), 0), ""

    rows = []
    # A. 実際に記録した買い目
    P = pd.read_sql(f"SELECT race_id, phase, bet_type, combo, stake, ref_odds FROM predictions WHERE stake>0 AND phase IN ({','.join('?'*len(FRAMES))}) AND race_id IN ({q})", con, params=tuple(FRAMES) + ids)
    for rid, ph, bt, cb, st, o in P.itertuples(index=False):
        rows.append(("A", ph, rid, bt, cb, o))
    # B/C. 記録した倍率から選び直す
    for (rid, ph), od in ODS.items():
        if ph not in ("B1R", "T1", "POST") or not od["3連単"]: continue
        row = races[rid]
        if ph == "POST" and (rid, "B1R") not in ODS and (rid, "T1") not in ODS: continue  # 比較は締切前の記録があるレースに揃える
        try: picks = pick_all(con, row, od)
        except Exception as e: print("ERR", rid, ph, repr(e)); continue
        tag = {"B1R": "B", "T1": "B1", "POST": "C"}[ph]
        for fr, ps in picks.items():
            for bt, cb, o in ps: rows.append((tag, fr, rid, bt, cb, o))
    D = pd.DataFrame(rows, columns=["kind", "frame", "race_id", "bet_type", "combo", "odds"]).drop_duplicates(["kind", "frame", "race_id", "bet_type", "combo"])
    st = [settle(r, b, c) for r, b, c in zip(D.race_id, D.bet_type, D.combo)]
    D["pay"] = [s[0] for s in st]; D["note"] = [s[1] for s in st]
    D["date"] = D.race_id.map(lambda r: races[r]["date"])
    D["fin"] = [fin_odds.get((r, b, c)) for r, b, c in zip(D.race_id, D.bet_type, D.combo)]
    pend = D[D.pay.isna()]; S = D[D.pay.notna()].copy(); S["ret"] = S.pay / 100

    def line(g):
        if not len(g): return "| 0 | − | − | − | − | − | − |"
        by = g.groupby("race_id").agg(inv=("ret", "size"), r=("ret", "sum"))
        i = np.random.default_rng(0).integers(0, len(by), (2000, len(by))); bs = by.r.to_numpy()[i].sum(1) / by.inv.to_numpy()[i].sum(1)
        ch = (g.fin / g.odds - 1).dropna()
        return (f"| {len(g)} | {g.race_id.nunique()} | {int(((g.ret > 0) & (g.note != '返還')).sum())} | {len(g)*100:,}円→{int(g.pay.sum()):,}円 | **{g.ret.mean():.0%}** "
                f"| {np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%} | {('%+.0f%%' % (np.median(ch)*100)) if len(ch) else '−'} |")
    d0, d1 = S.date.min(), S.date.max()
    L = [f"# 締切前に固定した買い目 × 確定の払戻（{d0[4:6]}/{d0[6:]}〜{d1[4:6]}/{d1[6:]}・各100円）\n",
         "条件は今のまま固定。払戻は確定の払戻表だけ（判断後の欠場は返還）。払戻表が無いレースは未確定で除外。",
         "「買った時→最終」は、選んだ時点の倍率から最終の倍率への変化（中央値。マイナス＝払戻が減った）。\n",
         "| 枠 | 種類 | 点数 | レース | 的中 | 投資→払戻 | 回収率 | 95%の範囲 | 買った時→最終 |", "|---|---|---|---|---|---|---|---|---|"]
    KL = {"A": "A 実際に記録した買い目", "B": "B 判断時点（2〜3分前）の倍率で選び直し", "B1": "B' 締切1分前の倍率で選び直し", "C": "C 最終オッズで選び直し（比較・買えない）"}
    for fr, lab in FRAMES.items():
        for k in ("A", "B", "B1", "C"):
            g = S[(S.frame == fr) & (S.kind == k)]
            if k == "A" and not len(g): L.append(f"| {lab} | {KL[k]} | まだ記録なし | | | | | | |"); continue
            L.append(f"| {lab} | {KL[k]} " + line(g))
    # 日ごと（B と A）
    L += ["\n## 日ごと（B 判断時点で選び直し ／ A 実際の記録）", "| 枠 | " + " | ".join(f"{d[4:6]}/{d[6:]}" for d in sorted(S.date.unique())) + " |", "|---|" + "---|" * S.date.nunique()]
    for fr, lab in FRAMES.items():
        cells = []
        for d in sorted(S.date.unique()):
            b = S[(S.frame == fr) & (S.kind == "B") & (S.date == d)]; a = S[(S.frame == fr) & (S.kind == "A") & (S.date == d)]
            cells.append((f"{b.ret.mean():.0%}({len(b)})" if len(b) else "−") + " ／ " + (f"{a.ret.mean():.0%}({len(a)})" if len(a) else "−"))
        L.append(f"| {lab} | " + " | ".join(cells) + " |")
    # 一致の確認（実際の記録 と 判断時点の選び直し）
    L += ["\n## 選び直しの正しさの確認（同じ判断時点の倍率から、実際の記録と同じ目を選べているか）"]
    for fr in FRAMES:
        a = set(map(tuple, D[(D.frame == fr) & (D.kind == "A")][["race_id", "combo"]].to_numpy())); b = set(map(tuple, D[(D.frame == fr) & (D.kind == "B")][["race_id", "combo"]].to_numpy()))
        if a: L.append(f"- {FRAMES[fr]}：記録 {len(a)}点・選び直し {len(b & {x for x in b if x[0] in {y[0] for y in a} or True})}点・一致 {len(a & b)}点（記録のうち {len(a & b)/len(a):.0%}）")
    L.append(f"\n未確定で除外：{pend.race_id.nunique()}レース・{len(pend)}点 ／ 返還：{int((S.note == '返還').sum())}点")
    txt = "\n".join(L)
    os.makedirs(os.path.join(BASE, "reports"), exist_ok=True)
    open(os.path.join(BASE, "reports", "preclose_live.md"), "w", encoding="utf-8").write(txt); print(txt)
    D.to_csv(os.path.join(BASE, "reports", "preclose_picks.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "eval_work", "keirin.sqlite"))
