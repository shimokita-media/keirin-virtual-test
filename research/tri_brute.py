"""3連単の買い方の総当たり。探す=2025/2〜5/29＋2026/2〜8、答え合わせ=2025/5/30〜7/5（未使用）。2026/9〜は使わない"""
import itertools, numpy as np, pandas as pd
exec(open("tri2_model.py", encoding="utf-8").read().split("cols = ")[0])
ALL = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(ALL); T = T[T.date < "20260901"].reset_index(drop=True)
g = T.groupby("race_id")
T["fav_p1"] = g.r0_p1.transform("max"); T["pop_rank"] = g.odds.rank(method="first")
# 買い目の形
s01, s12, s02 = T.s01 == 1, T.s12 == 1, T.s02 == 1
p0, p1, p2 = T.r0_pos, T.r1_pos, T.r2_pos
PAT = {
 "ライン順(先頭-2番手-3番手)": s01 & s12 & (p0 == 0) & (p1 == 1) & (p2 == 2),
 "同ライン先頭-2番手→3着は誰でも": s01 & (p0 == 0) & (p1 == 1),
 "同ライン2番手-先頭（差し）→3着誰でも": s01 & (p0 == 1) & (p1 == 0),
 "同ライン1-2着（順不同）→3着別ライン": s01 & ~s02,
 "3人とも同じライン（順不同）": s01 & s12,
 "先頭-2番手→3着に別ラインの先頭": s01 & (p0 == 0) & (p1 == 1) & ~s02 & (p2 == 0),
 "1着が先頭以外の別ライン3人ばらばら": ~s01 & ~s12 & ~s02 & (p0 != 0),
 "3着が同ラインの3番手": (p2 == 2) & s12,
 "1着が先頭・2着が別ラインの先頭": ~s01 & (p0 == 0) & (p1 == 0),
 "全部（形なし）": pd.Series(True, index=T.index),
}
BAND = {"10倍以下": T.odds <= 10, "10〜30倍": T.odds.between(10, 30), "30〜60倍": T.odds.between(30, 60), "60〜100倍": T.odds.between(60, 100), "100〜300倍": T.odds.between(100, 300), "30倍以下": T.odds <= 30, "60倍以下": T.odds <= 60}
fin = T.race_type.astype(str).str.contains("決勝|準決") if "race_type" in T else None
COND = {
 "7車": T.entries_number == 7, "9車": T.entries_number >= 9, "二分戦": T.nlines == 2, "三分戦": T.nlines == 3, "四分戦以上": T.nlines >= 4,
 "本命強い(1着見込み45%以上)": T.fav_p1 >= 0.45, "本命ふつう(30〜45%)": T.fav_p1.between(0.3, 0.45), "混戦(30%未満)": T.fav_p1 < 0.3,
 "1〜3R": T.race_no <= 3, "4〜8R": T.race_no.between(4, 8), "9R以降": T.race_no >= 9,
 "S級": T.S == 1, "A級": T.S == 0, "G戦": T.G == 1, "初日": T.day_index == 1, "2日目以降": T.day_index >= 2,
 "強風5m以上": T.wind >= 5, "弱風3m未満": T.wind < 3, "強い逃げ0人": T.n_strong_nige == 0, "強い逃げ2人以上": T.n_strong_nige >= 2,
 "1着が一番人気の選手": T.r0_mk_rank == 1, "1着が人気2〜3番手": T.r0_mk_rank.between(2, 3), "1着が人気4番手以下": T.r0_mk_rank >= 4,
 "3連複から割安": T.g_tf > 0, "3連複から割安1.2倍": T.g_tf > np.log(1.2), "2車単から割安": T.g_ex > 0, "3連複・2車単どちらも割安": (T.g_tf > 0) & (T.g_ex > 0),
 "朝(〜12時)": T.hour < 12, "夜(18時〜)": T.hour >= 18, "予想印1着◎": T.r0_prediction_mark >= 3,
}
NEW = T.date.between("20250530", "20250705"); SR = ~NEW
Y25 = SR & (T.date < "20260101"); Y26 = SR & (T.date >= "20260101")
ret = T.ret.to_numpy(); hit = ret > 0; mon = T.date.str[:6].to_numpy()
rows = []
for (pn, pm), (bn, bm) in itertools.product(PAT.items(), BAND.items()):
    base = (pm & bm).to_numpy()
    if base[SR.to_numpy()].sum() < 200: continue
    keys = [((), None)] + [((c,), COND[c].to_numpy()) for c in COND] + [((a, b), (COND[a] & COND[b]).to_numpy()) for a, b in itertools.combinations(COND, 2)]
    for ks, cm in keys:
        m = base if cm is None else base & cm
        ms = m & SR.to_numpy(); n = ms.sum()
        if n < 150 or hit[ms].sum() < 20: continue
        r = ret[ms].mean()
        if r < 1.05: continue
        r25 = ret[m & Y25.to_numpy()]; r26 = ret[m & Y26.to_numpy()]
        if len(r25) < 40 or len(r26) < 40 or r25.mean() < 1.0 or r26.mean() < 1.0: continue
        mm = pd.Series(ret[ms]).groupby(mon[ms]).mean(); 
        z = (r - 1) / (ret[ms].std() / np.sqrt(n))
        mn = m & NEW.to_numpy()
        rows.append(dict(形=pn, 倍率=bn, 条件="×".join(ks) or "なし", 点数=n, 当たり=int(hit[ms].sum()), 回収=r, y25=r25.mean(), y26=r26.mean(), 月=f"{(mm>=1).sum()}/{len(mm)}", 強さ=z,
                         未点数=int(mn.sum()), 未当たり=int(hit[mn].sum()), 未回収=ret[mn].mean() if mn.sum() else np.nan, 未レース=T.race_id[mn].nunique(), 日数=T.date[ms].nunique()))
R = pd.DataFrame(rows).sort_values("強さ", ascending=False)
R.to_pickle("tri_brute.pkl")
print("候補数", len(R), " 調べた組み合わせ≒", len(PAT) * len(BAND) * (1 + len(COND) + len(COND) * (len(COND) - 1) // 2))
# 似たもの重複を減らす：同じ「形×倍率」から最大2つ
top = R.groupby(["形", "倍率"]).head(2).head(25)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 40)
for c in ("回収", "y25", "y26", "未回収"): top[c] = (top[c] * 100).round().astype("Int64").astype(str) + "%"
print(top[["形", "倍率", "条件", "点数", "当たり", "回収", "y25", "y26", "月", "強さ", "未点数", "未当たり", "未回収"]].to_string(index=False))
