import sys, numpy as np, pandas as pd
sys.argv += []; exec(open("pre_eval.py", encoding="utf-8").read().split("fin = prep")[0])
W = prep(pd.read_pickle(sys.argv[1])); W["m"] = W.date.str[2:6]; W["ev0"] = W.pw * W.odds
def s(g):
    if len(g) < 30: return f"{len(g)}点"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); A, B = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (2000, len(gg))); bs = A[i].sum(1) / B[i].sum(1)
    return f"{len(g)}点 1日{len(g)/W.date.nunique():.1f} {g.ret.mean():.0%}[{np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}] 月:" + " ".join(f"{m}:{x.ret.mean():.0%}" for m, x in g.groupby("m"))
print(W.date.min(), W.date.max(), W.date.nunique(), "日")
for th in (1.0, 1.1, 1.15, 1.2, 1.3): print(f"機械≥{th}", s(W[W.ev >= th]), "| 3連単だけ", s(W[W.ev0 >= th]))
