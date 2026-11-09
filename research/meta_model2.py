"""機械を磨く v2（2026-11-09 17:35〜）：v1 と同じ特徴量づくり＋選手の癖を「1着」「3着以内」に分け、縮小を強め、設定とレース内の正規化を比べる。
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


def ll(y, p): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
def renorm(d, p):  # レース内で合計を市場の合計（=1）に合わせる
    return p / pd.Series(p, index=d.index).groupby(d.race_id).transform("sum").to_numpy()
NL = chr(10)
P("# 機械を磨く v2（案の選択は止めどころ期間だけ）" + NL)
variants = {
    "A v1の設定＋新しい癖": dict(learning_rate=0.03, num_leaves=31, min_data_in_leaf=3000, feature_fraction=0.7),
    "B 小さく慎重に": dict(learning_rate=0.01, num_leaves=15, min_data_in_leaf=10000, feature_fraction=0.5),
    "C とても慎重（浅い木）": dict(learning_rate=0.01, num_leaves=7, min_data_in_leaf=20000, feature_fraction=0.5),
}
res = {}
for nm, pp in variants.items():
    prm = dict(objective="binary", bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, seed=0, **pp)
    for drop_t in (False, True):
        fs = [f for f in feats if not (drop_t and f.startswith("tend"))]
        dtr = lgb.Dataset(T.loc[tr, fs], T.loc[tr, "y"], init_score=T.loc[tr, "init"]); dva = lgb.Dataset(T.loc[va, fs], T.loc[va, "y"], init_score=T.loc[va, "init"])
        mm = lgb.train(prm, dtr, 5000, valid_sets=[dva], callbacks=[lgb.early_stopping(200, verbose=False)])
        raw = mm.predict(T.loc[va, fs], raw_score=True) + T.loc[va, "init"].to_numpy(); pv = 1 / (1 + np.exp(-raw))
        key_ = nm + ("（癖なし）" if drop_t else "")
        res[key_] = (ll(T.loc[va, "y"], pv), ll(T.loc[va, "y"], renorm(T.loc[va], pv)), mm, fs)
        P(f"- {key_}: 木{mm.best_iteration}本・止めどころの対数損失 {res[key_][0]:.6f}（レース内で正規化 {res[key_][1]:.6f}）")
mkt = ll(T.loc[va, "y"], T.loc[va, "pm"]); P(f"- 市場: {mkt:.6f}")
best = min(res, key=lambda k: min(res[k][0], res[k][1])); use_norm = res[best][1] < res[best][0]
_, _, m, fs = res[best]
P(NL + f"**選んだ案：{best}**（レース内の正規化 {'あり' if use_norm else 'なし'}）" + NL)
raw = m.predict(T[fs], raw_score=True) + T.init.to_numpy(); T["pmod"] = 1 / (1 + np.exp(-raw))
if use_norm: T["pmod"] = renorm(T, T.pmod.to_numpy())
m.save_model(K + "research/meta_model_v2.txt")
sets = {"止めどころ 26/6/16〜8/31": va, "③ 25/10/12〜26/1/14": p_ == "③", "⑥ 26/9〜11/5": p_ == "⑥"}
P("## 当てる力（対数損失）" + NL + NL + "| 期間 | 市場 | v2 | 改善 |" + NL + "|---|---|---|---|")
for k, mk in sets.items():
    x = T[mk]; a_, b_ = ll(x.y, x.pm), ll(x.y, x.pmod); P(f"| {k} | {a_:.5f} | {b_:.5f} | {(a_ - b_) / a_:+.3%} |")
T["ev"] = T.pmod * T.odds; rng2 = np.random.default_rng(1)
def cell(x):
    if len(x) < 20: return f"−（{len(x)}点）"
    by = x.groupby("race_id").ret.agg(["sum", "size"]); ii = rng2.integers(0, len(by), (500, len(by)))
    bs = by["sum"].to_numpy()[ii].sum(1) / by["size"].to_numpy()[ii].sum(1)
    return f"**{x.ret.mean():.0%}**（{len(x)}点・{int((x.ret > 0).sum())}本・{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}）"
rules = {f"期待値≥{t}": (lambda x, t=t: x[x.ev >= t]) for t in (1.0, 1.1, 1.2)}
rules["期待値≥1.1×60倍以下"] = lambda x: x[(x.ev >= 1.1) & (x.odds <= 60)]
rules["一番の目（比較）"] = lambda x: x[x.is_top]
for t in (0.9, 1.0, 1.1):
    rules[f"一番の目×期待値≥{t}"] = (lambda x, t=t: x[x.is_top & (x.ev >= t)]); rules[f"一番の目×期待値<{t}"] = (lambda x, t=t: x[x.is_top & (x.ev < t)])
rules["3連単枠×期待値≥1.0"] = lambda x: x[x.in_B & (x.ev >= 1.0)]
P(NL + "## 期待値で選んだ回収率（最終オッズ）" + NL + NL + "| 選び方 | " + " | ".join(sets) + " |" + NL + "|---|---|---|---|")
for nm, fn in rules.items(): P(f"| {nm} | " + " | ".join(cell(fn(T[mk])) for mk in sets.values()) + " |")
imp = pd.Series(m.feature_importance("gain"), index=fs).sort_values(ascending=False)
P(NL + "## 効いている特徴量（上位15）" + NL + NL + NL.join(f"- {k}: {v / imp.sum():.1%}" for k, v in imp.head(15).items()))
T.loc[:, ["race_id", "combo", "date", "odds", "ret", "pm", "pmod", "ev", "in_B", "is_top"]].to_pickle(K + "out/meta_pred_v2.pkl")
print("done", best)
