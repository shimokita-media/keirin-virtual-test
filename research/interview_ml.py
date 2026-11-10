"""インタビューを機械に学ばせる（探す期間の中だけで学習と確認。事前登録I の③⑥は使わない）。
市場（最終の3連単の確率）を出発点（init_score）にして、3人の選手のインタビューの特徴だけで補正を学ぶ LightGBM。
学習：2026/2/1〜5/31、確認：6/1〜8/31（どちらも探す期間）。確認で当てる力が上がるか（レースごとの対数損失の差・t値）と、
補正後の 見込み×倍率 で選んだ組の回収率を見る。良ければ、別の事前登録をしてから⑥（9/1〜）で確かめる。
使い方: python -I -X utf8 research/interview_ml.py 出力.md [学習の終わり 確認の終わり]"""
import sys, json, sqlite3, numpy as np, pandas as pd, lightgbm as lgb
K = "C:/Users/take0/.claude/keirin/"
outp = sys.argv[1]; _a = [x for x in sys.argv[2:] if not x.startswith("--")]; TR_END, VA_END = (_a[0], _a[1]) if len(_a) > 1 else ("20260531", "20260831")
S0 = "20260201"  # 学習用の表（angle_base_full）は 2026/1/15〜31 が抜けている
OUT = open(K + outp if not outp.startswith(("C:", "/")) else outp, "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
G = {"怪我": ["腰", "痛", "ケガ", "怪我", "落車"], "体調": ["体調", "風邪", "疲れ", "疲労"],
     "状態悪": ["重い", "重かった", "悪い", "悪かった", "良くない", "よくない", "本調子", "不安", "迷走", "決まらない", "戻っていない", "戻ってない"],
     "苦戦": ["苦しい", "きつい", "一杯", "いっぱい", "脚がない", "ダメ", "だめ"], "苦手": ["嫌い", "苦手"],
     "好調": ["良い", "良かった", "悪くない", "調子がいい", "状態はいい", "状態がいい", "感じはいい", "感触はいい", "軽い", "軽かった", "仕上が", "手応え", "好調", "自信"],
     "得意": ["得意", "好き", "相性"]}
_src = open(K + "research/interview_eval.py", encoding="utf-8").read()
exec(_src[_src.index("import re"): _src.index("def score")])  # 打ち消し（体調問題ない等）を数えない hit() を事前登録I と同じにする
def answers(qa):
    try: return " ".join(t.get("answer", "") for t in json.loads(qa))
    except Exception: return ""
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
IV = pd.read_sql("SELECT cup_id, player_id, qa_json FROM interviews WHERE kind='前検'", con)
RI = pd.read_sql("SELECT race_id, player_id, qa_json FROM result_interviews", con)
con.close()
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")[["race_id", "date", "cup_id", "day_index"]]
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0][["race_id", "number", "player_id"]].drop_duplicates(["race_id", "number"])
E = E.merge(RA, on="race_id"); E = E[E.date.between(S0, VA_END)]
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
T = T[T.date.between(S0, VA_END)].copy()
T = T[T.race_id.isin(set(E[(E.has_pre + E.has_post) > 0].race_id))]  # インタビューのあるレースだけ
T["pm"] = T.p / T.groupby("race_id").p.transform("sum")
T["init"] = np.log(T.pm.clip(1e-7, 1 - 1e-7) / (1 - T.pm.clip(1e-7, 1 - 1e-7)))
nums = T.combo.str.split("-", expand=True).astype(int)
X = []
for k in range(3):
    f = RF.reindex(list(zip(T.race_id, nums[k]))).to_numpy(); X.append(pd.DataFrame(f, columns=[f"r{k}_{c}" for c in F], index=T.index))
T = pd.concat([T] + X, axis=1); FX = [c for c in T.columns if c[:2] in ("r0", "r1", "r2") and c[2] == "_"]
T["lodds"] = np.log(T.odds); FX = FX + ["lodds"]
T["y"] = (T.ret > 0).astype(int)
tr, va = T[T.date <= TR_END], T[T.date > TR_END]
P("# インタビューを機械に学ばせる（市場からの補正だけを学ぶ）" + NL)
P(f"インタビューのあるレース：学習 {tr.race_id.nunique():,}R（{S0}〜{TR_END}）・確認 {va.race_id.nunique():,}R（〜{VA_END}）。特徴量 {len(FX)} 個（3人×前検/レース後×言葉の7グループ＋有無・長さ＋倍率）" + NL)
if (tr.race_id.nunique() < 300 or va.race_id.nunique() < 100) and "--force" not in sys.argv:
    P("**まだ材料が少ないので学習しない（学習300R・確認100R 以上で動かす）。過去分の取り込みが進んでから。**")
    print("too few", tr.race_id.nunique(), va.race_id.nunique()); sys.exit()
prm = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=500, feature_fraction=0.7, lambda_l2=10, verbose=-1, seed=0)
dtr = lgb.Dataset(tr[FX], tr.y, init_score=tr.init); dva = lgb.Dataset(va[FX], va.y, init_score=va.init)
m = lgb.train(prm, dtr, 1000, valid_sets=[dva], callbacks=[lgb.early_stopping(50, verbose=False)])
pn = 1 / (1 + np.exp(-(m.predict(va[FX], raw_score=True) + va.init.to_numpy())))
def ll(p, y): p = np.clip(p, 1e-7, 1 - 1e-7); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
d = pd.Series(ll(va.pm.to_numpy(), va.y.to_numpy()) - ll(pn, va.y.to_numpy())).groupby(va.race_id.to_numpy()).sum()
P(f"- 木の数（確認で止めた）：{m.best_iteration}")
P(f"- 当てる力（確認期間、レースごとの対数損失の差・＋なら機械が良い）：平均 {d.mean():+.4f}、**t={d.mean() / (d.std() / np.sqrt(len(d))):+.2f}**（{len(d):,}R）")
def fit(cols):
    a = lgb.Dataset(tr[cols], tr.y, init_score=tr.init); b = lgb.Dataset(va[cols], va.y, init_score=va.init)
    mm = lgb.train(prm, a, 1000, valid_sets=[b], callbacks=[lgb.early_stopping(50, verbose=False)])
    return 1 / (1 + np.exp(-(mm.predict(va[cols], raw_score=True) + va.init.to_numpy()))), mm.best_iteration
P(NL + "### インタビューの分だけ効いているか（同じ作り方で特徴量を減らしたモデルと比べる。＋なら全部入りが良い）")
P("| 比べる相手 | 木の数 | 相手の市場からの改善の t | 全部入り−相手 の平均 | t |" + NL + "|---|---|---|---|---|")
LF = [c for c in FX if "_len_" in c or "_has_" in c]
for lab, cols in (("倍率だけ", ["lodds"]), ("倍率＋話の有無・長さ（言葉の中身なし）", ["lodds"] + LF)):
    pb, bi = fit(cols)
    db = pd.Series(ll(va.pm.to_numpy(), va.y.to_numpy()) - ll(pb, va.y.to_numpy())).groupby(va.race_id.to_numpy()).sum()
    dd = pd.Series(ll(pb, va.y.to_numpy()) - ll(pn, va.y.to_numpy())).groupby(va.race_id.to_numpy()).sum()
    P(f"| {lab} | {bi} | {db.mean() / (db.std() / np.sqrt(len(db))):+.2f} | {dd.mean():+.4f} | **{dd.mean() / (dd.std() / np.sqrt(len(dd))):+.2f}** |")
va = va.assign(pn=pn)
P(NL + "| 選び方（確認期間） | 点数 | 当たり | 回収率 |" + NL + "|---|---|---|---|")
for th in (1.0, 1.1, 1.2, 1.3):
    z = va[va.pn * va.odds >= th]
    if len(z): P(f"| 補正後の見込み×倍率 ≥ {th} | {len(z):,} | {(z.ret > 0).sum()} | {z.ret.mean():.0%} |")
z = va[(va.pn >= 0.10) & (va.pn * va.odds >= 0.9)]
if len(z): P(f"| Z と同じ形（見込み≥10%×期待値≥0.9） | {len(z):,} | {(z.ret > 0).sum()} | {z.ret.mean():.0%} |")
P(f"| 参考：全部 | {len(va):,} | {(va.ret > 0).sum()} | {va.ret.mean():.0%} |")
imp = pd.Series(m.feature_importance("gain"), index=FX).sort_values(ascending=False)
P(NL + "効いた特徴量：" + "、".join(f"{k} {v / max(imp.sum(), 1e-9):.0%}" for k, v in imp.head(10).items()))
m.save_model(K + "research/interview_ml_draft.txt")
print("done", len(tr), len(va))
