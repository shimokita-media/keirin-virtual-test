"""機械つき3連単枠を、期間を入れ替えて学習・答え合わせ（4分割）。基準は毎回学習側だけで決める（学習側の一番新しい期間を基準決め用に取り分け）"""
import numpy as np, pandas as pd, lightgbm as lgb
src = open("tri_ml.py", encoding="utf-8").read()
exec(src.split("UN = C.date.between")[0])
C["blk"] = np.select([C.date.between("20250201", "20250531"), C.date.between("20250601", "20250931"), C.date.between("20260201", "20260531")], [0, 1, 2], 3)
NAMES = ["25年2〜5月", "25年6〜9月", "26年2〜5月", "26年6〜8月"]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=500, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1)
def frame(D): return D[D.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6)
def ev(m, D): return 1 / (1 + np.exp(-(m.predict(D[F], raw_score=True) + D.lp))) * D.odds
def topk(B, th): return B[B.ev >= th].sort_values("ev").groupby("race_id").tail(1)
res = []
for b in range(4):
    train_blks = [x for x in range(4) if x != b]; inner = max(train_blks)  # 学習側で一番新しい期間を基準決め用に
    tr = C[C.blk.isin([x for x in train_blks if x != inner])]; iv = C[C.blk == inner]; te = C[C.blk == b].copy()
    m = lgb.train(P, lgb.Dataset(tr[F], tr.y, init_score=tr.lp), 3000, valid_sets=[lgb.Dataset(iv[F], iv.y, init_score=iv.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
    iv = iv.copy(); iv["ev"] = ev(m, iv); Bi = frame(iv)
    cand = [0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1]
    th1 = max([t for t in cand if len(Bi[Bi.ev >= t]) >= 100] or [0.8], key=lambda t: Bi[Bi.ev >= t].ret.mean())
    th2 = max([t for t in cand if len(topk(Bi, t)) >= 80] or [1.0], key=lambda t: topk(Bi, t).ret.mean())
    m2 = lgb.train(P, lgb.Dataset(C[C.blk.isin(train_blks)][F], C[C.blk.isin(train_blks)].y, init_score=C[C.blk.isin(train_blks)].lp), max(m.best_iteration, 20))
    te["ev"] = ev(m2, te); B = frame(te); a = B[B.ev >= th1]; t1 = topk(B, th2)
    one = B.sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(1)
    res.append((NAMES[b], B, a, t1, one, th1, th2))
    f = lambda g: f"{g.ret.mean():.0%}（{len(g)}点・当たり{int((g.ret>0).sum())}）"
    print(f"答え合わせ {NAMES[b]}（学習 {', '.join(NAMES[x] for x in train_blks)}・基準 {th1}/{th2}）: 枠そのまま {f(B)} ｜ 一番の目1点 {f(one)} ｜ 枠×機械 {f(a)} ｜ 機械の上位1点 {f(t1)}")
tot = lambda k: pd.concat([r[k] for r in res])
print(f"\n4回の合計: 枠そのまま {tot(1).ret.mean():.0%} ｜ 一番の目1点 {tot(4).ret.mean():.0%} ｜ 枠×機械 {tot(2).ret.mean():.0%} ｜ 機械の上位1点 {tot(3).ret.mean():.0%}")
for k, nm in ((2, "枠×機械"), (3, "機械の上位1点")):
    g = tot(k); by = g.groupby("race_id").agg(i=("ret", "size"), x=("ret", "sum")); i = np.random.default_rng(0).integers(0, len(by), (2000, len(by))); bs = by.x.to_numpy()[i].sum(1) / by.i.to_numpy()[i].sum(1)
    print(f"  {nm}: 95%の範囲 {np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}、払戻5%減なら {g.ret.mean()*0.95:.0%}")
