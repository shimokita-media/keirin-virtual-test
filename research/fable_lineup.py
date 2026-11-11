"""探す段階（Fable・4回目）：「並び（ラインの組み方）の読み違い」＝A 連携経験・B 同じ地区の選手が別ラインにいる。
見た3期間だけ：y4（2022/11/8〜2023/11/7）・2024年（2023/11/8〜2025/1/31）・2025/2〜2026/11/5。y5・y6 は見ない。keirin.sqlite は開かない。
元の表＝scratchpad の fable_contest_<期間>.pkl（research/fable_contest.py build が作った、ライン順＝同じライン3人で先頭→番手→3番手、確定オッズ300倍以下、pn＝見込み、hit、ret つき）。
並び＝out/side_races_*.pkl の line_json、選手＝out/side_entries_*.pkl（player_id・prefecture）。
条件は締切前に分かる情報（並び・選手の過去の並び・都道府県）と3連単の倍率の帯だけ。g_tf などの券種どうしの割安さは使わない。
選手の過去の並びは、そのレースの日より前の分だけ数える。

【筋書き・定義・しきい値（集計の前に固定。しきい値は特徴量の分布だけを見て決めた。成績は見ていない）】
A 連携経験
 筋書き：初めて組んだライン・地区をまたいだ急造のラインは、ライン順で決まりにくいのに市場は並びどおりに買うので割高。
        逆に何度も組んでいるラインのライン順は軽く見られている（→ 回数が多いほど回収率が上がる向きを予想）。
 履歴＝見た3期間の side_races の line_json（2022/11/8〜2026/11/8）から作る「同じラインにいた」記録。レースの日より前・365日以内の回数。
  H01＝先頭と番手が同じラインにいた回数、H12＝番手と3番手、H02＝先頭と3番手、H3＝3人とも同じライン、Hmin＝min(H01,H12,H02)
  区分（固定）：0回（初めて）／1〜2回／3〜9回／10回以上
 履歴の数え始め：y4 は履歴が 2022/11/8 から＝365日の窓が欠けるので**参考だけ**（「初めて」が多めに出る）。
  **選ぶ＝2024年（2023/11/8〜、窓が全部そろう）、確かめる＝2025/2〜**。
 A2 急造の印（履歴を使わない）：3人の都道府県が全部同じ／地区（競輪の8地区）は同じが都道府県は違う／地区をまたぐ。
B 同じ地区の選手が別ラインにいる
 筋書き：同じ地区の選手が分かれたとき、その2つのラインの先頭どうしは競り合わない、あるいは片方が軽く見られている。
  B1 自分の先頭と同じ都道府県の選手が別のライン（2人以上）にいる
  B2 自分の先頭と同じ地区の選手が別のライン（2人以上）の先頭にいる
  B3 自分の先頭と同じ地区の選手が別のライン（2人以上）のどこかにいる
  B4 自分のライン3人の誰かと同じ都道府県の選手が別のライン（2人以上）にいる
 履歴が要らないので **選ぶ＝y4、確かめる＝2024年・2025/2〜**。
8地区：北日本（北海道・青森・岩手・宮城・秋田・山形・福島）、関東（茨城・栃木・群馬・埼玉・新潟・長野・山梨）、南関東（千葉・東京・神奈川・静岡）、
 中部（富山・石川・福井・岐阜・愛知・三重）、近畿（滋賀・京都・大阪・兵庫・奈良・和歌山）、中国（鳥取・島根・岡山・広島・山口）、四国（徳島・香川・愛媛・高知）、
 九州（福岡・佐賀・長崎・熊本・大分・宮崎・鹿児島・沖縄）。外国は独立。
見る集合（確定オッズ）：LO300 ライン順×300倍以下／LO30 ライン順×30倍以下／W7-30 ライン順×r2_pt_rank>=7×30倍以下／
 L1 ライン順×r2_pt_rank>=7×10倍以下／L5 9車×ライン順×r2_pt_rank>=7×20倍以下
候補の決め方：選ぶ年で区分が110%超（200点以上）かつ隣の区分より上、確かめる年でも100%超で同じ向き。
出し方：点数・当たり本数・当たり÷見込み・回収率・95%の範囲（レース単位ブートストラップ2,000回・種0）。110%超は上位5本除き・100%未満の四半期の数。
使い方: python -I -X utf8 research/fable_lineup.py hist                → scratchpad の fable_hist.pkl（並びの履歴）
        python -I -X utf8 research/fable_lineup.py build y4|2024|2025  → scratchpad の fable_lineup_<期間>.pkl
        python -I -X utf8 research/fable_lineup.py report reports/fable_lineup.md"""
import sys, os, json, pickle, gc, numpy as np, pandas as pd
from collections import defaultdict
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SCR = os.environ.get("FABLE_SCR", "C:/Users/take0/AppData/Local/Temp/claude/38c435bfe2a07bd9/cfa8c5a0-353c-4b57-81d8-9e3789cdb845/scratchpad/")
SUF = {"y4": "_y4", "2024": "_y2024full", "2025": "_full"}
NAME = {"y4": "y4", "2024": "2024年", "2025": "2025/2〜"}
WIN = 365
REG = {}
for reg, prefs in {"北日本": "北海道 青森 岩手 宮城 秋田 山形 福島", "関東": "茨城 栃木 群馬 埼玉 新潟 長野 山梨", "南関東": "千葉 東京 神奈川 静岡",
                   "中部": "富山 石川 福井 岐阜 愛知 三重", "近畿": "滋賀 京都 大阪 兵庫 奈良 和歌山", "中国": "鳥取 島根 岡山 広島 山口",
                   "四国": "徳島 香川 愛媛 高知", "九州": "福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄"}.items():
    for p in prefs.split(): REG[p] = reg
def region(p): return REG.get(p, p if isinstance(p, str) else "不明")
def ordinal(dates): return (pd.to_datetime(dates.astype(str), format="%Y%m%d") - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
def lines_of(lj):
    return [[x for e in l["entries"] for x in e["numbers"]] for l in json.loads(lj)]

def load_side(per):
    R = pd.read_pickle(K + f"out/side_races{SUF[per]}.pkl")[["race_id", "date", "line_json"]]
    E = pd.read_pickle(K + f"out/side_entries{SUF[per]}.pkl")[["race_id", "number", "player_id", "prefecture"]]
    return R, E

def hist():
    """全期間の並びの履歴：ペア・3人組ごとに、同じラインにいた日（2000/1/1 からの日数）の並び（昇順）。"""
    pair = defaultdict(list); trio = defaultdict(list); seen = set(); n_races = 0
    for per in ("y4", "2024", "2025"):
        R, E = load_side(per)
        R = R[~R.race_id.isin(seen) & R.line_json.notna()].copy(); seen |= set(R.race_id)
        R["od"] = ordinal(R.date)
        E = E[E.race_id.isin(R.race_id)]
        pid = {(r, int(n)): str(p) for r, n, p in zip(E.race_id, E.number, E.player_id)}
        for rid, od, lj in zip(R.race_id, R.od, R.line_json):
            n_races += 1
            for l in lines_of(lj):
                ps = sorted(pid.get((rid, n), "?" + str(n)) for n in l)
                for i in range(len(ps)):
                    for j in range(i + 1, len(ps)):
                        pair[(ps[i], ps[j])].append(od)
                        for k in range(j + 1, len(ps)): trio[(ps[i], ps[j], ps[k])].append(od)
        del R, E, pid; gc.collect(); print(per, "履歴に入れたレース", n_races, "ペア", len(pair), "3人組", len(trio), flush=True)
    pair = {k: np.array(sorted(v), dtype=np.int32) for k, v in pair.items()}
    trio = {k: np.array(sorted(v), dtype=np.int32) for k, v in trio.items()}
    with open(SCR + "fable_hist.pkl", "wb") as f: pickle.dump((pair, trio), f)

def count(h, key, od):
    a = h.get(key)
    if a is None: return 0
    return int(np.searchsorted(a, od, side="left") - np.searchsorted(a, od - WIN, side="left"))

def build(per):
    d = pd.read_pickle(SCR + "fable_contest_" + per + ".pkl").reset_index(drop=True)
    sp = d.combo.str.split("-"); d["b"] = sp.str[1].astype(int); d["c"] = sp.str[2].astype(int)
    d["od"] = ordinal(d.date)
    with open(SCR + "fable_hist.pkl", "rb") as f: pair, trio = pickle.load(f)
    R, E = load_side(per); R = R.set_index("race_id")
    E = E[E.race_id.isin(d.race_id.unique())]
    info = {(r, int(n)): (str(p), pf) for r, n, p, pf in zip(E.race_id, E.number, E.player_id, E.prefecture)}
    rows = []
    for rid, a, b, c, od in zip(d.race_id, d.a, d.b, d.c, d.od):
        pa, fa = info.get((rid, a), ("?", None)); pb, fb = info.get((rid, b), ("?", None)); pc, fc = info.get((rid, c), ("?", None))
        s01 = tuple(sorted((pa, pb))); s12 = tuple(sorted((pb, pc))); s02 = tuple(sorted((pa, pc))); s3 = tuple(sorted((pa, pb, pc)))
        H01, H12, H02, H3 = count(pair, s01, od), count(pair, s12, od), count(pair, s02, od), count(trio, s3, od)
        ra, rb, rc = region(fa), region(fb), region(fc)
        mix = 0 if (fa == fb == fc) else (1 if (ra == rb == rc) else 2)   # 0 同じ県 1 同じ地区 2 地区またぎ
        lj = R.line_json.get(rid); B1 = B2 = B3 = B4 = np.nan; n_other = np.nan
        if isinstance(lj, str):
            lines = lines_of(lj); own = next((l for l in lines if a in l), None)
            if own is not None:
                others = [l for l in lines if l is not own and len(l) >= 2]; n_other = len(others)
                oth_pref = [[info.get((rid, n), ("?", None))[1] for n in l] for l in others]
                B1 = float(any(fa in pf for pf in oth_pref))
                B2 = float(any(region(pf[0]) == ra for pf in oth_pref))
                B3 = float(any(region(p) == ra for pf in oth_pref for p in pf))
                own_pref = {info.get((rid, n), ("?", None))[1] for n in own[:3]}
                B4 = float(any(p in own_pref for pf in oth_pref for p in pf))
        rows.append((pa, pb, pc, H01, H12, H02, H3, mix, B1, B2, B3, B4, n_other))
    f = pd.DataFrame(rows, columns=["pa", "pb", "pc", "H01", "H12", "H02", "H3", "mix", "B1", "B2", "B3", "B4", "n_other"])
    d = pd.concat([d, f], axis=1); d["Hmin"] = d[["H01", "H12", "H02"]].min(axis=1)
    bad = (d.pa == "?") | (d.pb == "?") | (d.pc == "?") | d.B1.isna()
    print(per, d.shape, "選手不明・並び不明で落とした", int(bad.sum())); d = d[~bad].reset_index(drop=True)
    for c in ["H01", "H12", "H02", "H3", "Hmin"]: print(" ", c, d[c].clip(upper=12).value_counts().sort_index().to_dict())
    for c in ["mix", "B1", "B2", "B3", "B4", "n_other"]: print(" ", c, d[c].value_counts().sort_index().to_dict())
    d.to_pickle(SCR + "fable_lineup_" + per + ".pkl")

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
    "LO300 ライン順×300倍以下": lambda d: d.odds <= 300,
    "LO30 ライン順×30倍以下": lambda d: d.odds <= 30,
    "W7-30 ライン順×3着7位以下×30倍以下": lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 30),
    "L1 ライン順×3着7位以下×10倍以下": lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 10),
    "L5 9車×ライン順×3着7位以下×20倍以下": lambda d: (d.entries_number >= 9) & (d.r2_pt_rank >= 7) & (d.odds <= 20),
}
def hcat(x): return pd.cut(x, [-1, 0, 2, 9, 10**6], labels=["0回", "1〜2回", "3〜9回", "10回以上"])
A_SPLITS = {"H01 先頭-番手": "H01", "H12 番手-3番手": "H12", "H02 先頭-3番手": "H02", "H3 3人とも": "H3", "Hmin 一番弱いつながり": "Hmin"}
MIX = {0: "同じ県", 1: "同じ地区・違う県", 2: "地区またぎ"}
B_SPLITS = {"B1 先頭と同じ県が別ライン": "B1", "B2 先頭と同じ地区が別ラインの先頭": "B2", "B3 先頭と同じ地区が別ラインのどこか": "B3", "B4 3人の誰かと同じ県が別ライン": "B4"}

def table(P, D, ALL, setf, cats, label):
    """cats: dict 区分名 -> (lambda d: bool mask)。"""
    P("| " + label + " | y4（参考） | 2024年（選ぶ） | 2025/2〜（確かめる） | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    for cn, cf in cats.items():
        cells = [fmt(summ(D[p][setf(D[p]) & cf(D[p])])) for p in D]
        gA = ALL[setf(ALL) & cf(ALL)]; sA = summ(gA); cells.append(fmt(sA))
        ex = ("<br>" + extra(gA)) if sA["roi"] > 1.1 else ""
        P(f"| {cn} | " + " | ".join(cells) + f" |{ex}")

def report(out):
    D = {per: pd.read_pickle(SCR + "fable_lineup_" + per + ".pkl") for per in SUF}
    for per in D:
        for k in A_SPLITS.values(): D[per][k + "c"] = hcat(D[per][k])
    ALL = pd.concat(D.values(), ignore_index=True)
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    P("# 探す段階（Fable・4回目）：並び（ラインの組み方）の読み違い＝A 連携経験・B 同じ地区の選手が別ラインにいる（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円。ライン順＝同じライン3人で先頭→番手→3番手。見込み pn＝1/倍率をレースの中で合計1。定義・しきい値・選ぶ年と確かめる年は research/fable_lineup.py の冒頭に、成績を見る前に固定した。表の中身＝点数・当たり本数・当たり÷見込み・**回収率**（95%の範囲＝レース単位ブートストラップ2,000回）。110%超（3期間まとめ）には上位5本の当たりを除いた回収率と100%未満の四半期の数。" + NL)
    P("A の履歴は 2022/11/8 からなので、y4 は365日の窓が欠ける（「0回」が多めに出る）＝**参考**。A は 2024年で選び 2025/2〜 で確かめる。B は履歴を使わないので y4 で選び 2024年・2025/2〜 で確かめる（表の見出しは A に合わせてあるが、B では y4 が「選ぶ」、2024年・2025/2〜 が「確かめる」）。" + NL)
    P("## 区分の割合（ライン順の目の数ベース）" + NL + "| 区分 | y4 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|---|")
    for sn, k in A_SPLITS.items():
        for lab in ["0回", "1〜2回", "3〜9回", "10回以上"]:
            P(f"| {sn}＝{lab} | " + " | ".join(f"{(D[p][k + 'c'] == lab).mean():.0%}" for p in D) + " |")
    for m, lab in MIX.items(): P(f"| 急造の印＝{lab} | " + " | ".join(f"{(D[p].mix == m).mean():.0%}" for p in D) + " |")
    for sn, k in B_SPLITS.items(): P(f"| {sn}＝あり | " + " | ".join(f"{(D[p][k] == 1).mean():.0%}" for p in D) + " |")
    P(NL + "相関（2024年・ライン順の目）：" + NL)
    P(D["2024"][["H01", "H12", "H02", "H3", "Hmin", "mix", "B1", "B2", "B3", "B4", "entries_number", "nlines", "r2_pt_rank"]].corr().round(2).to_markdown() + NL)
    # A
    P("# A 連携経験（365日以内に同じラインにいた回数）" + NL)
    for setn, setf in SETS.items():
        P(f"## {setn}" + NL)
        table(P, D, ALL, setf, {"（全部）": lambda d: d.odds > 0}, "区分")
        for sn, k in A_SPLITS.items():
            table(P, D, ALL, setf, {f"{sn}＝{lab}": (lambda d, k=k, lab=lab: d[k + "c"] == lab) for lab in ["0回", "1〜2回", "3〜9回", "10回以上"]}, sn)
        table(P, D, ALL, setf, {f"急造の印＝{lab}": (lambda d, m=m: d.mix == m) for m, lab in MIX.items()}, "A2 急造の印（都道府県・地区）")
        table(P, D, ALL, setf, {"地区またぎ×先頭-番手0回": lambda d: (d.mix == 2) & (d.H01 == 0), "同じ地区×先頭-番手10回以上": lambda d: (d.mix <= 1) & (d.H01 >= 10)}, "A 組み合わせ")
        P("")
    # B
    P("# B 同じ地区の選手が別ラインにいる（選ぶ＝y4、確かめる＝2024年・2025/2〜）" + NL)
    for setn, setf in SETS.items():
        P(f"## {setn}" + NL)
        for sn, k in B_SPLITS.items():
            table(P, D, ALL, setf, {f"{sn}＝あり": (lambda d, k=k: d[k] == 1), f"{sn}＝なし": (lambda d, k=k: d[k] == 0)}, sn)
        P("")
    # B × 車立て（同じ地区の分かれ方は9車で多いはずなので、車立てで分けて見る）
    P("# B × 車立て（B2 先頭と同じ地区が別ラインの先頭。ライン順×3着7位以下×20倍以下）" + NL)
    s = lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 20)
    table(P, D, ALL, s, {"9車×あり": lambda d: (d.entries_number >= 9) & (d.B2 == 1), "9車×なし": lambda d: (d.entries_number >= 9) & (d.B2 == 0),
                          "7車以下×あり": lambda d: (d.entries_number <= 7) & (d.B2 == 1), "7車以下×なし": lambda d: (d.entries_number <= 7) & (d.B2 == 0)}, "区分")
    P(NL + "# B × 自分のラインの先頭の得点順位（B2。LO30）" + NL)
    table(P, D, ALL, SETS["LO30 ライン順×30倍以下"], {"あり×先頭が得点1位": lambda d: (d.B2 == 1) & (d.r0_pt_rank == 1), "あり×先頭が得点2位以下": lambda d: (d.B2 == 1) & (d.r0_pt_rank >= 2),
                                                         "なし×先頭が得点1位": lambda d: (d.B2 == 0) & (d.r0_pt_rank == 1), "なし×先頭が得点2位以下": lambda d: (d.B2 == 0) & (d.r0_pt_rank >= 2)}, "区分")
    OUT.close(); print("wrote", out)

if __name__ == "__main__":
    if sys.argv[1] == "hist": hist()
    elif sys.argv[1] == "build": build(sys.argv[2])
    else: report(sys.argv[2])
