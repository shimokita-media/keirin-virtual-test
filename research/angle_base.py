"""学習サイクル用の共通データ（3連単・2025/2〜2026/11・最終オッズ・L級除く・300倍以下）。
初回だけ大きな元データから作って out/angle_base.pkl に保存し、2回目からはそれを読む。
使い方: exec(open(".../research/angle_base.py", encoding="utf-8").read()) → T（全組）, B（3連単枠）, top（一番の目）, per(d)（期間ラベル）, summ(g)（回収率の要約）"""
import os, sqlite3, numpy as np, pandas as pd
from scipy.stats import norm
K = "C:/Users/take0/.claude/keirin/"
SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
CACHE = K + "out/angle_base.pkl"
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
if os.path.exists(CACHE):
    T = pd.read_pickle(CACHE)
else:
    A0 = pd.concat([pd.read_pickle(SP + "tri3_all.pkl"), pd.read_pickle(SP + "tri3_new.pkl")] +
                   [pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh", "fresh2", "fresh3", "fresh4", "fresh5", "fresh6", "fresh7")])
    A0 = A0[A0.date >= "20250201"].drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
    T = prep(A0); del A0
    T = T[(T["class"] != "L級") & (T.odds <= 300)].reset_index(drop=True)
    con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True)
    R = pd.read_sql("SELECT race_id, race_type, venue, venue_id, cup_id, close_at, start_at FROM races", con).set_index("race_id")
    for c in R.columns: T[c] = T.race_id.map(R[c])
    s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12
    order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2); nine, d2 = T.entries_number >= 9, T.day_index >= 2
    RL = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
          order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
    T["nr"] = sum(r.astype(int) for r in RL)
    X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
    T["in_B"] = False; T.loc[X.groupby("race_id").head(6).index, "in_B"] = True
    T["is_top"] = False; T.loc[X.groupby("race_id").head(1).index, "is_top"] = True
    T.to_pickle(CACHE)
B, top = T[T.in_B], T[T.is_top]
def per(d):
    return np.select([d.between("20251012", "20260114"), d >= "20260901"], ["③", "⑥"], "探す")
rng = np.random.default_rng(0)
def summ(g):
    """{'探す': (点数, 回収率, t値), '③': (...), '⑥': (...)}"""
    out = {}
    p = per(g.date)
    for k in ("探す", "③", "⑥"):
        x = g.ret[p == k].to_numpy()
        if len(x) < 2: out[k] = (len(x), np.nan, np.nan); continue
        out[k] = (len(x), x.mean(), (x.mean() - 1) / (x.std(ddof=1) / np.sqrt(len(x))))
    return out
def fmt(s):
    return " / ".join(f"{s[k][1]:.0%}({s[k][0]})" if s[k][0] else "−" for k in ("探す", "③", "⑥"))
