"""条件を最大3つ重ねた組み合わせで、回収率100%超の法則を統計的に厳しく探す（確定オッズ・事後分析）。
- 探索期間で候補を作り、検証期間で確かめる。前半→後半、後半→前半の両方向で行う
- 検証では、レース単位のブートストラップで「回収率が100%以下である確率」(片側p値)を出し、
  ベンジャミニ・ホッホバーグ法で多重検定を補正する（偽発見率10%）
使い方: python rule_search3.py -> out/rule_search3.md"""
import itertools
import json
import os

import numpy as np
import pandas as pd

import kr
import rule_search2 as rs2

OUT = os.path.join(kr.BASE, "out")
RNG = np.random.default_rng(1)


def features():
    p = os.path.join(OUT, "bets_features3.pkl")
    if os.path.exists(p):
        return pd.read_pickle(p)
    df = pd.read_pickle(os.path.join(OUT, "bets_features.pkl"))
    c = kr.db()
    eq = rs2.build_equiv()
    df = df.merge(eq, on=["race_id", "券種", "combo"], how="left")
    df["値段比帯"] = pd.cut(df.値段比, [0, 1.0, 1.1, 1.25, 99], labels=["〜1.0", "1.0〜1.1", "1.1〜1.25", "1.25〜"]).astype(str)
    df.loc[~df.券種.isin(["2車複", "3連複"]), "値段比帯"] = "対象外"
    races = pd.read_sql("SELECT race_id, line_type, line_json, start_at FROM races", c).set_index("race_id")
    ent = pd.read_sql("SELECT race_id, number, style, race_point, comment FROM entries WHERE absent=0", c)
    # レース単位の特徴
    o = pd.read_sql("SELECT race_id, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket' "
                    "AND bet_type='3連単' AND odds<9999", c).sort_values("fetched_at").drop_duplicates(["race_id", "combo"], keep="last")
    o["q"] = 1 / o.odds
    o["f"] = o.combo.str.split("-").str[0]
    w = o.groupby(["race_id", "f"]).q.sum() / o.groupby("race_id").q.sum()
    fav = w.groupby("race_id").max()
    ri = races.reindex(df.race_id.unique())
    hour = ri.start_at.map(lambda t: kr.dt.datetime.fromtimestamp(t, kr.JST).hour)
    rf = pd.DataFrame({
        "並び": ri.line_type.fillna("不明"),
        "本命の強さ": pd.cut(fav.reindex(ri.index), [0, .3, .45, .6, 1], labels=["混戦", "30〜45%", "45〜60%", "本命が強い"]).astype(str),
        "時間帯": pd.cut(hour, [-1, 11, 15, 18, 20, 24], labels=["朝", "昼", "夕方", "ナイター", "深夜"]).astype(str)}, index=ri.index)
    df = df.join(rf, on="race_id")
    # 買い目に入っている選手どうしの関係
    info = {}
    for rid, g in ent.groupby("race_id"):
        lines = json.loads(races.line_json.get(rid) or "[]") if isinstance(races.line_json.get(rid), str) else []
        lid, head = {}, set()
        for li, l in enumerate(lines):
            nums = [n for x in l["entries"] for n in x["numbers"]]
            for k, n in enumerate(nums):
                lid[n] = li
            if nums:
                head.add(nums[0])
        g = g.set_index("number")
        top = g.race_point.idxmax()
        jiriki_head = {n for n in head if n in g.index and g.style.get(n) in ("逃", "両")}
        info[rid] = (lid, top, jiriki_head)
    rel, has_top, n_jh = [], [], []
    for rid, cb in zip(df.race_id, df.combo):
        lid, top, jh = info.get(rid, ({}, None, set()))
        nums = list(map(int, cb.split("-")))
        ls = [lid.get(n) for n in nums]
        if None in ls:
            rel.append("不明")
        elif len(set(ls)) == 1:
            rel.append("全員同じライン")
        elif len(set(ls)) < len(ls):
            rel.append("一部同じライン")
        else:
            rel.append("全員別ライン")
        has_top.append("得点1位を含む" if top in nums else "得点1位を含まない")
        n_jh.append(f"自力先頭{sum(1 for n in nums if n in jh)}人")
    df["選手の関係"] = rel
    df["得点1位"] = has_top
    df["自力先頭の数"] = n_jh
    df["人気帯"] = df.groupby(["race_id", "券種"]).倍率.rank(method="first").pipe(
        lambda r: pd.cut(r, [0, 1, 3, 6, 10, 20, 50, 1e6], labels=["1番人気", "2〜3", "4〜6", "7〜10", "11〜20", "21〜50", "51〜"])).astype(str)
    for col in ["倍率帯", "見込み帯"]:
        df[col] = df[col].astype(str)
    df.to_pickle(p)
    return df


def boot_p(t, B=2000):
    """回収率が100%以下である確率（片側p値）と95%範囲。レース単位で再標本化"""
    gg = t.groupby("race_id").agg(r=("払戻", "sum"), n=("払戻", "size"))
    a, b = gg.r.to_numpy(), gg.n.to_numpy()
    idx = RNG.integers(0, len(gg), (B, len(gg)))
    rr = a[idx].sum(1) / b[idx].sum(1)
    return (rr <= 1).mean(), np.percentile(rr, 2.5), np.percentile(rr, 97.5)


def bh(p, q=0.10):
    p = np.asarray(p)
    order = np.argsort(p)
    m = len(p)
    thr = q * (np.arange(1, m + 1)) / m
    passed = np.zeros(m, bool)
    ok = np.where(p[order] <= thr)[0]
    if len(ok):
        passed[order[: ok.max() + 1]] = True
    return passed


FEATS = ["券種", "倍率帯", "見込み帯", "値段比帯", "日程", "級班", "車立て", "並び", "本命の強さ", "時間帯",
         "選手の関係", "得点1位", "自力先頭の数", "人気帯"]


def discover(tr, max_k=3, min_n=300, min_hits=30, min_roi=1.10, min_races=50):
    res = []
    for k in range(1, max_k + 1):
        for fs in itertools.combinations(FEATS, k):
            g = tr.groupby(list(fs), observed=True).agg(n=("払戻", "size"), h=("的中", "sum"), r=("払戻", "sum"), nr=("race_id", "nunique"))
            g = g[(g.n >= min_n) & (g.h >= min_hits) & (g.r / g.n >= min_roi) & (g.nr >= min_races)]
            for key, row in g.iterrows():
                key = key if isinstance(key, tuple) else (key,)
                res.append((fs, key, int(row.n), row.r / row.n))
    return res


def mask(d, fs, key):
    m = np.ones(len(d), bool)
    for f, v in zip(fs, key):
        m &= (d[f] == v).to_numpy()
    return m


def run_direction(df, a, b, label):
    cands = discover(a)
    rows = []
    for fs, key, n, roi in cands:
        t = b[mask(b, fs, key)]
        if len(t) < 100 or t.race_id.nunique() < 30:  # 検証期間に30レース以上ないものは判定しない
            continue
        p, lo, hi = boot_p(t)
        rows.append({"条件": " × ".join(f"{f}={v}" for f, v in zip(fs, key)), "fs": fs, "key": key, "条件数": len(fs),
                     "探索_点数": n, "探索_回収率": roi, "検証_点数": len(t), "検証_的中": int((t.払戻 > 0).sum()),
                     "検証_回収率": t.払戻.sum() / len(t), "検証_下限": lo, "検証_上限": hi, "p値": p})
    R = pd.DataFrame(rows)
    if len(R):
        R["補正後に有意"] = bh(R.p値.to_numpy())
    return R, len(cands)


def main():
    df = features()
    df["的中"] = (df.払戻 > 0).astype(int)
    dates = sorted(df.date.unique())
    half = dates[len(dates) // 2]
    A, B = df[df.date < half], df[df.date >= half]
    L = [f"# 条件の組み合わせによる法則探し（統計的な検証つき）\n",
         f"対象 {df.race_id.nunique()} レース・{len(df):,} 組番。条件 {len(FEATS)} 種類を最大3つ重ねて総当たり。",
         f"前半 = {dates[0]}〜{half}の前日、後半 = {half}〜{dates[-1]}。\n",
         "判定: 探索期間で回収率110%以上（点数300以上・的中30以上）の組み合わせを候補にし、検証期間で確かめる。",
         "検証期間の p値 = レース単位のブートストラップで「本当は回収率100%以下」である確率。多数の候補を同時に調べているので、"
         "ベンジャミニ・ホッホバーグ法（偽発見率10%）で補正し、それでも残ったものだけを「統計的に有意」とする。",
         "※ 確定オッズ（締切後に決まる倍率）での事後分析。実際に買える締切直前の倍率ではずれる。\n"]
    out = {}
    for a, b, lab in [(A, B, "前半で探索→後半で検証"), (B, A, "後半で探索→前半で検証")]:
        R, n = run_direction(df, a, b, lab)
        out[lab] = R
        sig = R[R.補正後に有意] if len(R) else R
        L.append(f"## {lab}\n候補 {n} 件 → 検証期間でも100%超 {int((R.検証_回収率 > 1).sum()) if len(R) else 0} 件 → "
                 f"多重検定の補正後も有意 **{len(sig)} 件**\n")
        if len(R):
            top = R.sort_values("p値").head(15)
            show = top.assign(**{c: top[c].map(lambda x: f"{x:.0%}") for c in ["探索_回収率", "検証_回収率", "検証_下限", "検証_上限"]},
                              p値=top.p値.map(lambda x: f"{x:.3f}"), 補正後に有意=top.補正後に有意.map(lambda x: "○" if x else ""))
            L.append(show[["条件", "探索_点数", "探索_回収率", "検証_点数", "検証_的中", "検証_回収率", "検証_下限", "検証_上限", "p値", "補正後に有意"]].to_markdown(index=False))
            L.append("")
    # 両方向で検証期間でも100%超だった条件
    if all(len(v) for v in out.values()):
        x, y = out["前半で探索→後半で検証"], out["後半で探索→前半で検証"]
        both = x.merge(y, on="条件", suffixes=("_1", "_2"))
        both = both[(both.検証_回収率_1 > 1) & (both.検証_回収率_2 > 1)].copy()
        both["最小p"] = both[["p値_1", "p値_2"]].max(axis=1)
        both = both.sort_values("最小p")
        L.append(f"## 両方向とも検証期間で100%超だった条件: {len(both)} 件\n")
        if len(both):
            b2 = both.head(20)
            L.append(b2.assign(後半での回収率=b2.検証_回収率_1.map(lambda v: f"{v:.0%}"), 前半での回収率=b2.検証_回収率_2.map(lambda v: f"{v:.0%}"),
                               p値_後半=b2.p値_1.map(lambda v: f"{v:.3f}"), p値_前半=b2.p値_2.map(lambda v: f"{v:.3f}"))[
                ["条件", "後半での回収率", "p値_後半", "前半での回収率", "p値_前半"]].to_markdown(index=False))
            # 全期間での成績
            L.append("\n### 上位条件の全期間成績\n")
            rows = []
            for _, r in b2.head(10).iterrows():
                t = df[mask(df, r.fs_1, r.key_1)]
                p, lo, hi = boot_p(t)
                rows.append({"条件": r.条件, "レース数": t.race_id.nunique(), "点数": len(t), "的中": int((t.払戻 > 0).sum()),
                             "回収率": f"{t.払戻.sum() / len(t):.0%}", "95%範囲": f"{lo:.0%}〜{hi:.0%}"})
            L.append(pd.DataFrame(rows).to_markdown(index=False))
    open(os.path.join(OUT, "rule_search3.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
