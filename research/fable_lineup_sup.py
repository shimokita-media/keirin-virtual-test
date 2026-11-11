"""fable_lineup.py の補足（結果を見た後の点検＝候補の判定には使わない・偶然かどうかの見極め用）。
 1 L1×B2（先頭と同じ地区が別ラインの先頭）が3期間とも100%超に見えた → 倍率の帯（10倍以下／10〜20倍／20〜30倍）と車立てで割ると続くか。
 2 A の「先頭-番手 0回（初めて）は少し割高」が全体で一貫して見えた → LO30 で 0回 と 1回以上 の差の t 値（目ごとの ret の差、レース内の相関は無視した近似）。
 3 W7-30×H01 1〜2回（111/109/107%）→ 1回以上にまとめると。
使い方: python -I -X utf8 research/fable_lineup_sup.py reports/fable_lineup.md  （末尾に追記）"""
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fable_lineup import SCR, SUF, summ, fmt, extra, NL
D = {per: pd.read_pickle(SCR + "fable_lineup_" + per + ".pkl") for per in SUF}
ALL = pd.concat(D.values(), ignore_index=True)
OUT = open(sys.argv[1], "a", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
def table(setf, cats, label):
    P("| " + label + " | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|")
    for cn, cf in cats.items():
        cells = [fmt(summ(D[p][setf(D[p]) & cf(D[p])], boot=1000)) for p in D]
        gA = ALL[setf(ALL) & cf(ALL)]; sA = summ(gA, boot=1000); cells.append(fmt(sA))
        P(f"| {cn} | " + " | ".join(cells) + " |" + (("<br>" + extra(gA)) if sA["roi"] > 1.1 else ""))
P(NL + "# 補足（結果を見た後の点検。候補の判定には使わない）" + NL)
P("## 1 L1×B2 は倍率の帯・車立てで続くか（ライン順×3着7位以下×B2＝あり）" + NL)
w = lambda d: (d.r2_pt_rank >= 7) & (d.B2 == 1)
table(w, {"10倍以下（＝L1×B2）": lambda d: d.odds <= 10, "10〜20倍": lambda d: (d.odds > 10) & (d.odds <= 20), "20〜30倍": lambda d: (d.odds > 20) & (d.odds <= 30),
          "30〜300倍": lambda d: d.odds > 30, "10倍以下×7車以下": lambda d: (d.odds <= 10) & (d.entries_number <= 7), "10倍以下×9車": lambda d: (d.odds <= 10) & (d.entries_number >= 9),
          "B3＝あり×10倍以下": lambda d: d.odds <= 10}, "帯")
P(NL + "比べる：B2＝なし の同じ帯" + NL)
w0 = lambda d: (d.r2_pt_rank >= 7) & (d.B2 == 0)
table(w0, {"10倍以下": lambda d: d.odds <= 10, "10〜20倍": lambda d: (d.odds > 10) & (d.odds <= 20), "20〜30倍": lambda d: (d.odds > 20) & (d.odds <= 30)}, "帯")
P(NL + "## 2 A「先頭-番手 0回（初めて）」と「1回以上」の差（LO30。ret の差の t 値＝目ごと・近似）" + NL + "| 期間 | 0回 | 1回以上 | 差（ポイント） | t |" + NL + "|---|---|---|---|---|")
for p, d in list(D.items()) + [("3期間まとめ", ALL)]:
    s = d[d.odds <= 30]; a = s[s.H01 == 0].ret; b = s[s.H01 >= 1].ret
    t = (b.mean() - a.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))
    P(f"| {p} | {a.mean():.1%}（{len(a):,}点） | {b.mean():.1%}（{len(b):,}点） | {100 * (b.mean() - a.mean()):+.1f} | {t:.2f} |")
P(NL + "同じく「3人の地区」（LO30）：同じ地区（同じ県を含む）と地区またぎ" + NL + "| 期間 | 同じ地区 | 地区またぎ | 差 | t |" + NL + "|---|---|---|---|---|")
for p, d in list(D.items()) + [("3期間まとめ", ALL)]:
    s = d[d.odds <= 30]; a = s[s.mix == 2].ret; b = s[s.mix <= 1].ret
    t = (b.mean() - a.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))
    P(f"| {p} | {b.mean():.1%}（{len(b):,}点） | {a.mean():.1%}（{len(a):,}点） | {100 * (b.mean() - a.mean()):+.1f} | {t:.2f} |")
P(NL + "## 3 W7-30（ライン順×3着7位以下×30倍以下）で先頭-番手を「0回／1回以上」にまとめる" + NL)
table(lambda d: (d.r2_pt_rank >= 7) & (d.odds <= 30), {"0回": lambda d: d.H01 == 0, "1回以上": lambda d: d.H01 >= 1,
      "1回以上×10倍以下（L1 の中）": lambda d: (d.H01 >= 1) & (d.odds <= 10), "1回以上×10〜30倍": lambda d: (d.H01 >= 1) & (d.odds > 10)}, "区分")
OUT.close(); print("appended")
