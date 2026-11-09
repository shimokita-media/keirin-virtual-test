"""総当たり×統計（ワイド・3連単）。条件の1〜3個の組み合わせを全部、探す期間で検定→BH補正→未使用期間で確認→でたらめな組み合わせと比較。
探す＝2025/2〜2026/8（未使用 25/10/12〜26/1/14 と最終確認用 2026/9〜11 を除く）。最終オッズ。使い方: python brute_stat.py wide|tri
条件名の先頭の $ は「割安さ（最終オッズ）を使う」＝締切前には崩れやすい"""
import sys, itertools, numpy as np, pandas as pd
from scipy.stats import norm
K = "C:/Users/take0/.claude/keirin/"; SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
kind = sys.argv[1] if len(sys.argv) > 1 else "wide"
OOS0, OOS1 = "20251012", "20260114"
if kind == "wide":
    W = pd.read_pickle(SP + "wide_all7.pkl"); W = W[(W.odds >= 1.5) & (W.odds <= 50) & (W["class"] != "L級") & (W.date < "20260901")].reset_index(drop=True)
    W["ev0"] = W.pw * W.odds; W["fav"] = W.groupby("race_id").pw.transform("max"); same = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)
    lo, hi = np.minimum(W.a_pos, W.b_pos), np.maximum(W.a_pos, W.b_pos)
    def q(c, p): return W[c].quantile(p)
    A = {"倍率1.5〜3": W.odds < 3, "倍率3〜6": W.odds.between(3, 6, "left"), "倍率6〜10": W.odds.between(6, 10, "left"), "倍率10〜20": W.odds.between(10, 20, "left"), "倍率20〜50": W.odds >= 20,
         "$割安0.9未満": W.ev0 < 0.9, "$割安0.9以上": W.ev0 >= 0.9, "$割安1.0以上": W.ev0 >= 1.0, "$割安1.2以上": W.ev0 >= 1.2,
         "同ライン": same, "別ライン": ~same, "同ライン先頭-番手": same & (lo == 0) & (hi == 1), "同ライン先頭-3番手": same & (lo == 0) & (hi == 2), "同ライン番手-3番手": same & (lo == 1) & (hi == 2),
         "単騎を含む": (W.a_single == 1) | (W.b_single == 1), "本命が強くない(<0.6)": W.fav < 0.6, "本命が強い(≥0.75)": W.fav >= 0.75,
         "9車": W.entries_number >= 9, "7車以下": W.entries_number <= 7, "G戦": W.grade.astype(str).str.startswith("G"), "S級": W["class"] == "S級", "A級": W["class"] == "A級",
         "初日": W.day_index == 1, "2日目以降": W.day_index >= 2, "決勝・準決": W.race_type.astype(str).str.contains("決勝|準決"), "1〜3R": W.race_no <= 3, "10R以降": W.race_no >= 10,
         "3分戦": W.nlines == 3, "4分戦以上": W.nlines >= 4, "強い逃げ0人": W.n_strong_nige == 0, "強い逃げ1人": W.n_strong_nige == 1, "強い逃げ2人以上": W.n_strong_nige >= 2,
         "印1位を含む": np.minimum(W.a_mk_rank, W.b_mk_rank) == 1, "印3位以内どうし": np.maximum(W.a_mk_rank, W.b_mk_rank) <= 3, "得点5位以下を含む": np.maximum(W.a_pt_rank, W.b_pt_rank) >= 5,
         "逃げを含む": (W.a_style == "逃") | (W.b_style == "逃"), "追込どうし": (W.a_style == "追") & (W.b_style == "追"), "40歳以上を含む": np.maximum(W.a_age, W.b_age) >= 40, "25歳以下を含む": np.minimum(W.a_age, W.b_age) <= 25,
         "番狂わせが多い選手を含む": np.maximum(W.a_h_surp_rate, W.b_h_surp_rate) >= q("a_h_surp_rate", 0.75), "最近好調どうし": np.maximum(W.a_ro_mean, W.b_ro_mean) <= q("a_ro_mean", 0.33),
         "最近不調を含む": np.maximum(W.a_ro_mean, W.b_ro_mean) >= q("a_ro_mean", 0.67), "対戦で上回る": W.a_h2h_edge.fillna(0) > 0, "ナイター": W.hour >= 18, "午前": W.hour < 12, "風が強い": W.wind >= q("wind", 0.75)}
else:
    exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
    IS0 = pd.read_pickle(SP + "tri3_all.pkl"); IS0 = IS0[(IS0.date < "20260901") & ~IS0.date.between(OOS0, OOS1)]
    OS0 = pd.concat([pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh6", "fresh7")]); OS0 = OS0[OS0.date <= OOS1]
    W = prep(pd.concat([IS0, OS0], ignore_index=True)); del IS0, OS0
    W = W[W["class"] != "L級"].reset_index(drop=True)
    s01, s12 = W.s01 == 1, W.s12 == 1; same3 = s01 & s12; order = same3 & (W.r0_pos == 0) & (W.r1_pos == 1) & (W.r2_pos == 2)
    s02 = (W.s02 == 1) if "s02" in W else pd.Series(False, index=W.index)
    def q(c, p): return W[c].quantile(p)
    A = {"倍率〜10": W.odds <= 10, "倍率10〜30": (W.odds > 10) & (W.odds <= 30), "倍率30〜60": (W.odds > 30) & (W.odds <= 60), "倍率60〜120": (W.odds > 60) & (W.odds <= 120), "倍率120〜300": W.odds > 120,
         "$3連複より割安": W.g_tf > 0, "$2車単より割安": W.g_ex > 0, "$3連複より割高": W.g_tf < 0,
         "ライン3人が並び順": order, "ライン3人": same3, "1-2着が同ライン": s01, "2-3着が同ライン": s12, "全部別ライン": ~s01 & ~s12 & ~s02,
         "3着が3番手": W.r2_pos == 2, "1着が先頭": W.r0_pos == 0, "1着が番手": W.r0_pos == 1, "1着が単騎": W.r0_single == 1,
         "9車": W.entries_number >= 9, "7車以下": W.entries_number <= 7, "G戦": W.G == 1, "S級": W.S == 1, "初日": W.day_index == 1, "2日目以降": W.day_index >= 2,
         "1〜3R": W.race_no <= 3, "10R以降": W.race_no >= 10, "3分戦": W.nlines == 3, "4分戦以上": W.nlines >= 4, "強い逃げ0人": W.n_strong_nige == 0, "強い逃げ2人以上": W.n_strong_nige >= 2,
         "1着が印1位": W.r0_mk_rank == 1, "1着が印4位以下": W.r0_mk_rank >= 4, "3着が印5位以下": W.r2_mk_rank >= 5, "1着の予想印が強い": W.r0_prediction_mark >= 3,
         "1着が得点1位": W.r0_pt_rank == 1, "1着が逃げ": W.r0_style == "逃", "1着が追込": W.r0_style == "追", "1着が40歳以上": W.r0_age >= 40, "1着が25歳以下": W.r0_age <= 25,
         "1着が最近好調": W.r0_ro_mean <= q("r0_ro_mean", 0.33), "3着が番狂わせ多い": W.r2_h_surp_rate >= q("r2_h_surp_rate", 0.75), "ナイター": W.hour >= 18, "午前": W.hour < 12, "風が強い": W.wind >= q("wind", 0.75)}
names = list(A); M = np.column_stack([np.asarray(A[k], dtype=bool) for k in names]).astype(np.float32)
oos = W.date.between(OOS0, OOS1).to_numpy(); ret = W.ret.to_numpy(np.float32)
Mi, ri = M[~oos], ret[~oos]; Mo, ro = M[oos], ret[oos]
print(f"{kind}: 探す {(~oos).sum():,}点・{W[~oos].race_id.nunique():,}R 全体{ri.mean():.0%} ／ 未使用 {oos.sum():,}点・{W[oos].race_id.nunique():,}R 全体{ro.mean():.0%} ／ 条件{len(names)}個")


def table(Mx, r):
    out = {}
    Mr, Mr2 = Mx * r[:, None], Mx * (r ** 2)[:, None]
    n1, s1, q1 = Mx.sum(0), Mr.sum(0), Mr2.sum(0)
    for i in range(len(names)): out[(i,)] = (n1[i], s1[i], q1[i])
    N, S, Q = Mx.T @ Mx, Mx.T @ Mr, Mx.T @ Mr2
    for i, j in itertools.combinations(range(len(names)), 2): out[(i, j)] = (N[i, j], S[i, j], Q[i, j])
    for k in range(len(names)):
        c = Mx[:, k].astype(bool); X = Mx[c]; rr = r[c]
        N, S, Q = X.T @ X, X.T @ (X * rr[:, None]), X.T @ (X * (rr ** 2)[:, None])
        for i, j in itertools.combinations(range(k + 1, len(names)), 2): out[(k, i, j)] = (N[i, j], S[i, j], Q[i, j])
    return out


TI = table(Mi, ri)
R = pd.DataFrame([(k, *v) for k, v in TI.items()], columns=["key", "n", "s", "q"]); R = R[R.n >= 300].copy()
R["m"] = R.s / R.n; R["sd"] = np.sqrt(np.maximum(R.q / R.n - R.m ** 2, 1e-9) * R.n / (R.n - 1)); R["t"] = (R.m - 1) / (R.sd / np.sqrt(R.n)); R["p"] = norm.sf(R.t)
R = R.sort_values("p").reset_index(drop=True); kk = np.arange(1, len(R) + 1); R["qv"] = np.minimum.accumulate((R.p * len(R) / kk)[::-1])[::-1]
TO = table(Mo, ro); R["on"] = [TO.get(x, (0, 0, 0))[0] for x in R.key]; R["om"] = [TO.get(x, (0, 0, 0))[1] / max(TO.get(x, (0, 0, 0))[0], 1) for x in R.key]
R["label"] = [" × ".join(names[i] for i in x) for x in R.key]; R["pre"] = ~R.label.str.contains("$", regex=False)
print(f"\n試した組み合わせ（探す期間で300点以上）: {len(R):,}通り")
print(f"- 探す期間で100%超: {(R.m > 1).sum():,}通り ／ t値2以上: {(R.t >= 2).sum():,} ／ t値3以上: {(R.t >= 3).sum():,} ／ BH補正後も有意(q<0.05): {(R.qv < 0.05).sum():,}")
base = R.sample(min(3000, len(R)), random_state=0); base = base[base.on >= 50]
print(f"- でたらめに選んだ組み合わせの未使用の回収率: 平均{base.om.mean():.0%}・100%超は{(base.om > 1).mean():.0%}")


def grp(G, lab):
    G = G[G.on >= 50]
    if not len(G): print(f"- {lab}: 0通り"); return
    print(f"- {lab}: {len(G)}通り → 未使用の回収率 平均{G.om.mean():.0%}・中央{G.om.median():.0%}・100%超は{(G.om > 1).mean():.0%}")


print("\n## 探す期間で強かった組み合わせは未使用でも強いか（未使用50点以上のもの）")
grp(R[R.qv < 0.05], "BH補正後も有意"); grp(R[R.t >= 3], "t値3以上"); grp(R[(R.t >= 2) & (R.t < 3)], "t値2〜3"); grp(R[(R.m > 1) & (R.t < 2)], "100%超だがt値2未満")
grp(R[(R.qv < 0.05) & R.pre], "BH有意×割安を使わない（締切前向き）"); grp(R[(R.qv < 0.05) & ~R.pre], "BH有意×割安を使う")
print("\n## 探す期間のt値トップ25（$＝割安を使う＝最終オッズ頼み）\n| 組み合わせ | 探す | t値 | q値 | 未使用 |\n|---|---|---|---|---|")
for r in R.head(25).itertuples(): print(f"| {r.label} | {r.m:.0%}（{r.n:,}点） | {r.t:+.1f} | {r.qv:.3f} | {r.om:.0%}（{r.on:.0f}点） |")
print("\n## 割安を使わない（締切前でも崩れにくい）t値トップ15\n| 組み合わせ | 探す | t値 | q値 | 未使用 |\n|---|---|---|---|---|")
for r in R[R.pre].head(15).itertuples(): print(f"| {r.label} | {r.m:.0%}（{r.n:,}点） | {r.t:+.1f} | {r.qv:.3f} | {r.om:.0%}（{r.on:.0f}点） |")
S = R[(R.qv < 0.05) & (R.om > 1) & (R.on >= 100)]
print(f"\n## 両方の期間で100%超（探すでBH有意・未使用100点以上）: {len(S)}通り。よく出てくる条件:")
if len(S):
    cnt = pd.Series([names[i] for x in S.key for i in x]).value_counts().head(12); print(" ／ ".join(f"{k}({v})" for k, v in cnt.items()))
R.drop(columns=["key"]).to_pickle(SP + f"brute_stat_{kind}.pkl")
