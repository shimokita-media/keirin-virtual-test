"""3連単枠の買い目の中で「外す条件／厚く買う条件」を探す。探す=探した期間、確認=未使用①②③（すべて最終オッズ）"""
import itertools
exec(open("robust.py", encoding="utf-8").read().split("def per(d)")[0])
X = TB.copy()
X["per"] = np.select([X.date.between("20250530", "20250705"), X.date.between("20250706", "20250803"), X.date.between("20250804", "20250822")], ["u", "u", "u"], "s")
X["fav_p1"] = T.groupby("race_id").r0_p1.max().reindex(X.race_id).to_numpy()
X["npick"] = X.groupby("race_id").combo.transform("size")
X["rank_in"] = X.groupby("race_id").odds.rank(method="first")
C = {
 "1点だけのレース": X.npick == 1, "2点以上のレース": X.npick >= 2, "3点以上のレース": X.npick >= 3,
 "そのレースで一番安い目": X.rank_in == 1, "2番目以降の目": X.rank_in >= 2,
 "10倍未満": X.odds < 10, "10〜20倍": X.odds.between(10, 20), "20倍以上": X.odds > 20,
 "複数の法則に当たる目": X.nr >= 2, "法則1つだけの目": X.nr == 1,
 "本命強い(1着見込み45%以上)": X.fav_p1 >= 0.45, "本命ふつう": X.fav_p1.between(0.3, 0.45), "混戦(30%未満)": X.fav_p1 < 0.3,
 "1着がラインの先頭": X.r0_pos == 0, "1着がラインの2番手": X.r0_pos == 1, "1着が別ライン": X.s01 == 0,
 "1着が一番人気の選手": X.r0_mk_rank == 1, "1着が人気2番手以下": X.r0_mk_rank >= 2,
 "3連複から割安": X.g_tf > 0, "3連複から割高": X.g_tf <= 0, "2車単から割安": X.g_ex > 0, "2車単から割高": X.g_ex <= 0,
 "二分戦": X.nlines == 2, "三分戦": X.nlines == 3, "四分戦以上": X.nlines >= 4,
 "強い逃げ0人": X.n_strong_nige == 0, "強い逃げ1人": X.n_strong_nige == 1, "強い逃げ2人以上": X.n_strong_nige >= 2,
 "1着に予想印あり": X.r0_prediction_mark > 0, "1着に予想印なし": X.r0_prediction_mark == 0,
 "1〜6R": X.race_no <= 6, "7〜10R": X.race_no.between(7, 10), "11R以降": X.race_no >= 11,
 "初日": X.day_index == 1, "2日目": X.day_index == 2, "3日目以降": X.day_index >= 3, "G戦": X.G == 1, "F戦": X.G == 0,
 "3人とも得点上位5位以内": (X.r0_pt_rank <= 5) & (X.r1_pt_rank <= 5) & (X.r2_pt_rank <= 5), "得点下位(6位以下)を含む": (X.r0_pt_rank >= 6) | (X.r1_pt_rank >= 6) | (X.r2_pt_rank >= 6),
 "ラインが3人以上で1つだけ": None,
}
C = {k: v for k, v in C.items() if v is not None}
base_s, base_u = X[X.per == "s"].ret.mean(), X[X.per == "u"].ret.mean()
print(f"3連単枠ぜんぶ: 探す {base_s:.0%}（{(X.per=='s').sum()}点） ｜ 未使用まとめ {base_u:.0%}（{(X.per=='u').sum()}点）\n")
rows = []
for k, m in list(C.items()) + [(f"{a}×{b}", C[a] & C[b]) for a, b in itertools.combinations(C, 2)]:
    g = X[m]; s, u = g[g.per == "s"], g[g.per == "u"]
    if len(s) < 300: continue
    y25, y26 = s[s.date < "2026"].ret.mean(), s[s.date >= "2026"].ret.mean()
    rows.append((k, len(s), s.ret.mean(), y25, y26, len(u), u.ret.mean(), int((u.ret > 0).sum())))
R = pd.DataFrame(rows, columns=["条件", "探す点数", "探す", "25年", "26年", "未点数", "未使用", "未当たり"])
good = R[(R["25年"] > base_s + 0.05) & (R["26年"] > base_s + 0.05)].sort_values("探す", ascending=False)
bad = R[(R["25年"] < 1.0) & (R["26年"] < 1.0)].sort_values("探す")
f = lambda D: D.assign(**{c: (D[c] * 100).round().astype(int).astype(str) + "%" for c in ("探す", "25年", "26年", "未使用")}).to_string(index=False)
pd.set_option("display.width", 250)
print("### 厚く買う候補（探す期間で2025・2026とも全体より5ポイント以上高い）上位15"); print(f(good.head(15)))
print("\n### 外す候補（探す期間で2025・2026とも100%未満）"); print(f(bad.head(15)))
