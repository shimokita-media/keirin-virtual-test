"""y4（2022/11/08〜2023/11/07）での事前登録 U・V・W・Z の判定（KNOWLEDGE.md の登録どおり。結果を見てから変えない）。BH補正つき。
X（機械v1×期待値≥1.0）は research/x_predict_period.py の予測（v1 の選手の癖は out/v1_tend.pkl＝2025/2〜2026/6/15 で作った表。v1 の予測を完全に再現できることを確認済み）を9番目の引数で渡すと判定する。
使い方: python -I -X utf8 research/prereg_eval_y4.py 表.pkl sideの接尾辞 予測.pkl 開始日 終了日 前半の最終日 出力.md [v1の予測.pkl]
（表・予測は research/prereg_full_2024.py で作る：... 20221108 20231107 20230507 y4 --no-check）"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
fT, suf, fZ, d0, d1, half, outp = sys.argv[1:8]
fX = sys.argv[8] if len(sys.argv) > 8 else None
P_ = lambda f: f if f.startswith(("C:", "/")) else K + f
OUT = open(P_(outp), "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
T = pd.read_pickle(P_(fT)); T = T[T.date.between(d0, d1)].copy().reset_index(drop=True)
Z = pd.read_pickle(P_(fZ)); Z = Z[Z.date.between(d0, d1)].copy()
E = pd.read_pickle(K + f"out/side_entries{suf}.pkl"); E = E[E.absent == 0].copy()
E["rk"] = pd.to_numeric(E["class"], errors="coerce") * 10 + pd.to_numeric(E.grp, errors="coerce")
nk = E.groupby("race_id").rk.nunique()
RA = pd.read_pickle(K + f"out/side_races{suf}.pkl").drop_duplicates("race_id"); nd = RA.groupby("cup_id").day_index.max()
top = T[T.is_top].copy(); top["nkind"] = top.race_id.map(nk); top["nd"] = top.cup_id.map(nd)
rt = top.race_type.fillna("").astype(str)
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
U = top[top.nkind >= 2]; U_rest = top[top.nkind == 1]
V = top[(top.nd >= 3) & (top.day_index == top.nd - 1)]; V_noS = V[~rt.loc[V.index].str.contains("準決勝")]
W = top[~top.venue.isin(S333 | S500)]; W_333 = top[top.venue.isin(S333)]
Zg = Z[(Z.p_v2 >= 0.10) & (Z.p_v2 * Z.odds >= 0.9)]
rng = np.random.default_rng(0)
def st(g):
    if len(g) < 2: return None
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    h1, h2 = g[g.date <= half].ret, g[g.date > half].ret
    return dict(n=len(g), roi=g.ret.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                h1=h1.mean() if len(h1) else np.nan, h2=h2.mean() if len(h2) else np.nan, hit=(g.ret > 0).mean(), hits=int((g.ret > 0).sum()))
res = {"U 一番の目×級班2種類以上": (st(U), lambda s: s["roi"] > (U_rest.ret.mean() if len(U_rest) else 9)),
       "V 一番の目×最終日の前日（3日制以上）": (st(V), lambda s: (V_noS.ret.mean() if len(V_noS) else 0) > 1.0),
       "W 一番の目×400mバンク": (st(W), lambda s: s["roi"] > (W_333.ret.mean() if len(W_333) else 9)),
       "Z 機械v2：当たる確率≥10%×期待値≥0.9": (st(Zg), lambda s: s["hit"] >= 0.15)}
if fX:
    XP = pd.read_pickle(P_(fX)); XP = XP[XP.date.between(d0, d1) & XP.is_top]
    Xg, X_rest = XP[XP.p_v1 * XP.odds >= 1.0], XP[XP.p_v1 * XP.odds < 1.0]
    res["X 一番の目×機械v1の期待値≥1.0"] = (st(Xg), lambda s: s["roi"] > (X_rest.ret.mean() if len(X_rest) else 9))
X_NOHALF = "X 一番の目×機械v1の期待値≥1.0"  # X の登録は「下限95%以上」と「期待値<1.0 の一番の目より高い」（前半後半の条件はない）
# BH補正（片側：本当の回収率≦100% という仮説の p値＝ブートストラップで 100% 以下になる割合）。X を後で足すときは m=5 にする
names = [k for k in res if res[k][0] is not None]; pv = np.array([res[k][0]["p"] for k in names]); m = 5  # U・V・W・X・Z の5つで補正（X 未判定でも数に入れる＝厳しめ）
order = np.argsort(pv); bh_ok = np.zeros(len(names), bool)
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0)
for i, j in enumerate(order):
    if i < kmax: bh_ok[j] = True
P(f"# y4 での事前登録 U・V・W・Z の判定（{d0}〜{d1}・前半〜{half}）" + NL)
P(f"{T.date.nunique()}日・{T.race_id.nunique():,}R。最終オッズ・確定の払戻・各100円。合格＝登録の基準（95%の範囲の下限95%以上・前半後半とも100%超・それぞれの追加条件）を満たし、かつ BH補正（U・V・W・X・Z の5つ、q=0.05）で有意。X は v1 の予測を渡したときだけ判定（渡さないと未判定のまま、補正の数には入れる）。" + NL)
P("| 登録 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | 追加条件 | p値（BH） |" + NL + "|---|---|---|---|---|---|---|---|")
for i, k in enumerate(names):
    s, extra = res[k]; ex = bool(extra(s)); base_ok = s["lo"] >= 0.95 and (k == X_NOHALF or (s["h1"] > 1 and s["h2"] > 1))
    P(f"| {k} | {'**合格**' if (base_ok and ex and bh_ok[i]) else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本（的中{s['hit']:.0%}） | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%} / {s['h2']:.0%} | {'満たす' if ex else '満たさない'} | {s['p']:.3f}（{'有意' if bh_ok[i] else '有意でない'}） |")
P(NL + f"参考：一番の目 全部 {top.ret.mean():.0%}（{len(top)}点）／級班1種類 {U_rest.ret.mean() if len(U_rest) else float('nan'):.0%}／最終日の前日から準決勝を除く {V_noS.ret.mean() if len(V_noS) else float('nan'):.0%}／333m系 {W_333.ret.mean() if len(W_333) else float('nan'):.0%}／3連単全部 {T.ret.mean():.0%}")
if not fX: P("| X 一番の目×機械v1×期待値≥1.0 | 未判定 | v1 の予測（research/x_predict_period.py）を9番目の引数で渡すと判定する |")
print("done", outp)
