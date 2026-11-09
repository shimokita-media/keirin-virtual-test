"""事前登録Z の前向き確認：締切1分前の倍率で v2full を動かし、確定の払戻で精算（ANGLE_CACHE=out/angle_base_t1.pkl で実行）。以下は v2 の説明。v2（2026-11-09 17:35〜）：v1 と同じ特徴量づくり＋選手の癖を「1着」「3着以内」に分け、縮小を強め、設定とレース内の正規化を比べる。
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
mo = lgb.Booster(model_file=K + "research/meta_model_v2full.txt")
T["p"] = 1 / (1 + np.exp(-(mo.predict(T[mo.feature_name()], raw_score=True) + T.init.to_numpy())))
T["ev"] = T.p * T.odds
FIN = pd.read_pickle(K + "out/fresh8/tri.pkl")[["race_id", "combo", "odds"]].rename(columns={"odds": "fin"}) if False else None
import sqlite3
con = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True)
F = pd.read_sql("SELECT race_id, combo, odds AS fin, fetched_at FROM odds WHERE bet_type='3連単' AND phase='POST' AND substr(race_id,-8) >= '20261107'", con).sort_values("fetched_at").drop_duplicates(["race_id", "combo"], keep="last")
T = T.merge(F[["race_id", "combo", "fin"]], on=["race_id", "combo"], how="left")
rng = np.random.default_rng(0)
def cell(x):
    if not len(x): return "−（0点）"
    by = x.groupby("race_id").ret.agg(["sum", "size"]); w = rng.dirichlet(np.ones(len(by)), 3000); post = (w @ by["sum"].to_numpy()) / (w @ by["size"].to_numpy())
    return f"**{x.ret.mean():.0%}**（{len(x)}点・{x.race_id.nunique()}R・的中{(x.ret > 0).mean():.0%}・倍率の動き（1分前→最終）{(x.fin / x.odds).median() - 1:+.1%}・P>100% {(post > 1).mean():.0%}）"
P("# 事前登録Z を締切1分前の倍率で動かしたら（本番の記録・11/7〜）" + NL)
P(f"機械 v2full、特徴量は1分前の倍率から作成、精算は確定の払戻。{T.date.min()}〜{T.date.max()}・{T.race_id.nunique()}R。" + NL)
P("| 選び方 | 1分前で選んだ成績 |" + NL + "|---|---|")
for nm, m in (("★Z 当たる確率≥10%×期待値≥0.9", (T.p >= 0.10) & (T.ev >= 0.9)), ("当たる確率≥15%×期待値≥0.9", (T.p >= 0.15) & (T.ev >= 0.9)),
              ("期待値≥1.1", T.ev >= 1.1), ("一番の目（1分前）", T.is_top), ("3連単を全部（1分前の300倍以下）", T.odds > 0)):
    P(f"| {nm} | {cell(T[m])} |")
P(NL + "日ごとの Z：" + ", ".join(f"{d} {x.ret.mean():.0%}（{len(x)}点）" for d, x in T[(T.p >= 0.10) & (T.ev >= 0.9)].groupby("date")))
T[(T.p >= 0.10) & (T.ev >= 0.9)][["race_id", "combo", "date", "odds", "fin", "p", "ev", "ret"]].to_pickle(K + "out/z_forward_picks.pkl")
print("done")
