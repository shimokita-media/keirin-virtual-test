"""★事前登録（y6）「ライン順の機械・期待値の線と配分」の判定（KNOWLEDGE.md 2026-11-12 の登録どおり。y6 を見る前に作成。結果を見てから変えない）。
対象＝ライン順×確定オッズ15倍以下。係数＝research/lo_model_coef_4yr.json（4年で学んで固定）。ev＝比×pn×odds（機械の見込み×倍率）。
E1＝ev≥1.2 一律／E2＝ev≥1.3 一律／E3＝比≥1.2 で賭け金∝(比−1)²。回収率＝Σ(賭け金×払戻倍率)/Σ賭け金。
1年で E1 は130〜250点しかなく y6 だけでは下限100%に届かない（検出力不足）ので、5年まとめ（out/lo_stake_heldout.pkl の4年の1年抜き＋y6）で判定する。
合格（それぞれ）＝5年まとめの95%の範囲（レース単位ブートストラップ4,000回・種0、片側 p＝回収率≤100% の割合）の下限100%以上／y6 が100%超／5年の各年が100%超／BH（m=3、q=0.05）。
120%候補＝合格＋5年まとめ120%以上＋y6 が110%以上。y6 の前半（〜20210508・暦日）・後半は参考に出す。
回収率はどれも Σ(賭け金×払戻倍率)/Σ賭け金（一律は1点1、E3 は (比−1)² をそのまま、丸めなし）。「安定して120%」は本番の1分前の記録でも確かめてから。
使い方: python -I -X utf8 research/prereg_eval_y6_ev.py out/y6/cache.pkl 20201108 20211107 20210508 出力.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
fT, d0, d1, half, outp = sys.argv[1:6]
src = open(K + "research/prereg_eval_y5_lo.py", encoding="utf-8").read().split("base = d[")[0]  # 読み込み・hit・当日の流れまで
ns = {"__name__": "x"}; keep = sys.argv; sys.argv = ["x", fT, d0, d1, half, "NUL"]
try: exec(src, ns)
finally: sys.argv = keep
d = ns["d"]; nR = d.race_id.nunique()
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
q_ = 1 / d.odds; d["pn"] = q_ / q_.groupby(d.race_id).transform("sum")
lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy()
del d, ns
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8")); assert C["cols"] == ["const"] + LO_COLS
lo["ratio"] = lo_ratio(C["coef"], lo); lo["ev"] = lo.ratio * lo.pn * lo.odds; lo["yr"] = "y6"
H = pd.read_pickle(K + "out/lo_stake_heldout.pkl")
def sets(x):
    a = x[x.ev >= 1.2]; b = x[x.ev >= 1.3]; c = x[x.ratio >= 1.2]
    return {"E1 期待値1.2以上（一律）": (a, pd.Series(1.0, index=a.index)), "E2 期待値1.3以上（一律）": (b, pd.Series(1.0, index=b.index)),
            "E3 比1.2以上・賭け金∝(比−1)²": (c, (c.ratio - 1) ** 2)}
def r_(g, w): return float((w * g.ret).sum() / w.sum()) if w.sum() > 0 else float("nan")
rng = np.random.default_rng(0); R = {}
S6, SH = sets(lo), sets(H)
for k, (g, w) in S6.items():
    hm = g.date <= half
    gh, wh = SH[k]; gp = pd.concat([gh, g]); wp = pd.concat([wh, w])
    x = pd.DataFrame({"r": gp.race_id.to_numpy(), "a": (wp * gp.ret).to_numpy(), "w": wp.to_numpy()}).groupby("r").sum()
    a, s = x.a.to_numpy(), x.w.to_numpy(); ii = rng.integers(0, len(x), (4000, len(x))); bs = a[ii].sum(1) / s[ii].sum(1)
    yrs = {y: r_(gp[gp.yr == y], wp[gp.yr == y]) for y in ["y4", "2024年", "2025/2〜", "y5", "y6"]}
    R[k] = dict(n=len(g), hits=int((g.ret > 0).sum()), roi=r_(g, w), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1).mean(),
                h1=r_(g[hm], w[hm]), h2=r_(g[~hm], w[~hm]), pool=r_(gp, wp), npool=len(gp), yrs=yrs)
names = list(R); pv = np.array([R[k]["p"] for k in names]); order = np.argsort(pv); m = 3
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = [f"# 事前登録（y6）「ライン順の機械・期待値の線と配分」の判定（{d0}〜{d1}・前半〜{half}）", "",
     f"y6 {nR:,}R。ライン順×15倍以下 全部 {len(lo):,}点・{lo.ret.mean():.0%}。合格＝5年まとめの下限100%以上・y6 100%超・各年100%超・BH（m=3）。120%候補＝合格＋5年まとめ≥120%＋y6≥110%", "",
     "| 候補 | 判定 | y6 回収率 | y6 点数・当たり | y6 前半 / 後半（参考） | 5年まとめ | 5年の95%の範囲 | p値（BH） | 年別 y4/2024/2025〜/y5/y6 |", "|---|---|---|---|---|---|---|---|---|"]
for k in names:
    s = R[k]; ok = s["lo"] >= 1.0 and s["roi"] > 1 and all(v > 1 for v in s["yrs"].values()) and bh[k]
    c120 = ok and s["pool"] >= 1.2 and s["roi"] >= 1.1
    L.append(f"| {k} | {'**120%候補**' if c120 else ('**合格**' if ok else '不合格')} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['h1']:.0%} / {s['h2']:.0%} | {s['npool']:,}点・**{s['pool']:.0%}** | {s['lo']:.0%}〜{s['hi']:.0%} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） | "
             + " / ".join(f"{v:.0%}" for v in s["yrs"].values()) + " |")
open(outp if outp.startswith(("C:", "/")) else K + outp, "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
