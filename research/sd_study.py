"""標準偏差を使った分析（3連単・一番の目と3連単枠）。探す＝これまでの16か月、確認＝未使用2期間（25/10/12〜26/1/14）。最終オッズ"""
import sys, json, sqlite3, numpy as np, pandas as pd
SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
K = "C:/Users/take0/.claude/keirin/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
def picks(T):
    T = T[T["class"] != "L級"].copy()
    s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
    nine, d2 = T.entries_number >= 9, T.day_index >= 2
    R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
         order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
    T["nr"] = sum(r.astype(int) for r in R)
    X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
    return X.groupby("race_id").head(6)[["race_id", "combo", "odds", "ret", "date", "nr"]], X.groupby("race_id").head(1)[["race_id", "combo", "odds", "ret", "date", "nr"]]
B_in = pd.read_pickle(SP + "card_B.pkl"); top_in = pd.read_pickle(SP + "score_top.pkl")
excl = lambda d: d[~d.date.between("20251012", "20260114")]
B_in, top_in = excl(B_in)[["race_id", "combo", "odds", "ret", "date", "nr"]], excl(top_in)[["race_id", "combo", "odds", "ret", "date", "nr"]]
Bo, To = [], []
for f in ("fresh6", "fresh7"):
    b, t = picks(prep(pd.read_pickle(K + f"out/{f}/tri.pkl"))); Bo.append(b); To.append(t)
B_out, top_out = pd.concat(Bo), pd.concat(To)
B_out = B_out[B_out.date <= "20260114"]; top_out = top_out[top_out.date <= "20260114"]
# 出走表の得点からレースごとの標準偏差
con = sqlite3.connect(f"file:{K}keirin.sqlite?mode=ro", uri=True)
ids = pd.concat([B_in, B_out]).race_id.unique().tolist(); E = []; L = {}
for i in range(0, len(ids), 900):
    q = ",".join("?" * len(ids[i:i+900]))
    E.append(pd.read_sql(f"SELECT race_id, number, race_point rp FROM entries WHERE absent=0 AND race_id IN ({q})", con, params=ids[i:i+900]))
    L.update(dict(con.execute(f"SELECT race_id, line_json FROM races WHERE race_id IN ({q})", ids[i:i+900])))
E = pd.concat(E); E = E[E.rp > 0]
g = E.groupby("race_id").rp; E["z"] = (E.rp - g.transform("mean")) / g.transform("std").replace(0, np.nan)
R = pd.DataFrame({"rp_sd": g.std(), "rp_cv": g.std() / g.mean()})
def line_sd(rid):
    try:
        lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(L.get(rid) or "[]")]
        m = EI.get(rid); v = [np.mean([m[n] for n in l if n in m]) for l in lines if len(l) >= 2 and any(n in m for n in l)]
        return np.std(v, ddof=1) if len(v) >= 2 else np.nan
    except Exception: return np.nan
EI = {r: dict(zip(x.number, x.rp)) for r, x in E.groupby("race_id")}
R["line_sd"] = [line_sd(r) for r in R.index]
Z = {(r, n): z for r, n, z in zip(E.race_id, E.number, E.z)}
def add(D):
    D = D.merge(R, left_on="race_id", right_index=True, how="left")
    zs = [[Z.get((r, int(n)), np.nan) for n in c.split("-")] for r, c in zip(D.race_id, D.combo)]
    D["z_mean"] = [np.nanmean(z) if not all(np.isnan(z)) else np.nan for z in zs]; D["z_min"] = [np.nanmin(z) if not all(np.isnan(z)) else np.nan for z in zs]
    D["z3"] = [z[2] for z in zs]
    D["oz"] = D.groupby("race_id").odds.transform(lambda s: (np.log(s) - np.log(s).mean()) / np.log(s).std() if len(s) > 1 else 0)
    return D
B_in, B_out, top_in, top_out = map(add, (B_in, B_out, top_in, top_out))
def stat(g):
    if len(g) < 5: return f"{len(g)}点"
    m, sd = g.ret.mean(), g.ret.std(); t = (m - 1) / (sd / np.sqrt(len(g)))
    return f"{m:.0%}（{len(g)}点・当たり{int((g.ret>0).sum())}・ばらつき{sd:.1f}・t値{t:+.1f}）"
print("## 1) 標準偏差で見た成績のばらつき（1点100円あたり。t値＝100%からどれだけ確かに離れているか。±2で「偶然ではなさそう」）")
for nm, D in (("一番の目", top_in), ("3連単枠", B_in)):
    print(f"- {nm} 探す期間: {stat(D)}")
for nm, D in (("一番の目", top_out), ("3連単枠", B_out)):
    print(f"- {nm} 未使用2期間: {stat(D)}")
    mo = D.groupby(D.date.str[:6]).ret.mean(); print(f"    月ごと {' '.join(f'{x:.0%}' for x in mo)} → 月の標準偏差 {mo.std():.0%}")
print("\n## 2) 標準偏差の項目ごと（3等分：低・中・高。境目は探す期間で決めて固定）")
FE = {"rp_sd": "レースの得点の標準偏差（大＝実力差がある／小＝混戦）", "rp_cv": "得点のばらつき率", "line_sd": "ラインの強さの標準偏差",
      "z_mean": "買い目3人の偏差値（得点のz平均）", "z_min": "買い目3人で一番低い偏差値", "z3": "3着の人の偏差値", "oz": "倍率の偏差値（レース内で安い↔高い）"}
best = []
for f, lab in FE.items():
    for nm, Di, Do in (("一番の目", top_in, top_out), ("3連単枠", B_in, B_out)):
        q = Di[f].quantile([1/3, 2/3]).to_numpy()
        if q[0] == q[1]: continue
        cut = lambda D: pd.cut(D[f], [-np.inf, q[0], q[1], np.inf], labels=["低", "中", "高"])
        a, b = Di.groupby(cut(Di), observed=True).ret.mean(), Do.groupby(cut(Do), observed=True).ret.mean()
        print(f"- {lab}｜{nm}: 探す " + " ".join(f"{k}{v:.0%}" for k, v in a.items()) + " ／ 未使用 " + " ".join(f"{k}{v:.0%}" for k, v in b.items()) + f"  (境目 {q[0]:.2f}/{q[1]:.2f})")
        for k in a.index:
            best.append((nm, lab, k, a[k], b.get(k, np.nan), Di[cut(Di) == k], Do[cut(Do) == k]))
print("\n## 3) 探す期間で一番よかった区切り → 未使用でそのまま確認")
for nm in ("一番の目", "3連単枠"):
    c = sorted([x for x in best if x[0] == nm], key=lambda x: -x[3])[:3]
    for _, lab, k, a, b, gi, go in c: print(f"- {nm}×{lab}={k}: 探す {stat(gi)} → 未使用 {stat(go)}")
print("\n## 4) 標準偏差を使った賭け金（ケリー基準の考え方：賭け割合 ≒ (回収率−1)÷ばらつき²）")
for nm, D in (("一番の目", top_in), ("3連単枠", B_in)):
    m, sd = D.ret.mean(), D.ret.std(); f = (m - 1) / sd**2
    print(f"- {nm}: 回収率{m:.0%}・ばらつき{sd:.1f} → 資金の{f*100:.2f}%／点が上限の目安（10万円なら{f*1e5:,.0f}円）。安全のため半分（ハーフ）推奨")
