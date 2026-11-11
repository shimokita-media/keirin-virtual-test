"""探す段階（Fable・5回目）：「ラインが多いレースはお金が散り、1つのラインがそろって決まる目（ライン順）が軽く見られる」という仕組みの検証。
見た3期間だけ：y4（2022/11/8〜2023/11/7）・2024年（2023/11/8〜2025/1/31）・2025/2〜2026/11/5。y5・y6 は見ない。keirin.sqlite は開かない。
元の表＝scratchpad の slim2_<期間>.pkl（research/fable_player.py build。3連単の全部の目・確定オッズ300倍以下・各100円・pn＝1/倍率をレースの中で合計1・lo＝ライン順）。
並び＝out/side_races_*.pkl の line_json、選手→車番＝out/side_entries_*.pkl。
条件は締切前に分かる情報（並び・ラインの数・車立て・得点順位）と3連単の倍率の帯だけ。g_tf などの券種どうしの割安さは使わない。

【仕組み】ラインの数（nlines＝line_json のラインの数。単騎も1つに数える＝lo_wide の nlines と同じ定義）が多いレースは「荒れる」と見られ、
 市場のお金が多くの目（ラインをまたぐ目）に散る。その結果、1つのラインが3人そろって決まる目（ライン順＝先頭→番手→3番手）が軽く見られる。

【予言（集計の前に固定。向きと比べ方まで。成績は見ていない）】
 比べる物差し＝当たり÷見込み（hits/Σpn）。「向きがそろう」＝3期間それぞれで不等号が同じ向き。
 P0 前提：ラインが多いレースほど市場のお金は散っている。
     比べ方＝同じ車立て（7車以下／9車）の中で、レースの一番人気の目の見込み pn（最大の pn）の平均が nlines 4以上 ＜ nlines 3 ＜ nlines 2以下。
 P1 ライン順の目全体（3着の強さを問わない・300倍以下、30倍以下でも）は、nlines が多いほど当たり÷見込みが高い。
     比べ方＝ratio(nlines>=4) > ratio(nlines==3) > ratio(nlines<=2)。7車以下・9車のそれぞれで見る（9車は nlines<=2 がほぼ無いので 4以上 対 3 だけ）。
 P2 ラインをまたぐ目（3人が3つの別々のラインから＝お金が散った先）は、nlines 4以上のレースで割高（当たり÷見込み<1）で、nlines 3 のレースより低い。
     比べ方＝ratio(3ラインまたぎ, nlines>=4) < ratio(3ラインまたぎ, nlines==3)、かつ前者 < 1。300倍以下・30倍以下の両方。
     注意：同じレースの中では Σhit＝Σpn＝1 なので、ライン順が軽ければ「残り全部」は自動的に割高。だから「残り全部」ではなく「3ラインまたぎ」に限って見る。
 P3 nlines 4以上では、ライン順の「本命の順番」（弱い3番手に限らない）も軽く見られている。
     比べ方＝(a) ライン順×3着の得点順位6位以内：ratio(nlines>=4) > ratio(nlines<=3)。(b) ライン順×10倍以下：同じ。(c) ライン順でレースの一番人気の目：同じ。
 P4 nlines が同じなら、9車と7車以下の差は小さい（9車の強さは「ラインが多くなりやすいから」）。
     比べ方＝ライン順×3着7位以下×20倍以下で、|ratio(9車)−ratio(7車以下)| は nlines 4以上の中では、車立てだけで分けたとき（nlines を問わない）の差より小さい。
     かつ nlines 4以上の中の 9車−7車以下 の差は3期間で向きがそろわない（どちらが上か決まらない）。
 仕組みが支持されたら（P1・P2 の向きが3期間でそろう）、1つの決まり＝**nlines>=4 × ライン順 × 3着7位以下 × 20倍以下（車立てを問わない）**の成績を出す。条件は足さない。

出し方：点数・当たり本数・当たり÷見込み・回収率・95%の範囲（レース単位ブートストラップ2,000回・種0）。110%超は上位5本除き・100%未満の四半期の数。
使い方: python -I -X utf8 research/fable_nlines.py build y4|2024|2025   → scratchpad の fable_nl_<期間>.pkl
        python -I -X utf8 research/fable_nlines.py report reports/fable_nlines.md"""
import sys, os, json, gc, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SCR = os.environ.get("FABLE_SCR", "C:/Users/take0/AppData/Local/Temp/claude/38c435bfe2a07bd9/cfa8c5a0-353c-4b57-81d8-9e3789cdb845/scratchpad/")
SUF = {"y4": "_y4", "2024": "_y2024full", "2025": "_full"}
NAME = {"y4": "y4", "2024": "2024年", "2025": "2025/2〜"}
KEEP = ["race_id", "date", "odds", "ret", "pn", "hit", "lo", "entries_number", "r0_pt_rank", "r1_pt_rank", "r2_pt_rank", "pa", "pb", "pc"]

def build(per):
    d = pd.read_pickle(SCR + "slim2_" + per + ".pkl")[KEEP].reset_index(drop=True)
    R = pd.read_pickle(K + f"out/side_races{SUF[per]}.pkl").drop_duplicates("race_id")
    R = R[R.race_id.isin(d.race_id.unique()) & R.line_json.notna()]
    E = pd.read_pickle(K + f"out/side_entries{SUF[per]}.pkl")[["race_id", "number", "player_id"]]
    E = E[E.race_id.isin(R.race_id)].copy(); E["pid"] = pd.to_numeric(E.player_id, errors="coerce").fillna(-1).astype(np.int32)
    nl, nreal, lidx = {}, {}, {}
    for rid, lj in zip(R.race_id, R.line_json):
        lines = [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(lj)]
        nl[rid] = len(lines); nreal[rid] = sum(1 for l in lines if len(l) >= 2)
        for i, l in enumerate(lines):
            for n in l: lidx[(rid, int(n))] = i
    E["li"] = [lidx.get((r, int(n)), -1) for r, n in zip(E.race_id, E.number)]
    look = E.set_index(["race_id", "pid"]).li
    look = look[~look.index.duplicated()]
    for col, nm in (("pa", "la"), ("pb", "lb"), ("pc", "lc")):
        d[nm] = look.reindex(pd.MultiIndex.from_arrays([d.race_id, d[col]])).fillna(-1).to_numpy().astype(np.int8)
    d["nlines"] = d.race_id.map(nl).fillna(-1).astype(np.int8); d["n_real"] = d.race_id.map(nreal).fillna(-1).astype(np.int8)
    bad = (d.la < 0) | (d.lb < 0) | (d.lc < 0) | (d.nlines < 0)
    print(per, d.shape, "並び・選手が不明で落とした", int(bad.sum()), "レース", d.race_id[bad].nunique()); d = d[~bad].reset_index(drop=True)
    d["ndl"] = ((d.la != d.lb).astype(np.int8) + (d.lb != d.lc).astype(np.int8) + (d.la != d.lc).astype(np.int8)).map({0: 1, 2: 2, 3: 3}).astype(np.int8)  # 目の3人が属するラインの数
    chk = d[d.lo]; print("  ライン順の目で ndl==1 の割合", float((chk.ndl == 1).mean()))
    d["fav"] = d.groupby("race_id").odds.rank(method="first") == 1
    d["top_pn"] = d.groupby("race_id").pn.transform("max").astype(np.float32)
    d = d.drop(columns=["pa", "pb", "pc", "la", "lb", "lc"])
    print("  nlines", d.drop_duplicates("race_id").nlines.value_counts().sort_index().to_dict())
    print("  nlines×車立て（レース数）"); print(pd.crosstab(d.drop_duplicates("race_id").entries_number, d.drop_duplicates("race_id").nlines).to_string())
    d.to_pickle(SCR + "fable_nl_" + per + ".pkl"); print(per, d.shape, "races", d.race_id.nunique())

# ---------- 集計 ----------
def summ(g, boot=2000, seed=0):
    n = len(g)
    if n == 0: return dict(n=0, nR=0, hits=0, ratio=np.nan, rlo=np.nan, rhi=np.nan, roi=np.nan, lo=np.nan, hi=np.nan)
    hits = int(g.hit.sum()); ratio = hits / g.pn.sum(); roi = g.ret.mean()
    a = g.groupby("race_id", sort=False).agg(r=("ret", "sum"), c=("ret", "size"), h=("hit", "sum"), p=("pn", "sum")); nR = len(a)
    rng = np.random.default_rng(seed); rv, cv, hv, pv = a.r.to_numpy(), a.c.to_numpy(), a.h.to_numpy(float), a.p.to_numpy(float)
    rs = np.empty(boot); qs = np.empty(boot)
    for i in range(boot):
        idx = rng.integers(0, nR, nR); rs[i] = rv[idx].sum() / cv[idx].sum(); qs[i] = hv[idx].sum() / pv[idx].sum()
    return dict(n=n, nR=nR, hits=hits, ratio=ratio, rlo=np.quantile(qs, 0.025), rhi=np.quantile(qs, 0.975), roi=roi, lo=np.quantile(rs, 0.025), hi=np.quantile(rs, 0.975))
def fmt(s):
    if s["n"] == 0: return "0点"
    return f"{s['n']:,}点・{s['hits']}本・**{s['ratio']:.2f}**（{s['rlo']:.2f}〜{s['rhi']:.2f}）・{s['roi']:.0%}（{s['lo']:.0%}〜{s['hi']:.0%}）"
def fmt_roi(s):
    if s["n"] == 0: return "0点"
    return f"{s['n']:,}点・{s['hits']}本・{s['ratio']:.2f}・**{s['roi']:.0%}**（{s['lo']:.0%}〜{s['hi']:.0%}）"
def extra(g):
    if len(g) == 0: return ""
    r = np.sort(g.ret.to_numpy())[::-1]; top5 = (r.sum() - r[:5].sum()) / len(r)
    qtr = g.date.str[:4] + "Q" + ((g.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
    qr = g.groupby(qtr).ret.mean(); return f"上位5本除き {top5:.0%}／四半期 {int((qr < 1).sum())}/{len(qr)} が100%未満"

NLC = {"2以下": lambda d: d.nlines <= 2, "3": lambda d: d.nlines == 3, "4以上": lambda d: d.nlines >= 4}
CAR = {"7車以下": lambda d: d.entries_number <= 7, "9車": lambda d: d.entries_number >= 9}

def table(P, D, ALL, cells, label, boot=2000, roi=False):
    f = fmt_roi if roi else fmt
    P("| " + label + " | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    out = {}
    for cn, cf in cells.items():
        ss = [summ(D[p][cf(D[p])], boot=boot) for p in D]; sA = summ(ALL[cf(ALL)], boot=boot); out[cn] = (ss, sA)
        ex = ("<br>" + extra(ALL[cf(ALL)])) if (roi and sA["roi"] > 1.1) else ""
        P(f"| {cn} | " + " | ".join(f(s) for s in ss) + f" | {f(sA)} |{ex}")
    return out

def verdict(P, name, pairs, out, key="ratio", want=">"):
    """pairs: [(上側の区分名, 下側の区分名)]。3期間とも 上側 want 下側 なら○。"""
    lines = []
    for hi, lo in pairs:
        if hi not in out or lo not in out: continue
        sh, sl = out[hi][0], out[lo][0]
        signs = []
        for a, b in zip(sh, sl):
            if a["n"] == 0 or b["n"] == 0: signs.append("－"); continue
            diff = a[key] - b[key]; ok = (diff > 0) if want == ">" else (diff < 0)
            signs.append(("○" if ok else "×") + f"{diff:+.2f}")
        allok = all(s.startswith("○") for s in signs)
        lines.append(f"- {name}：{hi} 対 {lo}（{key}、予言は{hi}{'＞' if want == '>' else '＜'}{lo}）：" + "／".join(signs) + f" → **{'3期間そろう' if allok else 'そろわない'}**")
    for l in lines: P(l)
    return lines

def report(out):
    D = {per: pd.read_pickle(SCR + "fable_nl_" + per + ".pkl") for per in SUF}
    ALL = pd.concat(D.values(), ignore_index=True)
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    P("# 探す段階（Fable・5回目）：「ラインが多いレースはお金が散り、ライン順が軽く見られる」の予言と検証（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円・3連単の全部の目。ライン順＝同じライン3人で先頭→番手→3番手。見込み pn＝1/倍率をレースの中で合計1。nlines＝並び（line_json）のラインの数（単騎も1つ）。"
      "予言（P0〜P4）は research/fable_nlines.py の冒頭に、成績を見る前に固定した。表の中身＝点数・当たり本数・**当たり÷見込み**（95%の範囲）・回収率（95%の範囲）。範囲はレース単位ブートストラップ2,000回。" + NL)
    # 分布
    P("## レースの分布（nlines × 車立て、レース数）" + NL)
    for per in D:
        r = D[per].drop_duplicates("race_id")
        ct = pd.crosstab(r.entries_number.clip(5, 9), r.nlines.clip(1, 5)); ct.columns = [f"nlines {c}" + ("以上" if c == 5 else "") for c in ct.columns]
        P(f"**{NAME[per]}**（{len(r):,}R）" + NL); P(ct.to_markdown() + NL)
    # P0 前提
    P("## P0 前提：ラインが多いレースほどお金は散っているか（一番人気の目の見込み pn の平均。予言：4以上 ＜ 3 ＜ 2以下）" + NL)
    P("| 車立て | nlines | y4 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|---|---|")
    p0 = {}
    for cn, cf in CAR.items():
        for ln, lf in NLC.items():
            vals = []
            for per in D:
                r = D[per][cf(D[per]) & lf(D[per])].drop_duplicates("race_id"); vals.append((len(r), r.top_pn.mean() if len(r) else np.nan))
            p0[(cn, ln)] = vals
            P(f"| {cn} | {ln} | " + " | ".join((f"{v:.3f}（{n:,}R）" if n else "－") for n, v in vals) + " |")
    P("")
    for cn in CAR:
        for hi, lo in (("3", "4以上"), ("2以下", "3")):
            s = []
            for (na, va), (nb, vb) in zip(p0[(cn, hi)], p0[(cn, lo)]):
                s.append("－" if (na < 30 or nb < 30) else ("○" if va > vb else "×") + f"{va - vb:+.3f}")
            P(f"- P0 {cn}：{hi} ＞ {lo}（一番人気の見込み）：" + "／".join(s))
    P("")
    # P1
    P("## P1 ライン順の目全体：nlines が多いほど当たり÷見込みが高いか（予言：4以上 ＞ 3 ＞ 2以下）" + NL)
    V = []
    for band, bf in (("300倍以下", lambda d: d.odds <= 300), ("30倍以下", lambda d: d.odds <= 30)):
        for cn, cf in CAR.items():
            cells = {ln: (lambda d, lf=lf, cf=cf, bf=bf: d.lo & cf(d) & lf(d) & bf(d)) for ln, lf in NLC.items()}
            o = table(P, D, ALL, cells, f"ライン順×{band}×{cn}"); P("")
            V += verdict(P, f"P1 {band}・{cn}", [("4以上", "3"), ("3", "2以下")] if cn == "7車以下" else [("4以上", "3")], o); P("")
    # P2
    P("## P2 ラインをまたぐ目（3人が3つの別のライン）：nlines 4以上で割高か（予言：ratio(4以上) ＜ ratio(3)、かつ 4以上は 1未満）" + NL)
    P("目の3人が属するラインの数 ndl：1＝同じライン（ライン順でない並びも含む）、2＝2つのライン、3＝3つのライン。" + NL)
    for band, bf in (("300倍以下", lambda d: d.odds <= 300), ("30倍以下", lambda d: d.odds <= 30)):
        cells = {}
        for k, kn in ((3, "3ラインまたぎ"), (2, "2ライン"), (1, "同じライン（ライン順以外）")):
            for ln, lf in NLC.items():
                if ln == "2以下" and k == 3: continue
                cells[f"{kn}×nlines {ln}"] = (lambda d, k=k, lf=lf, bf=bf: (d.ndl == k) & (~d.lo) & lf(d) & bf(d))
        o = table(P, D, ALL, cells, f"ラインをまたぐ目×{band}（車立てを問わない）"); P("")
        V += verdict(P, f"P2 {band}", [("3ラインまたぎ×nlines 3", "3ラインまたぎ×nlines 4以上")], o)
        s = o["3ラインまたぎ×nlines 4以上"][0]; P(f"- P2 {band}：3ラインまたぎ×nlines 4以上の ratio が1未満か：" + "／".join(("○" if x["ratio"] < 1 else "×") + f"{x['ratio']:.2f}" for x in s)); P("")
    # P2 車立て別（参考）
    cells = {}
    for cn, cf in CAR.items():
        for ln, lf in (("3", NLC["3"]), ("4以上", NLC["4以上"])):
            cells[f"{cn}×nlines {ln}"] = (lambda d, cf=cf, lf=lf: (d.ndl == 3) & cf(d) & lf(d) & (d.odds <= 300))
    o = table(P, D, ALL, cells, "参考：3ラインまたぎ×300倍以下×車立て"); P("")
    V += verdict(P, "P2 参考 7車以下", [("7車以下×nlines 3", "7車以下×nlines 4以上")], o)
    V += verdict(P, "P2 参考 9車", [("9車×nlines 3", "9車×nlines 4以上")], o); P("")
    # P3
    P("## P3 nlines 4以上では、ライン順の「本命の順番」も軽く見られているか（予言：4以上 ＞ 3以下）" + NL)
    cells = {}
    for sn, sf in (("(a) 3着6位以内", lambda d: d.r2_pt_rank <= 6), ("(a') 3着4位以内", lambda d: d.r2_pt_rank <= 4), ("(b) 10倍以下", lambda d: d.odds <= 10), ("(c) レースの一番人気", lambda d: d.fav),
                   ("参考 3着7位以下", lambda d: d.r2_pt_rank >= 7)):
        for ln, lf in (("3以下", lambda d: d.nlines <= 3), ("4以上", NLC["4以上"])):
            cells[f"{sn}×nlines {ln}"] = (lambda d, sf=sf, lf=lf: d.lo & sf(d) & lf(d) & (d.odds <= 300))
    o = table(P, D, ALL, cells, "ライン順×300倍以下（車立てを問わない）"); P("")
    for sn in ("(a) 3着6位以内", "(a') 3着4位以内", "(b) 10倍以下", "(c) レースの一番人気", "参考 3着7位以下"):
        V += verdict(P, f"P3 {sn}", [(f"{sn}×nlines 4以上", f"{sn}×nlines 3以下")], o)
    P("")
    cells = {}
    for sn, sf in (("(a) 3着6位以内", lambda d: d.r2_pt_rank <= 6), ("(b) 10倍以下", lambda d: d.odds <= 10), ("(c) レースの一番人気", lambda d: d.fav)):
        for cn, cf in CAR.items():
            for ln, lf in (("3以下", lambda d: d.nlines <= 3), ("4以上", NLC["4以上"])):
                cells[f"{sn}×{cn}×nlines {ln}"] = (lambda d, sf=sf, lf=lf, cf=cf: d.lo & sf(d) & lf(d) & cf(d) & (d.odds <= 300))
    o = table(P, D, ALL, cells, "参考：車立て別"); P("")
    for sn in ("(a) 3着6位以内", "(b) 10倍以下", "(c) レースの一番人気"):
        for cn in CAR: V += verdict(P, f"P3 {sn}・{cn}", [(f"{sn}×{cn}×nlines 4以上", f"{sn}×{cn}×nlines 3以下")], o)
    P("")
    # P4
    P("## P4 nlines が同じなら 9車と7車以下の差は小さいか（ライン順×3着7位以下×20倍以下）" + NL)
    base = lambda d: d.lo & (d.r2_pt_rank >= 7) & (d.odds <= 20)
    cells = {"9車（nlines 問わず）": lambda d: base(d) & (d.entries_number >= 9), "7車以下（nlines 問わず）": lambda d: base(d) & (d.entries_number <= 7)}
    for ln, lf in (("3", NLC["3"]), ("4以上", NLC["4以上"])):
        for cn, cf in CAR.items(): cells[f"{cn}×nlines {ln}"] = (lambda d, lf=lf, cf=cf: base(d) & lf(d) & cf(d))
    o = table(P, D, ALL, cells, "区分", roi=True); P("")
    d_all = [a["ratio"] - b["ratio"] for a, b in zip(o["9車（nlines 問わず）"][0], o["7車以下（nlines 問わず）"][0])]
    d_4 = [a["ratio"] - b["ratio"] for a, b in zip(o["9車×nlines 4以上"][0], o["7車以下×nlines 4以上"][0])]
    d_3 = [a["ratio"] - b["ratio"] for a, b in zip(o["9車×nlines 3"][0], o["7車以下×nlines 3"][0])]
    P("- P4 9車−7車以下（当たり÷見込みの差）：nlines 問わず " + "／".join(f"{x:+.2f}" for x in d_all) + "、nlines 4以上の中 " + "／".join(f"{x:+.2f}" for x in d_4) + "、nlines 3 の中 " + "／".join(f"{x:+.2f}" for x in d_3))
    ok1 = all(abs(x4) < abs(xa) for x4, xa in zip(d_4, d_all)); ok2 = not (all(x > 0 for x in d_4) or all(x < 0 for x in d_4))
    P(f"- P4 判定：nlines 4以上の中の差が、nlines を問わない差より小さい（3期間とも）：**{'○' if ok1 else '×'}**／nlines 4以上の中の差の向きが3期間でそろわない：**{'○' if ok2 else '×'}**")
    V.append(f"- P4：縮む {'○' if ok1 else '×'}・向きがそろわない {'○' if ok2 else '×'}")
    P("")
    # 1つの決まり
    P("## 1つの決まり：nlines>=4 × ライン順 × 3着7位以下 × 20倍以下（車立てを問わない。条件は足さない）" + NL)
    rule = lambda d: d.lo & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.nlines >= 4)
    cells = {"決まり（全部）": rule, "参考：同じ形で nlines 3": lambda d: d.lo & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.nlines == 3),
             "参考：同じ形で nlines 2以下": lambda d: d.lo & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.nlines <= 2),
             "参考：L5（9車・nlines 問わず）": lambda d: d.lo & (d.r2_pt_rank >= 7) & (d.odds <= 20) & (d.entries_number >= 9)}
    o = table(P, D, ALL, cells, "区分", roi=True); P("")
    P("中身（決まりの中。選ぶためではなく、偏りを見るため）" + NL)
    cells = {"9車": lambda d: rule(d) & (d.entries_number >= 9), "7車以下": lambda d: rule(d) & (d.entries_number <= 7), "nlines 5以上": lambda d: rule(d) & (d.nlines >= 5),
             "10倍以下": lambda d: rule(d) & (d.odds <= 10), "10〜20倍": lambda d: rule(d) & (d.odds > 10), "本当のライン数（2人以上）4以上": lambda d: rule(d) & (d.n_real >= 4),
             "本当のライン数 3以下（単騎込みで4以上）": lambda d: rule(d) & (d.n_real <= 3)}
    table(P, D, ALL, cells, "区分", roi=True); P("")
    P("## 予言の当たり外れ（まとめ）" + NL); [P(v) for v in V]
    OUT.close(); print("wrote", out)

if __name__ == "__main__":
    if sys.argv[1] == "build": build(sys.argv[2])
    else: report(sys.argv[2])
