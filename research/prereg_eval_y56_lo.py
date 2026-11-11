"""★事前登録「5・6年目まとめて（ライン順）」の判定（KNOWLEDGE.md 2026-11-11 21:15 の登録どおり。y5・y6 の結果を見る前に作成。結果を見てから変えない）。
対象：L1・L3・L4・L5（定義は research/prereg_eval_y5_lo.py をそのまま実行して使う＝書き直さない。L2 は確定オッズを使うので入れない）
期間：A＝y5（20211108〜20221107）と B＝y6（20201108〜20211107）を足した2年分
合格（それぞれ）＝2年分まとめた95%の範囲（レース単位ブートストラップ4,000回・種0）の下限100%以上 かつ A・B それぞれ100%超 かつ BH（この4つ、m=4、q=0.05、p＝ブートストラップで100%以下になる割合）
120%の候補＝合格 かつ 2年分まとめて120%以上 かつ A・B とも110%以上
使い方: python -I -X utf8 research/prereg_eval_y56_lo.py 表A.pkl 開始A 終了A 表B.pkl 開始B 終了B 出力.md
（表は build_cache_period.py の出力＝out/y5/cache.pkl・out/y6/cache.pkl。y5 の判定と同時に回さない）"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
a = sys.argv[1:]; outp = a[6]
SRC = open(K + "research/prereg_eval_y5_lo.py", encoding="utf-8").read().split("rng = np.random")[0]
def groups(fT, d0, d1):
    ns = {"__name__": "x"}; keep = sys.argv; sys.argv = ["x", fT, d0, d1, d1, "NUL"]  # 前半・後半は使わない（年ごとに見る）
    try: exec(SRC, ns)
    finally: sys.argv = keep
    G = ns["G"]; out = {}
    for tag in ("L1", "L3", "L4", "L5"):
        ks = [k for k in G if k.startswith(tag + " ")]; assert len(ks) == 1, tag; out[tag] = (ks[0], G[ks[0]])
    nR = ns["d"].race_id.nunique(); ns.clear()  # 大きな表はここで手放す（2年分を同時に持つとメモリが足りない）
    return out, nR
(GA, nRA), (GB, nRB) = groups(*a[0:3]), groups(*a[3:6])
names = ["L1", "L3", "L4", "L5"]; rng = np.random.default_rng(0); R = {}
for k in names:
    gA, gB = GA[k][1], GB[k][1]; g = pd.concat([gA, gB], ignore_index=True)
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1); r = g.ret
    R[k] = dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                rA=gA.ret.mean() if len(gA) else np.nan, nA=len(gA), rB=gB.ret.mean() if len(gB) else np.nan, nB=len(gB), sd=r.std(), t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))))
pv = np.array([R[k]["p"] for k in names]); m = 4; order = np.argsort(pv)
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = [f"# 事前登録「5・6年目まとめて（ライン順）」の判定（A＝{a[1]}〜{a[2]}／B＝{a[4]}〜{a[5]}）", "",
     f"A {nRA:,}R・B {nRB:,}R。最終オッズ・確定の払戻・各100円。合格＝2年分の下限100%以上・A・B それぞれ100%超・BH（m=4）で有意。120%の候補＝合格＋2年分120%以上＋A・B とも110%以上。", "",
     "| 候補 | 判定 | 120%の候補 | 回収率（2年分） | 点数・当たり | 95%の範囲 | A / B | 標準偏差・t | p値（BH） |", "|---|---|---|---|---|---|---|---|---|"]
for k in names:
    s = R[k]; ok = s["lo"] >= 1.0 and s["rA"] > 1 and s["rB"] > 1 and bh[k]; c120 = ok and s["roi"] >= 1.2 and s["rA"] >= 1.1 and s["rB"] >= 1.1
    L.append(f"| {GA[k][0]} | {'**合格**' if ok else '不合格'} | {'**はい**' if c120 else 'いいえ'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['rA']:.0%}（{s['nA']}）/ {s['rB']:.0%}（{s['nB']}） | {s['sd']:.2f}・{s['t']:+.2f} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） |")
open(outp if outp.startswith(("C:", "/")) else K + outp, "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
