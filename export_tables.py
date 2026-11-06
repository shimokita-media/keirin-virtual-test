"""レース一覧・選手一覧・全組み合わせの確定オッズを CSV に書き出す（Excel で開ける UTF-8 BOM 付き）。
使い方: python export_tables.py 20261106 [20261106]  -> out/tables/ に3ファイル
  races_YYYYMMDD.csv / players_YYYYMMDD.csv / odds_YYYYMMDD.csv（期間指定なら races_開始_終了.csv など）"""
import json
import os
import sys

import pandas as pd

import kr

OUTDIR = os.path.join(kr.BASE, "out", "tables")
CLS = {1: "S", 2: "A", 3: "L"}


def _races(c, d0, d1):
    return pd.read_sql("SELECT race_id, date, venue, grade, race_no, class, race_type, close_at, line_type, line_json "
                       "FROM races WHERE date BETWEEN ? AND ?", c, params=(d0, d1))


def races_table(c, d0, d1):
    r = _races(c, d0, d1)
    ids = tuple(r.race_id) or ("",)
    ph = ",".join("?" * len(ids))
    n_ent = pd.read_sql(f"SELECT race_id, COUNT(*) n FROM entries WHERE absent=0 AND race_id IN ({ph}) GROUP BY race_id", c, params=ids).set_index("race_id").n
    oc = pd.read_sql(f"SELECT race_id, bet_type, COUNT(DISTINCT combo) n FROM odds WHERE phase='POST' AND source='winticket' "
                     f"AND race_id IN ({ph}) GROUP BY race_id, bet_type", c, params=ids)
    oc = oc.pivot(index="race_id", columns="bet_type", values="n") if len(oc) else pd.DataFrame()
    res = pd.read_sql(f"SELECT race_id, rank, number, factor FROM results WHERE rank BETWEEN 1 AND 3 AND race_id IN ({ph}) "
                      "ORDER BY race_id, rank, number", c, params=ids)
    order = res.groupby("race_id").apply(lambda g: "-".join(map(str, g.number)) + ("（同着あり）" if g["rank"].duplicated().any() else "")) if len(res) else pd.Series(dtype=str)
    fac = res[res["rank"] == 1].groupby("race_id").factor.first() if len(res) else pd.Series(dtype=str)
    pay = pd.read_sql(f"SELECT race_id, bet_type, combo, payout, popularity FROM payouts WHERE race_id IN ({ph})", c, params=ids)
    out = pd.DataFrame({"レースID": r.race_id, "日付": r.date.str[:4] + "/" + r.date.str[4:6] + "/" + r.date.str[6:], "競輪場": r.venue,
                        "グレード": r.grade, "R": r.race_no, "級班": r["class"], "種類": r.race_type,
                        "締切": r.close_at.map(lambda t: kr.ts(t)[11:16]), "出走": r.race_id.map(n_ent), "並び": r.line_type})
    for bt in kr.BET_TYPES:
        out[f"オッズ件数_{bt}"] = r.race_id.map(oc[bt]) if bt in oc else None
    out["着順"] = r.race_id.map(order)
    out["決まり手"] = r.race_id.map(fac)
    for bt in ["3連単", "3連複", "2車単", "2車複", "ワイド"]:
        g = pay[pay.bet_type == bt].groupby("race_id")
        out[f"{bt}_組番"] = r.race_id.map(g.combo.apply(lambda s: " / ".join(s))) if len(pay) else None
        out[f"{bt}_払戻"] = r.race_id.map(g.payout.apply(lambda s: " / ".join(f"{int(p):,}" for p in s))) if len(pay) else None
        out[f"{bt}_人気"] = r.race_id.map(g.popularity.apply(lambda s: " / ".join("" if p != p else str(int(p)) for p in s))) if len(pay) else None
    out["状態"] = out["3連単_払戻"].isna().map({True: "中止または未確定", False: ""})
    return out.sort_values(["日付", "締切", "競輪場"])


def players_table(c, d0, d1):
    r = _races(c, d0, d1).set_index("race_id")
    ids = tuple(r.index) or ("",)
    ph = ",".join("?" * len(ids))
    e = pd.read_sql(f"SELECT * FROM entries WHERE race_id IN ({ph})", c, params=ids)
    res = pd.read_sql(f"SELECT race_id, number, rank, factor, margin FROM results WHERE race_id IN ({ph})", c, params=ids)
    pos = []
    for rid, lj in r.line_json.items():
        try:
            lines = json.loads(lj) if isinstance(lj, str) else []
        except Exception:
            lines = []
        for l in lines:
            nums = [n for x in l["entries"] for n in x["numbers"]]
            for k, n in enumerate(nums):
                pos.append((rid, n, "-".join(map(str, nums)), "単騎" if len(nums) == 1 else ["先頭", "番手", "3番手", "4番手以降"][min(k, 3)]))
    pos = pd.DataFrame(pos, columns=["race_id", "number", "ライン", "ライン内の位置"])
    d = e.merge(pos, on=["race_id", "number"], how="left").merge(res, on=["race_id", "number"], how="left")
    d = d.join(r[["date", "venue", "grade", "race_no", "class", "race_type", "line_type"]], on="race_id", rsuffix="_r")
    out = pd.DataFrame({
        "レースID": d.race_id, "日付": d.date.str[:4] + "/" + d.date.str[4:6] + "/" + d.date.str[6:], "競輪場": d.venue, "グレード": d.grade,
        "R": d.race_no, "レース級班": d["class_r"], "種類": d.race_type, "並びの型": d.line_type, "車番": d.number, "枠": d.bracket,
        "選手名": d["name"], "府県": d.prefecture, "期": d.term, "年齢": d.age,
        "級班": d["class"].map(lambda x: CLS.get(x, x)).astype(str) + d.grp.fillna(0).astype(int).astype(str) + "班",
        "脚質": d["style"], "ギア": d.gear, "競走得点": d.race_point, "コメント": d.comment, "1着率": d.first_rate,
        "2連対率": d.second_rate, "3連対率": d.third_rate, "逃げ回数": d.n_front, "捲り回数": d.n_stalker, "差し回数": d.n_closer,
        "マーク回数": d.n_marker, "直近の着順": d.recent_orders, "ライン": d["ライン"], "ライン内の位置": d["ライン内の位置"],
        "欠場": d.absent.map({1: "欠場", 0: ""}),
        "着順": d["rank"].map(lambda x: "" if x != x else ("失格・落車など" if x == 0 else int(x))), "決まり手": d.factor, "着差": d.margin})
    return out.sort_values(["日付", "競輪場", "R", "車番"])


def odds_table(c, d0, d1):
    r = _races(c, d0, d1).set_index("race_id")
    o = pd.read_sql("""SELECT o.race_id, o.bet_type, o.combo, o.odds, o.odds_max, o.popularity, o.fetched_at FROM odds o JOIN races x USING(race_id)
                       WHERE o.phase='POST' AND o.source='winticket' AND x.date BETWEEN ? AND ?""", c, params=(d0, d1))
    o = o.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo"], keep="last")
    pay = pd.read_sql("""SELECT p.race_id, p.bet_type, p.combo, p.payout FROM payouts p JOIN races x USING(race_id)
                         WHERE x.date BETWEEN ? AND ?""", c, params=(d0, d1)).set_index(["race_id", "bet_type", "combo"]).payout
    idx = pd.MultiIndex.from_frame(o[["race_id", "bet_type", "combo"]])
    out = pd.DataFrame({"レースID": o.race_id.values, "日付": o.race_id.map(r.date).values, "競輪場": o.race_id.map(r.venue).values,
                        "R": o.race_id.map(r.race_no).values, "券種": o.bet_type.values, "組番": o.combo.values, "確定オッズ": o.odds.values,
                        "ワイド上限": o.odds_max.values, "人気": o.popularity.values, "的中なら払戻": pay.reindex(idx).values})
    return out.sort_values(["日付", "競輪場", "R", "券種", "人気"])


def main(d0, d1=None):
    d1 = d1 or d0
    tag = d0 if d0 == d1 else f"{d0}_{d1}"
    os.makedirs(OUTDIR, exist_ok=True)
    c = kr.db()
    paths = []
    for name, fn in [("races", races_table), ("players", players_table), ("odds", odds_table)]:
        df = fn(c, d0, d1)
        p = os.path.join(OUTDIR, f"{name}_{tag}.csv")
        df.to_csv(p, index=False, encoding="utf-8-sig")
        paths.append((p, len(df)))
    return paths


if __name__ == "__main__":
    for p, n in main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None):
        print(p, n, "行")
