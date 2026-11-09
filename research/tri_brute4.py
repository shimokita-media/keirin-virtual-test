"""3連単の総当たり第4弾（2026-11-09 午後）：これまで試していない切り口（レースの種類・2着/3着の位置と印・人気順位・脚質）を中心に、条件1〜3個の全組み合わせ。
割安さ（他の券種との差＝最終オッズでしか分からない）は使わない＝締切前でも崩れにくい条件だけ。
探す＝2025/2〜2026/8（③25/10/12〜26/1/14 を除く）。確認＝③と⑥26/9〜11/5 の2つの未使用期間。最終オッズ・L級除く。2024年のデータは使わない（事前登録用に温存）。
使い方: python research/tri_brute4.py 出力.md"""
import sys, itertools, sqlite3, numpy as np, pandas as pd
from scipy.stats import norm
K = "C:/Users/take0/.claude/keirin/"
SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
A0 = pd.concat([pd.read_pickle(SP + "tri3_all.pkl"), pd.read_pickle(SP + "tri3_new.pkl")] +
               [pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh", "fresh2", "fresh3", "fresh4", "fresh5", "fresh6", "fresh7")])
A0 = A0[A0.date >= "20250201"].drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
W = prep(A0); del A0
W = W[(W["class"] != "L級") & (W.odds <= 300)].reset_index(drop=True)
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True)
rt = pd.Series(dict(con.execute("SELECT race_id, race_type FROM races").fetchall()))
W["rt"] = W.race_id.map(rt).fillna("").astype(str)
s01, s12 = W.s01 == 1, W.s12 == 1; same3 = s01 & s12; order = same3 & (W.r0_pos == 0) & (W.r1_pos == 1) & (W.r2_pos == 2)
s02 = (W.s02 == 1) if "s02" in W else pd.Series(False, index=W.index)
pop = W.popularity
A = {
    "倍率〜10": W.odds <= 10, "倍率10〜30": W.odds.between(10, 30, "right"), "倍率30〜60": W.odds.between(30, 60, "right"), "倍率60〜120": W.odds.between(60, 120, "right"), "倍率120〜300": W.odds > 120,
    "人気1〜3番": pop <= 3, "人気4〜10番": pop.between(4, 10), "人気11〜30番": pop.between(11, 30), "人気31番以下": pop >= 31,
    "ライン3人が並び順": order, "ライン3人": same3, "1-2着が同ライン": s01, "2-3着が同ライン": s12, "全部別ライン": ~s01 & ~s12 & ~s02,
    "準決勝": W.rt.str.contains("準決勝"), "決勝": W.rt.str.contains("決勝") & ~W.rt.str.contains("準"), "特選・選抜": W.rt.str.contains("特選|選抜"),
    "予選": W.rt.str.contains("予選"), "一般戦": W.rt.str.contains("一般"), "チャレンジ": W.rt.str.contains("チャレンジ"),
    "1着が先頭": W.r0_pos == 0, "1着が番手": W.r0_pos == 1, "1着が単騎": W.r0_single == 1, "1着が印1位": W.r0_mk_rank == 1, "1着が印4位以下": W.r0_mk_rank >= 4,
    "2着が先頭": W.r1_pos == 0, "2着が番手": W.r1_pos == 1, "2着が3番手": W.r1_pos == 2, "2着が単騎": W.r1_single == 1, "2着が印1位": W.r1_mk_rank == 1, "2着が印4位以下": W.r1_mk_rank >= 4,
    "3着が先頭": W.r2_pos == 0, "3着が番手": W.r2_pos == 1, "3着が3番手": W.r2_pos == 2, "3着が単騎": W.r2_single == 1, "3着が印1位": W.r2_mk_rank == 1, "3着が印5位以下": W.r2_mk_rank >= 5,
    "1着が逃げ": W.r0_style == "逃", "2着が逃げ": W.r1_style == "逃", "3着が逃げ": W.r2_style == "逃", "3人とも追込": (W.r0_style == "追") & (W.r1_style == "追") & (W.r2_style == "追"),
    "2着が40歳以上": W.r1_age >= 40, "3着が40歳以上": W.r2_age >= 40, "3着が得点5位以下": W.r2_pt_rank >= 5,
    "9車": W.entries_number >= 9, "7車以下": W.entries_number <= 7, "G戦": W.G == 1, "初日": W.day_index == 1, "2日目以降": W.day_index >= 2, "10R以降": W.race_no >= 10,
    "3分戦": W.nlines == 3, "4分戦以上": W.nlines >= 4, "強い逃げ0人": W.n_strong_nige == 0, "強い逃げ2人以上": W.n_strong_nige >= 2,
}
names = list(A); M = np.column_stack([np.asarray(A[k], dtype=bool) for k in names]).astype(np.float32)
d = W.date
h1 = d.between("20251012", "20260114").to_numpy(); h2 = (d >= "20260901").to_numpy(); ins = ~h1 & ~h2
ret = W.ret.to_numpy(np.float32)
P("# 3連単の総当たり第4弾（未試行の切り口・割安さは使わない）\n")
P(f"探す {ins.sum():,}点・{W[ins].race_id.nunique():,}R 全体{ret[ins].mean():.1%} ／ ③ {h1.sum():,}点 全体{ret[h1].mean():.1%} ／ ⑥ {h2.sum():,}点 全体{ret[h2].mean():.1%} ／ 条件{len(names)}個\n")

def table(Mx, r):
    out = {}
    Mr, Mr2 = Mx * r[:, None], Mx * (r ** 2)[:, None]
    n1, s1, q1 = Mx.sum(0), Mr.sum(0), Mr2.sum(0)
    for i in range(len(names)): out[(i,)] = (n1[i], s1[i], q1[i])
    N, S, Q = Mx.T @ Mx, Mx.T @ Mr, Mx.T @ Mr2
    for i, j in itertools.combinations(range(len(names)), 2): out[(i, j)] = (N[i, j], S[i, j], Q[i, j])
    for k in range(len(names)):
        c = Mx[:, k].astype(bool); X = Mx[c]; rr = r[c]
        if not len(rr): continue
        N, S, Q = X.T @ X, X.T @ (X * rr[:, None]), X.T @ (X * (rr ** 2)[:, None])
        for i, j in itertools.combinations(range(k + 1, len(names)), 2): out[(k, i, j)] = (N[i, j], S[i, j], Q[i, j])
    return out

TI = table(M[ins], ret[ins])
R = pd.DataFrame([(k, *v) for k, v in TI.items()], columns=["key", "n", "s", "q"]); R = R[R.n >= 300].copy()
R["m"] = R.s / R.n; R["sd"] = np.sqrt(np.maximum(R.q / R.n - R.m ** 2, 1e-9) * R.n / (R.n - 1)); R["t"] = (R.m - 1) / (R.sd / np.sqrt(R.n)); R["p"] = norm.sf(R.t)
R = R.sort_values("p").reset_index(drop=True); kk = np.arange(1, len(R) + 1); R["qv"] = np.minimum.accumulate((R.p * len(R) / kk)[::-1])[::-1]
for tag, msk in (("1", h1), ("2", h2)):
    TO = table(M[msk], ret[msk])
    R["n" + tag] = [TO.get(x, (0, 0, 0))[0] for x in R.key]; R["m" + tag] = [TO.get(x, (0, 0, 0))[1] / max(TO.get(x, (0, 0, 0))[0], 1) for x in R.key]
R["label"] = [" × ".join(names[i] for i in x) for x in R.key]
P(f"試した組み合わせ（探す期間で300点以上）: {len(R):,}通り")
P(f"- 探す期間で100%超: {(R.m > 1).sum():,} ／ t値2以上: {(R.t >= 2).sum():,} ／ t値3以上: {(R.t >= 3).sum():,} ／ BH補正後も有意(q<0.05): {(R.qv < 0.05).sum():,}")
ok = (R.n1 >= 50) & (R.n2 >= 50)
base = R[ok].sample(min(3000, ok.sum()), random_state=0)
P(f"- でたらめな組み合わせ：③平均{base.m1.mean():.0%}（100%超{(base.m1 > 1).mean():.0%}）・⑥平均{base.m2.mean():.0%}（100%超{(base.m2 > 1).mean():.0%}）・両方100%超{((base.m1 > 1) & (base.m2 > 1)).mean():.0%}")
for lab, G in (("t値3以上", R[ok & (R.t >= 3)]), ("t値2.5以上", R[ok & (R.t >= 2.5)]), ("BH有意", R[ok & (R.qv < 0.05)])):
    if len(G): P(f"- {lab} {len(G)}通り → ③平均{G.m1.mean():.0%}（100%超{(G.m1 > 1).mean():.0%}）・⑥平均{G.m2.mean():.0%}（100%超{(G.m2 > 1).mean():.0%}）・両方100%超{((G.m1 > 1) & (G.m2 > 1)).mean():.0%}")
    else: P(f"- {lab}: 0通り")
P("\n## 探す期間のt値上位40（③・⑥は確認用）\n")
P("| 条件 | 探す 点数 | 探す 回収率 | t値 | BH q | ③ 点数 | ③ | ⑥ 点数 | ⑥ |")
P("|---|---|---|---|---|---|---|---|---|")
for _, r in R.head(40).iterrows():
    P(f"| {r.label} | {int(r.n)} | {r.m:.0%} | {r.t:.1f} | {r.qv:.2f} | {int(r.n1)} | {r.m1:.0%} | {int(r.n2)} | {r.m2:.0%} |")
S = R[ok & (R.t >= 2.5) & (R.m1 > 1) & (R.m2 > 1)].copy()
P(f"\n## 候補：探すでt値2.5以上 かつ ③・⑥とも100%超（各50点以上） {len(S)}通り\n")
P("| 条件 | 探す 点数 | 探す | t値 | ③ 点数 | ③ | ⑥ 点数 | ⑥ |")
P("|---|---|---|---|---|---|---|---|")
for _, r in S.head(40).iterrows():
    P(f"| {r.label} | {int(r.n)} | {r.m:.0%} | {r.t:.1f} | {int(r.n1)} | {r.m1:.0%} | {int(r.n2)} | {r.m2:.0%} |")
R.drop(columns=["key"]).to_pickle(K + "out/tri_brute4.pkl")
