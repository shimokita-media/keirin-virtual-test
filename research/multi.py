"""2車複・2車単・3連複・ワイドを同じ方法で学習（市場の見込み＝3連単から）。使い方: python multi.py 券種 学習の終わり(この日の前まで) [確認の終わり]"""
import sys, sqlite3, numpy as np, pandas as pd, lightgbm as lgb
BT, SPLIT = sys.argv[1], sys.argv[2]; END = sys.argv[3] if len(sys.argv) > 3 else "99999999"
c = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True)
F = pd.read_pickle(sys.argv[4] if len(sys.argv) > 4 else "ana_2026.pkl"); F = F[F["class"] != "L級"]
Fi = F.set_index(["race_id", "number"]); ids_all = F.race_id.unique()
cols = ["pos", "ls", "single", "pt_rank", "mk_rank", "age", "third_rate", "first_rate", "second_rate", "lead_rank", "line_idx", "prediction_mark", "gear"]
k = 3 if BT.startswith("3") else 2; ordered = BT in ("2車単",)
out = []
for i0 in range(0, len(ids_all), 1500):
    ids = tuple(ids_all[i0:i0 + 1500]); q = ",".join("?" * len(ids))
    o = pd.read_sql(f"SELECT race_id, bet_type, combo, odds, fetched_at FROM odds WHERE phase='POST' AND source='winticket' AND bet_type IN ('3連単',?) AND odds>0 AND race_id IN ({q})", c, params=(BT,) + ids)
    o = o[o.fetched_at == o.groupby("race_id").fetched_at.transform("max")]
    t = o[o.bet_type == "3連単"].copy(); t["p"] = 1 / t.odds; t["p"] /= t.groupby("race_id").p.transform("sum")
    cb = t.combo.str.split("-", expand=True).astype(int).to_numpy()
    if BT == "3連複": keys = ["-".join(map(str, sorted(r))) for r in cb]
    elif BT == "2車複": keys = [f"{min(r[0], r[1])}-{max(r[0], r[1])}" for r in cb]
    elif BT == "2車単": keys = [f"{r[0]}-{r[1]}" for r in cb]
    if BT == "ワイド":
        parts = [pd.DataFrame({"race_id": t.race_id.values, "combo": [f"{min(r[i], r[j])}-{max(r[i], r[j])}" for r in cb], "p": t.p.values}) for i, j in ((0, 1), (0, 2), (1, 2))]
        pm = pd.concat(parts).groupby(["race_id", "combo"]).p.sum()
    else:
        pm = pd.DataFrame({"race_id": t.race_id.values, "combo": keys, "p": t.p.values}).groupby(["race_id", "combo"]).p.sum()
    w = o[o.bet_type == BT][["race_id", "combo", "odds"]].merge(pm.rename("pw").reset_index(), on=["race_id", "combo"])
    pay = pd.read_sql(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type=? AND race_id IN ({q})", c, params=(BT,) + ids)
    w = w.merge(pay, on=["race_id", "combo"], how="left"); w["ret"] = w.payout.fillna(0) / 100
    nb = w.combo.str.split("-", expand=True).astype(int)
    for j in range(k):
        X = Fi[cols].reindex(list(zip(w.race_id, nb[j]))); X.columns = [f"r{j}_{x}" for x in cols]
        w = pd.concat([w.reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    out.append(w)
W = pd.concat(out); W = W[W.r0_pos.notna()]
R = F.drop_duplicates("race_id").set_index("race_id")
for col in ("date", "entries_number", "nlines", "n_strong_nige", "class", "grade", "day_index", "race_no"): W[col] = W.race_id.map(R[col])
W["S"] = (W["class"] == "S級").astype(float); W["G"] = W.grade.astype(str).str.startswith("G").astype(float)
li = [f"r{j}_line_idx" for j in range(k)]
W["s01"] = ((W.r0_line_idx == W.r1_line_idx) & (W.r0_line_idx >= 0)).astype(float)
if k == 3:
    W["s12"] = ((W.r1_line_idx == W.r2_line_idx) & (W.r1_line_idx >= 0)).astype(float); W["s02"] = ((W.r0_line_idx == W.r2_line_idx) & (W.r0_line_idx >= 0)).astype(float)
W["pw"] = W.pw.clip(1e-5, 0.999); W["lp"] = np.log(W.pw / (1 - W.pw)); W["lodds"] = np.log(W.odds); W["gap"] = np.log(W.odds * W.pw); W["y"] = (W.ret > 0).astype(int)
feats = ["lodds", "gap", "s01"] + (["s12", "s02"] if k == 3 else []) + [f"r{j}_{x}" for j in range(k) for x in cols if x != "line_idx"] + ["entries_number", "nlines", "n_strong_nige", "S", "G", "day_index", "race_no"]
for f in feats: W[f] = W[f].astype(float)
W = W[W.odds <= 200]
tr, te = W[W.date < SPLIT], W[(W.date >= SPLIT) & (W.date <= END)]
cut = sorted(tr.date.unique())[int(tr.date.nunique() * 0.8)]; a, v = tr[tr.date < cut], tr[tr.date >= cut]
P = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=400, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1)
m = lgb.train(P, lgb.Dataset(a[feats], a.y, init_score=a.lp), 2000, valid_sets=[lgb.Dataset(v[feats], v.y, init_score=v.lp)], callbacks=[lgb.early_stopping(100, verbose=False)])
nb_ = max(m.best_iteration, 1)
m = lgb.train(P, lgb.Dataset(tr[feats], tr.y, init_score=tr.lp), nb_)
te = te.copy(); te["pm"] = 1 / (1 + np.exp(-(m.predict(te[feats], raw_score=True) + te.lp))); te["ev"] = te.pm * te.odds; te["ev0"] = te.pw * te.odds
print(f"=== {BT}  学習〜{SPLIT} 確認{te.date.min()}〜{te.date.max()} 木{nb_} ===")
def s(g):
    if len(g) < 30: return f"{len(g)}点"
    gg = g.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size")); A, B = gg.r.to_numpy(), gg.n.to_numpy()
    i = np.random.default_rng(0).integers(0, len(gg), (1000, len(gg))); bs = A[i].sum(1) / B[i].sum(1)
    return f"{len(g)}点 1日{len(g)/te.date.nunique():.1f} {g.ret.mean():.0%}[{np.percentile(bs,2.5):.0%}-{np.percentile(bs,97.5):.0%}] 月:" + " ".join(f"{x.ret.mean():.0%}" for _, x in g.groupby(g.date.str[4:6]))
for th in (1.0, 1.1, 1.15, 1.2, 1.3):
    print(f" 機械≥{th}", s(te[te.ev >= th]), " | 3連単だけ", s(te[te.ev0 >= th]))
te[te.ev >= 1.0][["race_id", "date", "combo", "odds", "ev", "ev0", "ret"]].to_pickle(f"multi_te_{BT}_{SPLIT}.pkl"); m.save_model(f"multi_{BT}_{SPLIT}.txt")
