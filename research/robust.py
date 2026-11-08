"""3つ目の未使用期間（2025/8/4〜8/22）での確認＋偏りチェック（競輪場・クラス・月）。最終オッズ"""
import numpy as np, pandas as pd
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
K = "C:/Users/take0/.claude/keirin/out/"
A = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl"), pd.read_pickle(K + "fresh/tri.pkl"), pd.read_pickle(K + "fresh2/tri.pkl")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(A); T = T[(T["class"] != "L級") & (T.date < "20260901")].copy()
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
TB = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6).copy()
W = pd.concat([pd.read_pickle("wide_all3.pkl"), pd.read_pickle(K + "fresh/wide.pkl"), pd.read_pickle(K + "fresh2/wide.pkl")]).drop_duplicates(["race_id", "combo"])
W = W[(W["class"] != "L級") & (W.odds <= 50) & (W.date < "20260901")].copy()
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0); W["ev0"] = W.pw * W.odds; W["fav_pw"] = W.groupby("race_id").pw.transform("max")
lo, hi = W[["a_pos", "b_pos"]].min(1), W[["a_pos", "b_pos"]].max(1)
G = W.grade.astype(str).str.startswith("G")
WS = W[W.same & (lo == 0) & (hi == 2) & W.odds.between(3, 20) & ((W.entries_number >= 9) | G)].copy()
WA = W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (W.fav_pw < 0.6)].copy()
def per(d): return np.select([d.between("20250530", "20250705"), d.between("20250706", "20250803"), d.between("20250804", "20250822")], ["未①", "未②", "★未③"], "探す")
def s(g):
    if not len(g): return "0点"
    by = g.groupby("race_id").agg(inv=("ret", "size"), r=("ret", "sum"))
    i = np.random.default_rng(0).integers(0, len(by), (1000, len(by))); bs = by.r.to_numpy()[i].sum(1) / by.inv.to_numpy()[i].sum(1)
    return f"{g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］({len(g)}点・当たり{int((g.ret>0).sum())})"
nd = T.groupby(per(T.date)).date.nunique().to_dict(); print("日数", nd, " 3連単全部(未③)", f"{T[per(T.date)=='★未③'].ret.mean():.0%}", " ワイド全部(未③)", f"{W[per(W.date)=='★未③'].ret.mean():.0%}")
for lab, X in (("🎰3連単枠", TB), ("🎯形のワイド(同ライン先頭-3番手×3〜20倍×9車かG戦)", WS), ("ワイドA(割安×同ライン×本命が強くない)", WA)):
    X = X.assign(per=per(X.date))
    print(f"\n## {lab}"); print("  期間別: " + " ｜ ".join(f"{p} {s(X[X.per == p])}" for p in ("探す", "未①", "未②", "★未③")))
    print("  通し: " + s(X))
    vc = X.groupby("venue_c" if "venue_c" in X else "venue").ret.agg(["mean", "size", "sum"]) if False else None
    ven = X.race_id.str[:2]  # race_id の先頭2桁＝競輪場
    v = X.groupby(ven).agg(n=("ret", "size"), r=("ret", "mean"), tot=("ret", "sum")).sort_values("tot", ascending=False)
    share = (v.tot - v.n).clip(lower=0) / max((X.ret.sum() - len(X)), 1)
    print(f"  競輪場の数 {len(v)}、100%超えの場 {(v.r >= 1).sum()}/{len(v)}、もうけ上位3場のもうけ割合 {share.head(3).sum():.0%}")
    top3 = v.index[:3]; print(f"  もうけ上位3場を除くと {s(X[~ven.isin(top3)])}")
    if "class" in X: print("  クラス別: " + " ｜ ".join(f"{k} {s(g)}" for k, g in X.groupby("class")))
    print("  9車/それ以外: " + " ｜ ".join(f"{'9車' if k else '9車以外'} {s(g)}" for k, g in X.groupby(X.entries_number >= 9)))
    print("  開催日: " + " ｜ ".join(f"{k}日目 {s(g)}" for k, g in X.groupby(X.day_index.clip(upper=4))))
    mm = X.groupby(X.date.str[:6]).ret.mean(); print(f"  100%超えの月 {(mm>=1).sum()}/{len(mm)}  " + " ".join(f"{m[2:4]}/{m[4:]}:{v:.0%}" for m, v in mm.items()))
# 組み合わせ
days = sorted(set(T.date) & set(W.date))
for lab, X in (("3連単枠＋形のワイド", pd.concat([TB.assign(k="t"), WS.assign(k="w")])), ("3連単枠＋ワイドA", pd.concat([TB.assign(k="t"), WA.assign(k="w")]))):
    X = X[X.date.isin(days)]
    by = X.groupby(["date", "race_id"]).ret.agg(["size", "sum"]).reset_index().sort_values("date")
    net = np.cumsum(by["sum"] - by["size"]).to_numpy() * 100; dd = (np.maximum.accumulate(np.r_[0, net]) - np.r_[0, net]).max()
    dl = X.groupby("date").ret.max() > 0
    print(f"\n{lab}: {s(X)} 1日{len(X)/len(days):.1f}点 収支{int(net[-1]):+,}円 最大のへこみ−{int(dd):,}円 当たりのある日{dl.mean():.0%}")
