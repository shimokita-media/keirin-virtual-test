"""探す段階（Fable・2回目）B：前回見つけた「買われすぎの目（外す材料）」を L1・L5・W23 から外したら上がるか。
見た3期間だけ：y4・2024年（2023/11/8〜2025/1/31）・2025/2〜2026/11/5。y5・y6 は見ない。
元の表＝scratchpad の slim2_*.pkl（research/fable_player.py build。確定オッズ300倍以下・各100円・pn＝1/倍率をレースの中で合計1）。
条件は締切前に分かる情報と倍率の帯だけ（g_tf などは使わない）。

もとの形（定義は KNOWLEDGE.md 2026-11-11 の登録と同じ。lo＝s01==1・s12==1・r0_pos==0・r1_pos==1・r2_pos==2）
 L1＝lo × r2_pt_rank>=7 × 10倍以下
 L5＝entries_number>=9 × lo × r2_pt_rank>=7 × 20倍以下
 W23＝lo × r1_pt_rank>=5 × r2_pt_rank>=7 × 5倍超10倍以下
外す決まり（データを見る前に固定。前回 reports/fable_habits.md で3期間とも当たり÷見込み<1 だったもの）
 X1 連番：a<b<c で b=a+1・c=b+1（1-2-3 型）
 X2 直前の当たり目：同じ場・同じ日の1つ前のレースの当たり目（1-2-3着）と車番の並びまで同じ目
 X3 S班を1着：1着の選手が S級S班（class=1・grp=0）
 X123 上のどれか
出し方：3期間それぞれ＋まとめ：点数・当たり・当たり÷見込み・回収率・95%の範囲（レース単位ブートストラップ2,000回）。110%超は上位5本除き・100%未満の四半期の数。
「外した後」と「外された目」の両方を出し、外された目が3期間とも低いかを見る。
使い方: python -I -X utf8 research/fable_exclude.py reports/fable_exclude.md"""
import sys, os, gc, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fable_player import SCR, SUF, NAME, summ, fmt, extra, NL

def report(out):
    D = {}
    for per in SUF:
        d = pd.read_pickle(SCR + "slim2_" + per + ".pkl")
        d = d[d.lo & (d.r2_pt_rank >= 7) & (d.odds <= 20)].reset_index(drop=True); D[per] = d; gc.collect()
    BASES = {"L1 ライン順×3着7位以下×10倍以下": lambda d: d[d.odds <= 10],
             "L5 9車×ライン順×3着7位以下×20倍以下": lambda d: d[d.entries_number >= 9],
             "W23 ライン順×2着5位以下×3着7位以下×5倍超10倍以下": lambda d: d[(d.r1_pt_rank >= 5) & (d.odds > 5) & (d.odds <= 10)]}
    XS = {"X1 連番": lambda d: d.consec, "X2 直前の当たり目と同じ目": lambda d: d.same_combo, "X3 S班を1着": lambda d: d.sb_a,
          "X123 どれか": lambda d: d.consec | d.same_combo | d.sb_a}
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    P("# 探す段階（Fable・2回目）B：買われすぎの目を L1・L5・W23 から外したら上がるか（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円。外す決まりは research/fable_exclude.py の冒頭に、データを見る前に固定した。各セル：点数・当たり・当たり÷見込み・回収率（95%の範囲＝レース単位ブートストラップ）。" + NL)
    def row(nm, fn):
        cells = []; parts = []
        for p, d in D.items():
            g = fn(d); cells.append(fmt(summ(g, boot=500))); parts.append(g)
        g = pd.concat(parts); s = summ(g)
        P(f"| {nm} | " + " | ".join(cells) + f" | {fmt(s)} | {extra(g) if s['n'] and s['roi'] > 1.1 else ''} |")
    for bn, bf in BASES.items():
        P(f"## {bn}" + NL + "| 区分 | " + " | ".join(NAME.values()) + " | まとめ | 追加（まとめ110%超） |" + NL + "|---|---|---|---|---|---|")
        row("もとの形", bf)
        for xn, xf in XS.items():
            row(f"{xn} を外した後", lambda d, bf=bf, xf=xf: (lambda g: g[~xf(g)])(bf(d)))
            row(f"　外された目（{xn}）", lambda d, bf=bf, xf=xf: (lambda g: g[xf(g)])(bf(d)))
        P("")
    # 参考：外す材料そのものが、ライン順×3着7位以下×20倍以下 の全体でどうか（帯ごと）
    P("## 参考：ライン順×3着7位以下×20倍以下 の全体で、外す材料ごとの当たり÷見込み" + NL + "| 区分 | " + " | ".join(NAME.values()) + " | まとめ | |" + NL + "|---|---|---|---|---|---|")
    row("全部（20倍以下）", lambda d: d)
    for xn, xf in XS.items(): row(f"　{xn}", lambda d, xf=xf: d[xf(d)])
    row("S班のいるレース（比べる）", lambda d: d[d.sb_n > 0])
    row("　うち S班を1着にしない目", lambda d: d[(d.sb_n > 0) & ~d.sb_a])
    OUT.close(); print("done")

if __name__ == "__main__":
    report(sys.argv[1])
