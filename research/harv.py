import sys, numpy as np, pandas as pd
mode = sys.argv[1]
Q = pd.read_pickle(f"rider_q_{mode}.pkl").set_index(["race_id", "number"])
T = pd.read_pickle("tri3_all.pkl"); T = T[T.race_id.isin(set(Q.index.get_level_values(0)))].copy()
cb = T.combo.str.split("-", expand=True).astype(int)
def H(col):
    a = Q[col].reindex(list(zip(T.race_id, cb[0]))).to_numpy(); b = Q[col].reindex(list(zip(T.race_id, cb[1]))).to_numpy(); c = Q[col].reindex(list(zip(T.race_id, cb[2]))).to_numpy()
    return a * b / (1 - a) * c / (1 - a - b)
T["adj"] = H("q") / H("pm")
T["ev"] = T.p * T.adj * T.odds
s01 = (T.r0_line_idx == T.r1_line_idx) & (T.r0_line_idx >= 0); s12 = T.r1_line_idx == T.r2_line_idx
T["order"] = s01 & s12 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
def s(g):
    if len(g) < 30: return f"{len(g)}点 当たり{int((g.ret>0).sum())}"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); X, Y = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = X[i].sum(1) / Y[i].sum(1)
    return f"{len(g)}点 1日{len(g)/T.date.nunique():.1f} {g.ret.mean():.0%}[{np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}] 当たり{int((g.ret>0).sum())} 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby(g.date.str[2:6]))
print(mode, T.date.min(), T.date.max())
for hi in (30, 100, 300):
    for th in (1.0, 1.05, 1.1, 1.2):
        print(f" {hi}倍以下 補正後≥{th}", s(T[(T.odds <= hi) & (T.ev >= th)]))
print(" 補正の大きさ≥1.1（市場より機械が10%以上高く見る）×30倍以下", s(T[(T.adj >= 1.1) & (T.odds <= 30)]))
print(" ライン順×30倍以下", s(T[T.order & (T.odds <= 30)]), "| ×補正≥1.05", s(T[T.order & (T.odds <= 30) & (T.adj >= 1.05)]))
print(" 9車×ライン順×30倍以下", s(T[T.order & (T.odds <= 30) & (T.entries_number >= 8)]))
