"""T05 の初期分析（2026-11-11 Codex が下書き、Claude が確かめて保存）。読み取り専用の本番DBコピーから Markdown 報告を書き出す。
使い方: python -I -X utf8 research/t05_analysis.py reports/t05_analysis.md
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DB = "file:C:/Users/take0/.claude/keirin/out/live_db/keirin.sqlite?mode=ro"
BET = "3連単"
PHASES = ("T1", "T05", "POST")
CAP = 200
BOOTSTRAPS = 4000
RNG_SEED = 0
NL = "\n"


def parse_utc(value):
    """DBの時刻はJSTのタイムゾーンなし文字列の場合がある。naive値はJSTとして扱う。"""
    if pd.isna(value) or value == "":
        return pd.NaT
    t = pd.Timestamp(value)
    if t.tzinfo is None:
        return t.tz_localize("Asia/Tokyo").tz_convert("UTC")
    return t.tz_convert("UTC")


def normalize_inverse_odds(frame, odds_col, prob_col):
    q = 1.0 / frame[odds_col]
    denom = q.groupby(frame["race_id"]).transform("sum")
    frame[prob_col] = q / denom


def make_fifths(values):
    """同値が多くても5区分を作れるよう、順位でほぼ同数に分ける。"""
    pct = values.rank(method="first", pct=True)
    idx = np.ceil(pct * 5).clip(1, 5).astype(int)
    names = {
        1: "1（伸びが大きい）",
        2: "2",
        3: "3",
        4: "4",
        5: "5（縮みが大きい）",
    }
    return idx.map(names)


def bootstrap_intervals(frame, bucket_col, p_col, rng):
    """レースを単位に再標本化し、的中÷見込みと回収率の95%範囲を返す。"""
    races = frame["race_id"].drop_duplicates().to_numpy()
    if len(races) == 0:
        return {}

    bins = list(frame[bucket_col].dropna().drop_duplicates())
    # race × bucket の合計値を作る。存在しない組み合わせは0。
    sums = frame.groupby(["race_id", bucket_col], observed=True).agg(
        hits=("hit", "sum"),
        expected=(p_col, "sum"),
        payout=("payout", "sum"),
        points=("hit", "size"),
    )
    result = {}
    for bucket in bins:
        per_race = sums.xs(bucket, level=bucket_col).reindex(races, fill_value=0)
        h = per_race["hits"].to_numpy(dtype=float)
        e = per_race["expected"].to_numpy(dtype=float)
        pay = per_race["payout"].to_numpy(dtype=float)
        n = per_race["points"].to_numpy(dtype=float)

        ratios = np.empty(BOOTSTRAPS)
        rois = np.empty(BOOTSTRAPS)
        for i in range(BOOTSTRAPS):
            sample = rng.integers(0, len(races), size=len(races))
            ratios[i] = h[sample].sum() / e[sample].sum() if e[sample].sum() else np.nan
            rois[i] = pay[sample].sum() / (100.0 * n[sample].sum()) if n[sample].sum() else np.nan

        result[bucket] = (
            np.nanpercentile(ratios, 2.5),
            np.nanpercentile(ratios, 97.5),
            np.nanpercentile(rois, 2.5),
            np.nanpercentile(rois, 97.5),
        )
    return result


def write_report(path):
    # SQLite自体を読み取り専用で開く。DBへの書き込みはしない。
    con = sqlite3.connect(DB, uri=True)
    try:
        odds = pd.read_sql_query(
            """
            SELECT rowid AS seq, race_id, combo, phase, odds,
                   source_updated_at, fetched_at
            FROM odds
            WHERE source='winticket'
              AND bet_type=?
              AND phase IN ('T1', 'T05', 'POST')
              AND odds > 0
            ORDER BY fetched_at, rowid
            """,
            con,
            params=(BET,),
        )
        payouts = pd.read_sql_query(
            """
            SELECT race_id, combo, payout
            FROM payouts
            WHERE bet_type=?
            """,
            con,
            params=(BET,),
        )
        races = pd.read_sql_query(
            "SELECT race_id, close_at FROM races",
            con,
        )
    finally:
        con.close()

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 開催日は race_id の末尾8桁で判定する。
    odds = odds[odds["race_id"].astype(str).str[-8:] >= "20261111"].copy()
    if odds.empty:
        out_path.write_text(
            "# T05 分析\n\n対象データがありません。\n",
            encoding="utf-8",
        )
        return

    # 同じレース・組・phaseの重複は、fetched_at順で最後の記録を使う。
    odds = odds.sort_values(["fetched_at", "seq"], kind="mergesort")
    latest = odds.drop_duplicates(
        ["race_id", "combo", "phase"],
        keep="last",
    )

    wide = latest.pivot(
        index=["race_id", "combo"],
        columns="phase",
        values="odds",
    ).reset_index()
    wide.columns.name = None
    wide = wide.dropna(subset=list(PHASES))
    wide = wide[wide["T1"] <= CAP].copy()

    # 各phaseの取得時刻・配信元更新時刻は、最後に取得した行を代表値にする。
    phase_meta = (
        latest.sort_values(["fetched_at", "seq"], kind="mergesort")
        .groupby(["race_id", "phase"], as_index=False)
        .tail(1)
        [["race_id", "phase", "source_updated_at", "fetched_at"]]
    )
    meta = phase_meta.pivot(
        index="race_id",
        columns="phase",
        values=["source_updated_at", "fetched_at"],
    )
    meta.columns = [f"{a}_{b}" for a, b in meta.columns]
    meta = meta.reset_index()

    payouts = payouts.drop_duplicates(["race_id", "combo"], keep="last")
    payout_races = set(payouts["race_id"].dropna().unique())
    wide = wide[wide["race_id"].isin(payout_races)].copy()
    wide = wide.merge(payouts, on=["race_id", "combo"], how="left")
    # 払戻のある組を的中とし、払戻なしは0円として回収率に含める。
    wide["payout"] = pd.to_numeric(wide["payout"], errors="coerce").fillna(0.0)
    wide["hit"] = (wide["payout"] > 0).astype(int)

    # 対象レースは、条件を満たす3連単の点が1点以上あるレース。
    eligible_races = set(wide["race_id"].unique())
    wide = wide[wide["race_id"].isin(eligible_races)].copy()
    for phase in PHASES:
        normalize_inverse_odds(wide, phase, f"p_{phase}")

    # 比率の正値が「その組の見込みが増えた＝縮んだ」を表す。
    wide["move_1_05"] = np.log(wide["p_T05"] / wide["p_T1"])
    wide["move_1_post"] = np.log(wide["p_POST"] / wide["p_T1"])
    wide["move_05_post"] = np.log(wide["p_POST"] / wide["p_T05"])
    wide["fifth_1_05"] = make_fifths(wide["move_1_05"])
    wide["fifth_1_post"] = make_fifths(wide["move_1_post"])

    # ① phaseごとの代表的な配信元更新時刻と取得時刻を比べる。
    meta = meta[meta["race_id"].isin(eligible_races)].copy()
    for col in (
        "source_updated_at_T1", "source_updated_at_T05",
        "fetched_at_T1", "fetched_at_T05",
    ):
        if col in meta:
            meta[col + "_utc"] = meta[col].map(parse_utc)

    valid_source = meta.dropna(
        subset=["source_updated_at_T1_utc", "source_updated_at_T05_utc"]
    ).copy()
    advanced = (
        valid_source["source_updated_at_T05_utc"]
        > valid_source["source_updated_at_T1_utc"]
    )
    same_source = (
        valid_source["source_updated_at_T05_utc"]
        == valid_source["source_updated_at_T1_utc"]
    )
    source_regressed = (
        valid_source["source_updated_at_T05_utc"]
        < valid_source["source_updated_at_T1_utc"]
    )

    # オッズ値そのものに差が出たレースの割合も別に確認する。
    moved_odds = wide.groupby("race_id").apply(
        lambda g: bool(
            ((g["T1"] - g["T05"]).abs() > 1e-12).any()
        ),
        include_groups=False,
    )
    odds_changed_races = int(moved_odds.sum())

    # close_atはUnix秒。取得時刻はJST naiveまたはtimezone付き文字列をUTCにそろえて差を取る。
    race_close = races[races["race_id"].isin(eligible_races)].copy()
    race_close["close_utc"] = pd.to_datetime(
        pd.to_numeric(race_close["close_at"], errors="coerce"),
        unit="s",
        utc=True,
        errors="coerce",
    )
    meta = meta.merge(race_close[["race_id", "close_utc"]], on="race_id", how="left")
    for phase in ("T1", "T05"):
        col = f"fetched_at_{phase}_utc"
        if col in meta:
            meta[f"seconds_before_{phase}"] = (
                meta["close_utc"] - meta[col]
            ).dt.total_seconds()

    # ② 5分位ごとの集計とレース単位ブートストラップ。
    rng = np.random.default_rng(RNG_SEED)
    ci_05 = bootstrap_intervals(wide, "fifth_1_05", "p_T05", rng)
    ci_post = bootstrap_intervals(wide, "fifth_1_post", "p_T1", rng)

    lines = []

    def P(*parts):
        lines.append(" ".join(str(x) for x in parts))

    nr = wide["race_id"].nunique()
    npoints = len(wide)
    nhits = int(wide["hit"].sum())
    dates = sorted(wide["race_id"].astype(str).str[-8:].unique())

    P("# T05 分析")
    P()
    P(f"- 対象開催日：{dates[0]}〜{dates[-1]}（{len(dates)}日）")
    P(f"- 対象レース：**{nr:,}R**、対象点数：**{npoints:,}点**、当たり：**{nhits:,}本**")
    P("- 条件：開催日が2026-11-11以降、T1・T05・POSTがそろい、確定払戻のあるレース。T1が200倍以下の3連単を対象。")
    P("- 見込みは各レース・各phase内で、対象点の逆数倍率を合計1に正規化。")
    if nr < 200:
        P()
        P(f"**まだ少ない：対象は{nr}Rで、200R未満です。**")
    P()

    P("## ① T1からT05の間に倍率が更新されたか")
    P()
    P(
        f"- 配信元の更新時刻（source_updated_at）がT1よりT05で進んだレース："
        f"**{int(advanced.sum()):,}/{len(valid_source):,}R**"
        f"（{advanced.mean():.1%}）"
        if len(valid_source) else
        "- 配信元の更新時刻を比較できるレースはありません。"
    )
    P(
        f"- 更新時刻が同じ：{int(same_source.sum()):,}R、"
        f"後退：{int(source_regressed.sum()):,}R"
    )
    P(
        f"- T1とT05で、対象3連単の倍率が1つ以上異なるレース："
        f"**{odds_changed_races:,}/{nr:,}R**"
        f"（{odds_changed_races / nr:.1%}）" if nr else
        "- 対象レースがありません。"
    )
    if len(valid_source):
        fetched_gaps = (
            valid_source["fetched_at_T05_utc"] - valid_source["fetched_at_T1_utc"]
        ).dt.total_seconds().dropna()
        if len(fetched_gaps):
            P(
                f"- T1からT05までの取得間隔：中央値"
                f"{fetched_gaps.median():.0f}秒"
            )
    P()

    P("## ② T1→T05で縮んだ目と的中・回収率")
    P()
    P("変化量は `log（T05の見込み / T1の見込み）`。値が大きいほどT05で縮んだ目を表します。")
    P()
    P("| T1→T05の5段階 | 点数 | 当たり | 平均変化量 | 当たり÷T05見込み | 95%範囲 | 回収率 | 95%範囲 |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|")
    for bucket in sorted(wide["fifth_1_05"].dropna().unique()):
        g = wide[wide["fifth_1_05"] == bucket]
        ratio = g["hit"].sum() / g["p_T05"].sum() if g["p_T05"].sum() else np.nan
        roi = g["payout"].sum() / (100.0 * len(g)) if len(g) else np.nan
        lo, hi, rlo, rhi = ci_05[bucket]
        P(
            f"| {bucket} | {len(g):,} | {int(g['hit'].sum()):,} | "
            f"{g['move_1_05'].mean():+.3f} | {ratio:.2f} | "
            f"{lo:.2f}〜{hi:.2f} | {roi:.1%} | {rlo:.1%}〜{rhi:.1%} |"
        )
    P()
    P("### 参考：T1→POSTの動きと的中")
    P()
    P("同じ5段階の作り方でT1→POSTの変化を分け、当たり÷T1見込みを計算します。既報の1.67倍はT1時点の見込みに対する比較値です。")
    P()
    P("| T1→POSTの5段階 | 点数 | 当たり | 平均変化量 | 当たり÷T1見込み | 95%範囲 | 回収率 | 95%範囲 |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|")
    for bucket in sorted(wide["fifth_1_post"].dropna().unique()):
        g = wide[wide["fifth_1_post"] == bucket]
        ratio = g["hit"].sum() / g["p_T1"].sum() if g["p_T1"].sum() else np.nan
        roi = g["payout"].sum() / (100.0 * len(g)) if len(g) else np.nan
        lo, hi, rlo, rhi = ci_post[bucket]
        P(
            f"| {bucket} | {len(g):,} | {int(g['hit'].sum()):,} | "
            f"{g['move_1_post'].mean():+.3f} | {ratio:.2f} | "
            f"{lo:.2f}〜{hi:.2f} | {roi:.1%} | {rlo:.1%}〜{rhi:.1%} |"
        )
    P()
    post_hits = wide[wide["hit"] == 1]
    if len(post_hits):
        winner_move = np.exp(post_hits["move_1_post"]).mean()
        P(
            f"- 的中目におけるPOST/T1見込み比の算術平均：{winner_move:.2f}倍"
            f"（既報の1.67倍と見比べる参考値。正規化後の見込み比）"
        )
    P()

    P("## ③ T05からPOSTまでの残りの動き")
    P()
    abs_05_post = wide["move_05_post"].abs()
    abs_1_post = wide["move_1_post"].abs()
    P(f"- T05→POSTの平均絶対log変化：**{abs_05_post.mean():.3f}**")
    P(f"- T1→POSTの平均絶対log変化：**{abs_1_post.mean():.3f}**")
    if abs_1_post.mean() > 0:
        P(f"- T05→POST / T1→POST：**{abs_05_post.mean() / abs_1_post.mean():.1%}**")
    P(f"- 符号付き平均変化（T05→POST）：{wide['move_05_post'].mean():+.3f}")
    P(f"- 符号付き平均変化（T1→POST）：{wide['move_1_post'].mean():+.3f}")
    P()

    # 締切からの秒数をレポートし、時刻の扱いを目視できるようにする。
    for phase in ("T1", "T05"):
        col = f"seconds_before_{phase}"
        s = meta[col].dropna() if col in meta else pd.Series(dtype=float)
        if len(s):
            P(
                f"- {phase}取得時刻の締切前秒数："
                f"{s.min():.0f}〜{s.max():.0f}秒前、中央値{s.median():.0f}秒前"
            )

    out_path.write_text(NL.join(lines) + NL, encoding="utf-8")
    print(f"wrote {out_path}: {nr}R, {npoints}点, {nhits}本")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "使い方: python -I -X utf8 research/t05_analysis.py reports/t05_analysis.md"
        )
    write_report(sys.argv[1])
