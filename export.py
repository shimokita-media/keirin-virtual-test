"""SQLite -> CSV 出力、B0/B1 別の損益照合、analysis_report.md 生成。
predictions は読み取りのみ（追記専用テーブル。照合結果は別ファイル settlement.csv に出力）。"""
import json
import os
import sqlite3
from collections import defaultdict

import pandas as pd

import kr

OUT = os.path.join(kr.BASE, "out")


def main(day=None):
    day = day or kr.now().strftime("%Y%m%d")
    os.makedirs(OUT, exist_ok=True)
    con = kr.db()
    q = lambda s, p=(): pd.read_sql_query(s, con, params=p)
    races = q("SELECT * FROM races WHERE date=? ORDER BY close_at", (day,))
    races["close_jst"] = races.close_at.map(kr.ts)
    races["start_jst"] = races.start_at.map(kr.ts)
    ids = tuple(races.race_id)
    ph = ",".join("?" * len(ids))
    entries = q(f"SELECT * FROM entries WHERE race_id IN ({ph})", ids)
    odds = q(f"SELECT * FROM odds WHERE race_id IN ({ph})", ids)
    preds = q(f"SELECT * FROM predictions WHERE race_id IN ({ph}) ORDER BY pred_id", ids)
    results = q(f"SELECT * FROM results WHERE race_id IN ({ph}) ORDER BY race_id, rank", ids)
    payouts = q(f"SELECT * FROM payouts WHERE race_id IN ({ph})", ids)
    flog = q("SELECT * FROM fetch_log WHERE substr(at,1,10)=?", (f"{day[:4]}-{day[4:6]}-{day[6:]}",))
    for name, df in [("races", races), ("entries", entries), ("odds", odds), ("predictions", preds),
                     ("results", results), ("payouts", payouts), ("fetch_log", flog)]:
        df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False, encoding="utf-8-sig")

    # ---- 照合
    pay = {(r.race_id, r.bet_type, r.combo): r.payout for r in payouts.itertuples()}
    settled_races = set(payouts.race_id)
    st = []
    for p in preds.itertuples():
        settled = p.race_id in settled_races
        ret = (pay.get((p.race_id, p.bet_type, p.combo), 0) * p.stake // 100) if settled and p.stake else 0
        st.append({"race_id": p.race_id, "phase": p.phase, "bet_type": p.bet_type, "combo": p.combo,
                   "stake": p.stake, "ref_odds": p.ref_odds, "bet_rating": p.bet_rating, "race_rating": p.race_rating,
                   "settled": settled, "hit": bool(ret), "return": ret})
    st = pd.DataFrame(st)
    # 参照オッズ → 確定オッズ（POSTスナップショット）の変化。B0/B1 自体は変更しない
    fo = odds[(odds.phase == "POST") & (odds.source == "winticket")].sort_values("fetched_at") \
        .drop_duplicates(["race_id", "bet_type", "combo"], keep="last") \
        .set_index(["race_id", "bet_type", "combo"]).odds
    if len(st):
        st["final_odds"] = [fo.get((a, b, c)) for a, b, c in zip(st.race_id, st.bet_type, st.combo)]
        st["odds_drift"] = st.final_odds / st.ref_odds - 1
    st.to_csv(os.path.join(OUT, "settlement.csv"), index=False, encoding="utf-8-sig")

    # ---- 取得統計
    nrace = len(races)
    def odds_cov(src):
        d = odds[odds.source == src]
        snaps = d.groupby(["race_id", "fetched_at"])
        per = d.groupby(["race_id", "fetched_at", "bet_type"]).size().unstack(fill_value=0)
        return len(d), snaps.ngroups, per
    lines = []
    A = lines.append
    A(f"# 競輪 市場の歪み分析レポート {day[:4]}-{day[4:6]}-{day[6:]}\n")
    A(f"生成: {kr.now().strftime('%Y-%m-%d %H:%M:%S')} JST ／ **全て仮想購入。実投票は一切行っていない。**\n")
    A("## 1. データ取得\n")
    A(f"- 開催 {races.cup_id.nunique()} 場 / {nrace} レース（グレード: " +
      ", ".join(f"{g} {n}R" for g, n in races.grade.value_counts().items()) + "）")
    ok = flog.groupby(["source", "ok"]).size().unstack(fill_value=0)
    for src in ok.index:
        A(f"- {src}: リクエスト成功 {ok.loc[src].get(1, 0)} / 失敗 {ok.loc[src].get(0, 0)}")
    for src in ["winticket", "netkeirin"]:
        n, ns, per = odds_cov(src)
        if ns:
            full = {bt: int((per.get(bt, 0) > 0).sum()) for bt in kr.BET_TYPES}
            A(f"- {src} 組番別オッズ: {n:,} 行 / {ns} スナップショット。券種別取得成功率: " +
              ", ".join(f"{bt} {full[bt]}/{ns} ({full[bt]/ns:.0%})" for bt in kr.BET_TYPES))
    A(f"- 出走表 {len(entries)} 行（{entries.race_id.nunique()} レース）／ 確定着順 {results.race_id.nunique()} レース ／ 払戻 {payouts.race_id.nunique()} レース")
    A("- 未取得: 選手の詳細なバンク別成績、売上規模（発売票数）、オッズパーク（robots.txt で ClaudeBot を拒否しているため不使用）、"
      "楽天Kドリームス・チャリロト・KEIRIN.JP（本日は未実装）")

    A("\n## 2. B0 / B1（締切前に固定した判断）\n")
    if len(preds):
        g = preds.groupby(["phase"]).agg(races=("race_id", "nunique"), stake=("stake", "sum"))
        A(g.to_markdown())
        rr = preds.drop_duplicates(["race_id", "phase"]).groupby(["phase", "race_rating"]).size().unstack(fill_value=0)
        A("\nレース評価の件数（A+/A/B = 購入、C = 見送り）\n")
        A(rr.to_markdown())
    A("\n## 3. 損益（B0とB1を別々に集計。確定済みレースのみ）\n")
    if len(st):
        s = st[st.settled]
        if len(s):
            agg = s.groupby("phase").agg(bets=("stake", lambda x: int((x > 0).sum())), stake=("stake", "sum"),
                                         ret=("return", "sum"), hits=("hit", "sum"))
            agg["net"] = agg.ret - agg.stake
            agg["roi"] = (agg.ret / agg.stake.replace(0, pd.NA)).map(lambda x: f"{x:.1%}" if pd.notna(x) else "-")
            A(agg.to_markdown())
            bybt = s[s.stake > 0].groupby(["phase", "bet_type"]).agg(stake=("stake", "sum"), ret=("return", "sum"), n=("stake", "size"), hits=("hit", "sum"))
            A("\n券種別\n")
            A(bybt.to_markdown())
        A(f"\n未確定: {int((~st.settled).sum())} 行")
        d = st[(st.stake > 0) & st.final_odds.notna()]
        if len(d):
            A("\n参照オッズ → 確定オッズの変化率（中央値。マイナスは締切までに妙味が縮んだことを示す）\n")
            A(d.groupby(["phase", "bet_type"]).odds_drift.agg(["size", "median", "min", "max"]).round(3).to_markdown())

    A("\n## 4. レース別の判断と結果\n")
    for rid, grp in preds.groupby("race_id", sort=False):
        r = races[races.race_id == rid].iloc[0]
        res = results[results.race_id == rid].sort_values("rank")
        order = "-".join(str(int(x)) for x in res.number.head(3)) if len(res) else "未確定"
        A(f"### {r.venue} {r.race_no}R {r.grade} {r['class']} {r.race_type}（締切 {r.close_jst[11:16]}）着順: {order}")
        A(f"並び予想[{r.line_type}] {r.line_json}")
        for ph_, g2 in grp.groupby("phase"):
            row0 = g2.iloc[0]
            A(f"- **{ph_}** 作成 {row0.created_at[11:19]}（締切{row0.minutes_to_close}分前、オッズ掲載元更新 {row0.ref_source_updated_at[11:]}）"
              f" 評価 {row0.race_rating}")
            for x in g2.itertuples():
                if x.stake:
                    s2 = st[(st.race_id == rid) & (st.phase == ph_) & (st.combo == x.combo) & (st.bet_type == x.bet_type)]
                    rs = ("的中 " + str(int(s2["return"].iloc[0])) + "円") if len(s2) and s2.hit.iloc[0] else ("不的中" if len(s2) and s2.settled.iloc[0] else "未確定")
                    A(f"  - {x.bet_type} {x.combo} {x.stake}円 @{x.ref_odds} p={x.model_prob:.3f} EV(α1.0/1.15)={x.ev_a10:.2f}/{x.ev_a115:.2f} [{x.bet_rating}] → {rs}")
                else:
                    A("  - 見送り")
            v = json.loads(row0.reason)
            for k in ["展開", "反対意見", "前提破壊", "見落とし", "検証", "統合"]:
                if k in v:
                    A(f"  - {k}: {v[k]}")
        A("")

    # ---- 終了レース傾向（参考データ。購入価値の検証ではない）
    A("\n## 5. 確定レースの傾向（参考。判断の事後作成はしていない）\n")
    tri = payouts[payouts.bet_type == "3連単"]
    if len(tri):
        A(f"- 3連単: {len(tri)} レース、払戻の中央値 {int(tri.payout.median()):,}円、平均 {int(tri.payout.mean()):,}円")
        A(f"- 3連単の人気順（中央値）{tri.popularity.median():.0f}番人気。1〜5番人気での決着 {int((tri.popularity <= 5).sum())}/{len(tri)}、"
          f"30番人気以下 {int((tri.popularity > 30).sum())}/{len(tri)}")
        for bt in ["2車単", "2車複", "3連複"]:
            b = payouts[payouts.bet_type == bt]
            if len(b):
                A(f"- {bt}: 1番人気での決着 {int((b.popularity == 1).sum())}/{len(b)}、払戻の中央値 {int(b.payout.median()):,}円")
        fac = results[results["rank"] == 1].factor.value_counts()
        A("- 1着の決まり手: " + ", ".join(f"{k or '不明'} {v}" for k, v in fac.items()))
    # 確定オッズ上の券種間歪みの的中率（事後シミュレーション：取引可能ではない）
    fin = odds[(odds.phase == "POST") & (odds.source == "winticket")]
    sim = []
    for rid, g in fin.groupby("race_id"):
        if rid not in settled_races:
            continue
        od = {bt: {} for bt in kr.BET_TYPES}
        for x in g.itertuples():
            od[x.bet_type][x.combo] = (x.odds, x.odds_max, x.popularity)
        for e in kr.evaluate(od):
            if kr.rate(e) != "C":
                sim.append({"race_id": rid, "bet_type": e["bet_type"], "rating": kr.rate(e), "odds": e["odds"],
                            "ret": pay.get((rid, e["bet_type"], e["combo"]), 0) / 100})
    n_fin = fin.race_id.nunique()
    A(f"\n確定オッズでの事後点検: {n_fin} レース中、評価B以上（EVc≥1.10 かつ p≥2%）の組番は {len(sim)} 件"
      "（確定時点の5券種プールはほぼ整合している。早い時間帯の歪みは票の薄さによるもので、締切までに消える可能性が高い）")
    if sim:
        sm = pd.DataFrame(sim)
        agg = sm.groupby("rating").agg(n=("ret", "size"), hits=("ret", lambda x: int((x > 0).sum())), ret=("ret", "sum"))
        agg["roi"] = (agg.ret / agg.n).map("{:.1%}".format)
        A("\n**参考: 確定オッズを使った事後シミュレーション**（確定オッズは締切後にしか分からないため、取引可能な検証ではない。"
          "モデルの方向性を点検する目的に限る。各組番に1単位ずつ賭けた場合）\n")
        A(agg.to_markdown())
        A("\n券種別\n")
        agg2 = sm.groupby("bet_type").agg(n=("ret", "size"), hits=("ret", lambda x: int((x > 0).sum())), ret=("ret", "sum"))
        agg2["roi"] = (agg2.ret / agg2.n).map("{:.1%}".format)
        A(agg2.to_markdown())
        sm.to_csv(os.path.join(OUT, "posthoc_final_odds_sim.csv"), index=False, encoding="utf-8-sig")
    open(os.path.join(OUT, "analysis_report.md"), "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines[:60]))


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
