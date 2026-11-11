"""探す段階（Fable・3回目）の追記：fable_contest.py の結果を見てからの事後の確かめ（候補にはしない・参考）。
筋書き「争いが少ないほど良い」は逆で、「本当のライン数（2人以上のライン）が多いほどライン順×弱い3番手は良い」向きだった。
その向きが車立て・倍率の帯・単騎の数でどう見えるかを3期間それぞれで出す。元の表＝scratchpad の fable_contest_<期間>.pkl。
使い方: python -I -X utf8 research/fable_contest2.py reports/fable_contest2.md"""
import sys, os, numpy as np, pandas as pd
sys.argv_saved = sys.argv; exec(open("C:/Users/take0/.claude/keirin/research/fable_contest.py", encoding="utf-8").read().split("if __name__")[0])

def main(out):
    D = {per: pd.read_pickle(SCR + "fable_contest_" + per + ".pkl") for per in LOF}
    ALL = pd.concat(D.values(), ignore_index=True)
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    def row(lab, f, ex=True):
        cells = [fmt(summ(D[p][f(D[p])])) for p in LOF]; sA = summ(ALL[f(ALL)]); cells.append(fmt(sA))
        e = ("<br>" + extra(ALL[f(ALL)])) if (ex and sA["n"] > 0 and sA["roi"] > 1.1) else ""
        P(f"| {lab} | " + " | ".join(cells) + f" |{e}")
    P("# 追記（事後・参考）：「本当のライン数が多いほど、ライン順×弱い3番手は軽く見られる」の向きを分けて見る（見た3期間だけ）" + NL)
    P("fable_contest.md の結果を見てから作った表なので、候補の選び出しには使わない。表の中身＝点数・当たり本数・当たり÷見込み・**回収率**（95%の範囲）。" + NL)
    H = "| 条件 | y4 | 2024年 | 2025/2〜 | 3期間まとめ |" + NL + "|---|---|---|---|---|"
    w7 = lambda d: d.r2_pt_rank >= 7
    P("## ライン順×3着7位以下 × 本当のライン数 × 車立て（倍率の帯ごと）" + NL + H)
    for band, bf in (("10倍以下", lambda d: d.odds <= 10), ("10倍超20倍以下", lambda d: (d.odds > 10) & (d.odds <= 20)), ("20倍超30倍以下", lambda d: (d.odds > 20) & (d.odds <= 30))):
        for car, cf in (("7車以下", lambda d: d.entries_number <= 7), ("9車", lambda d: d.entries_number >= 9)):
            for nr, nf in (("ライン数<=2", lambda d: d.n_real <= 2), ("ライン数3", lambda d: d.n_real == 3), ("ライン数4以上", lambda d: d.n_real >= 4)):
                row(f"{band}・{car}・{nr}", lambda d, bf=bf, cf=cf, nf=nf: w7(d) & bf(d) & cf(d) & nf(d))
    P(NL + "## 単騎の数（ライン順×3着7位以下×20倍以下）" + NL + H)
    for car, cf in (("7車以下", lambda d: d.entries_number <= 7), ("9車", lambda d: d.entries_number >= 9)):
        for k in (0, 1, 2):
            row(f"{car}・単騎 {k}{'以上' if k == 2 else ''}", lambda d, cf=cf, k=k: w7(d) & (d.odds <= 20) & cf(d) & (d.n_single.clip(upper=2) == k))
    P(NL + "## ライン順全体（3着の得点順位を問わない）でも同じ向きか（30倍以下）" + NL + H)
    for car, cf in (("7車以下", lambda d: d.entries_number <= 7), ("9車", lambda d: d.entries_number >= 9)):
        for nr, nf in (("ライン数<=2", lambda d: d.n_real <= 2), ("ライン数3", lambda d: d.n_real == 3), ("ライン数4以上", lambda d: d.n_real >= 4)):
            row(f"{car}・{nr}", lambda d, cf=cf, nf=nf: (d.odds <= 30) & cf(d) & nf(d), ex=False)
    P(NL + "## 3着の得点順位ごと（ライン数3以上×30倍以下、当たり÷見込み）：弱い3番手だけで効いているか" + NL + "| 3着の得点順位 | ライン数<=2 | ライン数3以上 |" + NL + "|---|---|---|")
    s = ALL[ALL.odds <= 30]
    for lab, rf in (("1〜4位", lambda d: d.r2_pt_rank <= 4), ("5〜6位", lambda d: d.r2_pt_rank.between(5, 6)), ("7位以下", lambda d: d.r2_pt_rank >= 7)):
        a = summ(s[rf(s) & (s.n_real <= 2)], boot=200); b = summ(s[rf(s) & (s.n_real >= 3)], boot=200)
        P(f"| {lab} | {a['n']:,}点・{a['ratio']:.2f}・{a['roi']:.0%} | {b['n']:,}点・{b['ratio']:.2f}・{b['roi']:.0%} |")
    OUT.close(); print("wrote", out)

if __name__ == "__main__": main(sys.argv_saved[1])
