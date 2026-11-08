import sqlite3
exec(open("robust.py", encoding="utf-8").read().split("def per(d)")[0])
def sel(T, hi=30, hi6=60, hi8=10, nine_min=9, dmin=2, odds=None):
    o = T.odds if odds is None else odds
    s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
    nine, d2 = T.entries_number >= nine_min, T.day_index >= dmin
    R = [third & (o <= hi) & nine & d2, same3 & (o <= hi) & nine & d2, same3 & (o <= hi) & nine & (T.g_tf > 0),
         order & (o <= hi6) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (o <= hi8) & (T.G == 1) & (T.r0_mk_rank == 1)]
    nr = sum(r.astype(int) for r in R); X = T[nr > 0].assign(nr=nr[nr > 0], o=o[nr > 0])
    return X.sort_values(["race_id", "nr", "o"], ascending=[True, False, True]).groupby("race_id").head(6)
def s(g):
    by = g.groupby("race_id").agg(inv=("ret", "size"), r=("ret", "sum"))
    i = np.random.default_rng(0).integers(0, len(by), (1000, len(by))); bs = by.r.to_numpy()[i].sum(1) / by.inv.to_numpy()[i].sum(1)
    return f"{g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 1日{len(g)/T.date.nunique():.1f}点"
print("## 1) 条件を少しずらす（全期間 384日）")
print("- 本番の条件:", s(sel(T)))
for k, kw in [("30倍→20倍", dict(hi=20)), ("30倍→25倍", dict(hi=25)), ("30倍→35倍", dict(hi=35)), ("30倍→40倍", dict(hi=40)), ("30倍→50倍", dict(hi=50)),
              ("60倍→40倍(④)", dict(hi6=40)), ("60倍→80倍(④)", dict(hi6=80)), ("10倍→7倍(⑤)", dict(hi8=7)), ("10倍→15倍(⑤)", dict(hi8=15)),
              ("9車→8車以上", dict(nine_min=8)), ("2日目以降→3日目以降", dict(dmin=3)), ("2日目以降→全日", dict(dmin=1))]:
    print(f"- {k}:", s(sel(T, **kw)))
print("\n## 2) ニセのライン（同じレースの中で、ラインの割り当てをでたらめに入れ替える）")
rng = np.random.default_rng(7); res = []
num = lambda j: T.combo.str.split("-").str[j].astype(int)
n0, n1, n2 = num(0), num(1), num(2)
for t in range(20):
    # レースごとに番号→(ライン, 位置) をでたらめに並べ替え：各選手の line_idx と pos をレース内でシャッフル
    E = pd.concat([pd.DataFrame({"race_id": T.race_id, "n": n, "li": T[f"r{j}_line_idx"], "pos": T[f"r{j}_pos"]}) for j, n in enumerate((n0, n1, n2))]).drop_duplicates(["race_id", "n"])
    E["k"] = rng.random(len(E)); E = E.sort_values(["race_id", "k"])
    E["li2"] = E.groupby("race_id").li.transform(lambda v: v.sample(frac=1, random_state=int(rng.integers(1e9))).to_numpy())
    E["pos2"] = E.groupby("race_id").pos.transform(lambda v: v.sample(frac=1, random_state=int(rng.integers(1e9))).to_numpy())
    M = E.set_index(["race_id", "n"])
    F = T.copy()
    for j, n in enumerate((n0, n1, n2)):
        key = pd.MultiIndex.from_arrays([F.race_id, n]); F[f"r{j}_line_idx"] = M.li2.reindex(key).to_numpy(); F[f"r{j}_pos"] = M.pos2.reindex(key).to_numpy()
    for a, b in ((0, 1), (1, 2), (0, 2)): F[f"s{a}{b}"] = ((F[f"r{a}_line_idx"] == F[f"r{b}_line_idx"]) & (F[f"r{a}_line_idx"] >= 0)).astype(float)
    g = sel(F); res.append(g.ret.mean())
    if t >= 4: break
print(f"- ニセのラインで同じ買い方（{len(res)}回）: " + " ".join(f"{x:.0%}" for x in res), f" ／ 本物のライン {sel(T).ret.mean():.0%}")
print("\n## 3) 締切前の倍率のブレを入れる（11/6〜8に記録した 締切前÷最終 の倍率の比をランダムに掛けて選び、払戻は最終）")
c = sqlite3.connect("C:/Users/take0/.claude/keirin/out/eval_work/keirin.sqlite")
o = pd.read_sql("SELECT race_id, phase, combo, odds, fetched_at FROM odds WHERE source='winticket' AND bet_type='3連単' AND odds>0 AND phase IN ('B1R','POST')", c)
o = o[o.fetched_at == o.groupby(["race_id", "phase"]).fetched_at.transform("max")]
P = o.pivot_table(index=["race_id", "combo"], columns="phase", values="odds").dropna(); P = P[P.POST <= 80]
ratio = (P.B1R / P.POST).to_numpy(); print(f"  使った比の数 {len(ratio)}、締切前÷最終 の中央 {np.median(ratio):.2f}（10%〜90%: {np.percentile(ratio,10):.2f}〜{np.percentile(ratio,90):.2f}）")
out = []
for t in range(10):
    pre = T.odds * rng.choice(ratio, len(T))
    g = sel(T, odds=pre); out.append((g.ret.mean(), len(g)))
print("- 締切前の倍率で選んだ場合（10回）: " + " ".join(f"{r:.0%}" for r, _ in out), f" 平均{np.mean([r for r,_ in out]):.0%}（1日{np.mean([n for _,n in out])/T.date.nunique():.1f}点）")
