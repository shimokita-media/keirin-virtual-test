"""3連単の総当たり（第2弾）：締切前でも崩れにくい条件だけ。探す=2025/2〜5/29＋2026/2〜8、答え合わせ=2025/5/30〜9/11"""
import itertools, sqlite3, numpy as np, pandas as pd
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
K = "C:/Users/take0/.claude/keirin/out/"
A = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl")] + [pd.read_pickle(K + f + "/tri.pkl") for f in ("fresh", "fresh2", "fresh3")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(A); T = T[(T["class"] != "L級") & (T.date <= "20260831") & ~((T.date >= "20250912") & (T.date < "20260101"))].copy()
T["UN"] = T.date.between("20250530", "20250911")
s01, s12, s02 = T.s01 == 1, T.s12 == 1, T.s02 == 1; p0, p1, p2 = T.r0_pos, T.r1_pos, T.r2_pos
sg = lambda j: T[f"r{j}_single"].astype(bool) if f"r{j}_single" in T else (T[f"r{j}_ls"] == 1)
# 目の形
PAT = {}
same3 = s01 & s12
for a, b, c in itertools.permutations((0, 1, 2)):
    nm = {0: "先", 1: "番", 2: "3"}; PAT[f"3人同ライン {nm[a]}→{nm[b]}→{nm[c]}"] = same3 & (p0 == a) & (p1 == b) & (p2 == c)
PAT["1-2着が同ライン先→番・3着は別ラインの先頭"] = s01 & ~s02 & (p0 == 0) & (p1 == 1) & (p2 == 0)
PAT["1-2着が同ライン先→番・3着は別ラインの番手以降"] = s01 & ~s02 & (p0 == 0) & (p1 == 1) & (p2 >= 1) & ~sg(2)
PAT["1-2着が同ライン先→番・3着は単騎"] = s01 & ~s02 & (p0 == 0) & (p1 == 1) & sg(2)
PAT["1-2着が同ライン番→先・3着は別ライン"] = s01 & ~s02 & (p0 == 1) & (p1 == 0)
PAT["1着が別ライン・2-3着が同ライン先→番"] = ~s01 & s12 & (p1 == 0) & (p2 == 1)
PAT["1着が別ライン・2-3着が同ライン番→3"] = ~s01 & s12 & (p1 == 1) & (p2 == 2)
PAT["1着と3着が同ライン（2着が割り込み）"] = ~s01 & s02 & ~s12
PAT["3人ばらばら・1着が先頭"] = ~s01 & ~s12 & ~s02 & (p0 == 0) & ~sg(0)
PAT["3人ばらばら・1着が番手以降"] = ~s01 & ~s12 & ~s02 & (p0 >= 1)
PAT["1着が単騎"] = sg(0)
BAND = {"〜10倍": T.odds <= 10, "10〜20倍": T.odds.between(10, 20), "20〜30倍": T.odds.between(20, 30), "30〜60倍": T.odds.between(30, 60), "60〜100倍": T.odds.between(60, 100), "100〜300倍": T.odds.between(100, 300)}
fav = T.groupby("race_id").r0_p1.transform("max")
COND = {"7車": T.entries_number == 7, "8車": T.entries_number == 8, "9車": T.entries_number >= 9, "初日": T.day_index == 1, "2日目": T.day_index == 2, "3日目以降": T.day_index >= 3,
        "S級": T.S == 1, "A級": T.S == 0, "G戦": T.G == 1, "F戦": T.G == 0, "二分戦": T.nlines == 2, "三分戦": T.nlines == 3, "四分戦以上": T.nlines >= 4,
        "本命強い(1着45%〜)": fav >= 0.45, "本命ふつう": fav.between(0.3, 0.45), "混戦(〜30%)": fav < 0.3, "1〜4R": T.race_no <= 4, "5〜8R": T.race_no.between(5, 8), "9R〜": T.race_no >= 9,
        "1着が一番人気の選手": T.r0_mk_rank == 1, "1着が人気2〜3番手": T.r0_mk_rank.between(2, 3), "1着が人気4番手以下": T.r0_mk_rank >= 4,
        "強い逃げ0人": T.n_strong_nige == 0, "強い逃げ1人": T.n_strong_nige == 1, "強い逃げ2人〜": T.n_strong_nige >= 2,
        "1着のラインが3人以上": T.r0_ls >= 3, "1着のラインが2人": T.r0_ls == 2, "1着に予想印": T.r0_prediction_mark > 0, "3着に予想印なし": T.r2_prediction_mark == 0}
SR = ~T.UN; ret = T.ret.to_numpy(); hit = ret > 0; y25 = (T.date < "2026").to_numpy(); sr = SR.to_numpy(); un = T.UN.to_numpy()
mon = T.date.str[:6].to_numpy()
print(f"探す {T[SR].date.nunique()}日・{T[SR].race_id.nunique()}R ／ 未使用 {T[T.UN].date.nunique()}日 ／ 3連単全部 探す{T[SR].ret.mean():.0%}・未使用{T[T.UN].ret.mean():.0%}\n")
print("## 1) 傾向マップ（探す期間の回収率、点数）：目の形 × 倍率")
hdr = list(BAND); print("| 目の形 | " + " | ".join(hdr) + " | 全体 |"); print("|---|" + "---|" * (len(hdr) + 1))
for pn, pm in PAT.items():
    cells = []
    for bn, bm in BAND.items():
        m = (pm & bm).to_numpy() & sr; cells.append(f"{ret[m].mean():.0%}({m.sum()})" if m.sum() >= 100 else "−")
    m = pm.to_numpy() & sr & (T.odds <= 300).to_numpy(); print(f"| {pn} | " + " | ".join(cells) + f" | {ret[m].mean():.0%} |")
print("\n## 2) 傾向マップ：目の形（30倍以下） × レースの条件")
keyc = ["7車", "9車", "初日", "2日目", "3日目以降", "S級", "A級", "G戦", "二分戦", "三分戦", "混戦(〜30%)", "本命強い(1着45%〜)"]
print("| 目の形（30倍以下） | " + " | ".join(keyc) + " |"); print("|---|" + "---|" * len(keyc))
for pn, pm in PAT.items():
    cells = []
    for cn in keyc:
        m = (pm & (T.odds <= 30) & COND[cn]).to_numpy() & sr; cells.append(f"{ret[m].mean():.0%}" if m.sum() >= 150 else "−")
    print(f"| {pn} | " + " | ".join(cells) + " |")
print("\n## 3) 総当たり（目の形×倍率×条件1〜2つ）")
rows = []
for (pn, pm), (bn, bm) in itertools.product(PAT.items(), BAND.items()):
    base = (pm & bm).to_numpy()
    if (base & sr).sum() < 300: continue
    keys = [("なし", None)] + [(c, COND[c].to_numpy()) for c in COND] + [(f"{a}×{b}", (COND[a] & COND[b]).to_numpy()) for a, b in itertools.combinations(COND, 2)]
    for kn, cm in keys:
        m = base if cm is None else base & cm; ms = m & sr; n = ms.sum()
        if n < 250 or hit[ms].sum() < 25: continue
        r = ret[ms].mean()
        if r < 1.08: continue
        a25, a26 = ret[ms & y25], ret[ms & ~y25]
        if len(a25) < 60 or len(a26) < 60 or a25.mean() < 1.0 or a26.mean() < 1.0: continue
        mm = pd.Series(ret[ms]).groupby(mon[ms]).mean()
        mu = m & un
        rows.append((pn, bn, kn, n, r, a25.mean(), a26.mean(), f"{(mm>=1).sum()}/{len(mm)}", (r - 1) / (ret[ms].std() / np.sqrt(n)), int(mu.sum()), ret[mu].mean() if mu.sum() else np.nan, int(hit[mu].sum())))
R = pd.DataFrame(rows, columns=["形", "倍率", "条件", "点数", "探す", "25年", "26年", "月", "強さ", "未点数", "未使用", "未当たり"])
ntest = len(PAT) * len(BAND) * (1 + len(COND) + len(COND) * (len(COND) - 1) // 2)
print(f"調べた数 約{ntest:,}、探す期間で条件を満たした {len(R)}")
top = R.sort_values("強さ", ascending=False).groupby(["形", "倍率"]).head(2).head(30)
print(f"上位30のうち未使用で100%超え {(top['未使用'] >= 1).sum()}/30")
f = lambda D: D.assign(**{c: (D[c] * 100).round().astype("Int64").astype(str) + "%" for c in ("探す", "25年", "26年", "未使用")}).to_string(index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 30)
print(f(top[["形", "倍率", "条件", "点数", "探す", "25年", "26年", "月", "未点数", "未使用", "未当たり"]]))
R.to_pickle("tri_brute2.pkl")
