"""統計的手法（おすすめ順・2026-11-09）
1) ベイズ推定：一番の目・3連単枠の「本当の回収率」の事後分布（ベイズ・ブートストラップ＝レース単位のディリクレ重み）→ P(回収率>100%)
2) 逐次検定（SPRT）：本番の記録で「何点たまれば決着がつくか」を、実際の払戻の形を使ってシミュレーション
3) 置換検定（並べ替え検定）：①一番の目は「同じ倍率帯のでたらめな目」より本当に良いか ②一番の目の中の分け方（U・V・W・X）の差は偶然か
使い方: python -I -X utf8 research/stat_methods.py 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
T = pd.read_pickle(K + "out/angle_base.pkl")[["race_id", "combo", "date", "odds", "ret", "in_B", "is_top", "entries_number", "venue", "cup_id", "day_index"]]
def per(d): return np.select([d.between("20251012", "20260114"), d >= "20260901"], ["③", "⑥"], "探す")
T["per"] = per(T.date)
rng = np.random.default_rng(0)
# ---------- 1) ベイズ推定
def bayes(g, B=4000, adj=1.0):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy() * adj, by["size"].to_numpy()
    w = rng.dirichlet(np.ones(len(by)), B)  # レースごとの重み
    post = (w @ s) / (w @ n)
    return post
P("# 統計的手法：ベイズ推定・逐次検定・置換検定" + NL)
P("## 1. ベイズ推定：本当の回収率の事後分布（最終オッズ・各100円）" + NL)
P("ベイズ・ブートストラップ（レース単位のディリクレ重み、事前はほぼ無情報）。「締切前の目減り5%」は払戻×0.95、「WINTICKET 1%還元」は＋1%。" + NL)
P("| 買い方 | 期間 | 点数 | 回収率（事後の中央値） | 95%の範囲 | P(>100%) | 目減り5%後 P(>100%) | 目減り5%＋還元1% P(>100%) |" + NL + "|---|---|---|---|---|---|---|---|")
for nm, G in (("一番の目", T[T.is_top]), ("3連単枠", T[T.in_B])):
    for lab, m in (("全期間（探すを含む）", G.per.notna()), ("見ていない期間だけ（③⑥）", G.per != "探す"), ("⑥だけ（直近）", G.per == "⑥")):
        g = G[m]; po = bayes(g); po95 = po * 0.95
        P(f"| {nm} | {lab} | {len(g)} | {np.median(po):.0%} | {np.percentile(po, 2.5):.0%}〜{np.percentile(po, 97.5):.0%} | **{(po > 1).mean():.0%}** | {(po95 > 1).mean():.0%} | {(po95 + 0.01 > 1).mean():.0%} |")
P(NL + "※「探す」を含む期間は法則を選ぶのに使ったので、良く見えて当然。判断は「見ていない期間だけ」で。" + NL)
# ---------- 2) 逐次検定（SPRT）
P("## 2. 逐次検定（SPRT）：本番の記録で何点あれば決着がつくか" + NL)
top_ret = T[T.is_top].ret.to_numpy(); sd = top_ret.std()
mu0, mu1, alpha, beta_ = 1.00, 1.20, 0.05, 0.20
A, Bnd = np.log((1 - beta_) / alpha), np.log(beta_ / (1 - alpha))
P(f"仮説：H0「本当の回収率100%（上乗せなし）」対 H1「120%」。間違えて合格にする確率5%、本物を見逃す確率20%。1点の標準偏差は一番の目の実績 {sd:.2f}。" + NL)
P(f"判定：累積の対数尤度比 = ({mu1}-{mu0})/σ² ×（払戻の合計 − 点数×{(mu0 + mu1) / 2:.2f}）が {A:.2f} を超えたら合格、{Bnd:.2f} を下回ったら不合格。" + NL)
def sim(true_mu, R=3000, cap=6000):
    base = top_ret / top_ret.mean()  # 実際の払戻の形（大穴の偏り）をそのまま使い、平均だけ合わせる
    ns, res = [], []
    for _ in range(R):
        x = rng.choice(base, cap) * true_mu
        llr = (mu1 - mu0) / sd ** 2 * (np.cumsum(x) - np.arange(1, cap + 1) * (mu0 + mu1) / 2)
        up = np.argmax(llr >= A) if (llr >= A).any() else cap; dn = np.argmax(llr <= Bnd) if (llr <= Bnd).any() else cap
        if up == cap and dn == cap: ns.append(cap); res.append("未決"); continue
        ns.append(min(up, dn) + 1); res.append("合格" if up < dn else "不合格")
    ns, res = np.array(ns), np.array(res)
    return ns, res
P("| 本当の回収率 | 合格になる割合 | 不合格になる割合 | 決着までの点数（中央値） | 90%が決着する点数 | 1日6点なら（中央値） |" + NL + "|---|---|---|---|---|---|")
for tm in (0.90, 1.00, 1.10, 1.20, 1.30):
    ns, res = sim(tm)
    P(f"| {tm:.0%} | {(res == '合格').mean():.0%} | {(res == '不合格').mean():.0%} | {int(np.median(ns))}点 | {int(np.percentile(ns, 90))}点 | 約{int(np.median(ns) / 6)}日 |")
P(NL + "※本番の記録（11/10〜）は締切前の倍率で選ぶので、そのぶん目減りする。判定は確定の払戻で行う。" + NL)
# ---------- 3) 置換検定
P("## 3. 置換検定（並べ替え検定）" + NL)
P("### 3-1. 一番の目は「同じ倍率帯・同じ車立てのでたらめな目」より良いか" + NL)
P("一番の目の各点と同じ倍率帯（対数で細かく80区分）・同じ車立てから、でたらめに1点ずつ選び直して回収率を出す、を5000回。" + NL)
T["ob"] = pd.cut(np.log(T.odds), 80, labels=False); T["nine"] = (T.entries_number >= 9).astype(int)
P("| 期間 | 一番の目 | でたらめ（平均） | でたらめが一番の目以上になった割合（p値） |" + NL + "|---|---|---|---|")
for lab, m in (("全期間", T.per.notna()), ("見ていない期間（③⑥）", T.per != "探す")):
    X = T[m]; tops = X[X.is_top]; pool = X.groupby(["ob", "nine"]).ret.apply(np.array).to_dict()
    keys = list(zip(tops.ob, tops.nine)); sims = np.zeros(5000)
    for (k, cnt) in pd.Series(keys).value_counts().items():
        arr = pool[k]; sims += rng.choice(arr, (5000, cnt)).sum(1)
    sims /= len(tops); act = tops.ret.mean()
    P(f"| {lab} | {act:.0%}（{len(tops)}点） | {sims.mean():.0%} | **{(sims >= act).mean():.4f}** |")
P(NL + "### 3-2. 一番の目の中の分け方の差は偶然か（ラベルをレース単位で並べ替え、5000回。見ていない期間③⑥だけ）" + NL)
M1 = pd.read_pickle(K + "out/meta_pred_v1.pkl")[["race_id", "combo", "ev"]].rename(columns={"ev": "ev1"})
tops = T[T.is_top & (T.per != "探す")].copy()
tops = tops.merge(M1, on=["race_id", "combo"], how="left")
RA = pd.read_pickle(K + "out/side_races.pkl")[["race_id", "cup_id", "day_index"]]
E = pd.read_pickle(K + "out/side_entries.pkl"); E = E[E.absent == 0]
E["rk"] = pd.to_numeric(E["class"], errors="coerce") * 10 + pd.to_numeric(E.grp, errors="coerce"); nk = E.groupby("race_id").rk.nunique()
nd = RA.groupby("cup_id").day_index.max()
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
splits = {"U 級班2種類以上": tops.race_id.map(nk) >= 2, "V 最終日の前日": (tops.day_index == tops.cup_id.map(nd) - 1) & (tops.cup_id.map(nd) >= 3),
          "W 400mバンク": ~tops.venue.isin(S333 | S500), "X 機械v1の期待値≥1.0": tops.ev1 >= 1.0}
P("| 分け方 | 当てはまる | 当てはまらない | 差 | 並べ替えで差がこれ以上になった割合（p値） |" + NL + "|---|---|---|---|---|")
r = tops.ret.to_numpy()
for nm, mk in splits.items():
    mk = mk.to_numpy().astype(bool); d0 = r[mk].mean() - r[~mk].mean()
    perm = np.array([(lambda s: r[s].mean() - r[~s].mean())(rng.permutation(mk)) for _ in range(5000)])
    P(f"| {nm} | {r[mk].mean():.0%}（{mk.sum()}点） | {r[~mk].mean():.0%}（{(~mk).sum()}点） | {d0:+.0%} | **{(perm >= d0).mean():.3f}** |")
P(NL + "p値＝「本当は差がないのに、たまたまこれだけの差が出る確率」。0.05未満なら偶然とは言いにくい（ただし4つ試したので、BH補正なら最小のpが0.0125未満で有意）。")
print("done")
