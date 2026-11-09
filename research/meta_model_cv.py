"""もっと学習させる：学習のさせ方を時期をずらした交差検証で比べる（v2 の特徴量づくりを使う）。以下は v2 の説明。v2（2026-11-09 17:35〜）：v1 と同じ特徴量づくり＋選手の癖を「1着」「3着以内」に分け、縮小を強め、設定とレース内の正規化を比べる。
案の選択は止めどころ期間（26/6/16〜8/31）の対数損失だけで行い、③⑥は選んだ案を最後に1回だけ見る。
--- 以下 v1 の説明 ---
意味のある学習（2026-11-09 17:20〜）：今日見つけた歪みを全部「特徴量」にまとめ、市場の見込みを出発点にして1つの機械に学ばせる。
今日の切り口はどれも単独では控除（25%）を越えなかったが、小さな歪み（3〜15%）が重なれば越えるか、を未使用の期間で確かめる。
- 出発点：3連単の最終倍率から出した見込み（300倍以下で正規化）。機械は「市場からのズレ」だけを学ぶ（init_score）
- 学習：探す期間のうち 2025/2〜2026/6/15、止めどころ：2026/6/16〜8/31、確認：③ 25/10/12〜26/1/14 と ⑥ 26/9〜11/5（どちらも学習・止めどころに使わない）
- 選手ごとの癖は学習期間だけで作る（確認期間の情報を使わない）
使い方: python -I -X utf8 research/meta_model.py 出力.md"""
import sys, json, numpy as np, pandas as pd, lightgbm as lgb
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T); NUM = (a, b, c)
key = lambda r, n: (r, n)
# --- 写しのデータ
RA = pd.read_pickle(K + "out/side_races_full.pkl"); E = pd.read_pickle(K + "out/side_entries_full.pkl"); S = pd.read_pickle(K + "out/side_results_full.pkl")
S["rank"] = pd.to_numeric(S["rank"], errors="coerce")
E = E.merge(RA[["race_id", "date", "cup_id", "day_index", "venue"]], on="race_id", how="left")
def per_rider(col):
    d = dict(zip(zip(E.race_id, E.number), E[col]))
    return [pd.Series([d.get((r, x)) for r, x in zip(T.race_id, n)], index=T.index) for n in NUM]
# 1) 並び順の取り分・レースの散らばり・一番人気の倍率
srt = np.sort(np.column_stack(NUM), axis=1); trio = T.race_id + ":" + pd.Series([f"{x}{y}{z}" for x, y, z in srt], index=T.index)
g = T.groupby(trio).pm; T["share"] = T.pm / g.transform("sum"); T["rank_in_trio"] = g.rank(ascending=False, method="first")
T["ent"] = -(T.pm * np.log(T.pm)).groupby(T.race_id).transform("sum"); T["fav_odds"] = T.groupby("race_id").odds.transform("min")
# 2) 開催・レースの文脈
nd = RA.groupby("cup_id").day_index.max(); T["nd"] = T.cup_id.map(nd); T["to_last"] = T.nd - T.day_index
rt = T.race_type.fillna("").astype(str)
T["rtype"] = np.select([rt.str.contains("準決勝"), rt.str.contains("予選"), rt.str.contains("決勝") & ~rt.str.contains("準"), rt.str.contains("特選|選抜"), rt.str.contains("一般")], [1, 2, 3, 4, 5], 0)
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
T["bank"] = np.select([T.venue.isin(S333), T.venue.isin(S500)], [333, 500], 400)
st = pd.to_datetime(T.start_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo"); T["hr"] = st.dt.hour + st.dt.minute / 60
ab = set(E[E.absent == 1].race_id); T["scratch"] = T.race_id.isin(ab).astype(int)
# 3) 当日の流れ（同じ場・同じ日の前のレース）
W = T[T.ret > 0][["race_id", "r0_pos", "popularity"]].drop_duplicates("race_id").set_index("race_id")
R = T.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
R["lw"] = R.race_id.map(W.r0_pos).eq(0).astype(float); R["up"] = (R.race_id.map(W.popularity).fillna(999) >= 20).astype(float)
gg = R.groupby(["venue", "date"]); R["n_prev"] = gg.cumcount()
R["lead_prev"] = (gg.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R["upset_prev"] = (gg.up.cumsum() - R.up) / R.n_prev.replace(0, np.nan)
for col in ("n_prev", "lead_prev", "upset_prev"): T[col] = T.race_id.map(R.set_index("race_id")[col])
# 4) 選手：級班・期・得点の流れ・中何日・昨日の着順・地元
E["rk"] = pd.to_numeric(E["class"], errors="coerce") * 10 + pd.to_numeric(E.grp, errors="coerce")
E["term"] = pd.to_numeric(E.term, errors="coerce"); E["ym"] = E.date.str[:6]; E["tgap"] = E.groupby("ym").term.transform("max") - E.term
E["rp"] = pd.to_numeric(E.race_point, errors="coerce"); E["d"] = pd.to_datetime(E.date)
past = E[["player_id", "d", "rp"]].rename(columns={"d": "d0", "rp": "rp0"}).dropna()
E["kd"] = E.d - pd.Timedelta(days=60)
E = pd.merge_asof(E.sort_values("kd"), past.sort_values("d0"), left_on="kd", right_on="d0", by="player_id", direction="backward"); E["ptrend"] = E.rp - E.rp0
cup = E.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
cup["rest"] = (cup["min"] - cup.groupby("player_id")["max"].shift()).dt.days - 1
E = E.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
X = E.merge(S[["race_id", "player_id", "rank"]], on=["race_id", "player_id"], how="left")
prev = X[["player_id", "cup_id", "day_index", "rank"]].rename(columns={"rank": "prank"}); prev["day_index"] += 1
E = E.merge(prev.drop_duplicates(["player_id", "cup_id", "day_index"]), on=["player_id", "cup_id", "day_index"], how="left")
VP = {"函館": "北海道", "青森": "青森", "いわき平": "福島", "弥彦": "新潟", "前橋": "群馬", "取手": "茨城", "宇都宮": "栃木", "大宮": "埼玉", "西武園": "埼玉", "京王閣": "東京", "立川": "東京", "松戸": "千葉", "千葉": "千葉", "川崎": "神奈川", "平塚": "神奈川", "小田原": "神奈川", "伊東": "静岡", "静岡": "静岡", "名古屋": "愛知", "豊橋": "愛知", "岐阜": "岐阜", "大垣": "岐阜", "富山": "富山", "松阪": "三重", "四日市": "三重", "福井": "福井", "奈良": "奈良", "向日町": "京都", "和歌山": "和歌山", "岸和田": "大阪", "玉野": "岡山", "広島": "広島", "防府": "山口", "高松": "香川", "小松島": "徳島", "高知": "高知", "松山": "愛媛", "小倉": "福岡", "久留米": "福岡", "武雄": "佐賀", "佐世保": "長崎", "別府": "大分", "熊本": "熊本"}
E["home"] = (E.prefecture == E.venue.map(VP)).astype(float)
E["rk_gap"] = E.rk - E.groupby("race_id").rk.transform("min")
for col in ("rk_gap", "tgap", "ptrend", "rest", "prank", "home"):
    for i, s in enumerate(per_rider(col)): T[f"{col}{i}"] = pd.to_numeric(s, errors="coerce").astype("float32")
T["nkind"] = T.race_id.map(E.groupby("race_id").rk.nunique())
# 5) 選手ごとの癖（学習期間だけで作る）：実際の3着以内 ÷ 見込み、縮小推定（20レース分の事前）
TR_END, VA_END = "20260615", "20260831"
train_race = set(T[(per(T.date) == "探す") & (T.date <= TR_END)].race_id)
L = pd.concat([pd.DataFrame({"race_id": T.race_id, "number": n, "pm": T.pm}) for n in NUM]).groupby(["race_id", "number"]).pm.sum().rename("p3").reset_index()
Dd = L.merge(E[["race_id", "number", "player_id"]], on=["race_id", "number"]).merge(S[["race_id", "number", "rank"]], on=["race_id", "number"])
Dd = Dd[Dd.race_id.isin(train_race)]; Dd["t3"] = (Dd["rank"] <= 3).astype(float)
Dd["t1"] = (Dd["rank"] == 1).astype(float)
L1 = T[["race_id", "pm"]].assign(n=a).groupby(["race_id", "n"]).pm.sum().rename("p1").reset_index().rename(columns={"n": "number"})
Dd = Dd.merge(L1, on=["race_id", "number"], how="left")
k3 = Dd.t3.sum() / Dd.p3.sum(); k1 = Dd.t1.sum() / Dd.p1.sum()
pr = Dd.groupby("player_id").agg(a3=("t3", "sum"), e3=("p3", "sum"), a1=("t1", "sum"), e1=("p1", "sum"), n=("t3", "size"))
PRIOR = 40  # 縮小を v1（20）より強める
pr["tend"] = (pr.a3 / k3 + PRIOR * pr.e3.mean() / pr.n.mean()) / (pr.e3 + PRIOR * pr.e3.mean() / pr.n.mean())
pr["tend1"] = (pr.a1 / k1 + PRIOR * pr.e1.mean() / pr.n.mean()) / (pr.e1 + PRIOR * pr.e1.mean() / pr.n.mean())
for i, s_ in enumerate(per_rider("player_id")):
    T[f"tend{i}"] = s_.map(pr.tend).astype("float32"); T[f"tendw{i}"] = s_.map(pr.tend1).astype("float32")
# --- 特徴量
base_cols = [c for c in T.columns if c.startswith(("r0_", "r1_", "r2_")) and T[c].dtype.kind in "fiub"]
feats = base_cols + ["s01", "s12", "entries_number", "nlines", "n_strong_nige", "day_index", "race_no", "G", "S", "popularity",
                     "share", "rank_in_trio", "ent", "fav_odds", "nd", "to_last", "rtype", "bank", "hr", "scratch", "n_prev", "lead_prev", "upset_prev", "nkind"] + \
        [f"{c}{i}" for c in ("rk_gap", "tgap", "ptrend", "rest", "prank", "home", "tend", "tendw") for i in range(3)]
feats = [f for f in dict.fromkeys(feats) if f in T.columns and f not in ("ret",)]
T["lodds"] = np.log(T.odds); feats.append("lodds")
for f in feats: T[f] = pd.to_numeric(T[f], errors="coerce").astype("float32")
T["y"] = (T.ret > 0).astype(int); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
T["init"] = lg(T.pm)
p_ = per(T.date); tr = (p_ == "探す") & (T.date <= TR_END); va = (p_ == "探す") & (T.date > TR_END) & (T.date <= VA_END)


NL = chr(10)
fs = [f for f in feats if not f.startswith("tend")]
y_all = T.y.to_numpy(); init_all = T.init.to_numpy(); dts = pd.to_datetime(T.date)
def lli(y, p): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def fit(mask, cfg, seed=0):
    prm = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=10000, feature_fraction=cfg.get("ff", 0.5), bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, seed=seed)
    w = None
    if cfg.get("half"):  # 新しいデータほど重く（半減期 half 日）
        age = (dts[mask].max() - dts[mask]).dt.days.to_numpy(); w = 0.5 ** (age / cfg["half"])
    return lgb.train(prm, lgb.Dataset(T.loc[mask, fs], y_all[mask], init_score=init_all[mask], weight=w), cfg.get("n", 470))
def pred(models, mask):
    raw = np.mean([m.predict(T.loc[mask, fs], raw_score=True) for m in models], axis=0)
    return 1 / (1 + np.exp(-(raw + init_all[mask])))
CFG = {"A 今の作り方（v2full と同じ・学習率0.03）": dict(), "B 新しいデータほど重く（半減期180日）": dict(half=180), "C 新しいデータほど重く（半減期90日）": dict(half=90),
       "D 3つの機械の平均（特徴量の使い方をばらす）": dict(ens=[0.4, 0.5, 0.6])}
FOLDS = [("2025/2〜2025/12 で学習 → 2026/1〜4 で確認", ("20250201", "20251231"), ("20260101", "20260430")),
         ("2025/2〜2026/4 で学習 → 2026/5〜8 で確認", ("20250201", "20260430"), ("20260501", "20260831")),
         ("2025/2〜2026/8 で学習 → 2026/9〜11/8 で確認", ("20250201", "20260831"), ("20260901", "20261108"))]
P("# もっと学習させる：学習のさせ方を、時期をずらした交差検証で比べる" + NL)
P("各分け方で「学習期間 → その直後の期間」で確認（2024年は使わない）。数字＝市場との対数損失の差（レースごと平均、＋が市場より良い）と t値。" + NL)
P("| 学習のさせ方 | " + " | ".join(f[0] for f in FOLDS) + " | 平均 |" + NL + "|---|---|---|---|---|")
res = {}
for nm, cfg in CFG.items():
    cells, vals = [], []
    for fl, (a0, a1), (b0, b1) in FOLDS:
        tr = T.date.between(a0, a1).to_numpy(); te = T.date.between(b0, b1).to_numpy()
        ms = [fit(tr, dict(cfg, ff=f), seed=i) for i, f in enumerate(cfg["ens"])] if cfg.get("ens") else [fit(tr, cfg)]
        p = pred(ms, te); d = pd.Series(lli(y_all[te], T.pm.to_numpy()[te]) - lli(y_all[te], p)).groupby(T.race_id.to_numpy()[te]).sum()
        cells.append(f"{d.mean():+.4f}（t={d.mean() / (d.std() / np.sqrt(len(d))):+.1f}）"); vals.append(d.mean())
    res[nm] = np.mean(vals)
    P(f"| {nm} | " + " | ".join(cells) + f" | {np.mean(vals):+.4f} |")
best = max(res, key=res.get)
P(NL + f"**交差検証で一番良かった：{best}**" + NL)
# 一番良いやり方で 2025/2〜2026/11/8 を全部学習し、2024/2〜7/8 で1回だけ確認（v2full と比べる）
cfg = CFG[best]; trn = (T.date >= "20250201").to_numpy(); hold = ~trn
ms = [fit(trn, dict(cfg, ff=f, n=470), seed=i) for i, f in enumerate(cfg["ens"])] if cfg.get("ens") else [fit(trn, dict(cfg, n=470))]
for i, m in enumerate(ms): m.save_model(K + f"research/meta_model_v3cv_{i}.txt")
H = T[hold].copy(); H["p_new"] = pred(ms, hold)
mo = lgb.Booster(model_file=K + "research/meta_model_v2full.txt")
H["p_full"] = 1 / (1 + np.exp(-(mo.predict(H[mo.feature_name()], raw_score=True) + H.init.to_numpy())))
yh = H.y.to_numpy()
P("## 2024/2〜7/8 で確認（学習に使っていない）" + NL + NL + "| 機械 | 市場との差 | t値 |" + NL + "|---|---|---|")
for col, lab in (("p_full", "v2full"), ("p_new", f"新しい作り方（{best}）")):
    d = pd.Series(lli(yh, H.pm.to_numpy()) - lli(yh, H[col].to_numpy())).groupby(H.race_id.to_numpy()).sum()
    P(f"| {lab} | {d.mean():+.4f} | {d.mean() / (d.std() / np.sqrt(len(d))):+.1f} |")
rng = np.random.default_rng(0)
def cell(x):
    if len(x) < 20: return f"−（{len(x)}点）"
    by = x.groupby("race_id").ret.agg(["sum", "size"]); w = rng.dirichlet(np.ones(len(by)), 3000); post = (w @ by["sum"].to_numpy()) / (w @ by["size"].to_numpy())
    r = x.ret; return f"**{r.mean():.0%}**（{len(x)}点・的中{(r > 0).mean():.0%}・t={(r.mean() - 1) / (r.std() / np.sqrt(len(r))):+.1f}・P>100% {(post > 1).mean():.0%}・前半{x[x.date <= '20240615'].ret.mean():.0%}/後半{x[x.date > '20240615'].ret.mean():.0%}）"
P(NL + "| 選び方（2024/2〜7/8） | v2full | 新しい作り方 |" + NL + "|---|---|---|")
for nm, th in (("★Z 当たる確率≥10%×期待値≥0.9", (0.10, 0.9)), ("当たる確率≥8%×期待値≥0.95", (0.08, 0.95)), ("当たる確率≥12%×期待値≥0.9", (0.12, 0.9))):
    P(f"| {nm} | {cell(H[(H.p_full >= th[0]) & (H.p_full * H.odds >= th[1])])} | {cell(H[(H.p_new >= th[0]) & (H.p_new * H.odds >= th[1])])} |")
print("done", best)
