"""探す段階（Fable・2回目）A：選手ごとの「軽く見られやすさ」を古い年で測り、新しい年で使う。
見た3期間だけ：y4・2024年（2023/11/8〜2025/1/31）・2025/2〜2026/11/5。y5・y6 は見ない。
元の表＝前回作った scratchpad の slim_*.pkl（research/fable_habits.py build。確定オッズ300倍以下・各100円・pn＝1/倍率をレースの中で合計1）。
選手は out/side_entries_*.pkl の (race_id, number) → player_id でつなぐ。条件は締切前に分かる情報と倍率の帯だけ（g_tf などは使わない）。

筋書き（データを見る前に固定）
 A1 全体の軽く見られやすさ：選手 i について O_i＝3着以内に来た回数（表の当たり目に含まれた回数）、E_i＝その選手を含む目の見込み pn の合計。
    比 θ_i の縮小＝ガンマ・ポアソンの経験的ベイズ：θ_i〜Gamma(k,k)（平均1）、θ̂_i＝(O_i+k)/(E_i+k)。k＝1/τ²、τ²＝選手間の本当のばらつき（積率法：Σ_i E_i·((O_i/E_i−1)²−1/E_i) ÷ Σ_i E_i、下限 0.001）。
    データのない選手は θ̂＝1。
 A2 弱い3番手としての軽く見られやすさ：ライン順（lo＝同じライン3人 先頭→番手→3番手）の目で3番手（c）になっている目だけで、O3_i・E3_i を数え、同じ縮小で θ̂3_i。
確かめ方（学ぶ年 → 確かめる年：y4→2024年、y4→2025/2〜、2024年→2025/2〜、y4＋2024年→2025/2〜）
 持続：学ぶ年の θ̂ と確かめる年の生の比 O/E の順位相関（確かめる年で E≥3 の選手）。θ̂ の5分位ごとの確かめる年の O/E。
 買い方（しきい値は先に固定）：
  A1-a 目の score＝θ̂_a·θ̂_b·θ̂_c ≥1.2 × 10倍以下／30倍以下、A1-b score ≥1.4 × 同じ帯
  A2-a ライン順×10倍以下 × θ̂3_c ≥1.1／≥1.2（得点順位は使わない＝「弱い3番手」を選手で決める）
  A2-b L1（ライン順×r2_pt_rank≥7×10倍以下）の中で θ̂3_c ≥1.1／≥1.2、比べる用に θ̂3_c <1
  A2-c L5（9車×ライン順×r2_pt_rank≥7×20倍以下）の中で θ̂3_c ≥1.1、比べる用に <1
 出し方：点数・当たり・当たり÷見込み・回収率・95%の範囲（レース単位ブートストラップ2,000回）。110%超は上位5本除き・100%未満の四半期の数。
【事後に足したもの（結果を見てから。候補にはしない・参考）】しきい値 1.1〜1.4 では縮小後に該当する選手がいなかった（τ² が小さい）ので、θ̂ の順位（学ぶ年で E≥5 の選手の5分位）で分けた版も出す。
使い方: python -I -X utf8 research/fable_player.py build y4|2024|2025   → scratchpad の slim2_*.pkl（B の fable_exclude.py も使う）
        python -I -X utf8 research/fable_player.py report reports/fable_player.md"""
import sys, os, gc, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SCR = os.environ.get("FABLE_SCR", "C:/Users/take0/AppData/Local/Temp/claude/38c435bfe2a07bd9/cfa8c5a0-353c-4b57-81d8-9e3789cdb845/scratchpad/")
SUF = {"y4": "_y4", "2024": "_y2024full", "2025": "_full"}
NAME = {"y4": "y4", "2024": "2024年", "2025": "2025/2〜"}
KEEP = ["race_id", "date", "odds", "ret", "pn", "hit", "lo", "entries_number", "is_top", "r0_pt_rank", "r2_pt_rank", "a", "b", "c", "has_prev", "same_combo", "same_set", "sb_a", "sb_n"]

def build(per):
    d = pd.read_pickle(SCR + "slim_" + per + ".pkl")[KEEP]
    E = pd.read_pickle(K + f"out/side_entries{SUF[per]}.pkl")
    E = E[E.absent != 1].copy(); E["rp"] = pd.to_numeric(E.race_point, errors="coerce")
    E["ptr"] = E.groupby("race_id").rp.rank(ascending=False, method="min")
    E["pid"] = pd.to_numeric(E.player_id, errors="coerce").fillna(-1).astype(np.int32)
    look = E.set_index(["race_id", "number"])
    for col, nm in (("a", "pa"), ("b", "pb"), ("c", "pc")):
        idx = pd.MultiIndex.from_arrays([d.race_id, d[col].astype(int)])
        d[nm] = look.pid.reindex(idx).fillna(-1).to_numpy().astype(np.int32)
    d["r1_pt_rank"] = look.ptr.reindex(pd.MultiIndex.from_arrays([d.race_id, d.b.astype(int)])).to_numpy().astype(np.float32)
    chk = look.ptr.reindex(pd.MultiIndex.from_arrays([d.race_id, d.c.astype(int)])).to_numpy()
    print(per, "r2_pt_rank の再計算との一致", float(np.nanmean(chk == d.r2_pt_rank.to_numpy())), "選手不明の目", int((d.pa < 0).sum()))
    d["consec"] = (d.b == d.a + 1) & (d.c == d.b + 1)
    d = d.drop(columns=["a", "b", "c"]).reset_index(drop=True)
    d.to_pickle(SCR + "slim2_" + per + ".pkl"); print(per, d.shape)

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
    r = np.sort(g.ret.to_numpy())[::-1]; top5 = (r.sum() - r[:5].sum()) / len(r)
    qtr = g.date.str[:4] + "Q" + ((g.date.str[4:6].astype(int) - 1) // 3 + 1).astype(str)
    qr = g.groupby(qtr).ret.mean(); return f"上位5本除き {top5:.0%}／四半期 {int((qr < 1).sum())}/{len(qr)} が100%未満"

# ---------- 選手ごとの比 ----------
def player_oe(d, mode):
    """mode='all'：選手を含む全部の目。mode='third'：ライン順の目で3番手（c）のときだけ。
    レース×選手ごとに p＝3着以内（または3番手で3着以内）の見込み、o＝実際（0/1）を作り、選手ごとに E＝Σp、O＝Σo、V＝Σp(1−p)（二項のばらつき）"""
    if mode == "all":
        parts = [pd.DataFrame({"race_id": d.race_id.to_numpy(), "pid": d[k].to_numpy(), "pn": d.pn.to_numpy(), "hit": d.hit.to_numpy()}) for k in ("pa", "pb", "pc")]
        x = pd.concat(parts)
    else:
        s = d[d.lo]; x = pd.DataFrame({"race_id": s.race_id.to_numpy(), "pid": s.pc.to_numpy(), "pn": s.pn.to_numpy(), "hit": s.hit.to_numpy()})
    x = x[x.pid >= 0]
    r = x.groupby(["race_id", "pid"], sort=False).agg(p=("pn", "sum"), o=("hit", "max"))
    r["v"] = r.p * (1 - r.p)
    t = r.groupby(level="pid").agg(E=("p", "sum"), O=("o", "sum"), V=("v", "sum"), n=("p", "size")); t = t[t.E > 0]
    return t
def shrink(t):
    """経験的ベイズ。全体の比 μ＝ΣO/ΣE（表にない当たり目の分を吸収）。選手の比 θ_i（μ に対する倍率）〜Gamma(k,k)、
    τ²＝Σ_i E_i·((O_i/E_i/μ−1)²−V_i/(μE_i)²) ÷ Σ_i E_i（積率法・下限 0.001）、k＝1/τ²、θ̂_i＝(O_i/μ+k)/(E_i+k)"""
    E, O, V = t.E.to_numpy(), t.O.to_numpy(), t.V.to_numpy(); mu = O.sum() / E.sum()
    tau2 = max(0.001, float((E * ((O / E / mu - 1) ** 2 - V / (mu * E) ** 2)).sum() / E.sum())); k = 1 / tau2
    th = (O / mu + k) / (E + k); return pd.Series(th, index=t.index), tau2, k

def report(out):
    D = {per: pd.read_pickle(SCR + "slim2_" + per + ".pkl") for per in SUF}
    OUT = open(out, "w", encoding="utf-8")
    def P(*a): print(*a, file=OUT, flush=True)
    P("# 探す段階（Fable・2回目）A：選手ごとの「軽く見られやすさ」を古い年で測り、新しい年で使う（見た3期間だけ。y5・y6 は見ていない）" + NL)
    P("確定オッズ300倍以下・各100円。見込み＝1/倍率をレースの中で合計1。筋書き・しきい値は research/fable_player.py の冒頭に、データを見る前に固定した。縮小＝ガンマ・ポアソンの経験的ベイズ θ̂＝(O+k)/(E+k)。" + NL)
    # 各期間の選手の比
    TH = {}
    P("## 選手ごとの比の広がり（各期間・縮小の強さ）" + NL + "| 期間 | 種類 | 選手数 | τ²（本当のばらつき） | k | θ̂ の5%点〜95%点 | θ̂≥1.2 の選手 | θ̂≤0.8 の選手 |" + NL + "|---|---|---|---|---|---|---|---|")
    for per, d in D.items():
        for mode, lab in (("all", "A1 全体"), ("third", "A2 弱い3番手")):
            t = player_oe(d, mode); th, tau2, k = shrink(t); TH[(per, mode)] = (t, th)
            P(f"| {NAME[per]} | {lab} | {len(t):,} | {tau2:.4f} | {k:.1f} | {th.quantile(.05):.2f}〜{th.quantile(.95):.2f} | {int((th >= 1.2).sum())} | {int((th <= 0.8).sum())} |")
    # y4+2024 まとめて
    for mode in ("all", "third"):
        t = pd.concat([TH[("y4", mode)][0], TH[("2024", mode)][0]]).groupby(level=0).sum(); th, tau2, k = shrink(t); TH[("y4+2024", mode)] = (t, th)
        P(f"| y4＋2024年 | {'A1 全体' if mode == 'all' else 'A2 弱い3番手'} | {len(t):,} | {tau2:.4f} | {k:.1f} | {th.quantile(.05):.2f}〜{th.quantile(.95):.2f} | {int((th >= 1.2).sum())} | {int((th <= 0.8).sum())} |")
    P("")
    PAIRS = [("y4", "2024"), ("y4", "2025"), ("2024", "2025"), ("y4+2024", "2025")]
    # 持続
    P("## 持続：学ぶ年の θ̂ と確かめる年の生の比 O/E（確かめる年で E≥3 の選手）" + NL + "| 学ぶ→確かめ | 種類 | 選手数 | 順位相関（Spearman） | θ̂ 下位20% の O/E | 20〜40% | 40〜60% | 60〜80% | 上位20% |" + NL + "|---|---|---|---|---|---|---|---|---|")
    for tr, te in PAIRS:
        for mode, lab in (("all", "A1 全体"), ("third", "A2 弱い3番手")):
            th = TH[(tr, mode)][1]; t2 = TH[(te, mode)][0]; t2 = t2[t2.E >= 3]
            j = t2.join(th.rename("th"), how="inner")
            if len(j) < 20: P(f"| {tr}→{NAME[te]} | {lab} | {len(j)} | 少 | | | | | |"); continue
            rho = j.th.rank().corr(j.O.div(j.E).rank())
            q = pd.qcut(j.th.rank(method="first"), 5, labels=False)
            cells = [f"{j.O[q == i].sum() / j.E[q == i].sum():.3f}" for i in range(5)]
            P(f"| {tr}→{NAME[te]} | {lab} | {len(j):,} | {rho:.3f} | " + " | ".join(cells) + " |")
    P("")
    # 買い方
    def with_th(d, tr):
        th1 = TH[(tr, "all")][1]; th3 = TH[(tr, "third")][1]
        s = d.copy()
        for k in ("pa", "pb", "pc"): s["t_" + k] = s[k].map(th1).fillna(1.0).astype(np.float32)
        s["score"] = s.t_pa * s.t_pb * s.t_pc; s["t3"] = s.pc.map(th3).fillna(1.0).astype(np.float32)
        # 【事後】しきい値で0点だったので、順位（5分位・学ぶ年で E≥5 の選手だけ、他は NaN→−1）でも分ける
        t1 = TH[(tr, "all")][0]; t3 = TH[(tr, "third")][0]
        q1 = pd.qcut(th1[t1.E >= 5].rank(method="first"), 5, labels=False); q3 = pd.qcut(th3[t3.E >= 5].rank(method="first"), 5, labels=False)
        for k in ("pa", "pb", "pc"): s["q_" + k] = s[k].map(q1).fillna(-1).astype(np.int8)
        s["q3"] = s.pc.map(q3).fillna(-1).astype(np.int8)
        return s
    L1 = lambda s: s.lo & (s.r2_pt_rank >= 7) & (s.odds <= 10)
    L5 = lambda s: (s.entries_number >= 9) & s.lo & (s.r2_pt_rank >= 7) & (s.odds <= 20)
    RULES = {
        "A1-a score≥1.2×10倍以下": lambda s: s[(s.score >= 1.2) & (s.odds <= 10)],
        "A1-a score≥1.2×30倍以下": lambda s: s[(s.score >= 1.2) & (s.odds <= 30)],
        "A1-b score≥1.4×10倍以下": lambda s: s[(s.score >= 1.4) & (s.odds <= 10)],
        "A1-b score≥1.4×30倍以下": lambda s: s[(s.score >= 1.4) & (s.odds <= 30)],
        "（比べる）score<0.9×10倍以下": lambda s: s[(s.score < 0.9) & (s.odds <= 10)],
        "A2-a ライン順×10倍以下×θ̂3≥1.1": lambda s: s[s.lo & (s.odds <= 10) & (s.t3 >= 1.1)],
        "A2-a ライン順×10倍以下×θ̂3≥1.2": lambda s: s[s.lo & (s.odds <= 10) & (s.t3 >= 1.2)],
        "（比べる）ライン順×10倍以下×θ̂3<1": lambda s: s[s.lo & (s.odds <= 10) & (s.t3 < 1)],
        "A2-b L1×θ̂3≥1.1": lambda s: s[L1(s) & (s.t3 >= 1.1)],
        "A2-b L1×θ̂3≥1.2": lambda s: s[L1(s) & (s.t3 >= 1.2)],
        "（比べる）L1×θ̂3<1": lambda s: s[L1(s) & (s.t3 < 1)],
        "（比べる）L1 全部": lambda s: s[L1(s)],
        "A2-c L5×θ̂3≥1.1": lambda s: s[L5(s) & (s.t3 >= 1.1)],
        "（比べる）L5×θ̂3<1": lambda s: s[L5(s) & (s.t3 < 1)],
        "（比べる）L5 全部": lambda s: s[L5(s)],
        "【事後】A1-r 3人とも θ̂ 上位20%×10倍以下": lambda s: s[(s.q_pa >= 4) & (s.q_pb >= 4) & (s.q_pc >= 4) & (s.odds <= 10)],
        "【事後】A1-r 3人とも θ̂ 上位40%×10倍以下": lambda s: s[(s.q_pa >= 3) & (s.q_pb >= 3) & (s.q_pc >= 3) & (s.odds <= 10)],
        "【事後】A1-r 3人とも θ̂ 下位40%×10倍以下（比べる）": lambda s: s[(s.q_pa <= 1) & (s.q_pb <= 1) & (s.q_pc <= 1) & (s.odds <= 10)],
        "【事後】A2-r ライン順×10倍以下×θ̂3 上位20%": lambda s: s[s.lo & (s.odds <= 10) & (s.q3 >= 4)],
        "【事後】A2-r L1×θ̂3 上位20%": lambda s: s[L1(s) & (s.q3 >= 4)],
        "【事後】A2-r L1×θ̂3 下位20%（比べる）": lambda s: s[L1(s) & (s.q3 == 0)],
    }
    P("## 買い方：学ぶ年で θ̂ を決め、確かめる年で見る（点数・当たり・当たり÷見込み・回収率・95%の範囲）" + NL + "学ぶ年の列は合わせ込み（参考）。確かめる年の列が本番の見立て。" + NL)
    for tr in ("y4", "2024", "y4+2024"):
        tests = [p for p in ("y4", "2024", "2025") if p not in tr.split("+")]
        S = {p: with_th(D[p], tr) for p in D}
        P(f"### 学ぶ年＝{tr}" + NL + "| 買い方 | " + " | ".join((NAME[p] + ("（学ぶ）" if p in tr.split("+") else "（確かめ）")) for p in D) + " | 確かめまとめ | 追加（確かめまとめが110%超） |" + NL + "|---|---|---|---|---|---|")
        for nm, fn in RULES.items():
            cells = []; parts = []
            for p in D:
                g = fn(S[p]); s = summ(g, boot=500); cells.append(fmt(s))
                if p in tests: parts.append(g)
            g = pd.concat(parts); s = summ(g)
            P(f"| {nm} | " + " | ".join(cells) + f" | {fmt(s)} | {extra(g) if s['n'] and s['roi'] > 1.1 else ''} |")
        P("")
        del S; gc.collect()
    OUT.close(); print("done")

if __name__ == "__main__":
    if sys.argv[1] == "build": build(sys.argv[2])
    else: report(sys.argv[2])
