"""統計的な目線で3連単を解析（最終オッズ・300倍以下）。探す＝2025/2〜2026/8（9〜11月は最終確認用で除外）、確認＝未使用2期間 25/10/12〜26/1/14
A 市場の確率の歪み（較正）  B 形×倍率帯（多重検定の補正BH＋経験ベイズの縮小）  C 統計モデル（ロジスティック回帰）で期待値選択"""
import numpy as np, pandas as pd
from scipy.stats import norm
K = "C:/Users/take0/.claude/keirin/"; SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
COLS = None
IS = pd.read_pickle(SP + "tri3_all.pkl"); IS = IS[(IS.date < "20260901") & ~IS.date.between("20251012", "20260114")]
OS = pd.concat([pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh6", "fresh7")]); OS = OS[OS.date <= "20260114"]
IS, OS = prep(IS), prep(OS)
IS, OS = IS[IS["class"] != "L級"].copy(), OS[OS["class"] != "L級"].copy()
rng = np.random.default_rng(0)
def ci(g):
    if len(g) < 30: return ""
    by = g.groupby("race_id").ret.agg(["sum", "size"]); i = rng.integers(0, len(by), (800, len(by)))
    b = by["sum"].to_numpy()[i].sum(1) / by["size"].to_numpy()[i].sum(1); return f"［{np.percentile(b,2.5):.0%}〜{np.percentile(b,97.5):.0%}］"
def shape(D):
    s01, s12, s02 = D.s01 == 1, D.s12 == 1, D.get("s02", pd.Series(0, index=D.index)) == 1
    same3 = s01 & s12; order = same3 & (D.r0_pos == 0) & (D.r1_pos == 1) & (D.r2_pos == 2)
    return np.select([order, same3, s01, s12 | s02], ["①ライン3人が並び順", "②ライン3人（順不同）", "③1-2着が同ライン", "④2-3着か1-3着が同ライン"], "⑤全部別ライン")
for D in (IS, OS):
    D["shape"] = shape(D); D["band"] = pd.cut(D.odds, [0, 10, 30, 60, 120, 300], labels=["〜10倍", "10〜30", "30〜60", "60〜120", "120〜300"]); D["hit"] = (D.ret > 0).astype(int)
print(f"探す {IS.date.nunique()}日・{IS.race_id.nunique()}R・{len(IS):,}点 全体{IS.ret.mean():.0%} ／ 未使用 {OS.date.nunique()}日・{OS.race_id.nunique()}R 全体{OS.ret.mean():.0%}\n")
print("## A 倍率帯ごとの回収率（市場の歪み＝本命・大穴バイアス）\n| 倍率帯 | 探す 回収率 | 実際÷市場の当たり | 未使用 回収率 |\n|---|---|---|---|")
for b in IS.band.cat.categories:
    a, o = IS[IS.band == b], OS[OS.band == b]
    print(f"| {b} | {a.ret.mean():.0%}{ci(a)} | {a.hit.sum()/a.p.sum():.2f} | {o.ret.mean():.0%}{ci(o)} |")
print("\n## B 形×倍率帯（探す期間でt検定→BHで多重補正→全体平均へ縮小。未使用でそのまま確認）")
grand = IS.ret.mean(); rows = []
for (s, b), g in IS.groupby(["shape", "band"], observed=True):
    if len(g) < 200: continue
    by = g.groupby("race_id").ret.sum(); m, sd, n = g.ret.mean(), g.ret.std(), len(g)
    se = sd / np.sqrt(n); t = (m - 1) / se; p = norm.sf(t)
    tau2 = max(np.var([0]), 0.0)
    rows.append([s, b, n, m, se, t, p])
R = pd.DataFrame(rows, columns=["shape", "band", "n", "m", "se", "t", "p"])
tau2 = max(R.m.var() - (R.se ** 2).mean(), 1e-4)      # 経験ベイズ：セル間の本当のばらつき
R["shrunk"] = grand + (R.m - grand) * tau2 / (tau2 + R.se ** 2)
R = R.sort_values("p"); k = np.arange(1, len(R) + 1); R["q"] = np.minimum.accumulate((R.p * len(R) / k)[::-1])[::-1]
print("| 形 | 倍率帯 | 点数 | 探す | 縮小後 | t値 | q値(BH) | 未使用 |\n|---|---|---|---|---|---|---|---|")
for r in R.sort_values("shrunk", ascending=False).itertuples():
    o = OS[(OS["shape"] == r.shape) & (OS.band == r.band)]
    print(f"| {r.shape} | {r.band} | {r.n:,} | {r.m:.0%} | {r.shrunk:.0%} | {r.t:+.1f} | {r.q:.2f} | {o.ret.mean():.0%}（{len(o)}点・当たり{o.hit.sum()}） |")
sel = R[R.shrunk > 1.0]
mk = lambda D: D.set_index(["shape", "band"]).index.isin(list(zip(sel["shape"], sel.band)))
g1, g2 = IS[mk(IS)], OS[mk(OS)]
print(f"\n→ 縮小後100%超のセルをまとめ買い：探す {g1.ret.mean():.0%}{ci(g1)} {len(g1)/IS.date.nunique():.1f}点/日 → 未使用 **{g2.ret.mean():.0%}**{ci(g2)}（{len(g2)}点・当たり{g2.hit.sum()}）")
print("\n## C 統計モデル（ロジスティック回帰：当たり ~ 市場の確率 + 形 + 他の賭け式との差）")
def X(D):
    lp = np.log(D.p.clip(1e-5) / (1 - D.p.clip(1e-5)))
    return np.column_stack([lp, (D["shape"] == "①ライン3人が並び順"), (D["shape"] == "②ライン3人（順不同）"), (D["shape"] == "③1-2着が同ライン"), (D["shape"] == "④2-3着か1-3着が同ライン"),
                            D.g_tf.clip(-1, 1), D.g_ex.clip(-1, 1), (D.entries_number >= 9), (D.day_index >= 2), (D.G == 1)]).astype(float)
names = ["市場の確率(logit)", "形①", "形②", "形③", "形④", "3連複との差", "2車単との差", "9車", "2日目以降", "G戦"]
def fit(y, Xm):
    Xm = np.column_stack([np.ones(len(Xm)), Xm]); b = np.zeros(Xm.shape[1]); b[1] = 1
    for _ in range(40):
        p = 1 / (1 + np.exp(-Xm @ b)); H = Xm.T @ (Xm * (p * (1 - p))[:, None]) + np.eye(len(b)) * 1e-6; b += np.linalg.solve(H, Xm.T @ (y - p))
    return b, np.sqrt(np.diag(np.linalg.inv(H)))
b, se = fit(IS.hit.to_numpy(float), X(IS))
print("| 項目 | 係数 | t値 |\n|---|---|---|")
for nm, bb, ss in zip(["切片"] + names, b, se): print(f"| {nm} | {bb:+.3f} | {bb/ss:+.1f} |")
print("（市場の確率の係数が1より大きい＝本命が過小評価／小さい＝大穴が過小評価）")
for nm, D in (("探す", IS), ("未使用", OS)):
    D["pm"] = 1 / (1 + np.exp(-(np.column_stack([np.ones(len(D)), X(D)]) @ b))); D["ev"] = D.pm * D.odds
    print(f"- {nm}: " + " ／ ".join(f"期待値≥{t}: {D[D.ev>=t].ret.mean():.0%}{ci(D[D.ev>=t])}（{len(D[D.ev>=t])/D.date.nunique():.1f}点/日）" for t in (1.0, 1.1, 1.2, 1.3)))
    top = D[D.ev >= 1.1].sort_values("ev", ascending=False).groupby("race_id").head(1)
    print(f"    1レース1点（期待値≥1.1で一番高い目）: {top.ret.mean():.0%}{ci(top)}（{len(top)}点・当たり{top.hit.sum()}）")
IS[["race_id", "combo", "date", "ret", "pm", "ev", "shape", "band"]].to_pickle(SP + "stat_IS.pkl"); OS[["race_id", "combo", "date", "ret", "pm", "ev", "shape", "band"]].to_pickle(SP + "stat_OS.pkl")
