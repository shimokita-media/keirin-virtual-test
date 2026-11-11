"""B1W（ワイド枠）の最終オッズ事後判定（2026-11-11 Codex が下書き、Claude が確かめて保存）。y5 の下書き ④ 用。
実行例:
  python -I -X utf8 research/prereg_eval_y5_wide.py \
    20260901 20261004 reports/wide_20260901_20261004.md --m 5
  python -I -X utf8 research/prereg_eval_y5_wide.py \
    20211108 20221107 reports/wide_y5.md --half 20220508 --m 5

書き込み先は指定したレポートのみ。DBはmode=roで接続する。
"""
import argparse
import datetime as dt
import os
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kr  # noqa: E402


def parse_date(s):
    return dt.datetime.strptime(s, "%Y%m%d").date()


def db_uri(path):
    # WindowsパスもSQLite URIで扱えるようにする
    p = Path(path).resolve().as_posix()
    if len(p) >= 2 and p[1] == ":":
        p = "/" + p
    return "file:" + p + "?mode=ro"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", help="開始日 YYYYMMDD（含む）")
    ap.add_argument("end", help="終了日 YYYYMMDD（含む）")
    ap.add_argument("output", help="出力 Markdown")
    ap.add_argument("--half", help="前半の最終日 YYYYMMDD")
    ap.add_argument("--m", type=int, required=True, help="BH補正で使う事前登録仮説数")
    ap.add_argument(
        "--db",
        default=os.environ.get("KDB", str(ROOT / "keirin.sqlite")),
        help="読み取り専用で開くSQLiteファイル（既定: KDB環境変数または keirin.sqlite）",
    )
    args = ap.parse_args()

    d0, d1 = parse_date(args.start), parse_date(args.end)
    if d1 < d0:
        ap.error("終了日は開始日以降にしてください")
    if args.m < 1:
        ap.error("--m は1以上にしてください")
    half = parse_date(args.half) if args.half else d0 + (d1 - d0) // 2
    if not d0 <= half < d1:
        ap.error("前半最終日は開始日以上、終了日より前にしてください")

    # 指定期間内で払戻が存在するレースだけを対象にする。
    # DBから日付・race_idの一覧を得た後、オッズと払戻は50レースずつ読む。
    con = sqlite3.connect(db_uri(args.db), uri=True, timeout=30)
    try:
        races = con.execute(
            """SELECT r.race_id, r.date
                 FROM races r
                WHERE r.date BETWEEN ? AND ?
                  AND EXISTS (SELECT 1 FROM payouts p WHERE p.race_id = r.race_id)
                ORDER BY r.date, r.race_id""",
            (args.start, args.end),
        ).fetchall()

        selected = []
        for i0 in range(0, len(races), 50):
            if i0:
                time.sleep(1.0)
            batch = races[i0:i0 + 50]
            ids = [r[0] for r in batch]
            marks = ",".join("?" for _ in ids)

            # 各レースのPOST・WINTICKETで最も新しいスナップショットを取得。
            # BET_TYPES全券種を読み、kr.evaluateにそのまま渡す。
            odds_rows = con.execute(
                f"""SELECT o.race_id, o.bet_type, o.combo, o.odds,
                           o.odds_max, o.popularity
                      FROM odds o
                     WHERE o.phase='POST'
                       AND o.source='winticket'
                       AND o.race_id IN ({marks})
                       AND o.fetched_at = (
                           SELECT MAX(o2.fetched_at)
                             FROM odds o2
                            WHERE o2.race_id=o.race_id
                              AND o2.phase='POST'
                              AND o2.source='winticket'
                       )""",
                ids,
            ).fetchall()

            payout_rows = con.execute(
                f"""SELECT race_id, combo, payout
                      FROM payouts
                     WHERE bet_type='ワイド'
                       AND race_id IN ({marks})""",
                ids,
            ).fetchall()

            by_race = {rid: {bt: {} for bt in kr.BET_TYPES} for rid in ids}
            for rid, bt, combo, odds, odds_max, popularity in odds_rows:
                if bt in by_race[rid]:
                    by_race[rid][bt][combo] = (odds, odds_max, popularity)

            payout = {(rid, combo): amount for rid, combo, amount in payout_rows}

            for rid, date in batch:
                od = by_race[rid]
                if not od.get("3連単") or not od.get("ワイド"):
                    continue

                # 本番と同じ評価・選び方。払戻がない組番は不的中=0円。
                evrows = kr.evaluate(od)
                candidates = [
                    r for r in evrows
                    if r["bet_type"] == "ワイド"
                    and 6 <= r["odds"] <= 10
                    and r["evc"] >= 0.85
                ]
                candidates.sort(key=lambda r: -r["evc"])
                for r in candidates[:5]:
                    amount = payout.get((rid, r["combo"]), 0) or 0
                    selected.append({
                        "race_id": rid,
                        "date": date,
                        "combo": r["combo"],
                        "odds": r["odds"],
                        "evc": r["evc"],
                        "ret": amount / 100.0,
                    })
    finally:
        con.close()

    if not selected:
        raise SystemExit("対象買い目がありません。期間・POSTオッズ・払戻の収録状況を確認してください。")

    # レース単位ブートストラップ。各点100円なので、総払戻倍率/点数が回収率。
    rng = np.random.default_rng(0)
    race_ids = list(dict.fromkeys(x["race_id"] for x in selected))
    per_race = {}
    for x in selected:
        s, n = per_race.get(x["race_id"], (0.0, 0))
        per_race[x["race_id"]] = (s + x["ret"], n + 1)

    sums = np.array([per_race[r][0] for r in race_ids])
    counts = np.array([per_race[r][1] for r in race_ids])
    draw = rng.integers(0, len(race_ids), size=(4000, len(race_ids)))
    boot = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)

    ret = np.array([x["ret"] for x in selected])
    dates = np.array([x["date"] for x in selected])
    half_s = half.strftime("%Y%m%d")  # 日付は文字列 YYYYMMDD でそろえる（Codex の下書きの型の誤りを直した）
    h1 = ret[dates <= half_s]
    h2 = ret[dates > half_s]
    roi = ret.mean()
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p = float((boot <= 1.0).mean())

    # 今回の行はワイド仮説1つ。BHの順位1に対し、
    # 他の事前登録仮説も含むmを適用する。
    bh_pass = p <= 0.05 / args.m
    passed = lo >= 0.95 and len(h1) > 0 and len(h2) > 0 \
        and h1.mean() > 1.0 and h2.mean() > 1.0 and bh_pass

    report = [
        f"# ワイド枠の判定（{args.start}〜{args.end}）",
        "",
        f"- 前半：{args.start}〜{half:%Y%m%d}、後半：{(half + dt.timedelta(days=1)):%Y%m%d}〜{args.end}",
        f"- 対象レース：{len(race_ids):,}、買い目：{len(selected):,}点（各100円）",
        f"- 回収率：{roi:.1%}（95%レース単位ブートストラップ範囲 {lo:.1%}〜{hi:.1%}）",
        f"- 前半 / 後半：{h1.mean():.1%} / {h2.mean():.1%}",
        f"- BH用 p値：{p:.4f}、m={args.m}、判定閾値={0.05 / args.m:.4f}",
        f"- 判定：{'合格' if passed else '不合格'}",
        "",
        "選定条件：POSTのWINTICKET確定オッズ、ワイド6〜10倍、"
        "kr.evaluateのevc 0.85以上、evc順で1レース最大5点。",
    ]
    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
