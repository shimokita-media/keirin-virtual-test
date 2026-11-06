"""回収率100%超の法則を新しい角度から探す（確定オッズ・事後分析）。前半で探索→後半で検証。
使い方: python rule_search2.py -> out/rule_search2.md"""
import itertools
import json
import os

import numpy as np
import pandas as pd

import kr

OUT = os.path.join(kr.BASE, "out")
RNG = np.random.default_rng(0)


def build_equiv():
    """各レースの2車複・3連複について、同じ結果を2車単/3連単で買った場合の合成倍率との比を出す"""
    c = kr.db()
    o = pd.read_sql("SELECT race_id, bet_type, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket' "
                    "AND bet_type IN ('2車単','3連単','2車複','3連複')", c)
    o = o.sort_values("fetched_at").drop_duplicates(["race_id", "bet_type", "combo"], keep="last")
    o = o[o.odds < 9999]
    rows = []
    for rid, g in o.groupby("race_id"):
        d = {(b, cb): od for b, cb, od in zip(g.bet_type, g.combo, g.odds)}
        for (b, cb), od in d.items():
            if b == "2車複":
                i, j = cb.split("-")
                a, bb = d.get(("2車単", f"{i}-{j}")), d.get(("2車単", f"{j}-{i}"))
                if a and bb:
                    rows.append((rid, b, cb, od / (1 / (1 / a + 1 / bb))))
            elif b == "3連複":
                ks = cb.split("-")
                os_ = [d.get(("3連単", "-".join(p))) for p in itertools.permutations(ks)]
                if all(os_):
                    rows.append((rid, b, cb, od / (1 / sum(1 / x for x in os_))))
    return pd.DataFrame(rows, columns=["race_id", "券種", "combo", "値段比"])


def ci(t):
    gg = t.groupby("race_id").agg(r=("払戻", "sum"), n=("払戻", "size"))
    a, b = gg.r.to_numpy(), gg.n.to_numpy()
    idx = RNG.integers(0, len(gg), (1000, len(gg)))
    rr = a[idx].sum(1) / b[idx].sum(1)
    return np.percentile(rr, 2.5), np.percentile(rr, 97.5)


def main():
    df = pd.read_pickle(os.path.join(OUT, "bets_features.pkl"))
    c = kr.db()
    eq = build_equiv()
    df = df.merge(eq, on=["race_id", "券種", "combo"], how="left")
    df["値段比帯"] = pd.cut(df.値段比, [0, 0.9, 1.0, 1.1, 1.25, 99], labels=["〜0.9", "0.9〜1.0", "1.0〜1.1", "1.1〜1.25", "1.25〜"])
    races = pd.read_sql("SELECT race_id, venue_id, race_no, race_type, start_at FROM races", c).set_index("race_id")
    try:
        q = json.load(open(os.path.join(kr.BASE, "tomorrow.json"), encoding="utf-8"))
        bank = {v["id"]: f"{v['trackDistance']}m" for v in q["FETCH_KEIRIN_VENUE_LIST"]["venues"]}
    except Exception:
        bank = {}
    ri = races.reindex(df.race_id.unique())
    hour = ri.start_at.map(lambda t: kr.dt.datetime.fromtimestamp(t, kr.JST).hour)
    def rtype(s):
        for k in ("決勝", "準決", "ガールズ", "選抜", "特選", "予選", "チャレンジ", "一般"):
            if k in str(s):
                return k
        return "その他"
    m = pd.DataFrame({
        "時間帯": pd.cut(hour, [-1, 11, 15, 18, 20, 24], labels=["朝", "昼", "夕方", "ナイター", "深夜"]).astype(str),
        "レース番号": ri.race_no.map(lambda n: "1〜3R" if n <= 3 else ("4〜8R" if n <= 8 else "9R以降")),
        "レース種別": ri.race_type.map(rtype), "バンク": ri.venue_id.map(bank).fillna("不明")}, index=ri.index)
    df = df.join(m, on="race_id")
    dates = sorted(df.date.unique())
    half = dates[len(dates) // 2]
    L = [f"# 回収率100%超の法則探し（新しい角度）\n",
         f"対象 {df.race_id.nunique()} レース・{len(df):,} 組番（確定オッズ・事後分析）。前半 〜{half}の前日 で探索、後半 {half}〜 で検証。\n"]

    # A. 事前に決めた仮説（値段比べ）
    L.append("## A. 同じ結果の値段比べ（事前に決めた仮説）\n")
    L.append("2車複 i-j と 2車単 i-j / j-i の2点買い、3連複 と 3連単6点買い は、当たる結果が完全に同じ。"
             "値段比 = 2車複(3連複)の倍率 ÷ 2車単(3連単)をまとめて買った場合の倍率。1より大きいほど2車複(3連複)が割安。\n")
    rows = []
    for bt in ("2車複", "3連複"):
        for band, g in df[df.券種 == bt].groupby("値段比帯", observed=True):
            lo, hi = ci(g)
            f, s = g[g.date < half], g[g.date >= half]
            rows.append({"券種": bt, "値段比": str(band), "点数": len(g), "的中": int((g.払戻 > 0).sum()),
                         "回収率": f"{g.払戻.sum() / len(g):.0%}", "95%範囲": f"{lo:.0%}〜{hi:.0%}",
                         "前半": f"{f.払戻.sum() / max(len(f), 1):.0%}", "後半": f"{s.払戻.sum() / max(len(s), 1):.0%}"})
    L.append(pd.DataFrame(rows).to_markdown(index=False))

    # B. 新しい角度を含めた総当たり（前半で探索→後半で検証）
    tr, te = df[df.date < half], df[df.date >= half]
    feats = ["券種", "倍率帯", "見込み帯", "値段比帯", "時間帯", "レース番号", "レース種別", "バンク", "日程", "級班", "先頭車の位置", "同ライン決着"]
    res = []
    for k in (1, 2):
        for fs in itertools.combinations(feats, k):
            g = tr.groupby(list(fs), observed=True).agg(n=("払戻", "size"), hits=("払戻", lambda x: int((x > 0).sum())), ret=("払戻", "sum"))
            g = g[(g.n >= 300) & (g.hits >= 25)]
            for key, row in g.iterrows():
                key = key if isinstance(key, tuple) else (key,)
                res.append({"fs": fs, "key": key, "条件": " × ".join(f"{f}={v}" for f, v in zip(fs, key)),
                            "前半点数": int(row.n), "前半回収率": row.ret / row.n})
    R = pd.DataFrame(res).sort_values("前半回収率", ascending=False)
    cand = R[R.前半回収率 >= 1.05].head(50).copy()
    for i, r in cand.iterrows():
        mk = np.ones(len(te), bool)
        for f, v in zip(r.fs, r.key):
            mk &= (te[f].astype(str) == str(v)).to_numpy()
        t = te[mk]
        cand.loc[i, "後半点数"] = len(t)
        cand.loc[i, "後半回収率"] = t.払戻.sum() / max(len(t), 1)
        if len(t) > 30:
            cand.loc[i, "後半下限"], cand.loc[i, "後半上限"] = ci(t)
    ok = cand[(cand.後半回収率 >= 1.0)].sort_values("後半回収率", ascending=False)
    L.append(f"\n## B. 総当たり（{len(R):,}条件を前半で調べ、上位50件を後半で検証）\n")
    L.append(f"後半でも100%以上だったもの: {len(ok)} / {len(cand)} 件\n")
    if len(ok):
        show = ok.assign(**{c: ok[c].map(lambda x: f"{x:.0%}" if pd.notna(x) else "-") for c in ["前半回収率", "後半回収率", "後半下限", "後半上限"]})
        L.append(show[["条件", "前半点数", "前半回収率", "後半点数", "後半回収率", "後半下限", "後半上限"]].to_markdown(index=False))
    # C. 単独の角度ごとの全体像（時間帯・レース種別・バンク・レース番号）
    L.append("\n## C. 角度ごとの全体像（全券種・全組番を100円ずつ買った場合の回収率）\n")
    for f in ["時間帯", "レース種別", "バンク", "レース番号"]:
        g = df.groupby(f, observed=True).agg(点数=("払戻", "size"), 回収率=("払戻", lambda x: x.sum() / len(x)))
        L.append(f"**{f}**: " + " / ".join(f"{k} {v:.0%}" for k, v in g.回収率.items()))
    open(os.path.join(OUT, "rule_search2.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
