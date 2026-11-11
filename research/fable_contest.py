"""探す段階（Fable・3回目）：「ライン順が決まりやすいレースの形」＝主導権争いが起きにくいレースほど、ライン順の目（とくに弱い3番手）は軽く見られているか。
見た3期間だけ：y4（2022/11/8〜2023/11/7）・2024年（2023/11/8〜2025/1/31）・2025/2〜2026/11/5。y5・y6 は見ない。keirin.sqlite は開かない。
元の表＝out/lo_wide_<期間>.pkl（ライン順＝同じライン3人で先頭→番手→3番手、確定オッズ300倍以下、pn＝見込み、hit、ret、flow つき）。
並び＝out/side_races_*.pkl の line_json、選手＝out/side_entries_*.pkl（style・race_point・n_back＝B回数）。
条件は締切前に分かる情報（並び・脚質・得点・B回数・車立て）と3連単の倍率の帯だけ。g_tf などの券種どうしの割安さは使わない。

【定義としきい値（集計の前に固定。しきい値は y4 の特徴量の分布だけを見て決めた。成績は見ていない）】
 レースの並び（line_json）の各ラインについて：先頭＝最初の車番、先頭の脚質 style、先頭の得点順位（出走選手の中・降順・同点は小さい方）、先頭のB回数 n_back、人数。
 目の「自分のライン」＝1着に置く選手（先頭）がいるライン。「相手のライン」＝それ以外の全部（単騎も含む）。
 F1 相手の逃げ先頭の数   n_rival_nige＝相手のラインのうち先頭の脚質が「逃」の数
 F2 相手のB持ち先頭の数  n_rival_B   ＝相手のラインのうち先頭のB回数が5以上の数（y4 の選手のB回数の75%点が5）
 F3 本当のラインの数     n_real      ＝2人以上のラインの数（単騎を除く）。n_single＝単騎の数
 F4 先頭の格             dominant    ＝自分の先頭が得点1位 かつ 相手の先頭はみな得点3位以下
 F0 既存の列 n_strong_nige（逃×得点3位以内の先頭がいるラインの数。自分のラインも含む）
 分け方（少ない／多い）：
  D0 n_strong_nige<=1 ／ >=2
  D1 n_rival_nige==0 ／ >=1
  D2 n_rival_B==0 ／ >=1
  D3 n_real<=2 ／ >=3
  D4 dominant ／ それ以外
  C  （D1 少）+（D2 少）+（D3 少）の数。3＝争いがほぼ無い、0＝争いが多い
 見る集合（確定オッズ）：LO30 ライン順×30倍以下／W7-30 ライン順×r2_pt_rank>=7×30倍以下／L1 ライン順×r2_pt_rank>=7×10倍以下／
  L5 9車×ライン順×r2_pt_rank>=7×20倍以下／W23 ライン順×r1_pt_rank>=5×r2_pt_rank>=7×5倍超10倍以下／Lx 7車以下×ライン順×r2_pt_rank>=7×20倍以下（L5 の7車版）
 選び方：y4 で「少ない＞多い」の差がはっきりし、少ないが110%超のものを候補にし、2024年・2025/2〜 で確かめる。
 逆向き：C==0（争い多い）のライン順全体（30倍以下・300倍以下）の当たり÷見込みが1未満か。
 出し方：点数・当たり本数・当たり÷見込み・回収率・95%の範囲（レース単位ブートストラップ2,000回・種0）。110%超は上位5本除き・100%未満の四半期の数。
使い方: python -I -X utf8 research/fable_contest.py build y4|2024|2025   → scratchpad の fable_contest_<期間>.pkl
        python -I -X utf8 research/fable_contest.py report reports/fable_contest.md"""
import sys, os, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SCR = os.environ.get("FABLE_SCR", "C:/Users/take0/AppData/Local/Temp/claude/38c435bfe2a07bd9/cfa8c5a0-353c-4b57-81d8-9e3789cdb845/scratchpad/")
LOF = {"y4": "y4", "2024": "2024年", "2025": "20252"}
SUF = {"y4": "_y4", "2024": "_y2024full", "2025": "_full"}
NAME = {"y4": "y4", "2024": "2024年", "2025": "2025/2〜"}
KEEP = ["race_id", "combo", "date", "odds", "ret", "pn", "hit", "entries_number", "nlines", "n_strong_nige", "r0_pt_rank", "r1_pt_rank", "r2_pt_rank",
        "r0_style", "r1_style", "r0_ls", "G", "is_top", "flow", "n_prev", "grade", "race_type", "day_index"]
B_TH = 5  # F2 のしきい値（B回数）

def build(per):
    d = pd.read_pickle(K + f"out/lo_wide_{LOF[per]}.pkl")[KEEP].reset_index(drop=True)
    d["a"] = d.combo.str.split("-").str[0].astype(int)
    R = pd.read_pickle(K + f"out/side_races{SUF[per]}.pkl").set_index("race_id")
    E = pd.read_pickle(K + f"out/side_entries{SUF[per]}.pkl")
    E = E[(E.absent != 1) & E.race_id.isin(d.race_id.unique())].copy()
    E["rp"] = pd.to_numeric(E.race_point, errors="coerce"); E["ptr"] = E.groupby("race_id").rp.rank(ascending=False, method="min")
    E["nb"] = pd.to_numeric(E.n_back, errors="coerce").fillna(0)
    Eg = {k: g.set_index("number") for k, g in E.groupby("race_id")}
    rows = []
    for rid, a in zip(d.race_id, d.a):
        lj = R.line_json.get(rid); g = Eg.get(rid)
        if not isinstance(lj, str) or g is None: rows.append((np.nan,) * 6); continue
        lines = [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(lj)]
        own = next((l for l in lines if a in l), None)
        if own is None: rows.append((np.nan,) * 6); continue
        riv = [l for l in lines if l is not own]
        n_nige = sum(1 for l in riv if g["style"].get(l[0]) == "逃")
        n_B = sum(1 for l in riv if g.nb.get(l[0], 0) >= B_TH)
        n_real = sum(1 for l in lines if len(l) >= 2); n_single = sum(1 for l in lines if len(l) == 1)
        own_rank = g.ptr.get(a, np.nan); riv_best = min((g.ptr.get(l[0], 9) for l in riv), default=9)
        dom = float(own_rank == 1 and riv_best >= 3)
        rows.append((n_nige, n_B, n_real, n_single, dom, riv_best))
    f = pd.DataFrame(rows, columns=["n_rival_nige", "n_rival_B", "n_real", "n_single", "dominant", "riv_best"])
    d = pd.concat([d, f], axis=1); d = d[d.n_real.notna()].reset_index(drop=True)
    d["C"] = (d.n_rival_nige == 0).astype(int) + (d.n_rival_B == 0).astype(int) + (d.n_real <= 2).astype(int)
    print(per, d.shape, "並び不明で落とした", len(f) - len(d))
    for c in ["n_rival_nige", "n_rival_B", "n_real", "n_single", "dominant", "C", "n_strong_nige"]:
        print(" ", c, d[c].value_counts().sort_index().to_dict())
    d.to_pickle(SCR + "fable_contest_" + per + ".pkl")

# ---------- 集計 ----------
def summ(g, boot=2000, seed=0):
    n = len(g)
    if n == 0: return dict(n=0, hits=0, ratio=np.nan, roi=np.nan, lo=np.nan, hi=np.nan)
    hits = int(g.hit.sum()); ratio = hits / g.pn.sum(); roi = g.ret.mean()
    a = g.groupby("race_id", sort=False).agg(r=("ret", "sum"), c=("ret", "size")); nR = len(a)
    rng = np.random.default_rng(seed); rv, cv = a.r.to_numpy(), a.c.to_numpy()
    rs = np.empty(boot)
    for i in range(boot):
        idx = rng.integers(0, nR, nR); rs[i] = rv[idx].sum() / cv[idx].sum()
    return dict(n=n, hits=hits, ratio=ratio, roi=roi, lo=np.quantile(rs, 0.025), hi=np.quantile(rs, 0.975))
def fmt(s):
    if s["n"] == 0: return "0点"
    return f"{s['n']:,}点・{s['hits']}本・{s['ratio']:.2f}・**{s['roi']:.0%}**（{s['lo']:.0%}〜{s['hi']:.0%}）"
def extra(g):
    if len(g) == 0: return ""
    r = np.sort(g.ret.to_numpy())[::-1]; top5 = (r.sum() - r[:5].sum()) / len(r)
    qtr = g.date.str[:4] + "Q" + ((g.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
    qr = g.groupby(qtr).ret.mean(); return f"上位5本除き {top5:.0%}／四半期 {int((qr < 1).sum())}/{len(qr)} が100%未満"

SETS = {
    "LO30 ライン順×30倍以下": lambda d: d.odds <= 30,
    "W7-30 ライン順×3着7位以下×30倍以下": lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 30),
    "L1 ライン順×3着7位以下×10倍以下": lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 10),
    "L5 9車×ライン順×3着7位以下×20倍以下": lambda d: (d.entries_number >= 9) & (d.r2_pt_rank >= 7) & (d.odds <= 20),
    "Lx 7車以下×ライン順×3着7位以下×20倍以下": lambda d: (d.entries_number <= 7) & (d.r2_pt_rank >= 7) & (d.odds <= 20),
    "W23 ライン順×2着5位以下×3着7位以下×5倍超10倍以下": lambda d: (d.r1_pt_rank >= 5) & (d.r2_pt_rank >= 7) & (d.odds > 5) & (d.odds <= 10),
}
SPLITS = {
    "D0 強い逃げ先頭<=1／>=2": lambda d: d.n_strong_nige <= 1,
    "D1 相手の逃げ先頭 0／1以上": lambda d: d.n_rival_nige == 0,
    "D2 相手のB持ち先頭 0／1以上": lambda d: d.n_rival_B == 0,
    "D3 本当のライン数<=2／>=3": lambda d: d.n_real <= 2,
    "D4 先頭の格（得点1位・相手3位以下）／それ以外": lambda d: d.dominant == 1,
    "C3 争いほぼ無し（C==3）／それ以外": lambda d: d.C == 3,
    "C2 C>=2／C<=1": lambda d: d.C >= 2,
}

def report(out):
    D = {per: pd.read_pickle(SCR + "fable_contest_" + per + ".pkl") for per in LOF}
    ALL = pd.concat(D.values(), ignore_index=True)
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    P("# 探す段階（Fable・3回目）：「ライン順が決まりやすいレースの形」＝主導権争いの少なさで分ける（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円。ライン順＝同じライン3人で先頭→番手→3番手。見込み pn＝1/倍率をレースの中で合計1。定義・しきい値は research/fable_contest.py の冒頭に、成績を見る前に固定した。表の中身＝点数・当たり本数・当たり÷見込み・**回収率**（95%の範囲＝レース単位ブートストラップ2,000回）。" + NL)
    # 分布
    P("## 分け方ごとの「少ない」側の割合（ライン順の目の数ベース）" + NL + "| 分け方 | y4 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|---|")
    for sn, sf in SPLITS.items():
        P(f"| {sn} | " + " | ".join(f"{sf(D[p]).mean():.0%}" for p in LOF) + " |")
    P(NL + "特徴量どうしの相関（y4・ライン順の目）：" + NL)
    cc = D["y4"][["n_strong_nige", "n_rival_nige", "n_rival_B", "n_real", "n_single", "dominant", "entries_number", "nlines"]].corr().round(2)
    P(cc.to_markdown() + NL)
    # 主な表
    for setn, setf in SETS.items():
        P(f"## {setn}" + NL)
        P("| 分け方 | 側 | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|---|")
        base = {p: D[p][setf(D[p])] for p in LOF}; baseA = ALL[setf(ALL)]
        P("| （全部） | | " + " | ".join(fmt(summ(base[p])) for p in LOF) + f" | {fmt(summ(baseA))} |")
        for sn, sf in SPLITS.items():
            for side, lab in ((True, "少ない"), (False, "多い")):
                cells = [fmt(summ(base[p][sf(base[p]) == side])) for p in LOF]
                sA = summ(baseA[sf(baseA) == side]); cells.append(fmt(sA))
                ex = ""
                if side and sA["roi"] > 1.1: ex = "<br>" + extra(baseA[sf(baseA) == side])
                P(f"| {sn} | {lab} | " + " | ".join(cells) + f" |{ex}")
        P("")
    # C の段階
    P("## C（争いの少なさ 0〜3）の段階ごと" + NL)
    for setn in ("LO30 ライン順×30倍以下", "W7-30 ライン順×3着7位以下×30倍以下", "L1 ライン順×3着7位以下×10倍以下", "L5 9車×ライン順×3着7位以下×20倍以下"):
        P(f"### {setn}" + NL + "| C | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|")
        setf = SETS[setn]
        for c in range(4):
            cells = [fmt(summ(D[p][setf(D[p]) & (D[p].C == c)])) for p in LOF]; cells.append(fmt(summ(ALL[setf(ALL) & (ALL.C == c)])))
            P(f"| {c} | " + " | ".join(cells) + " |")
        P("")
    # 9車と争い
    P("## L5 の中の9車は「主導権争い」で説明できるか（ライン順×3着7位以下×20倍以下、3期間まとめ）" + NL)
    P("| 車立て | C | 点数 | 当たり÷見込み | 回収率 | 目の割合（車立ての中） |" + NL + "|---|---|---|---|---|---|")
    s = ALL[(ALL.r2_pt_rank >= 7) & (ALL.odds <= 20)]
    for nine, lab in ((True, "9車"), (False, "7車以下")):
        ss = s[(s.entries_number >= 9) == nine]
        for c in range(4):
            x = summ(ss[ss.C == c], boot=200); P(f"| {lab} | {c} | {x['n']:,} | {x['ratio']:.2f} | {x['roi']:.0%} | {(ss.C == c).mean():.0%} |")
    P(NL + "| 車立て | 相手の逃げ先頭 | 点数 | 当たり÷見込み | 回収率 |" + NL + "|---|---|---|---|---|")
    for nine, lab in ((True, "9車"), (False, "7車以下")):
        ss = s[(s.entries_number >= 9) == nine]
        for k in (0, 1, 2):
            x = summ(ss[ss.n_rival_nige.clip(upper=2) == k], boot=200); P(f"| {lab} | {k}{'以上' if k == 2 else ''} | {x['n']:,} | {x['ratio']:.2f} | {x['roi']:.0%} |")
    P(NL + "| 車立て | 本当のライン数 | 点数 | 当たり÷見込み | 回収率 |" + NL + "|---|---|---|---|---|")
    for nine, lab in ((True, "9車"), (False, "7車以下")):
        ss = s[(s.entries_number >= 9) == nine]
        for k in (1, 2, 3, 4):
            x = summ(ss[ss.n_real.clip(upper=4) == k], boot=200); P(f"| {lab} | {k}{'以上' if k == 4 else ''} | {x['n']:,} | {x['ratio']:.2f} | {x['roi']:.0%} |")
    # 逆向き
    P(NL + "## 逆向き：争いが多いレースで、ライン順の目は割高か" + NL + "| 集合 | 側 | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|---|")
    for setn, setf in (("ライン順×300倍以下", lambda d: d.odds <= 300), ("ライン順×30倍以下", lambda d: d.odds <= 30), ("ライン順×3着7位以下×30倍以下", lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 30))):
        for sn, sf in (("C==0（争い多い）", lambda d: d.C == 0), ("相手の逃げ先頭2以上", lambda d: d.n_rival_nige >= 2), ("本当のライン数4以上", lambda d: d.n_real >= 4), ("強い逃げ先頭2以上", lambda d: d.n_strong_nige >= 2)):
            cells = [fmt(summ(D[p][setf(D[p]) & sf(D[p])], boot=500)) for p in LOF]; cells.append(fmt(summ(ALL[setf(ALL) & sf(ALL)], boot=500)))
            P(f"| {setn} | {sn} | " + " | ".join(cells) + " |")
    OUT.close(); print("wrote", out)

if __name__ == "__main__":
    if sys.argv[1] == "build": build(sys.argv[2])
    else: report(sys.argv[2])
