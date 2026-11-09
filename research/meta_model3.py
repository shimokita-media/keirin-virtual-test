"""機械を磨く v3（偏差値＋ロジスティック回帰）。以下は v2 の説明を引き継ぐ。v2（2026-11-09 17:35〜）：v1 と同じ特徴量づくり＋選手の癖を「1着」「3着以内」に分け、縮小を強め、設定とレース内の正規化を比べる。
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
RA = pd.read_pickle(K + "out/side_races.pkl"); E = pd.read_pickle(K + "out/side_entries.pkl"); S = pd.read_pickle(K + "out/side_results.pkl")
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
# --- v3：レース内の偏差値（50＋10×レース内の標準化）
def dev(col):
    g_ = E.groupby("race_id")[col]
    mu, sd = g_.transform("mean"), g_.transform("std").replace(0, np.nan)
    return 50 + 10 * (E[col] - mu) / sd
for col in ("first_rate", "second_rate", "third_rate", "agari_avg", "n_back", "n_standing", "age"):
    E[col] = pd.to_numeric(E[col], errors="coerce")
E["dev_rp"] = dev("rp"); E["dev_r1"] = dev("first_rate"); E["dev_r2"] = dev("second_rate"); E["dev_r3"] = dev("third_rate")
E["dev_agari"] = 100 - dev("agari_avg")  # 上がりタイムは小さいほど速い
E["dev_back"] = dev("n_back"); E["dev_s"] = dev("n_standing"); E["dev_ptrend"] = dev("ptrend"); E["dev_age"] = dev("age")
# ラインの強さ（並びの中の得点の合計）の偏差値
lrows = []
for rid, lj in zip(RA.race_id, RA.line_json):
    try: lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(lj or "[]")]
    except Exception: continue
    for li, ln in enumerate(lines):
        for n in ln: lrows.append((rid, n, li))
LN = pd.DataFrame(lrows, columns=["race_id", "number", "li"])
E = E.merge(LN, on=["race_id", "number"], how="left")
E["lstr"] = E.groupby(["race_id", "li"]).rp.transform("sum")
lu = E.drop_duplicates(["race_id", "li"]); lmu = lu.groupby("race_id").lstr.mean(); lsd = lu.groupby("race_id").lstr.std().replace(0, np.nan)
E["dev_line"] = 50 + 10 * (E.lstr - E.race_id.map(lmu)) / E.race_id.map(lsd)
DEVS = ["dev_rp", "dev_r1", "dev_r2", "dev_r3", "dev_agari", "dev_back", "dev_s", "dev_ptrend", "dev_age", "dev_line"]
for col in DEVS:
    for i, s_ in enumerate(per_rider(col)): T[f"{col}{i}"] = pd.to_numeric(s_, errors="coerce").astype("float32")
# 3人の偏差値の合計と差（目としての強さ）
T["dev_rp_sum"] = T.dev_rp0 + T.dev_rp1 + T.dev_rp2; T["dev_rp_gap01"] = T.dev_rp0 - T.dev_rp1; T["dev_line_gap02"] = T.dev_line0 - T.dev_line2
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
def ll(y, p): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
feats3 = [f for f in feats if not f.startswith("tend")] + [f"{c}{i}" for c in DEVS for i in range(3)] + ["dev_rp_sum", "dev_rp_gap01", "dev_line_gap02"]
feats3 = list(dict.fromkeys(feats3))
for f in feats3: T[f] = pd.to_numeric(T[f], errors="coerce").astype("float32")
P("# 機械を磨く v3：レース内の偏差値＋ロジスティック回帰" + NL)
P(f"特徴量 {len(feats3)} 個（v2 の特徴量－選手の癖＋偏差値 {len(DEVS) * 3 + 3} 個）。設定は v2 で選んだ B に固定（止めどころで木の本数だけ決める）。" + NL)
# --- 機械（v2 と同じ設定）
prm = dict(objective="binary", learning_rate=0.01, num_leaves=15, min_data_in_leaf=10000, feature_fraction=0.5, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, seed=0)
dtr = lgb.Dataset(T.loc[tr, feats3], T.loc[tr, "y"], init_score=T.loc[tr, "init"]); dva = lgb.Dataset(T.loc[va, feats3], T.loc[va, "y"], init_score=T.loc[va, "init"])
m = lgb.train(prm, dtr, 6000, valid_sets=[dva], callbacks=[lgb.early_stopping(200, verbose=False)])
T["p3"] = 1 / (1 + np.exp(-(m.predict(T[feats3], raw_score=True) + T.init.to_numpy())))
m.save_model(K + "research/meta_model_v3.txt")
V2 = pd.read_pickle(K + "out/meta_pred_v2.pkl")[["race_id", "combo", "pmod"]].rename(columns={"pmod": "p2"})
T = T.merge(V2, on=["race_id", "combo"], how="left")
p_ = pd.Series(per(T.date), index=T.index); va = ((p_ == "探す") & (T.date > TR_END) & (T.date <= VA_END)).to_numpy(); tr = ((p_ == "探す") & (T.date <= TR_END)).to_numpy()
# --- ロジスティック回帰：logit(実際) = logit(市場) を足場に、標準化した解釈しやすい項目で補正（係数・標準誤差・t値）
REG = ["lodds", "share", "ent", "fav_odds", "s01", "s12", "dev_rp0", "dev_rp1", "dev_rp2", "dev_line0", "dev_line1", "dev_line2", "dev_r3_0", "dev_agari0", "dev_back0",
       "dev_ptrend0", "dev_ptrend1", "dev_ptrend2", "dev_age0", "r0_pos", "r1_pos", "r2_pos", "rtype", "scratch", "lead_prev", "nkind", "to_last", "hr"]
T["dev_r3_0"] = T["dev_r30"]
REG = [r for r in REG if r in T.columns]
Z = T[REG].astype("float64"); mu, sd = Z[tr].mean(), Z[tr].std().replace(0, 1); Z = ((Z - mu) / sd).fillna(0).clip(-5, 5)
Xs = np.column_stack([np.ones(len(T)), T.init.to_numpy(), Z.to_numpy()])
names = ["定数", "logit(市場)"] + REG
rng = np.random.default_rng(0); idx = np.where(tr)[0]; idx = rng.choice(idx, min(600000, len(idx)), replace=False)
Xt, yt = Xs[idx], T.y.to_numpy()[idx]
beta = np.zeros(Xs.shape[1]); beta[1] = 1.0
for it in range(30):  # ニュートン法（L2 を少しだけ）
    eta = Xt @ beta; pp = 1 / (1 + np.exp(-eta)); W = pp * (1 - pp)
    H = (Xt * W[:, None]).T @ Xt + np.eye(len(beta)) * 1.0; gvec = Xt.T @ (yt - pp) - beta * 1.0 * np.r_[0, 0, np.ones(len(REG))]
    step = np.linalg.solve(H, gvec); beta += step
    if np.abs(step).max() < 1e-6: break
se = np.sqrt(np.diag(np.linalg.inv(H))); tv = beta / se
T["pr"] = 1 / (1 + np.exp(-(Xs @ beta)))
P("## 1. ロジスティック回帰の係数（学習期間から60万点・標準化した項目1ばらつきあたり）" + NL + NL + "| 項目 | 係数 | 標準誤差 | t値 |" + NL + "|---|---|---|---|")
order_ = np.argsort(-np.abs(tv)); order_ = [0, 1] + [i for i in order_ if i > 1]
for i in order_: P(f"| {names[i]} | {beta[i]:+.4f} | {se[i]:.4f} | {tv[i]:+.1f} |")
# --- 比べる
sets = {"止めどころ 26/6/16〜8/31": va, "③ 25/10/12〜26/1/14": (p_ == "③").to_numpy(), "⑥ 26/9〜11/5": (p_ == "⑥").to_numpy()}
P(NL + "## 2. 当てる力（レースごとの対数損失の差：市場−各モデル。平均・標準偏差・t値）" + NL + NL + "| 期間 | 回帰 | 機械v2 | 機械v3 |" + NL + "|---|---|---|---|")
y = T.y.to_numpy()
def lli(p): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
base_ll = lli(T.pm.to_numpy())
for k, mk in sets.items():
    cells = []
    for col in ("pr", "p2", "p3"):
        d = pd.Series(base_ll - lli(T[col].fillna(T.pm).to_numpy()))[mk].groupby(T.race_id[mk].to_numpy()).sum()
        cells.append(f"{d.mean():.4f}（標準偏差 {d.std():.3f}・t={d.mean() / (d.std() / np.sqrt(len(d))):.1f}）")
    P(f"| {k} | " + " | ".join(cells) + " |")
rng2 = np.random.default_rng(1)
def cell(x):
    if len(x) < 20: return f"−（{len(x)}点）"
    r = x.ret; t_ = (r.mean() - 1) / (r.std() / np.sqrt(len(r)))
    return f"**{r.mean():.0%}**（{len(x)}点・{int((r > 0).sum())}本・分散{r.var():.0f}・t={t_:+.1f}）"
P(NL + "## 3. 期待値（見込み×倍率）で選んだ回収率（最終オッズ・各100円。t は100%との比較）" + NL)
for col, lab in (("pr", "回帰"), ("p2", "機械v2"), ("p3", "機械v3")):
    T["ev"] = T[col] * T.odds
    P(f"### {lab}" + NL + NL + "| 選び方 | " + " | ".join(sets) + " |" + NL + "|---|---|---|---|")
    for th in (1.0, 1.05, 1.1, 1.2):
        P(f"| 期待値≥{th} | " + " | ".join(cell(T[mk & (T.ev >= th).to_numpy()]) for mk in sets.values()) + " |")
    P(f"| 期待値≥1.05×30倍以下 | " + " | ".join(cell(T[mk & ((T.ev >= 1.05) & (T.odds <= 30)).to_numpy()]) for mk in sets.values()) + " |")
    P(f"| 一番の目×期待値≥1.0 | " + " | ".join(cell(T[mk & (T.is_top & (T.ev >= 1.0)).to_numpy()]) for mk in sets.values()) + " |" + NL)
imp = pd.Series(m.feature_importance("gain"), index=feats3).sort_values(ascending=False)
P("## 4. 機械v3で効いている特徴量（上位15）" + NL + NL + NL.join(f"- {k}: {v / imp.sum():.1%}" for k, v in imp.head(15).items()))
P(NL + f"機械v3の木の数 {m.best_iteration}")
T.loc[:, ["race_id", "combo", "date", "odds", "ret", "pm", "pr", "p2", "p3", "in_B", "is_top"]].to_pickle(K + "out/meta_pred_v3.pkl")
print("done", m.best_iteration)
