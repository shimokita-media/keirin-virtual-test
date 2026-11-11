"""探す段階（Fable）：「強いラインの弱い3番手」とは構造の違う仕組みを、筋書きを先に立ててから確かめる。
見た3期間だけ：y4（out/y4/cache.pkl）・2024年（out/y2024full/cache.pkl）・2025/2〜2026/11/5（out/tri_base.parquet＋side_*_full）。y5・y6 は見ない。
確定オッズ300倍以下・各100円。見込み pn＝1/odds をレースの中で合計1。条件は締切前に分かる情報と倍率の帯だけ（g_tf などは使わない）。

筋書き（データを見る前に固定）
 M1 数字のきれいな目：人は 1-2-3 のような昇順・連番・1番車入りの目を買いがち → それらは買われすぎ（当たり÷見込み<1）、降順など「汚い並び」は軽く見られる
 M2 直前のレースの当たり目を引きずる：同じ場の直前のレースで来た車番の目（同じ目・同じ3人・同じ1着車番）は買われすぎ
 M3 最終レースの取り返し：その日その場の最終レースは、負けを取り返したい人のお金が穴に流れ、本命（低倍率）が軽く見られる（最終レース×低倍率は当たり÷見込み>1、大穴は<1）
 M4 名前買い：S級S班（全国区の有名選手）が出るレースでは、S班を1着にする目が買われすぎ、S班を含まない目・S班が3着の目が軽く見られる
選ぶ年＝y4（買い方の形を y4 で決める）、確かめる年＝2024年・2025/2〜。
使い方: python -I -X utf8 research/fable_habits.py build y4|2024|2025   → 作業用の小さい表
        python -I -X utf8 research/fable_habits.py report reports/fable_habits.md"""
import sys, os, gc, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SCR = os.environ.get("FABLE_SCR", "C:/Users/take0/AppData/Local/Temp/claude/38c435bfe2a07bd9/cfa8c5a0-353c-4b57-81d8-9e3789cdb845/scratchpad/") + "slim_"
SRC = {"y4": ("out/y4/cache.pkl", "_y4"), "2024": ("out/y2024full/cache.pkl", "_y2024full"), "2025": (None, "_full")}
NAME = {"y4": "y4", "2024": "2024年", "2025": "2025/2〜"}
BASE = ["race_id", "combo", "date", "venue", "odds", "ret", "s01", "s12", "r0_pos", "r1_pos", "r2_pos", "entries_number", "is_top"]

def build(per):
    src, suf = SRC[per]
    if src:
        d = pd.read_pickle(K + src); d = d[d.odds <= 300][BASE + ["r0_pt_rank", "r2_pt_rank", "G"]].copy(); gc.collect()
    else:
        import duckdb
        d = duckdb.sql(f"SELECT {', '.join(BASE)} FROM '{K}out/tri_base.parquet' WHERE date <= '20261105'").df()
    E = pd.read_pickle(K + f"out/side_entries{suf}.pkl"); R = pd.read_pickle(K + f"out/side_races{suf}.pkl").drop_duplicates("race_id")
    RS = pd.read_pickle(K + f"out/side_results{suf}.pkl")
    cb = d.combo.str.split("-", expand=True).astype(np.int8); d["a"], d["b"], d["c"] = cb[0], cb[1], cb[2]
    if not src:
        EA = E[E.absent != 1].copy(); EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
        look = EA.set_index(["race_id", "number"]).ptr
        d["r2_pt_rank"] = look.reindex(list(zip(d.race_id, d.c))).to_numpy(); d["r0_pt_rank"] = look.reindex(list(zip(d.race_id, d.a))).to_numpy()
        d["G"] = d.race_id.map(R.set_index("race_id").grade).fillna("").astype(str).str.startswith("G").astype(float)
    q = 1 / d.odds; d["pn"] = (q / q.groupby(d.race_id).transform("sum")).astype(np.float32); d["hit"] = d.ret > 0
    d["race_no"] = d.race_id.str[:2].astype(np.int8)
    # M3 最終レース：その日その場の全レース（L級も含む側の表）の最大レース番号
    Ri = R.set_index("race_id"); last = R.groupby(["venue", "date"]).race_no.max()
    key = pd.MultiIndex.from_arrays([d.venue, d.date]); d["n_day"] = last.reindex(key).to_numpy().astype(np.int8)
    d["last"] = d.race_no == d.n_day; d["first"] = d.race_no == 1; d["last2"] = d.race_no == d.n_day - 1
    d["hour"] = pd.to_datetime(d.race_id.map(Ri.start_at), unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.hour.astype(np.int8)
    # M2 直前のレース（同じ場・同じ日・レース番号−1）の当たり目（side_results の1〜3着）
    W = RS[RS["rank"].between(1, 3)].sort_values(["race_id", "rank"]).groupby("race_id").number.apply(list)
    W = W[W.str.len() == 3]; Wd = pd.DataFrame({"wa": [w[0] for w in W], "wb": [w[1] for w in W], "wc": [w[2] for w in W]}, index=W.index)
    Wd = Wd.join(R.set_index("race_id")[["venue", "date", "race_no"]]); Wd["race_no"] += 1  # 次のレースに付ける
    Wd = Wd.set_index(["venue", "date", "race_no"])
    key = pd.MultiIndex.from_arrays([d.venue, d.date, d.race_no.astype(int)]); pw = Wd.reindex(key)
    wa, wb, wc = (pw[k].to_numpy() for k in ("wa", "wb", "wc"))
    d["has_prev"] = ~np.isnan(wa)
    d["same_combo"] = (d.a == wa) & (d.b == wb) & (d.c == wc)
    ws = [set(x) for x in zip(wa, wb, wc)]; d["same_set"] = np.array([{x, y, z} == s for x, y, z, s in zip(d.a, d.b, d.c, ws)]) & d.has_prev
    d["same_first"] = d.a == wa
    d["prev_odds"] = np.nan  # 直前のレースの当たり目の倍率（この表の中にあれば）
    wk = d[d.hit].drop_duplicates("race_id").set_index(["venue", "date", "race_no"]).odds; wk.index = wk.index.set_levels(wk.index.levels[2] + 1, level=2)
    d["prev_odds"] = wk.reindex(pd.MultiIndex.from_arrays([d.venue, d.date, d.race_no])).to_numpy().astype(np.float32)
    # M4 S級S班（class=1・grp=0）の車番
    SB = E[(E["class"] == 1) & (E.grp == 0) & (E.absent != 1)].groupby("race_id").number.apply(set)
    sb = d.race_id.map(SB); d["sb_n"] = sb.map(lambda s: len(s) if isinstance(s, set) else 0).astype(np.int8)
    for col, nm in (("a", "sb_a"), ("b", "sb_b"), ("c", "sb_c")):
        d[nm] = np.array([(x in s) if isinstance(s, set) else False for x, s in zip(d[col], sb)])
    d["lo"] = (d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2)
    for c in ("odds", "ret"): d[c] = d[c].astype(np.float32)
    for c in ("r0_pos", "r1_pos", "r2_pos", "entries_number"): d[c] = d[c].astype(np.int8)
    d = d.drop(columns=["s01", "s12", "combo"]).reset_index(drop=True)
    d.to_pickle(SCR + per + ".pkl"); print(per, d.shape, "races", d.race_id.nunique(), "last-race rows", int(d["last"].sum()), "S班 rows", int((d.sb_n > 0).sum()))

# ---------- 集計 ----------
def summ(g, boot=2000, seed=0):
    """点数・当たり・当たり÷見込み・回収率・95%の範囲（レース単位ブートストラップ）"""
    n = len(g)
    if n == 0: return dict(n=0, hits=0, ratio=np.nan, roi=np.nan, lo=np.nan, hi=np.nan)
    hits = int(g.hit.sum()); ratio = hits / g.pn.sum(); roi = g.ret.mean()
    a = g.groupby("race_id", sort=False).agg(r=("ret", "sum"), c=("ret", "size")); nR = len(a)
    rng = np.random.default_rng(seed); idx = rng.integers(0, nR, size=(boot, nR))
    rv, cv = a.r.to_numpy(), a.c.to_numpy()
    rs = np.array([rv[i].sum() / cv[i].sum() for i in idx]) if nR < 50000 else np.array([rv[i].sum() / cv[i].sum() for i in idx])
    return dict(n=n, hits=hits, ratio=ratio, roi=roi, lo=np.quantile(rs, 0.025), hi=np.quantile(rs, 0.975))
def fmt(s):
    if s["n"] == 0: return "0点"
    return f"{s['n']:,}点・{s['hits']}本・{s['ratio']:.2f}・**{s['roi']:.0%}**（{s['lo']:.0%}〜{s['hi']:.0%}）"
def extra(g):
    """110%超のときの追加：上位5本の当たりを除いた回収率、四半期ごとの100%未満の回数"""
    r = np.sort(g.ret.to_numpy())[::-1]; top5 = (r.sum() - r[:5].sum()) / len(r)
    qtr = g.date.str[:4] + "Q" + ((g.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
    qr = g.groupby(qtr).ret.mean(); return f"上位5本除き {top5:.0%}／四半期 {int((qr < 1).sum())}/{len(qr)} が100%未満"
def cell_small(g): return f"{len(g):,}・{g.hit.sum() / g.pn.sum():.2f}・**{g.ret.mean():.0%}**" if len(g) >= 40 else f"{len(g)}（少）"

def report(out):
    D = {per: pd.read_pickle(SCR + per + ".pkl") for per in SRC}
    for d in D.values():
        d["asc"] = (d.a < d.b) & (d.b < d.c); d["desc"] = (d.a > d.b) & (d.b > d.c)
        d["consec"] = d.asc & (d.b == d.a + 1) & (d.c == d.b + 1)
        d["has1"] = (d.a == 1) | (d.b == 1) | (d.c == 1); d["first1"] = d.a == 1
        d["band"] = pd.cut(d.odds, [0, 10, 20, 50, 100, 300], labels=["〜10倍", "10〜20倍", "20〜50倍", "50〜100倍", "100〜300倍"])
        d["sb_none"] = (d.sb_n > 0) & ~d.sb_a & ~d.sb_b & ~d.sb_c
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    def grid(title, rows, note=""):
        P(f"### {title}" + NL + (note + NL if note else "") + "| 区分 | " + " | ".join(NAME.values()) + " |" + NL + "|---|---|---|---|")
        for lab, fn in rows: P(f"| {lab} | " + " | ".join(cell_small(fn(d)) for d in D.values()) + " |")
        P("")
    def full(title, fn, note=""):
        """3期間それぞれ＋まとめ（点数・当たり・当たり÷見込み・回収率・95%の範囲）。110%超は追加の数字"""
        P(f"### {title}" + NL + (note + NL if note else "") + "| 期間 | 点数・当たり・当たり÷見込み・回収率（95%の範囲） | 追加 |" + NL + "|---|---|---|")
        parts = []
        for per, d in D.items():
            g = fn(d); parts.append(g); s = summ(g); P(f"| {NAME[per]} | {fmt(s)} | {extra(g) if s['n'] and s['roi'] > 1.1 else ''} |")
        g = pd.concat(parts); s = summ(g); P(f"| **まとめ** | {fmt(s)} | {extra(g) if s['n'] and s['roi'] > 1.1 else ''} |"); P("")
        return s
    BANDS = ["〜10倍", "10〜20倍", "20〜50倍", "50〜100倍", "100〜300倍"]
    P("# 探す段階（Fable）：人の買い方のくせ・1日の流れ・名前買い（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円。見込み＝1/倍率をレースの中で合計1。各セル：点数・当たり÷見込み・回収率。筋書きはスクリプトの冒頭に、データを見る前に書いた。選ぶ年＝y4、確かめる年＝2024年・2025/2〜。" + NL)
    P("全部： " + " ／ ".join(f"{NAME[k]} {cell_small(d)}（{d.race_id.nunique():,}R）" for k, d in D.items()) + NL)

    # ---- M1 ----
    P("## M1 数字のきれいな目（昇順・連番・1番車入り）は買われすぎか" + NL + "筋書き：人は 1-2-3 のような並びを買いがち → 昇順・連番・1番車入りは当たり÷見込みが1より小さく、降順は大きい。" + NL)
    for b in BANDS:
        grid(f"倍率 {b}", [("昇順 a<b<c", lambda d, b=b: d[d.asc & (d.band == b)]), ("　うち連番（1-2-3 型）", lambda d, b=b: d[d.consec & (d.band == b)]),
                           ("降順 a>b>c", lambda d, b=b: d[d.desc & (d.band == b)]), ("その他の並び", lambda d, b=b: d[~d.asc & ~d.desc & (d.band == b)]),
                           ("1番車を含む", lambda d, b=b: d[d.has1 & (d.band == b)]), ("　1番車が1着", lambda d, b=b: d[d.first1 & (d.band == b)]), ("1番車を含まない", lambda d, b=b: d[~d.has1 & (d.band == b)])])
    grid("ライン順（先頭→番手→3番手）×10倍以下 の中で", [("昇順", lambda d: d[d.lo & d.asc & (d.odds <= 10)]), ("降順", lambda d: d[d.lo & d.desc & (d.odds <= 10)]), ("その他", lambda d: d[d.lo & ~d.asc & ~d.desc & (d.odds <= 10)])])

    # ---- M2 ----
    P("## M2 直前のレースの当たり目を引きずる（同じ場・同じ日の1つ前のレース）" + NL + "筋書き：直前に来た車番の目は目につく → 同じ目・同じ3人・同じ1着車番は買われすぎ（当たり÷見込み<1）。直前が大穴だったときほど強い。" + NL)
    hp = lambda d: d[d.has_prev]
    grid("300倍以下 全部", [("直前の当たり目と同じ目", lambda d: hp(d)[hp(d).same_combo]), ("同じ3人（順不同）", lambda d: hp(d)[hp(d).same_set]), ("同じ1着車番", lambda d: hp(d)[hp(d).same_first]),
                          ("1着車番が違う", lambda d: hp(d)[~hp(d).same_first]), ("（比べる）直前のレースがない＝1R", lambda d: d[~d.has_prev])])
    for b in ["〜10倍", "10〜20倍", "20〜50倍"]:
        grid(f"倍率 {b}", [("同じ1着車番", lambda d, b=b: hp(d)[hp(d).same_first & (hp(d).band == b)]), ("1着車番が違う", lambda d, b=b: hp(d)[~hp(d).same_first & (hp(d).band == b)]),
                           ("同じ3人（順不同）", lambda d, b=b: hp(d)[hp(d).same_set & (hp(d).band == b)])])
    grid("直前の当たり目の倍率で分けて（同じ1着車番の目）", [("直前が10倍以下", lambda d: hp(d)[hp(d).same_first & (hp(d).prev_odds <= 10)]), ("直前が10〜50倍", lambda d: hp(d)[hp(d).same_first & hp(d).prev_odds.between(10, 50, inclusive="right")]),
                                                      ("直前が50倍超", lambda d: hp(d)[hp(d).same_first & (hp(d).prev_odds > 50)]), ("直前が300倍超（表にない）", lambda d: hp(d)[hp(d).same_first & hp(d).prev_odds.isna()])])

    # ---- M3 ----
    P("## M3 最終レースの取り返し（その日その場の最終レース）" + NL + "筋書き：最終レースは負けを取り返したい人のお金が穴に流れる → 低倍率は軽く見られ（当たり÷見込み>1）、大穴は買われすぎ（<1）。最終の1つ前・1Rは比べる用。" + NL)
    for b in BANDS:
        grid(f"倍率 {b}", [("最終レース", lambda d, b=b: d[d["last"] & (d.band == b)]), ("最終の1つ前", lambda d, b=b: d[d.last2 & (d.band == b)]), ("1R", lambda d, b=b: d[d["first"] & (d.band == b)]), ("それ以外", lambda d, b=b: d[~d["last"] & ~d.last2 & ~d["first"] & (d.band == b)])])
    grid("最終レース×10倍以下 を分けて", [("7R制（モーニング・ミッドナイト）", lambda d: d[d["last"] & (d.odds <= 10) & (d.n_day <= 8)]), ("9R制", lambda d: d[d["last"] & (d.odds <= 10) & d.n_day.between(9, 10)]), ("12R制", lambda d: d[d["last"] & (d.odds <= 10) & (d.n_day >= 11)]),
                                   ("ナイター以降（17時〜）", lambda d: d[d["last"] & (d.odds <= 10) & (d.hour >= 17)]), ("昼まで", lambda d: d[d["last"] & (d.odds <= 10) & (d.hour < 17)]),
                                   ("ライン順", lambda d: d[d["last"] & (d.odds <= 10) & d.lo]), ("ライン順でない", lambda d: d[d["last"] & (d.odds <= 10) & ~d.lo]), ("9車", lambda d: d[d["last"] & (d.odds <= 10) & (d.entries_number >= 9)]), ("7車以下", lambda d: d[d["last"] & (d.odds <= 10) & (d.entries_number < 9)])])
    grid("最終レース×20倍以下 を分けて", [("ライン順", lambda d: d[d["last"] & (d.odds <= 20) & d.lo]), ("ライン順でない", lambda d: d[d["last"] & (d.odds <= 20) & ~d.lo]), ("一番の目", lambda d: d[d["last"] & (d.odds <= 20) & d.is_top]), ("一番の目でない", lambda d: d[d["last"] & (d.odds <= 20) & ~d.is_top])])

    # ---- M4 ----
    P("## M4 名前買い（S級S班の出るレース）" + NL + "筋書き：有名選手（S班）を1着にする目は買われすぎ、S班を含まない目・S班を3着にする目は軽く見られる。" + NL)
    P("S班の出るレース数： " + " ／ ".join(f"{NAME[k]} {d[d.sb_n > 0].race_id.nunique():,}R（1人 {d[d.sb_n == 1].race_id.nunique():,}・2人以上 {d[d.sb_n >= 2].race_id.nunique():,}）" for k, d in D.items()) + NL)
    for b in ["〜10倍", "10〜20倍", "20〜50倍", "50〜100倍", "100〜300倍"]:
        grid(f"倍率 {b}（S班の出るレース）", [("S班が1着", lambda d, b=b: d[d.sb_a & (d.band == b)]), ("S班が2着", lambda d, b=b: d[d.sb_b & ~d.sb_a & (d.band == b)]), ("S班が3着", lambda d, b=b: d[d.sb_c & ~d.sb_a & ~d.sb_b & (d.band == b)]),
                                           ("S班を含まない", lambda d, b=b: d[d.sb_none & (d.band == b)]), ("（比べる）S班のいないレース", lambda d, b=b: d[(d.sb_n == 0) & (d.band == b)])])
    grid("S班が1人だけのレース×S班を含まない目", [("〜20倍", lambda d: d[d.sb_none & (d.sb_n == 1) & (d.odds <= 20)]), ("20〜100倍", lambda d: d[d.sb_none & (d.sb_n == 1) & d.odds.between(20, 100, inclusive="right")]), ("100〜300倍", lambda d: d[d.sb_none & (d.sb_n == 1) & (d.odds > 100)])])

    # ---- 買い方の候補（y4 で選び、2024年・2025/2〜で確かめる） ----
    P("## 買い方の候補：y4 で形を選び、2024年・2025/2〜で確かめる（点数・当たり・当たり÷見込み・回収率・95%の範囲＝レース単位ブートストラップ2,000回）" + NL)
    CANDS = {
        "M1 降順の目×10倍以下": lambda d: d[d.desc & (d.odds <= 10)],
        "M1 降順の目×20倍以下": lambda d: d[d.desc & (d.odds <= 20)],
        "M1 1番車を含まない×10倍以下": lambda d: d[~d.has1 & (d.odds <= 10)],
        "M1 昇順でない×10倍以下": lambda d: d[~d.asc & (d.odds <= 10)],
        "M2 1着車番が直前と違う×10倍以下": lambda d: d[d.has_prev & ~d.same_first & (d.odds <= 10)],
        "M3 最終レース×10倍以下": lambda d: d[d["last"] & (d.odds <= 10)],
        "M3 最終レース×20倍以下": lambda d: d[d["last"] & (d.odds <= 20)],
        "M3 最終レース×ライン順×10倍以下": lambda d: d[d["last"] & d.lo & (d.odds <= 10)],
        "M3 最終レース×ライン順×20倍以下": lambda d: d[d["last"] & d.lo & (d.odds <= 20)],
        "M3 最終レース×一番の目": lambda d: d[d["last"] & d.is_top],
        "M4 S班1人のレース×S班を含まない×20倍以下": lambda d: d[d.sb_none & (d.sb_n == 1) & (d.odds <= 20)],
        "M4 S班1人のレース×S班を含まない×50倍以下": lambda d: d[d.sb_none & (d.sb_n == 1) & (d.odds <= 50)],
        "M4 S班が3着×20倍以下": lambda d: d[d.sb_c & ~d.sb_a & ~d.sb_b & (d.odds <= 20)],
        "M4 S班が3着×50倍以下": lambda d: d[d.sb_c & ~d.sb_a & ~d.sb_b & (d.odds <= 50)],
    }
    P("### y4 での一覧（選ぶ年）" + NL + "| 候補 | y4 |" + NL + "|---|---|")
    y4 = {}
    for nm, fn in CANDS.items():
        s = summ(fn(D["y4"])); y4[nm] = s; P(f"| {nm} | {fmt(s)} |")
    P("")
    P("### 3期間それぞれ＋まとめ（y4 は選んだ年なので参考。確かめは 2024年・2025/2〜）" + NL)
    res = {}
    for nm, fn in CANDS.items():
        res[nm] = full(nm, fn)
    P("### まとめの表（回収率）" + NL + "| 候補 | y4（選ぶ） | 2024年（確かめ） | 2025/2〜（確かめ） | まとめ | 確かめ2年とも100%超 |" + NL + "|---|---|---|---|---|---|")
    for nm, fn in CANDS.items():
        ss = [summ(fn(D[p]), boot=200) for p in ("y4", "2024", "2025")]; ok = all(s["roi"] > 1 for s in ss[1:])
        P(f"| {nm} | {ss[0]['roi']:.0%}（{ss[0]['n']:,}点） | {ss[1]['roi']:.0%}（{ss[1]['n']:,}点） | {ss[2]['roi']:.0%}（{ss[2]['n']:,}点） | {res[nm]['roi']:.0%}（{res[nm]['lo']:.0%}〜{res[nm]['hi']:.0%}） | {'○' if ok else ''} |")
    OUT.close(); print("done")

if __name__ == "__main__":
    if sys.argv[1] == "build": build(sys.argv[2])
    else: report(sys.argv[2])
