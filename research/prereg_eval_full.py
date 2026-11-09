"""事前登録 R・S・T・Y・Z の判定（KNOWLEDGE.md に書いた条件そのまま。結果を見てから変えない）
使い方: python -I -X utf8 research/prereg_eval_full.py 表.pkl sideの接尾辞 予測.pkl 開始日 終了日 前半の最終日 出力.md
- 表.pkl：research/build_cache_period.py の出力（angle_base 形式・最終オッズ・確定の払戻）
- 予測.pkl：research/z_predict_period.py の出力（p_v2＝事前登録Zの登録モデル、p_D＝今使う機械D）"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
fT, suf, fZ, d0, d1, half, outp = sys.argv[1:8]
P_ = lambda f: f if f.startswith(("C:", "/")) else K + f
OUT = open(P_(outp), "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
T = pd.read_pickle(P_(fT)); T = T[T.date.between(d0, d1)].copy()
Z = pd.read_pickle(P_(fZ)); Z = Z[Z.date.between(d0, d1)].copy()
E = pd.read_pickle(K + f"out/side_entries{suf}.pkl"); ab = set(E[E.absent == 1].race_id)
B = T[T.in_B]; top = T[T.is_top]; rt = top.race_type.fillna("").astype(str)
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
groups = {
    "R 3連単枠": B, "R 一番の目": top,
    "S 一番の目×準決勝": top[rt.str.contains("準決勝")],
    "T 10倍以下×(G戦か9車)×3着得点5位以下": T[(T.odds <= 10) & ((T.G == 1) | (T.entries_number >= 9)) & (T.r2_pt_rank >= 5)],
    "Y 一番の目×400m×欠場なし": top[~top.venue.isin(S333 | S500) & ~top.race_id.isin(ab)],
    "Z 機械v2：当たる確率≥10%×期待値≥0.9": Z[(Z.p_v2 >= 0.10) & (Z.p_v2 * Z.odds >= 0.9)],
}
ref = {
    "（参考）Z を機械Dで": Z[(Z.p_D >= 0.10) & (Z.p_D * Z.odds >= 0.9)],
    "（参考）一番の目×決勝": top[rt.str.contains("決勝") & ~rt.str.contains("準")],
    "（参考）一番の目×333m系": top[top.venue.isin(S333)], "（参考）一番の目×500m": top[top.venue.isin(S500)],
    "（参考）3連単を全部（300倍以下）": T,
}
rng = np.random.default_rng(0)
def st(g):
    if len(g) < 2: return None
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (2000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    w = rng.dirichlet(np.ones(len(by)), 4000); post = (w @ s) / (w @ n)
    r = g.ret; h1, h2 = g[g.date <= half].ret, g[g.date > half].ret
    return dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), sd=r.std(),
                t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))) if r.std() > 0 else np.nan, pp=(post > 1).mean(), pp95=(post * 0.95 > 1).mean(),
                h1=h1.mean() if len(h1) else np.nan, h2=h2.mean() if len(h2) else np.nan, n1=len(h1), n2=len(h2), hit=(r > 0).mean())
def verdict(nm, s):
    if s is None: return "判定不可（点数なし）"
    if nm.startswith("R") or nm.startswith("T"): ok = s["lo"] >= 0.95 and s["h1"] > 1 and s["h2"] > 1
    elif nm.startswith("S"): ok = s["roi"] >= 1.5 and s["lo"] >= 0.95 and s["hits"] >= 10
    elif nm.startswith("Y"): ok = s["roi"] >= 1.2 and s["lo"] >= 1.0 and s["h1"] > 1 and s["h2"] > 1
    elif nm.startswith("Z"): ok = s["lo"] >= 0.95 and s["h1"] > 1 and s["h2"] > 1 and s["hit"] >= 0.15
    else: return ""
    return "**合格**" if ok else "不合格"
P(f"# 事前登録 R・S・T・Y・Z の判定（{d0}〜{d1}）" + NL)
P(f"{T.date.nunique()}日・{T.race_id.nunique():,}レース。最終オッズ・確定の払戻・各100円。前半＝〜{half}、後半＝{half}の翌日〜。条件は KNOWLEDGE.md の登録どおり。" + NL)
P("| 登録 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | 標準偏差・t | P(>100%)（目減り5%後） |" + NL + "|---|---|---|---|---|---|---|---|")
for nm, g in {**groups, **ref}.items():
    s = st(g)
    if s is None: P(f"| {nm} | − | − | {len(g)}点 | − | − | − | − |"); continue
    P(f"| {nm} | {verdict(nm, s)} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本（的中{s['hit']:.0%}） | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%}（{s['n1']}）/ {s['h2']:.0%}（{s['n2']}） | {s['sd']:.2f}・{s['t']:+.2f} | {s['pp']:.0%}（{s['pp95']:.0%}） |")
P(NL + "合格基準：R＝95%の範囲の下限95%以上かつ前半・後半とも100%超／S＝150%以上・下限95%以上・当たり10本以上／T＝下限95%以上かつ前半・後半とも100%超／Y＝120%以上・下限100%以上・前半後半とも100%超／Z＝下限95%以上・前半後半とも100%超・的中率15%以上")
P(NL + "## 月別" + NL + NL + "| 月 | 3連単全部 | 3連単枠 | 一番の目 | T | Y | Z（v2） |" + NL + "|---|---|---|---|---|---|---|")
for ym in sorted(T.date.str[:6].unique()):
    m = lambda g: g[g.date.str[:6] == ym]
    cells = [f"{m(T).ret.mean():.0%}"] + [f"{m(g).ret.mean():.0%}（{len(m(g))}）" if len(m(g)) else "−" for g in (B, top, groups["T 10倍以下×(G戦か9車)×3着得点5位以下"], groups["Y 一番の目×400m×欠場なし"], groups["Z 機械v2：当たる確率≥10%×期待値≥0.9"])]
    P(f"| {ym[:4]}/{ym[4:]} | " + " | ".join(cells) + " |")
print("done", outp)
