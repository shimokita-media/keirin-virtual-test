"""★事前登録（y6）「ライン順の機械・4年版」の判定（KNOWLEDGE.md 2026-11-12 11:02 の登録どおり。y6 を見る前に作成。結果を見てから変えない）。
対象＝ライン順×確定オッズ15倍以下。係数＝research/lo_model_coef_4yr.json（y4・2024年・2025/2〜・y5 で学んで固定）。M1＝比1.2以上、M2＝比1.3以上。
表の読み込み・pn・当日の流れは prereg_eval_y5_lo.py と同じ（そのファイルの読み込み部分を exec で使う）。
合格（それぞれ）＝95%の範囲（レース単位ブートストラップ4,000回・種0）の下限100%以上／前半・後半とも100%超／BH（m=2、q=0.05）
使い方: python -I -X utf8 research/prereg_eval_y6_lo4.py out/y6/cache.pkl 20201108 20211107 20210508 出力.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
fT, d0, d1, half, outp = sys.argv[1:6]
src = open(K + "research/prereg_eval_y5_lo.py", encoding="utf-8").read().split("base = d[")[0]  # 読み込み・hit・当日の流れまで
ns = {"__name__": "x"}; keep = sys.argv; sys.argv = ["x", fT, d0, d1, half, "NUL"]
try: exec(src, ns)
finally: sys.argv = keep
d = ns["d"]
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
q_ = 1 / d.odds; d["pn"] = q_ / q_.groupby(d.race_id).transform("sum")
lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy()
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8")); assert C["cols"] == ["const"] + LO_COLS
lo["ratio"] = lo_ratio(C["coef"], lo)
G = {"M1 ライン順の機械・4年版（比1.2以上）": lo[lo.ratio >= 1.2], "M2 ライン順の機械・4年版（比1.3以上）": lo[lo.ratio >= 1.3]}
rng = np.random.default_rng(0); R = {}
for k, g in G.items():
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    R[k] = dict(n=len(g), hits=int((g.ret > 0).sum()), roi=g.ret.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1).mean(),
                h1=g[g.date <= half].ret.mean(), h2=g[g.date > half].ret.mean())
names = list(R); pv = np.array([R[k]["p"] for k in names]); order = np.argsort(pv); m = 2
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = [f"# 事前登録（y6）「ライン順の機械・4年版」の判定（{d0}〜{d1}・前半〜{half}）", "", f"{d.race_id.nunique():,}R。ライン順×15倍以下 全部 {len(lo):,}点・{lo.ret.mean():.0%}。合格＝下限100%以上・前半後半とも100%超・BH（m=2）", "",
     "| 候補 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | p値（BH） |", "|---|---|---|---|---|---|---|"]
for k in names:
    s = R[k]; ok = s["lo"] >= 1.0 and s["h1"] > 1 and s["h2"] > 1 and bh[k]
    L.append(f"| {k} | {'**合格**' if ok else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%} / {s['h2']:.0%} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） |")
open(outp if outp.startswith(("C:", "/")) else K + outp, "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
