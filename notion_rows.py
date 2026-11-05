"""Notion「競輪 仮想試験ログ」用に、日付×レース単位の行を SQLite から組み立てて JSON 出力する。
書き込み自体は Claude の Notion コネクタで行い、直後に読み戻して一致を確認する。"""
import json
import sqlite3
import sys

import kr


def build(day):
    con = kr.db()
    con.row_factory = sqlite3.Row
    out = []
    rids = [r[0] for r in con.execute(
        "SELECT DISTINCT p.race_id FROM predictions p JOIN races r USING(race_id) WHERE r.date=? ORDER BY r.close_at", (day,))]
    for rid in rids:
        r = con.execute("SELECT * FROM races WHERE race_id=?", (rid,)).fetchone()
        row = {"レースID": f"{day[:4]}-{day[4:6]}-{day[6:]}_{r['venue']}_{r['race_no']}R",
               "date:日付:start": f"{day[:4]}-{day[4:6]}-{day[6:]}", "date:日付:is_datetime": 0,
               "場": f"{r['venue']}（{r['grade']}）", "R": r["race_no"], "発走": kr.ts(r["start_at"])[11:16],
               "起動種別": "自動"}
        state = None
        for ph in ("B0", "B1"):
            ps = con.execute("SELECT * FROM predictions WHERE race_id=? AND phase=? ORDER BY pred_id", (rid, ph)).fetchall()
            if not ps:
                if ph == "B1" and r["close_at"] < kr.now().timestamp():
                    row["B1状態"] = "欠損"
                continue
            buy = [p for p in ps if p["stake"]]
            row[f"{ph}買い目"] = " / ".join(f"{p['bet_type']}{p['combo']} {p['stake']}円" for p in buy) or "見送り"
            row[f"{ph}金額"] = sum(p["stake"] for p in buy)
            row[f"{ph}保存時刻"] = ps[0]["created_at"]
            if ph == "B0":
                row["B0最低オッズ"] = " / ".join(f"{p['bet_type']}{p['combo']}≥{p['ref_odds']}" for p in buy) or "-"
                row["B0主観確率"] = " / ".join(f"{p['bet_type']}{p['combo']} p={p['model_prob']:.3f}" for p in buy) or "-"
                state = "B0保存済" if buy else "見送り"
            else:
                row["B1使用オッズ"] = " / ".join(f"{p['bet_type']}{p['combo']}@{p['ref_odds']}" for p in buy) or "-"
                row["B1オッズ取得時刻"] = ps[0]["ref_odds_fetched_at"]
                row["B1状態"] = "作成" if buy else "0円（全条件未達）"
                state = "B1判定済" if buy or state is None else state
        res = [x[0] for x in con.execute("SELECT number FROM results WHERE race_id=? ORDER BY rank LIMIT 3", (rid,))]
        if res:
            row["結果着順"] = "-".join(map(str, res))
            pay = {(b, c): p for b, c, p in con.execute("SELECT bet_type, combo, payout FROM payouts WHERE race_id=?", (rid,))}
            for ph in ("B0", "B1"):
                ps = con.execute("SELECT * FROM predictions WHERE race_id=? AND phase=? AND stake>0", (rid, ph)).fetchall()
                if ps or f"{ph}買い目" in row:
                    row[f"{ph}払戻"] = sum(pay.get((p["bet_type"], p["combo"]), 0) * p["stake"] // 100 for p in ps)
            state = "結果照合済"
        row["状態"] = state or "見送り"
        if "B0保存時刻" not in row:
            row["欠損"] = "B0なし（起動時点で締切30分未満）"
        row["備考"] = "ローカルSQLiteが正本。確率は券種間整合による市場由来の推定値（校正済みモデルではない）。実購入0円"
        out.append(row)
    return out


if __name__ == "__main__":
    day = sys.argv[1] if len(sys.argv) > 1 else kr.now().strftime("%Y%m%d")
    print(json.dumps(build(day), ensure_ascii=False, indent=1))
