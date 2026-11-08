import numpy as np, pandas as pd
W = pd.read_pickle("wide_all2.pkl"); W = W[(W["class"] != "L級") & (W.odds <= 50)].copy()
W["ev0"] = W.pw * W.odds; W["yr"] = np.where(W.date < "20260101", "25", "26"); W["m"] = W.date.str[2:6]
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)
fav = W.groupby("race_id").pw.transform("max"); W["fav_pw"] = fav
A2 = pd.read_pickle("ana_all2.pkl").drop_duplicates("race_id").set_index("race_id"); W["cup"] = W.race_id.map(A2.cup_id); W["lastday"] = W.day_index == W.groupby("cup").day_index.transform("max")
C = W[W.ev0 >= 1.0].copy()
# 1レースの中の情報
C["mark_both"] = (C.a_prediction_mark > 0) & (C.b_prediction_mark > 0); C["mark_none"] = (C.a_prediction_mark == 0) & (C.b_prediction_mark == 0)
C["young"] = (C.a_age < 30) | (C.b_age < 30); C["old2"] = (C.a_age >= 45) & (C.b_age >= 45)
C["rk_gap"] = (C.a_pt_rank - C.b_pt_rank).abs()
def s(g):
    if len(g) < 200: return None
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    mm = g.groupby("m").ret.mean(); y25, y26 = g[g.yr == "25"].ret.mean(), g[g.yr == "26"].ret.mean()
    return (len(g), round(len(g) / W.date.nunique(), 1), g.ret.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), y25, y26, f"{(mm >= 1).sum()}/{len(mm)}")
A = {
 "二分戦(ライン2つ)": C.nlines == 2, "三分戦": C.nlines == 3, "四分戦以上": C.nlines >= 4,
 "本命が強いレース(一番人気ワイドの見込み60%以上)": C.fav_pw >= 0.6, "混戦(一番人気の見込み40%未満)": C.fav_pw < 0.4,
 "開催の最終日": C.lastday, "初日": C.day_index == 1, "2日目": C.day_index == 2,
 "予想印が2人とも": C.mark_both, "予想印が2人ともなし": C.mark_none,
 "30歳未満を含む": C.young, "2人とも45歳以上": C.old2,
 "得点順位が離れた2人(4つ以上)": C.rk_gap >= 4, "得点順位が近い2人(1つ差)": C.rk_gap == 1,
 "倍率3倍未満": C.odds < 3, "3〜6倍": C.odds.between(3, 6), "6〜10倍": C.odds.between(6, 10), "10〜20倍": C.odds.between(10, 20), "20倍以上": C.odds > 20,
 "割安1.0〜1.1": C.ev0 < 1.1, "割安1.1〜1.25": C.ev0.between(1.1, 1.25), "割安1.25以上": C.ev0 > 1.25,
 "同じライン": C.same, "別ライン": ~C.same,
 "風が強い(6m以上)": C.wind >= 6, "風が弱い(2m未満)": C.wind < 2,
 "決勝・準決": C.race_type.astype(str).str.contains("決勝|準決"), "予選・一般": ~C.race_type.astype(str).str.contains("決勝|準決"),
 "1〜3R×同じライン": (C.race_no <= 3) & C.same, "1〜3R×別ライン": (C.race_no <= 3) & ~C.same,
 "1〜3R×10倍以上": (C.race_no <= 3) & (C.odds >= 10), "1〜3R×10倍未満": (C.race_no <= 3) & (C.odds < 10),
}
rows = [(k,) + v for k, m in A.items() if (v := s(C[m]))]
R = pd.DataFrame(rows, columns=["条件", "点数", "1日", "回収", "下", "上", "25年", "26年", "100%超の月"])
for c in ("回収", "下", "上", "25年", "26年"): R[c] = (R[c] * 100).round().astype(int).astype(str) + "%"
print("全体", f"{C.ret.mean():.0%}"); print(R.to_string(index=False))
print("\n=== 組み合わせ ===")
u20 = C.odds < 20; notfav = C.fav_pw < 0.6; nowind = ~(C.wind >= 6)
B = {"20倍未満": u20, "20倍未満×本命が強くない": u20 & notfav, "20倍未満×本命が強くない×強風でない": u20 & notfav & nowind,
     "20倍未満×同じライン": u20 & C.same, "20倍未満×同じライン×本命が強くない": u20 & C.same & notfav,
     "20倍未満×1〜3R": u20 & (C.race_no <= 3), "20倍未満×1〜3R×同じライン": u20 & (C.race_no <= 3) & C.same,
     "20倍未満×4R以降": u20 & (C.race_no > 3), "20倍未満×1〜3R×本命が強くない": u20 & (C.race_no <= 3) & notfav}
rows = [(k,) + v for k, m in B.items() if (v := s(C[m]))]
R = pd.DataFrame(rows, columns=["条件", "点数", "1日", "回収", "下", "上", "25年", "26年", "100%超の月"])
for c in ("回収", "下", "上", "25年", "26年"): R[c] = (R[c] * 100).round().astype(int).astype(str) + "%"
print(R.to_string(index=False))
