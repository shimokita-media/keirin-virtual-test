"""★事前登録（y9・y10）「ライン順の機械 E1・E2 の確かめ直し」の判定（KNOWLEDGE.md 2026-11-13 の登録どおり。y9・y10 を見る前に作成。結果を見てから変えない）。
対象＝ライン順×確定オッズ15倍以下。係数＝research/lo_model_coef_4yr.json（4年で学んで固定・sha 600c9ce08b487c1e…）。ev＝比×pn×odds。
G1＝E1 と同じ ev≥1.2 一律／G2＝E2 と同じ ev≥1.3 一律。
まとめ＝線を決めるときに見ていない3年（y6・y9・y10）。合格＝3年まとめの片側 p（レース単位ブートストラップ4,000回・種0、回収率≤100% の割合）が BH（m=2、q=0.05）で有意／y9 100%超／y10 100%超。
「安定して120%」と言える＝合格＋3年まとめ120%以上＋3年まとめの95%の範囲の下限100%以上。
使い方: python -I -X utf8 research/prereg_eval_y910_ev.py y6の表 y9の表 y10の表 出力.md（表＝cache.pkl。期間は固定）"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
PER = [("y6", "20201108", "20211107", "20210508"), ("y9", "20171108", "20181107", "20180508"), ("y10", "20161108", "20171107", "20170508")]
fs, outp = sys.argv[1:4], sys.argv[4]
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8")); assert C["cols"] == ["const"] + LO_COLS
src = open(K + "research/prereg_eval_y5_lo.py", encoding="utf-8").read().split("base = d[")[0]
P, NR = [], {}
for (yr, d0, d1, half), fT in zip(PER, fs):
    ns = {"__name__": "x"}; keep = sys.argv; sys.argv = ["x", fT, d0, d1, half, "NUL"]
    try: exec(src, ns)
    finally: sys.argv = keep
    d = ns["d"]; NR[yr] = d.race_id.nunique(); q_ = 1 / d.odds; d["pn"] = q_ / q_.groupby(d.race_id).transform("sum")
    lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy(); del d, ns
    lo["ratio"] = lo_ratio(C["coef"], lo); lo["ev"] = lo.ratio * lo.pn * lo.odds; lo["yr"] = yr; P.append(lo[["race_id", "date", "odds", "ret", "ratio", "ev", "yr"]])
A = pd.concat(P, ignore_index=True); rng = np.random.default_rng(0); R = {}
for k, th in (("G1 期待値1.2以上（E1 と同じ）", 1.2), ("G2 期待値1.3以上（E2 と同じ）", 1.3)):
    g = A[A.ev >= th]; x = g.groupby("race_id").ret.agg(["sum", "size"]); ii = rng.integers(0, len(x), (4000, len(x)))
    bs = x["sum"].to_numpy()[ii].sum(1) / x["size"].to_numpy()[ii].sum(1)
    R[k] = dict(n=len(g), hits=int((g.ret > 0).sum()), roi=g.ret.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1).mean(),
                yrs={y: (g[g.yr == y].ret.mean(), int((g.yr == y).sum())) for y, *_ in PER}, t5=g.drop(g.ret.nlargest(5).index).ret.mean())
names = list(R); pv = np.array([R[k]["p"] for k in names]); order = np.argsort(pv); m = 2
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = ["# 事前登録（y9・y10）「ライン順の機械 E1・E2 の確かめ直し」の判定", "", "レース数 " + "・".join(f"{y} {n:,}R" for y, n in NR.items()) + "。確定オッズ・確定の払戻・各100円", "",
     "合格＝見ていない3年（y6・y9・y10）まとめで BH（m=2）有意・y9 と y10 がそれぞれ100%超。安定して120%＝合格＋3年まとめ120%以上＋下限100%以上", "",
     "| 候補 | 判定 | 3年まとめ | 点数・当たり | 95%の範囲 | p値（BH） | y6 / y9 / y10 | 上位5本除く |", "|---|---|---|---|---|---|---|---|"]
for k in names:
    s = R[k]; ok = bh[k] and s["yrs"]["y9"][0] > 1 and s["yrs"]["y10"][0] > 1; st = ok and s["roi"] >= 1.2 and s["lo"] >= 1.0
    L.append(f"| {k} | {'**安定して120%**' if st else ('**合格**' if ok else '不合格')} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） | "
             + " / ".join(f"{v:.0%}（{n}）" for v, n in s["yrs"].values()) + f" | {s['t5']:.0%} |")
open(outp, "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
