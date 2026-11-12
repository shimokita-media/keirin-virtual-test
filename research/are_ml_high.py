"""高倍率（100〜300倍）の3連単の目だけで「市場の見込みからのズレ」を LightGBM に学ばせ、再現性を確かめる。
学習 2025/02〜2026/06/15（angle_base）、止めどころ 2026/06/16〜11/05、確認＝2024年の表（y2024full：2023/11〜2025/01、この機械には未使用）。
出発点（init_score）＝市場の確率の logit。期待値＝機械の見込み×最終オッズ。"""
import gc, numpy as np, pandas as pd, lightgbm as lgb
K = "C:/Users/take0/.claude/keirin/"
DROP = {"ret", "combo", "race_id", "date", "close_at", "start_at", "cup_id", "venue_id", "nr", "in_B", "is_top", "venue"}
def load(path):
    d = pd.read_pickle(path)
    d = d[(d.odds >= 100) & (d.odds <= 300)].copy(); gc.collect()
    return d
tr_all = load(K + "out/angle_base.pkl")
te = load(K + "out/y2024full/cache.pkl")
cat = [c for c in tr_all.columns if c not in DROP and not (pd.api.types.is_numeric_dtype(tr_all[c]) or pd.api.types.is_bool_dtype(tr_all[c]))]
feats = [c for c in tr_all.columns if c not in DROP]
for c in cat:
    cats = pd.Categorical(pd.concat([tr_all[c], te[c]]).astype(str)).categories
    tr_all[c] = pd.Categorical(tr_all[c].astype(str), categories=cats); te[c] = pd.Categorical(te[c].astype(str), categories=cats)
for d in (tr_all, te):
    for c in feats:
        if d[c].dtype == bool: d[c] = d[c].astype(int)
    d["y"] = (d.ret > 0).astype(int)
    pp = d.p.clip(1e-5, 0.5); d["init"] = np.log(pp / (1 - pp))
tr = tr_all[tr_all.date <= "20260615"]; va = tr_all[tr_all.date > "20260615"]
print("学習", len(tr), "止めどころ", len(va), "確認(2024)", len(te), "特徴量", len(feats))
dtr = lgb.Dataset(tr[feats], tr.y, init_score=tr.init, categorical_feature=cat, free_raw_data=False)
dva = lgb.Dataset(va[feats], va.y, init_score=va.init, categorical_feature=cat, reference=dtr)
params = dict(objective="binary", learning_rate=0.03, num_leaves=31, min_data_in_leaf=2000, feature_fraction=0.7, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10, verbose=-1, seed=1)
m = lgb.train(params, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
print("木の数", m.best_iteration)
m.save_model(K + "out/are_work/ml_high.txt")
def ll(d, p):
    y = d.y.values; return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
out = []
for name, d in [("学習", tr), ("止めどころ", va), ("確認2024", te)]:
    raw = m.predict(d[feats], raw_score=True, num_iteration=m.best_iteration) + d.init.values
    d = d.assign(q=1 / (1 + np.exp(-raw)))
    pm = d.p.clip(1e-5, 0.5)
    print(f"{name}: 対数損失 市場 {ll(d, pm):.5f} 機械 {ll(d, d.q):.5f} 改善 {100*(ll(d, pm)-ll(d, d.q))/ll(d, pm):+.2f}%")
    d["ev"] = d.q * d.odds; d["mon"] = d.date.str[:6]
    d["are"] = (d.groupby("race_id").odds.transform("min") >= 15)  # 表にある目の最小オッズ（≒一番人気）
    for lab, sel in [("全部", d.ev > 0), ("期待値≥1.0", d.ev >= 1.0), ("期待値≥1.2", d.ev >= 1.2), ("期待値≥1.5", d.ev >= 1.5), ("期待値上位1%", d.ev >= d.ev.quantile(.99)),
                     ("期待値≥1.2×荒れ予想", (d.ev >= 1.2) & (d.nlines >= 4) & d.are)]:
        s = d[sel]
        if not len(s): continue
        mo = s.groupby("mon").ret.mean()
        out.append((name, lab, len(s), int(s.y.sum()), round(100 * s.ret.mean(), 1), f"{(mo > 1).sum()}/{len(mo)}"))
    if name == "確認2024":
        te_s = d
pd.set_option("display.width", 200)
print(pd.DataFrame(out, columns=["期間", "選び方", "点数", "当たり", "回収率%", "100%超えの月"]).to_string())
# 確認期間のブートストラップ（レース単位）
for lab, thr in [("期待値≥1.2", 1.2), ("期待値≥1.5", 1.5)]:
    s = te_s[te_s.ev >= thr]; g = s.groupby("race_id").agg(r=("ret", "sum"), n=("ret", "size"))
    rng = np.random.default_rng(0); b = [g.iloc[rng.integers(0, len(g), len(g))].pipe(lambda x: x.r.sum() / x.n.sum()) for _ in range(2000)]
    print(lab, "確認2024 95%範囲", np.percentile(b, [2.5, 97.5]).round(3))
imp = pd.Series(m.feature_importance("gain"), index=feats).sort_values(ascending=False)
print("効いた特徴量", (imp / imp.sum()).head(12).round(3).to_dict())
