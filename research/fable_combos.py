"""探す段階（Fable・6回目）：「なぜ L5（9車×ライン順×弱い3番手×20倍以下）は9車だけで効くのか」を、3連単の目の数から説明できるかの検証。
見た3期間だけ：y4（2022/11/8〜2023/11/7）・2024年（2023/11/8〜2025/1/31）・2025/2〜2026/11/5。y5・y6 は見ない。keirin.sqlite は開かない。
元の表＝scratchpad の fable_nl_<期間>.pkl（research/fable_nlines.py build。3連単の全部の目・確定オッズ300倍以下・各100円・pn＝1/倍率をレースの中で合計1・lo＝ライン順）。
使う条件は締切前に分かる情報（車立て・並び・得点順位）と3連単の倍率の帯（レースの中の人気順位も倍率から作る）だけ。g_tf などの券種どうしの割安さは使わない。

【筋書き】3連単の目の数が多いほど（9車 504通り・8車 336通り・7車 210通り）、買う人は穴の目に散らばり、本命寄りの低い倍率の目が軽く見られる
 （本命・大穴のくせ favorite-longshot bias が強くなる）。だから9車では「低倍率の目」全体が7車より割安で、L5 はその一部にすぎないかもしれない。

【予言（集計の前に固定。向きと比べ方まで。成績は見ていない）】
 物差し＝当たり÷見込み（hits/Σpn）。「3期間そろう」＝y4・2024年・2025/2〜 のそれぞれで不等号が同じ向き。
 【最初の集計のあとで気づいた注意（予言の向きは変えていない）】pn は「300倍以下の目の中で合計1」に直してあるので、300倍超の目が多い9車では pn が7車より水増しされ、
   当たり÷見込み は9車の方が低く出る。車立てをまたぐ比べ（P1・P2・P4）は、この水増しの影響を受けない **回収率（hits×倍率÷点数）** と
   **当たり÷生の見込み（hits÷Σ(1/倍率)）** で判定する。同じ車立ての中の比べ（P3）は当たり÷見込みでよい（水増しが同じ）。
 P1 同じ倍率の帯（10倍以下・10〜20倍・20〜50倍）で、全部の目の 当たり÷見込み は 9車 ＞ 7車以下（3期間とも、3つの帯とも）。
     裏返し：100〜300倍の帯では 9車 ＜ 7車以下（お金が散った先は割高）。
 P2 レースの中の人気順位（1〜5番人気・6〜20・21〜50・51以降）で見ると、9車−7車以下 の差（当たり÷見込み）は人気上位ほど大きく、
     1〜5番人気 ＞ 6〜20 ＞ 21〜50 ＞ 51以降 の順に小さくなる（3期間とも）。最低限＝1〜5番人気の差 ＞ 51以降の差。
 P3 9車×20倍以下の中で、L5 の形（ライン順×3着7位以下）と、それ以外の目（残り）を比べる。
     筋書きどおり「L5 は9車の低倍率の一部にすぎない」なら、L5−残り の差は3期間で向きがそろわない（または 9車全体−7車全体 の差より小さい）。
     逆に L5−残り ＞ 0 が3期間そろい、しかも 9車全体−7車全体（20倍以下）の差より大きければ、L5 の強さは「9車の低倍率」では説明しつくせない（形に固有）。
 P4 8車（entries_number==8）は、20倍以下の帯で 7車以下 ＜ 8車 ＜ 9車 の間に来る（点数が少ないので3期間まとめで見る。各期間は参考）。
 1つの決まり（P1 が支持されたら成績を出す。条件は足さない）：**9車 × 確定オッズ10倍以下の全部の目**。
   参考として 9車×20倍以下の全部・9車×1〜5番人気 も並べるが、「決まり」は10倍以下の1つだけ（結果を見て選び替えない）。

出し方：点数・当たり本数・当たり÷見込み（95%の範囲）・回収率（95%の範囲。レース単位ブートストラップ2,000回・種0）。回収率110%超は上位5本除き・100%未満の四半期の数。
使い方: python -I -X utf8 research/fable_combos.py reports/fable_combos.md"""
import sys, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SCR = os.environ.get("FABLE_SCR", "C:/Users/take0/AppData/Local/Temp/claude/38c435bfe2a07bd9/cfa8c5a0-353c-4b57-81d8-9e3789cdb845/scratchpad/")
PERS = ["y4", "2024", "2025"]; NAME = {"y4": "y4", "2024": "2024年", "2025": "2025/2〜"}
KEEP = ["race_id", "date", "odds", "ret", "pn", "hit", "lo", "entries_number", "r2_pt_rank"]

def load(per):
    d = pd.read_pickle(SCR + "fable_nl_" + per + ".pkl")[KEEP].reset_index(drop=True)
    d["car"] = np.where(d.entries_number >= 9, 9, np.where(d.entries_number == 8, 8, 7)).astype(np.int8)
    d["prank"] = d.groupby("race_id").odds.rank(method="first").astype(np.int16)
    d["l5form"] = d.lo & (d.r2_pt_rank >= 7)
    d["band"] = pd.cut(d.odds, [0, 10, 20, 50, 100, 300], labels=["10倍以下", "10〜20倍", "20〜50倍", "50〜100倍", "100〜300倍"])
    d["pband"] = pd.cut(d.prank, [0, 5, 20, 50, 10000], labels=["1〜5番人気", "6〜20番人気", "21〜50番人気", "51番人気以降"])
    d["q"] = (1 / d.odds).astype(np.float32)
    d = d.drop(columns=["entries_number", "r2_pt_rank", "lo"])
    return d

# ---------- 集計 ----------
def summ(g, boot=2000, seed=0):
    n = len(g)
    if n == 0: return dict(n=0, nR=0, hits=0, ratio=np.nan, rlo=np.nan, rhi=np.nan, roi=np.nan, lo=np.nan, hi=np.nan, rr=np.nan)
    hits = int(g.hit.sum()); ratio = hits / g.pn.sum(); roi = g.ret.mean(); rr = hits / g.q.sum()
    a = g.groupby("race_id", sort=False).agg(r=("ret", "sum"), c=("ret", "size"), h=("hit", "sum"), p=("pn", "sum")); nR = len(a)
    rng = np.random.default_rng(seed); rv, cv, hv, pv = a.r.to_numpy(), a.c.to_numpy(), a.h.to_numpy(float), a.p.to_numpy(float)
    rs = np.empty(boot); qs = np.empty(boot)
    for i in range(boot):
        idx = rng.integers(0, nR, nR); rs[i] = rv[idx].sum() / cv[idx].sum(); qs[i] = hv[idx].sum() / pv[idx].sum()
    return dict(n=n, nR=nR, hits=hits, ratio=ratio, rlo=np.quantile(qs, 0.025), rhi=np.quantile(qs, 0.975), roi=roi, lo=np.quantile(rs, 0.025), hi=np.quantile(rs, 0.975), rr=rr)
def fmt(s):
    if s["n"] == 0: return "0点"
    return f"{s['n']:,}点・{s['hits']}本・{s['ratio']:.2f}（{s['rlo']:.2f}〜{s['rhi']:.2f}）・生 {s['rr']:.2f}・**{s['roi']:.0%}**（{s['lo']:.0%}〜{s['hi']:.0%}）"
def fmt_roi(s):
    if s["n"] == 0: return "0点"
    return f"{s['n']:,}点・{s['hits']}本・{s['ratio']:.2f}・**{s['roi']:.0%}**（{s['lo']:.0%}〜{s['hi']:.0%}）"
def extra(g):
    if len(g) == 0: return ""
    r = np.sort(g.ret.to_numpy())[::-1]; top5 = (r.sum() - r[:5].sum()) / len(r)
    qtr = g.date.str[:4] + "Q" + ((g.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
    qr = g.groupby(qtr).ret.mean(); return f"上位5本除き {top5:.0%}／四半期 {int((qr < 1).sum())}/{len(qr)} が100%未満"

def table(P, D, ALL, cells, label, boot=2000, roi=False):
    f = fmt_roi if roi else fmt
    P("| " + label + " | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    out = {}
    for cn, cf in cells.items():
        ss = [summ(D[p][cf(D[p])], boot=boot) for p in PERS]; sA = summ(ALL[cf(ALL)], boot=boot); out[cn] = (ss, sA)
        ex = ("<br>" + extra(ALL[cf(ALL)])) if (roi and sA["roi"] > 1.1) else ""
        P(f"| {cn} | " + " | ".join(f(s) for s in ss) + f" | {f(sA)} |{ex}")
    return out

def diffs(out, hi, lo, key="ratio"):
    return [((a[key] - b[key]) if (a["n"] > 0 and b["n"] > 0) else np.nan) for a, b in zip(out[hi][0], out[lo][0])]
def verdict(P, name, pairs, out, key="ratio", want=">"):
    lines = []
    for hi, lo in pairs:
        if hi not in out or lo not in out: continue
        ds = diffs(out, hi, lo, key); signs = []
        for diff in ds:
            if np.isnan(diff): signs.append("－"); continue
            ok = (diff > 0) if want == ">" else (diff < 0); signs.append(("○" if ok else "×") + f"{diff:+.2f}")
        allok = all(s.startswith("○") for s in signs)
        lines.append(f"- {name}：{hi} 対 {lo}（{key}、予言は{hi}{'＞' if want == '>' else '＜'}{lo}）：" + "／".join(signs) + f" → **{'3期間そろう' if allok else 'そろわない'}**")
    for l in lines: P(l)
    return lines

def report(out):
    D = {per: load(per) for per in PERS}
    ALL = pd.concat(D.values(), ignore_index=True)
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    P("# 探す段階（Fable・6回目）：「9車だけ効く」のは3連単の目の数（504通り 対 210通り）で説明できるか（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円・3連単の全部の目。見込み pn＝1/倍率をレースの中で合計1。人気順位＝レースの中で倍率の低い順（同じ倍率は先に出た方が上）。"
      "予言（P1〜P4）と「1つの決まり」は research/fable_combos.py の冒頭に、成績を見る前に固定した。表の中身＝点数・当たり本数・当たり÷見込み（95%の範囲）・生＝当たり÷生の見込み（hits÷Σ(1/倍率)。pn の水増しなし）・**回収率**（95%の範囲）。範囲はレース単位ブートストラップ2,000回。" + NL)
    P("**最初の集計のあとで気づいた注意（予言の向きは変えていない）**：見込み pn は「300倍以下の目の中で合計1」に直してあるので、300倍超の目が多い9車では pn が7車より水増しされ、当たり÷見込み は9車の方が低く出る（P1 の下の参考表）。車立てをまたぐ比べ（P1・P2・P4）は水増しの影響を受けない回収率と「生」で判定する。同じ車立ての中の比べ（P3）は当たり÷見込みでよい。" + NL)
    P("注意：この3期間では9車立てはほぼ G戦（GIII 以上）、7車立てはほぼ F戦なので、「9車」と「G戦（大きなレース）」はこの表では分けられない。ここで見るのは、筋書きの**目の数から出る予言が当たるか**（倍率の帯ごとの差・人気順位ごとの差・8車の位置）。" + NL)
    V = []
    # 分布
    P("## レースの分布（車立て、レース数）" + NL)
    P("| 期間 | 5〜7車 | 8車 | 9車 |" + NL + "|---|---|---|---|")
    for per in PERS:
        r = D[per].drop_duplicates("race_id"); vc = r.car.value_counts()
        P(f"| {NAME[per]} | {vc.get(7, 0):,} | {vc.get(8, 0):,} | {vc.get(9, 0):,} |")
    P("")
    # P1
    P("## P1 同じ倍率の帯で、全部の目の 当たり÷見込み は 9車 ＞ 7車以下 か（予言：10倍以下・10〜20倍・20〜50倍で 9車＞7車以下、100〜300倍で 9車＜7車以下）" + NL)
    bands = ["10倍以下", "10〜20倍", "20〜50倍", "50〜100倍", "100〜300倍"]
    cells = {}
    for b in bands:
        for c in (7, 9): cells[f"{b}×{c}車{'以下' if c == 7 else ''}"] = (lambda d, b=b, c=c: (d.band == b) & (d.car == c))
    o1 = table(P, D, ALL, cells, "倍率の帯×車立て"); P("")
    for key in ("roi", "rr"):
        for b in bands[:3]: V += verdict(P, f"P1 {b}", [(f"{b}×9車", f"{b}×7車以下")], o1, key=key)
        V += verdict(P, "P1 裏返し 50〜100倍", [(f"50〜100倍×9車", f"50〜100倍×7車以下")], o1, key=key, want="<")
        V += verdict(P, "P1 裏返し 100〜300倍", [(f"100〜300倍×9車", f"100〜300倍×7車以下")], o1, key=key, want="<")
    P("")
    P("参考（水増しの大きさ）：レースごとの Σ(1/倍率)（300倍以下の目だけ）の平均。控除25%なら全部の目で 1.33。これより小さい分が300倍超の目に乗っている。" + NL)
    P("| 車立て | y4 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|---|")
    for c in (7, 8, 9):
        vals = [D[p][D[p].car == c].groupby("race_id").q.sum().mean() for p in PERS]
        P(f"| {c}車{'以下' if c == 7 else ''} | " + " | ".join(f"{v:.3f}" for v in vals) + " |")
    P("")
    P("本命・大穴のくせの強さ（帯ごとの回収率の、10倍以下 − 100〜300倍。大きいほど穴が買われすぎ）：" + NL)
    for c in (7, 9):
        ds = [(a["roi"] - b["roi"]) for a, b in zip(o1[f"10倍以下×{c}車{'以下' if c == 7 else ''}"][0], o1[f"100〜300倍×{c}車{'以下' if c == 7 else ''}"][0])]
        dA = o1[f"10倍以下×{c}車{'以下' if c == 7 else ''}"][1]["roi"] - o1[f"100〜300倍×{c}車{'以下' if c == 7 else ''}"][1]["roi"]
        P(f"- {c}車{'以下' if c == 7 else ''}：" + "／".join(f"{x:+.0%}" for x in ds) + f"（まとめ {dA:+.0%}）")
    P("")
    # P2
    P("## P2 レースの中の人気順位で見ると、9車−7車以下 の差は人気上位ほど大きいか（予言：1〜5 ＞ 6〜20 ＞ 21〜50 ＞ 51以降）" + NL)
    pbands = ["1〜5番人気", "6〜20番人気", "21〜50番人気", "51番人気以降"]
    cells = {}
    for b in pbands:
        for c in (7, 9): cells[f"{b}×{c}車{'以下' if c == 7 else ''}"] = (lambda d, b=b, c=c: (d.pband == b) & (d.car == c))
    o2 = table(P, D, ALL, cells, "人気順位×車立て"); P("")
    dd = {b: diffs(o2, f"{b}×9車", f"{b}×7車以下", key="roi") for b in pbands}
    P("| 9車−7車以下（回収率の差） | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    for b in pbands:
        dA = o2[f"{b}×9車"][1]["roi"] - o2[f"{b}×7車以下"][1]["roi"]
        P(f"| {b} | " + " | ".join(f"{x:+.0%}" for x in dd[b]) + f" | {dA:+.0%} |")
    P("")
    P("| 9車−7車以下（当たり÷生の見込みの差） | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    for b in pbands:
        dr = diffs(o2, f"{b}×9車", f"{b}×7車以下", key="rr"); dA = o2[f"{b}×9車"][1]["rr"] - o2[f"{b}×7車以下"][1]["rr"]
        P(f"| {b} | " + " | ".join(f"{x:+.2f}" for x in dr) + f" | {dA:+.2f} |")
    P("")
    mono = []
    for i in range(3):
        mono.append(all(dd[pbands[j]][i] > dd[pbands[j + 1]][i] for j in range(3)))
    minimal = [dd[pbands[0]][i] > dd[pbands[3]][i] for i in range(3)]
    P(f"- P2（回収率の差で）単調（1〜5 ＞ 6〜20 ＞ 21〜50 ＞ 51以降）：" + "／".join("○" if m else "×" for m in mono) + f" → **{'3期間そろう' if all(mono) else 'そろわない'}**")
    P(f"- P2 最低限（1〜5番人気の差 ＞ 51以降の差）：" + "／".join("○" if m else "×" for m in minimal) + f" → **{'3期間そろう' if all(minimal) else 'そろわない'}**")
    V.append(f"- P2 単調 {'○' if all(mono) else '×'}・最低限 {'○' if all(minimal) else '×'}")
    P("")
    # P3
    P("## P3 9車×20倍以下の中で、L5 の形（ライン順×3着7位以下）は「残り」より特別に高いか（L5 が「9車の低倍率」で説明しつくせるか）" + NL)
    cells = {}
    for c in (9, 7):
        cn = f"{c}車{'以下' if c == 7 else ''}"
        cells[f"{cn}×20倍以下 全部"] = (lambda d, c=c: (d.car == c) & (d.odds <= 20))
        cells[f"{cn}×20倍以下 L5の形"] = (lambda d, c=c: (d.car == c) & (d.odds <= 20) & d.l5form)
        cells[f"{cn}×20倍以下 残り"] = (lambda d, c=c: (d.car == c) & (d.odds <= 20) & ~d.l5form)
    o3 = table(P, D, ALL, cells, "区分"); P("")
    V += verdict(P, "P3 9車：L5の形 対 残り", [("9車×20倍以下 L5の形", "9車×20倍以下 残り")], o3)
    V += verdict(P, "P3 7車以下：L5の形 対 残り", [("7車以下×20倍以下 L5の形", "7車以下×20倍以下 残り")], o3)
    for key in ("roi", "rr"):
        V += verdict(P, "P3 全部：9車 対 7車以下", [("9車×20倍以下 全部", "7車以下×20倍以下 全部")], o3, key=key)
        V += verdict(P, "P3 残り：9車 対 7車以下", [("9車×20倍以下 残り", "7車以下×20倍以下 残り")], o3, key=key)
        V += verdict(P, "P3 L5の形：9車 対 7車以下", [("9車×20倍以下 L5の形", "7車以下×20倍以下 L5の形")], o3, key=key)
    d_form = diffs(o3, "9車×20倍以下 L5の形", "9車×20倍以下 残り", key="rr"); d_car = diffs(o3, "9車×20倍以下 全部", "7車以下×20倍以下 全部", key="rr")
    bigger = [a > b for a, b in zip(d_form, d_car)]
    P(f"- P3（生の見込みで）L5の形−残り（9車の中）" + "／".join(f"{x:+.2f}" for x in d_form) + " 対 9車全体−7車全体 " + "／".join(f"{x:+.2f}" for x in d_car) + "：形の差の方が大きい " + "／".join("○" if b else "×" for b in bigger) + f" → **{'3期間とも形の差の方が大きい＝L5 は9車の低倍率では説明しつくせない' if all(bigger) else '形の差は9車の差より小さい期間がある'}**")
    V.append(f"- P3 形の差＞車立ての差 {'○' if all(bigger) else '×'}")
    P("")
    P("参考：10倍以下・10〜20倍に分けた同じ比べ（9車）" + NL)
    cells = {}
    for b in ("10倍以下", "10〜20倍"):
        cells[f"{b} 全部"] = (lambda d, b=b: (d.car == 9) & (d.band == b))
        cells[f"{b} L5の形"] = (lambda d, b=b: (d.car == 9) & (d.band == b) & d.l5form)
        cells[f"{b} 残り"] = (lambda d, b=b: (d.car == 9) & (d.band == b) & ~d.l5form)
    o3b = table(P, D, ALL, cells, "9車×帯"); P("")
    # P4
    P("## P4 8車は 7車以下 と 9車 の間に来るか（20倍以下の全部の目。予言：7車以下 ＜ 8車 ＜ 9車）" + NL)
    cells = {f"{c}車{'以下' if c == 7 else ''}×20倍以下": (lambda d, c=c: (d.car == c) & (d.odds <= 20)) for c in (7, 8, 9)}
    o4 = table(P, D, ALL, cells, "車立て"); P("")
    cells = {f"{c}車{'以下' if c == 7 else ''}×10倍以下": (lambda d, c=c: (d.car == c) & (d.odds <= 10)) for c in (7, 8, 9)}
    o4b = table(P, D, ALL, cells, "車立て"); P("")
    for lab, o in (("20倍以下", o4), ("10倍以下", o4b)):
        r7, r8, r9 = (o[f"7車以下×{lab}"][1]["roi"], o[f"8車×{lab}"][1]["roi"], o[f"9車×{lab}"][1]["roi"])
        n8 = o[f"8車×{lab}"][1]["n"]; ok = r7 < r8 < r9
        per_ok = []
        for a, b, c in zip(o[f"7車以下×{lab}"][0], o[f"8車×{lab}"][0], o[f"9車×{lab}"][0]):
            per_ok.append("－" if b["n"] < 100 else ("○" if a["roi"] < b["roi"] < c["roi"] else "×") + f"({b['roi']:.0%})")
        P(f"- P4 {lab}（回収率・まとめ）：7車以下 {r7:.0%} ／ 8車 {r8:.0%}（{n8:,}点） ／ 9車 {r9:.0%} → **{'○ 間に来る' if ok else '× 間に来ない'}**。期間ごと：" + "／".join(per_ok))
        V.append(f"- P4 {lab}：{'○' if ok else '×'}")
    P("")
    # 1つの決まり
    P("## 1つの決まり：9車 × 確定オッズ10倍以下の全部の目（条件は足さない。参考の2つは「決まり」ではない）" + NL)
    cells = {"決まり：9車×10倍以下の全部": lambda d: (d.car == 9) & (d.odds <= 10),
             "参考：9車×20倍以下の全部": lambda d: (d.car == 9) & (d.odds <= 20),
             "参考：9車×1〜5番人気": lambda d: (d.car == 9) & (d.prank <= 5),
             "参考：7車以下×10倍以下の全部": lambda d: (d.car == 7) & (d.odds <= 10),
             "参考：L5（9車×ライン順×3着7位以下×20倍以下）": lambda d: (d.car == 9) & (d.odds <= 20) & d.l5form}
    table(P, D, ALL, cells, "区分", roi=True); P("")
    P("1レースあたりの点数（決まり）：" + "／".join(f"{NAME[p]} {((D[p].car == 9) & (D[p].odds <= 10)).sum() / max(1, D[p][D[p].car == 9].race_id.nunique()):.1f}点" for p in PERS) + NL)
    P("## 予言の当たり外れ（まとめ）" + NL); [P(v) for v in V]
    OUT.close(); print("wrote", out)

if __name__ == "__main__":
    report(sys.argv[1])
