"""インタビューの機械学習を別の期間で確かめる（探す段階の確認。合否の判定ではない。⑥ 9/1〜 は使わない）。
作り方は research/interview_ml.py と同じ（打ち消しを数えない hit()、市場＝最終の3連単の確率を出発点 init_score にした補正）。
- 学習：2026/2/1〜4/14。確認：2026/7/5〜7/31
- 木の数は学習期間の中だけで決める：2/1〜3/24 で学び 3/25〜4/14 で止めどころを決め、その本数で 2/1〜4/14 全部で学び直す
  （確認期間＝7月では early stopping しない）
- 「全部入り」「倍率だけ」「倍率＋話の有無・長さ（言葉の中身なし）」を同じ分け方で比べる
- 取り込み中のローカルDBに大きな読み込みをしないため、インタビューは日ごと・race_id/cup_id 指定（索引で引く短いクエリ）で取り、
  out/interview_ml_jul_cache.pkl に保存して再利用する
使い方: python -I -X utf8 research/interview_ml_jul.py reports/interview_ml_jul.md"""
import sys, os, json, time, sqlite3, numpy as np, pandas as pd, lightgbm as lgb
K = "C:/Users/take0/.claude/keirin/"
outp = sys.argv[1] if len(sys.argv) > 1 else "reports/interview_ml_jul.md"
S0, ES_START, TR_END, VA_START, VA_END = "20260201", "20260325", "20260414", "20260705", "20260731"
CACHE = K + "out/interview_ml_jul_cache.pkl"
OUT = open(K + outp if not outp.startswith(("C:", "/")) else outp, "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
G = {"怪我": ["腰", "痛", "ケガ", "怪我", "落車"], "体調": ["体調", "風邪", "疲れ", "疲労"],
     "状態悪": ["重い", "重かった", "悪い", "悪かった", "良くない", "よくない", "本調子", "不安", "迷走", "決まらない", "戻っていない", "戻ってない"],
     "苦戦": ["苦しい", "きつい", "一杯", "いっぱい", "脚がない", "ダメ", "だめ"], "苦手": ["嫌い", "苦手"],
     "好調": ["良い", "良かった", "悪くない", "調子がいい", "状態はいい", "状態がいい", "感じはいい", "感触はいい", "軽い", "軽かった", "仕上が", "手応え", "好調", "自信"],
     "得意": ["得意", "好き", "相性"]}
_src = open(K + "research/interview_eval.py", encoding="utf-8").read()
exec(_src[_src.index("import re"): _src.index("def score")])  # 打ち消しを数えない hit()（事前登録I と同じ）
def answers(qa):
    try: return " ".join(t.get("answer", "") for t in json.loads(qa))
    except Exception: return ""

RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")[["race_id", "date", "cup_id", "day_index"]]
inper = lambda d: d.between(S0, TR_END) | d.between(VA_START, VA_END)
# レース後インタビューは同じ開催の前の日の分も使うので、開催の初日から取る
cups = set(RA[inper(RA.date)].cup_id)
RQ = RA[RA.cup_id.isin(cups)]

# ---- インタビューを日ごとに短いクエリで取る（取り込みの邪魔をしない） ----
if os.path.exists(CACHE):
    IV, RI = pd.read_pickle(CACHE)
else:
    con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
    ivs, ris = [], []
    for d, g in RQ.groupby("date"):
        ids = g.race_id.tolist()
        ris += con.execute("SELECT race_id, player_id, qa_json FROM result_interviews WHERE race_id IN (%s)" % ",".join("?" * len(ids)), ids).fetchall()
        time.sleep(0.05)
    cl = sorted(cups)
    for i in range(0, len(cl), 20):
        c = cl[i:i + 20]
        ivs += con.execute("SELECT cup_id, player_id, qa_json FROM interviews WHERE kind='前検' AND cup_id IN (%s)" % ",".join("?" * len(c)), c).fetchall()
        time.sleep(0.05)
    con.close()
    IV = pd.DataFrame(ivs, columns=["cup_id", "player_id", "qa_json"]); RI = pd.DataFrame(ris, columns=["race_id", "player_id", "qa_json"])
    pd.to_pickle((IV, RI), CACHE)

E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id"]].drop_duplicates(["race_id", "number"])
E = E.merge(RA, on="race_id"); E = E[inper(E.date)]
IV["t_pre"] = IV.qa_json.map(answers)
E = E.merge(IV[["cup_id", "player_id", "t_pre"]], on=["cup_id", "player_id"], how="left")
RI = RI.merge(RA, on="race_id"); RI["txt"] = RI.qa_json.map(answers)
pv = E[["race_id", "cup_id", "day_index", "player_id"]].merge(RI[["cup_id", "player_id", "day_index", "txt"]].rename(columns={"day_index": "d_iv"}), on=["cup_id", "player_id"])
pv = pv[pv.d_iv < pv.day_index].sort_values("d_iv").groupby(["race_id", "player_id"]).txt.agg(" ".join).rename("t_post").reset_index()
E = E.merge(pv, on=["race_id", "player_id"], how="left")
F = []
for src in ("pre", "post"):
    t = E[f"t_{src}"].fillna("")
    E[f"has_{src}"] = (t != "").astype(int); F.append(f"has_{src}")
    E[f"len_{src}"] = t.str.len(); F.append(f"len_{src}")
    for g, ws in G.items():
        E[f"{g}_{src}"] = t.map(lambda s: sum(1 for w in ws if hit(s, w))); F.append(f"{g}_{src}")
RF = E.set_index(["race_id", "number"])[F]
T = pd.read_pickle(K + "out/angle_base_full.pkl")[["race_id", "combo", "date", "p", "odds", "ret"]]
T = T[inper(T.date)].copy().reset_index(drop=True)
T = T[T.race_id.isin(set(E[(E.has_pre + E.has_post) > 0].race_id))].reset_index(drop=True)  # インタビューのあるレースだけ
T["pm"] = T.p / T.groupby("race_id").p.transform("sum")
T["init"] = np.log(T.pm.clip(1e-7, 1 - 1e-7) / (1 - T.pm.clip(1e-7, 1 - 1e-7)))
nums = T.combo.str.split("-", expand=True).astype(int)
X = []
for k in range(3):
    f = RF.reindex(list(zip(T.race_id, nums[k]))).to_numpy(); X.append(pd.DataFrame(f, columns=[f"r{k}_{c}" for c in F], index=T.index))
T = pd.concat([T] + X, axis=1); FX = [c for c in T.columns if c[:2] in ("r0", "r1", "r2") and c[2] == "_"]
T["lodds"] = np.log(T.odds); FX = FX + ["lodds"]
T["y"] = (T.ret > 0).astype(int)
tr, va = T[T.date <= TR_END], T[T.date >= VA_START]
tr_a, tr_b = tr[tr.date < ES_START], tr[tr.date >= ES_START]

# 月ごとのそろい具合（インタビューの件数）
RIm = RI.assign(m=RI.date.str[:6]).groupby("m").agg(件数=("player_id", "size"), レース=("race_id", "nunique"), 日=("date", "nunique"))
P("# インタビューの機械学習を7月で確かめる（探す段階の確認。合否の判定ではない）" + NL)
P(f"- 学習 {S0}〜{TR_END}（木の数は {S0}〜{(pd.Timestamp(ES_START) - pd.Timedelta(days=1)):%Y%m%d} で学び {ES_START}〜{TR_END} で決め、全部で学び直し）、確認 {VA_START}〜{VA_END}（確認期間では止めない）")
P(f"- インタビューのあるレース：学習 {tr.race_id.nunique():,}R・{len(tr):,}組、確認 {va.race_id.nunique():,}R・{len(va):,}組。特徴量 {len(FX)} 個")
P(f"- 作り方は research/interview_ml.py と同じ（打ち消しを数えない hit()、最終の3連単300倍以下から作った市場の見込みを出発点にした補正）。⑥（9/1〜）は使っていない" + NL)
P("レース後インタビューの件数（取り込んだ分、開催の初日から）：" + NL)
P("| 月 | 件数 | レース | 日 |" + NL + "|---|---|---|---|")
for m, r in RIm.iterrows(): P(f"| {m} | {r.件数:,} | {r.レース:,} | {r.日} |")
P(f"{NL}前検日インタビュー：{len(IV):,}件（{IV.cup_id.nunique()}開催）{NL}")

prm = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=500, feature_fraction=0.7, lambda_l2=10, verbose=-1, seed=0)
def ll(p, y): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def fit(cols):
    a = lgb.Dataset(tr_a[cols], tr_a.y, init_score=tr_a.init); b = lgb.Dataset(tr_b[cols], tr_b.y, init_score=tr_b.init)
    m0 = lgb.train(prm, a, 1000, valid_sets=[b], callbacks=[lgb.early_stopping(50, verbose=False)])
    n = max(m0.best_iteration, 1)
    m = lgb.train(prm, lgb.Dataset(tr[cols], tr.y, init_score=tr.init), n)
    return 1 / (1 + np.exp(-(m.predict(va[cols], raw_score=True) + va.init.to_numpy()))), n, m
y = va.y.to_numpy(); rid = va.race_id.to_numpy(); l0 = ll(va.pm.to_numpy(), y)
LF = [c for c in FX if "_len_" in c or "_has_" in c]
MODELS = [("全部入り", FX), ("倍率だけ", ["lodds"]), ("倍率＋話の有無・長さ（言葉の中身なし）", ["lodds"] + LF)]
res = {}
for lab, cols in MODELS:
    pn, n, m = fit(cols); res[lab] = (pn, n, m, ll(pn, y))
def tstat(s): return s.mean() / (s.std() / np.sqrt(len(s)))
P("## 当てる力（7月、レースごとの対数損失の差。＋なら市場より良い）" + NL)
P("| モデル | 木の数 | 市場からの改善（平均） | t | レース数 |" + NL + "|---|---|---|---|---|")
for lab, _ in MODELS:
    d = pd.Series(l0 - res[lab][3]).groupby(rid).sum()
    P(f"| {lab} | {res[lab][1]} | {d.mean():+.4f} | **{tstat(d):+.2f}** | {len(d):,} |")
P(NL + "## モデルどうしの差（7月、＋なら左が良い）" + NL)
P("| 比べ方 | 平均 | t |" + NL + "|---|---|---|")
for a, b in (("全部入り", "倍率だけ"), ("全部入り", "倍率＋話の有無・長さ（言葉の中身なし）"), ("倍率＋話の有無・長さ（言葉の中身なし）", "倍率だけ")):
    d = pd.Series(res[b][3] - res[a][3]).groupby(rid).sum()
    P(f"| {a} − {b} | {d.mean():+.4f} | **{tstat(d):+.2f}** |")
P(NL + "## 補正後の見込み×倍率で選んだ組（7月・最終オッズ・各100円。参考）" + NL)
P("| モデル | 選び方 | 点数 | 当たり | 回収率 | 1点の標準偏差 | t（100%との差） |" + NL + "|---|---|---|---|---|---|---|")
for lab, _ in MODELS:
    pn = res[lab][0]
    for th in (1.0, 1.1, 1.2):
        z = va[pn * va.odds.to_numpy() >= th]
        if len(z): r = z.ret; P(f"| {lab} | ≥ {th} | {len(z):,} | {(z.ret > 0).sum()} | {r.mean():.0%} | {r.std():.2f} | {(r.mean() - 1) / (r.std() / np.sqrt(len(r))):+.2f} |")
r = va.ret
P(f"| 参考 | 全部 | {len(va):,} | {(va.ret > 0).sum()} | {r.mean():.0%} | {r.std():.2f} | — |")
imp = pd.Series(res["全部入り"][2].feature_importance("gain"), index=FX).sort_values(ascending=False)
P(NL + "全部入りで効いた特徴量：" + "、".join(f"{k} {v / max(imp.sum(), 1e-9):.0%}" for k, v in imp.head(10).items()))
print("done", len(tr), len(va))
