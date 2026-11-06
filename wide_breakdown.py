"""ワイド枠（ワイド6〜10倍・割安度0.85以上・最大5点）を過去の全レースに当てはめ、
時間帯・曜日・何レース目か・グレード・競輪場などの区分ごとに成績を出す（確定オッズでの事後計算）。
各区分について、月ごとに100%を超えた月の数も出して、たまたまの偏りと区別する。
使い方: python wide_breakdown.py [開始] [終了] -> out/wide_breakdown.md"""
import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

import kr

OUT = os.path.join(kr.BASE, "out")
YOBI = "月火水木金土日"


def build(d0, d1):
    cache = os.path.join(OUT, f"wide_picks2_{d0}_{d1}.pkl")
    if os.path.exists(cache):
        return pd.read_pickle(cache)
    con = kr.db()
    con.row_factory = sqlite3.Row
    try:
        q = json.load(open(os.path.join(kr.BASE, "tomorrow.json"), encoding="utf-8"))
        bank = {v["id"]: f"{v['trackDistance']}m" for v in q["FETCH_KEIRIN_VENUE_LIST"]["venues"]}
    except Exception:
        bank = {}
    pay = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT p.race_id, p.combo, p.payout FROM payouts p JOIN races r USING(race_id) WHERE p.bet_type='ワイド' AND r.date BETWEEN ? AND ?", (d0, d1))}
    rows = []
    races = con.execute("SELECT * FROM races WHERE date BETWEEN ? AND ? AND race_id IN (SELECT race_id FROM payouts) ORDER BY close_at", (d0, d1)).fetchall()
    for r in races:
        od = {bt: {} for bt in kr.BET_TYPES}
        for bt, cb, o, om, p in con.execute("""SELECT bet_type, combo, odds, odds_max, popularity FROM odds WHERE race_id=? AND phase='POST'
                AND source='winticket' AND fetched_at=(SELECT MAX(fetched_at) FROM odds WHERE race_id=? AND phase='POST' AND source='winticket')""",
                                            (r["race_id"], r["race_id"])):
            od[bt][cb] = (o, om, p)
        if not od["3連単"]:
            continue
        ev = kr.evaluate(od)
        picks = sorted([e for e in ev if e["bet_type"] == "ワイド" and 6 <= e["odds"] <= 10 and e["evc"] >= 0.85], key=lambda e: -e["evc"])[:5]
        if not picks:
            continue
        P = kr.tri_probs(od, 1.0)
        win = {}
        for (i, j, k), p in P.items():
            win[i] = win.get(i, 0) + p
        fav = max(win.values()) if win else 0
        n_car = con.execute("SELECT COUNT(*) FROM entries WHERE race_id=? AND absent=0", (r["race_id"],)).fetchone()[0]
        # 買うワイドの中身（2人の関係）を調べるための情報
        ent = {x[0]: x for x in con.execute("SELECT number, style, race_point FROM entries WHERE race_id=? AND absent=0", (r["race_id"],))}
        lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(r["line_json"] or "[]")]
        lid = {n: i for i, l in enumerate(lines) for n in l}
        posd = {n: ("単騎" if len(l) == 1 else ["先頭", "番手", "3番手", "4番手以降"][min(k, 3)]) for l in lines for k, n in enumerate(l)}
        top_pt = max(ent.values(), key=lambda x: x[2] or 0)[0] if ent else None
        fav_no = max(win, key=win.get) if win else None
        wrank = {cb: i + 1 for i, (cb, o) in enumerate(sorted(od["ワイド"].items(), key=lambda kv: kv[1][0]))}
        st = dt.datetime.fromtimestamp(r["start_at"], kr.JST)
        day = "初日" if r["date"] == r["cup_id"][:8] else ("最終日" if "決勝" in (r["race_type"] or "") else "中日")
        for e in picks:
            rows.append({"race_id": r["race_id"], "月": r["date"][:6], "date": r["date"], "時刻": st.hour,
                         "曜日": YOBI[st.weekday()], "R": r["race_no"], "グレード": r["grade"], "級班": r["class"],
                         "競輪場": r["venue"], "バンク": bank.get(r["venue_id"], "不明"), "日程": day, "車立て": f"{n_car}車",
                         "並び": r["line_type"] or "不明", "本命の1着見込み": fav, "倍率": e["odds"], "割安度": e["evc"],
                         "払戻": pay.get((r["race_id"], e["combo"]), 0) / 100,
                         **pair_features(e["combo"], lid, posd, ent, top_pt, fav_no, wrank)})
    df = pd.DataFrame(rows)
    df.to_pickle(cache)
    return df


def pair_features(combo, lid, posd, ent, top_pt, fav_no, wrank):
    a, b = map(int, combo.split("-"))
    la, lb = lid.get(a), lid.get(b)
    rel = "不明" if la is None or lb is None else ("同じライン" if la == lb else "別のライン")
    pa, pb = posd.get(a, "?"), posd.get(b, "?")
    if rel == "同じライン":
        kind = "同じライン（" + "・".join(sorted([pa, pb], key=["先頭", "番手", "3番手", "4番手以降"].index if pa in ["先頭", "番手", "3番手", "4番手以降"] and pb in ["先頭", "番手", "3番手", "4番手以降"] else str)) + "）"
    else:
        kind = rel
    jh = sum(1 for n in (a, b) if posd.get(n) == "先頭" and ent.get(n) and ent[n][1] in ("逃", "両"))
    wr = wrank.get(combo, 99)
    return {"2人の関係": rel, "2人の位置": kind, "本命を含む": "含む" if fav_no in (a, b) else "含まない",
            "得点1位を含む": "含む" if top_pt in (a, b) else "含まない", "自力先頭の人数": f"{jh}人",
            "ワイドの人気": "1〜5番人気" if wr <= 5 else ("6〜10番人気" if wr <= 10 else "11番人気以下"),
            "単騎を含む": "含む" if "単騎" in (pa, pb) else "含まない"}


def table(df, col, order=None, min_n=150):
    rng = np.random.default_rng(0)
    months = sorted(df.月.unique())
    rows = []
    for v, g in df.groupby(col, observed=True):
        if len(g) < min_n:
            continue
        gg = g.groupby("race_id").agg(r=("払戻", "sum"), n=("払戻", "size"))
        a, b = gg.r.to_numpy(), gg.n.to_numpy()
        idx = rng.integers(0, len(gg), (1500, len(gg)))
        bs = a[idx].sum(1) / b[idx].sum(1)
        bym = g.groupby("月").apply(lambda x: x.払戻.sum() / len(x))
        rows.append({col: v, "点数": len(g), "的中率": f"{(g.払戻 > 0).mean():.0%}", "回収率": g.払戻.sum() / len(g),
                     "95%の範囲": f"{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}",
                     "100%超の月": f"{int((bym > 1).sum())}/{len(bym)}", "lo": np.percentile(bs, 2.5)})
    t = pd.DataFrame(rows)
    if order:
        t[col] = pd.Categorical(t[col], order, ordered=True)
        t = t.sort_values(col)
    else:
        t = t.sort_values("回収率", ascending=False)
    t["判定"] = np.where(t.lo > 1, "◎ 安定して100%超", np.where(t.回収率 < 0.9, "× 弱い", ""))
    t["回収率"] = t.回収率.map(lambda x: f"{x:.0%}")
    return t.drop(columns="lo")


def main(d0="20260601", d1="20261105"):
    df = build(d0, d1)
    df["時間帯"] = pd.cut(df.時刻, [-1, 11, 14, 17, 20, 24], labels=["朝（〜11時台）", "昼（12〜14時台）", "夕方（15〜17時台）", "ナイター（18〜20時台）", "深夜（21時〜）"]).astype(str)
    df["何レース目"] = pd.cut(df.R, [0, 3, 6, 9, 12], labels=["1〜3R", "4〜6R", "7〜9R", "10〜12R"]).astype(str)
    df["本命の強さ"] = pd.cut(df.本命の1着見込み, [0, .3, .45, .6, 1], labels=["混戦（30%未満）", "30〜45%", "45〜60%", "本命が強い（60%以上）"]).astype(str)
    df["倍率の帯"] = pd.cut(df.倍率, [5.9, 7, 8, 9, 10.01], labels=["6倍台", "7倍台", "8倍台", "9〜10倍"]).astype(str)
    df["割安度の帯"] = pd.cut(df.割安度, [0.85, 0.95, 1.05, 99], labels=["0.85〜0.95", "0.95〜1.05", "1.05以上"], include_lowest=True).astype(str)
    L = [f"# ワイド枠の区分別成績（{d0}〜{d1}、確定オッズでの事後計算・各100円）\n",
         f"対象 {df.race_id.nunique():,} レース・{len(df):,} 点。全体の回収率 {df.払戻.sum() / len(df):.0%}、的中率 {(df.払戻 > 0).mean():.0%}。",
         "「100%超の月」= 月ごとに分けて100%を超えた月の数。多いほど、たまたまではない可能性が高い。",
         "「◎」= 95%の範囲の下限も100%超。「×」= 回収率90%未満。150点未満の区分は省略。\n"]
    for col, order in [("時間帯", ["朝（〜11時台）", "昼（12〜14時台）", "夕方（15〜17時台）", "ナイター（18〜20時台）", "深夜（21時〜）"]),
                       ("曜日", list(YOBI)), ("何レース目", ["1〜3R", "4〜6R", "7〜9R", "10〜12R"]),
                       ("グレード", None), ("級班", None), ("日程", ["初日", "中日", "最終日"]), ("車立て", None), ("並び", None),
                       ("本命の強さ", ["混戦（30%未満）", "30〜45%", "45〜60%", "本命が強い（60%以上）"]),
                       ("倍率の帯", ["6倍台", "7倍台", "8倍台", "9〜10倍"]), ("割安度の帯", ["0.85〜0.95", "0.95〜1.05", "1.05以上"]),
                       ("バンク", None), ("競輪場", None),
                       ("2人の関係", None), ("2人の位置", None), ("本命を含む", None), ("得点1位を含む", None),
                       ("自力先頭の人数", None), ("ワイドの人気", ["1〜5番人気", "6〜10番人気", "11番人気以下"]), ("単騎を含む", None)]:
        L.append(f"\n## {col}\n")
        L.append(table(df, col, order).to_markdown(index=False))
    txt = "\n".join(L)
    open(os.path.join(OUT, "wide_breakdown.md"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main(*sys.argv[1:3])
