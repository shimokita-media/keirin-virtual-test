import sys, numpy as np, pandas as pd, lightgbm as lgb
m = lgb.Booster(model_file="wide_model.txt"); feats = m.feature_name()
cats = {"a_style", "b_style", "grade", "class", "pp", "venue"}
def prep(W):
    W = W[(W.odds >= 1.5) & (W.odds <= 50)].copy()
    W["same"] = ((W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0)).astype(float)
    W["pp"] = W.a_pos.astype(int).astype(str) + W.b_pos.astype(int).astype(str)
    W["fin"] = W.race_type.astype(str).str.contains("決勝|準決").astype(int)
    W["lpw"] = np.log(W.pw.clip(1e-4, 0.999) / (1 - W.pw.clip(1e-4, 0.999))); W["lodds"] = np.log(W.odds); W["mkt_gap"] = np.log(W.odds * W.pw)
    for f in feats:
        if f in cats: W[f] = W[f].astype("category")
        elif W[f].dtype == bool or W[f].dtype == object: W[f] = W[f].astype(float)
    W["pm"] = 1 / (1 + np.exp(-(m.predict(W[feats], raw_score=True) + W.lpw))); W["ev"] = W.pm * W.odds
    return W
fin = prep(pd.read_pickle("pre_wide_POST.pkl")).set_index(["race_id", "combo"])
for ph in ("B1R", "T5", "T1", "POST"):
    W = prep(pd.read_pickle(f"pre_wide_{ph}.pkl"))
    W["fodds"] = fin.odds.reindex(list(zip(W.race_id, W.combo))).to_numpy()
    W["fev"] = fin.ev.reindex(list(zip(W.race_id, W.combo))).to_numpy()
    print(f"--- {ph}（{W.race_id.nunique()}レース）---")
    for th in (1.0, 1.1, 1.15, 1.2):
        g = W[W.ev >= th]
        if len(g): print(f"  見込み×倍率≥{th}: {len(g)}点 回収{g.ret.mean():.0%} 的中{(g.ret>0).mean():.0%} 倍率変化{(g.fodds/g.odds-1).median():+.0%} 最終でも≥1.0が{(g.fev>=1.0).mean():.0%}")
