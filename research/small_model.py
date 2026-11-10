"""時期をまたいで続く割安さだけを材料にした小さな機械（ロジスティック回帰・市場の見込みを出発点＝offset）。
**2024年（2023/11/08〜2025/1/31、使い終わった年）だけで学び**、2025/2〜2026/11（探す・③・⑥）で確かめる。新しい特徴量は探さない：材料は KNOWLEDGE.md で時期をまたいで同じ向きと分かっているものだけ。
特徴量（各3連単の目について）：
  order   ライン順（同じライン3人で先頭→番手→3番手）           1.06〜1.09（2024・2025〜）
  same3   同じライン3人                                           〜1.0（order の比較用）
  s01     1-2着が同じライン
  a_top   1着が得点1位                                            割高（0.96）
  a_rest  1着が休み明け（中21日以上）                             割高
  c_new   3着が新人（tgap≦1）                                    割高
  fav3    一番人気3倍以下のレース                                  割高
  flow    当日・同じ場で、それより前のレースの「1着が先頭」の割合 × 1着が先頭（r0_pos=0）   1.10
  lp      log(見込み) と lp² （人気と穴の偏りの補正）
見込み p＝確定オッズをレースの中で合計1にそろえたもの（300倍以下の中で）。y＝当たり。
使い方: python -I -X utf8 research/small_model.py reports/small_model.md"""
import sys, duckdb, numpy as np, pandas as pd
class Fit:  # 市場の見込みを出発点（offset）にしたロジスティック回帰をニュートン法で（statsmodels が無いので自前）
    def __init__(self, y, X, off, names):
        X = np.column_stack([np.ones(len(X)), X]).astype(float); b = np.zeros(X.shape[1])
        for _ in range(30):
            mu = 1 / (1 + np.exp(-(off + X @ b))); w = mu * (1 - mu)
            H = (X * w[:, None]).T @ X; g = X.T @ (y - mu); step = np.linalg.solve(H, g); b += step
            if np.abs(step).max() < 1e-8: break
        se = np.sqrt(np.diag(np.linalg.inv(H)))
        self.params = pd.Series(b, index=["const"] + names); self.bse = pd.Series(se, index=self.params.index); self.tvalues = self.params / self.bse
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
def build(T, E, R):
    T = T.copy()
    q = 1 / T.odds; T["p"] = q / q.groupby(T.race_id).transform("sum"); T["y"] = (T.ret > 0).astype(float)
    T["fav"] = T.groupby("race_id").odds.transform("min")
    E = E.merge(R[["race_id", "date", "cup_id"]], on="race_id", how="left")
    ab = set(E[E.absent == 1].race_id)
    EA = E[E.absent != 1].copy()
    EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
    EA["term"] = pd.to_numeric(EA.term, errors="coerce"); EA["ym"] = EA.date.str[:6]; EA["tgap"] = EA.groupby("ym").term.transform("max") - EA.term
    EA["d"] = pd.to_datetime(EA.date)
    cup = EA.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
    cup["rest"] = (cup["min"] - cup.groupby("player_id")["max"].shift()).dt.days - 1
    EA = EA.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
    look = EA.set_index(["race_id", "number"])
    cb = T.combo.str.split("-", expand=True).astype(int)
    a = look.reindex(list(zip(T.race_id, cb[0]))); c = look.reindex(list(zip(T.race_id, cb[2])))
    T["a_top"] = (a.ptr.to_numpy() == 1).astype(float); T["a_rest"] = (a.rest.to_numpy() >= 21).astype(float); T["c_new"] = (c.tgap.to_numpy() <= 1).astype(float)
    T["same3"] = ((T.s01 == 1) & (T.s12 == 1)).astype(float)
    T["order"] = ((T.same3 == 1) & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)).astype(float)
    T["s01f"] = (T.s01 == 1).astype(float); T["fav3"] = (T.fav <= 3).astype(float)
    # 当日の流れ：同じ場・同じ日の、それより前のレースで「1着が先頭」だった割合（当たり目の r0_pos から）
    RR = R.set_index("race_id")
    W = T[T.y > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
    D = T.drop_duplicates("race_id")[["race_id", "date"]].copy(); D["venue"] = D.race_id.map(RR.venue); D["race_no"] = D.race_id.map(RR.race_no)
    D = D.sort_values(["venue", "date", "race_no"]); D["lw"] = D.race_id.map(W).fillna(0)
    g = D.groupby(["venue", "date"]); D["n_prev"] = g.cumcount(); D["lead_prev"] = (g.lw.cumsum() - D.lw) / D.n_prev.replace(0, np.nan)
    T["flow"] = (T.race_id.map(D.set_index("race_id").lead_prev).fillna(0.5) - 0.5) * (T.r0_pos == 0)
    T["absent_race"] = T.race_id.isin(ab).astype(float)
    T["lp"] = np.log(T.p); T["lp2"] = T.lp ** 2
    return T
X_COLS = ["order", "same3", "s01f", "a_top", "a_rest", "c_new", "fav3", "flow", "absent_race", "lp", "lp2"]
cols = ["race_id", "combo", "date", "odds", "ret", "s01", "s12", "r0_pos", "r1_pos", "r2_pos", "is_top"]
A = pd.read_pickle(K + "out/y2024full/cache.pkl")[cols]
TR = build(A, pd.read_pickle(K + "out/side_entries_y2024full.pkl"), pd.read_pickle(K + "out/side_races_y2024full.pkl").drop_duplicates("race_id")); del A
B = duckdb.sql(f"SELECT {', '.join(cols)} FROM '{K}out/tri_base.parquet'").df()
TE = build(B, pd.read_pickle(K + "out/side_entries_full.pkl"), pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")); del B
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
m = Fit(TR.y.to_numpy(), TR[X_COLS].to_numpy(float), lg(TR.p).to_numpy(), X_COLS)
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
P("# 時期をまたいで続く割安さだけの小さな機械（2024年だけで学び、2025〜26年で確かめる）" + NL)
P(f"学習：2024年 {TR.race_id.nunique():,}R・{len(TR):,}点（300倍以下）。確かめ：2025/2〜2026/11 {TE.race_id.nunique():,}R。市場の見込みを出発点（offset）にしたロジスティック回帰。" + NL)
P("## 係数（2024年で学習）" + NL + "| 特徴量 | 係数 | 標準誤差 | z | 倍率（exp） |" + NL + "|---|---|---|---|---|")
for k in m.params.index:
    P(f"| {k} | {m.params[k]:+.3f} | {m.bse[k]:.3f} | {m.tvalues[k]:+.1f} | {np.exp(m.params[k]):.2f} |")
def per(d): return np.select([d.between("20251012", "20260114"), d >= "20260901"], ["③", "⑥"], "探す")
TE["per"] = per(TE.date); TR["per"] = "2024年（学習）"
for D_ in (TR, TE):
    eta = lg(D_.p).to_numpy() + np.column_stack([np.ones(len(D_)), D_[X_COLS].to_numpy(float)]) @ m.params.to_numpy()
    D_["pm"] = 1 / (1 + np.exp(-eta)); D_["pm"] = D_.pm / D_.groupby("race_id").pm.transform("sum")  # レースの中で合計1にそろえる
    D_["ev"] = D_.pm * D_.odds
rng = np.random.default_rng(0)
def st(g):
    if len(g) < 2: return "−"
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (1000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    return f"{g.ret.mean():.0%}（{len(g):,}点・{int((g.ret > 0).sum())}本・{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）"
P(NL + "## 当てる力：レースごとの対数損失の改善（＋なら市場より良い）" + NL + "| 期間 | 平均の改善 | t | レース |" + NL + "|---|---|---|---|")
for D_ in (TR, TE):
    for pn, g in D_.groupby("per"):
        h = g[g.y > 0]; d = (np.log(h.pm) - np.log(h.p)).to_numpy()
        P(f"| {pn} | {d.mean():+.4f} | {d.mean() / (d.std() / np.sqrt(len(d))):+.2f} | {len(d):,} |")
P(NL + "## 期待値（機械の見込み×確定オッズ）で選んだ回収率" + NL)
for cap in (40, 300):
    P(f"### {cap}倍以下" + NL + "| 選び方 | 2024年（学習） | 探す | ③ | ⑥ |" + NL + "|---|---|---|---|---|")
    for th in (1.0, 1.1, 1.2, 1.3):
        cells = [st(TR[(TR.odds <= cap) & (TR.ev >= th)])] + [st(TE[(TE.odds <= cap) & (TE.ev >= th) & (TE.per == p)]) for p in ("探す", "③", "⑥")]
        P(f"| 期待値≥{th} | " + " | ".join(cells) + " |")
    P("")
print("done")
