"""割安度を使わない「形だけ」のワイド。探す=2025/2〜5/29＋2026/2〜8、確認=未使用①②。最終オッズ"""
import itertools, numpy as np, pandas as pd
W = pd.concat([pd.read_pickle("wide_all3.pkl"), pd.read_pickle("C:/Users/take0/.claude/keirin/out/fresh/wide.pkl")]).drop_duplicates(["race_id", "combo"])
W = W[(W["class"] != "L級") & (W.odds <= 50) & (W.date < "20260901")].copy()
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0); W["fav_pw"] = W.groupby("race_id").pw.transform("max")
W["pp"] = W[["a_pos", "b_pos"]].min(1).astype(int).astype(str) + W[["a_pos", "b_pos"]].max(1).astype(int).astype(str)
W["per"] = np.select([W.date.between("20250530", "20250705"), W.date.between("20250706", "20250803")], ["u1", "u2"], "s")
PAIR = {"同ライン先頭-2番手": W.same & (W.pp == "01"), "同ライン2番手-3番手": W.same & (W.pp == "12"), "同ライン先頭-3番手": W.same & (W.pp == "02"),
        "同ラインどれでも": W.same, "別ライン先頭どうし": ~W.same & (W.pp == "00"), "別ライン2番手どうし": ~W.same & (W.pp == "11")}
BAND = {"3倍未満": W.odds < 3, "3〜6倍": W.odds.between(3, 6), "6〜10倍": W.odds.between(6, 10), "10〜20倍": W.odds.between(10, 20), "3〜20倍": W.odds.between(3, 20), "20倍未満": W.odds < 20}
COND = {"なし": True, "9車": W.entries_number >= 9, "7車": W.entries_number == 7, "2日目以降": W.day_index >= 2, "初日": W.day_index == 1,
        "本命が強くない": W.fav_pw < 0.6, "本命が強い": W.fav_pw >= 0.6, "9車×2日目以降": (W.entries_number >= 9) & (W.day_index >= 2),
        "9車×本命が強くない": (W.entries_number >= 9) & (W.fav_pw < 0.6), "本命が強くない×2日目以降": (W.fav_pw < 0.6) & (W.day_index >= 2),
        "1〜3R": W.race_no <= 3, "三分戦以上": W.nlines >= 3, "二分戦": W.nlines == 2, "G戦": W.grade.astype(str).str.startswith("G"), "S級": W["class"] == "S級", "A級": W["class"] == "A級"}
rows = []
for (pn, pm), (bn, bm), (cn, cm) in itertools.product(PAIR.items(), BAND.items(), COND.items()):
    m = pm & bm & cm; g = W[m]
    s = g[g.per == "s"]
    if len(s) < 300: continue
    y25, y26 = s[s.date < "2026"].ret.mean(), s[s.date >= "2026"].ret.mean()
    rows.append((pn, bn, cn, len(s), s.ret.mean(), y25, y26, g[g.per == "u1"].ret.mean(), g[g.per == "u2"].ret.mean(), len(g[g.per != "s"]), (s.ret > 0).mean(), len(s) / s.date.nunique()))
R = pd.DataFrame(rows, columns=["形", "倍率", "条件", "点数", "探す", "25年", "26年", "未①", "未②", "未の点数", "的中", "1日"]).sort_values("探す", ascending=False)
ok = R[(R["25年"] >= 1) & (R["26年"] >= 1)]
print("調べた数", len(R), "探す期間で両年100%超え", len(ok), "その中で未使用①②とも100%超え", len(ok[(ok["未①"] >= 1) & (ok["未②"] >= 1)]))
pd.set_option("display.width", 250)
X = ok.copy()
for c in ("探す", "25年", "26年", "未①", "未②", "的中"): X[c] = (X[c] * 100).round().astype(int).astype(str) + "%"
X["1日"] = X["1日"].round(1)
print(X.head(25).to_string(index=False))
print("\n全体（ワイド全部）", f"{W.ret.mean():.0%}")
