"""★事前登録「一番の目×割高な目を外す」の判定（KNOWLEDGE.md 2026-11-11 2:25 の登録どおり。結果を見てから変えない）。
対象：一番の目 × 確定オッズ30倍以下 × 次の7つのどれにも当たらない目（定義は research/avoid_stack.py と同じ）
 欠場ありのレース／一番人気3倍以下／1着が得点1位／1着が休み明け（中21日以上）／3着が新人（tgap≦1）／決勝のライン3人／準決勝の番手→先頭
合格＝95%の範囲（レース単位ブートストラップ）の下限95%以上 かつ 前半・後半とも100%超 かつ BH補正（m=1）で有意
使い方: python -I -X utf8 research/prereg_eval_y4_avoid.py 表.pkl sideの接尾辞 開始日 終了日 前半の最終日 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
fT, suf, d0, d1, half, outp = sys.argv[1:7]
P_ = lambda f: f if f.startswith(("C:", "/")) else K + f
T = pd.read_pickle(P_(fT)); T = T[T.date.between(d0, d1)].copy().reset_index(drop=True)
T["fav"] = T.groupby("race_id").odds.transform("min")
E = pd.read_pickle(K + f"out/side_entries{suf}.pkl"); R = pd.read_pickle(K + f"out/side_races{suf}.pkl").drop_duplicates("race_id")
E = E.merge(R[["race_id", "date", "cup_id"]], on="race_id", how="left")
ab = set(E[E.absent == 1].race_id)
EA = E[E.absent != 1].copy()
EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
EA["term"] = pd.to_numeric(EA.term, errors="coerce"); EA["ym"] = EA.date.str[:6]; EA["tgap"] = EA.groupby("ym").term.transform("max") - EA.term
EA["d"] = pd.to_datetime(EA.date)
cup = EA.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
cup["rest"] = (cup["min"] - cup.groupby("player_id")["max"].shift()).dt.days - 1
EA = EA.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
look = EA.set_index(["race_id", "number"])
top = T[T.is_top & (T.odds <= 30)].copy()
for j, nm in ((0, "a"), (2, "c")):
    sub = look.reindex(list(zip(top.race_id, top.combo.str.split("-").str[j].astype(int))))
    top[f"{nm}_ptr"] = sub.ptr.to_numpy(); top[f"{nm}_rest"] = sub.rest.to_numpy(); top[f"{nm}_tgap"] = sub.tgap.to_numpy()
rt = top.race_type.fillna("").astype(str)
bad = (top.race_id.isin(ab) | (top.fav <= 3) | (top.a_ptr == 1) | (top.a_rest >= 21) | (top.c_tgap <= 1)
       | (rt.str.contains("決勝") & ~rt.str.contains("準") & (top.s01 == 1) & (top.s12 == 1))
       | (rt.str.contains("準決勝") & (top.r0_pos == 1) & (top.r1_pos == 0) & (top.s01 == 1)))
G = top[~bad]
rng = np.random.default_rng(0)
def st(g):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    h1, h2 = g[g.date <= half].ret, g[g.date > half].ret; r = g.ret
    return dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                h1=h1.mean() if len(h1) else np.nan, h2=h2.mean() if len(h2) else np.nan, sd=r.std(), t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))))
L = [f"# 事前登録「一番の目×割高な目を外す」の判定（{d0}〜{d1}・前半〜{half}）", "",
     f"{T.date.nunique()}日・{T.race_id.nunique():,}R。最終オッズ・確定の払戻・各100円。合格＝下限95%以上・前半後半とも100%超・BH補正（m=1）で有意。", ""]
if len(G) < 2:
    L.append(f"点数が足りない（{len(G)}点）＝判定不可")
else:
    s = st(G); ok = s["lo"] >= 0.95 and s["h1"] > 1 and s["h2"] > 1 and s["p"] <= 0.05
    L += ["| 呼び名 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | 標準偏差・t | p値 |", "|---|---|---|---|---|---|---|---|",
          f"| 一番の目×割高な目を外す | {'**合格**' if ok else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%} / {s['h2']:.0%} | {s['sd']:.2f}・{s['t']:+.2f} | {s['p']:.3f} |"]
    rest = top[bad]
    L += ["", f"参考（合否に使わない）：30倍以下の一番の目 全部 {top.ret.mean():.0%}（{len(top)}点）／外した側 {rest.ret.mean() if len(rest) else float('nan'):.0%}（{len(rest)}点）／一番の目 全部 {T[T.is_top].ret.mean():.0%}／3連単全部 {T.ret.mean():.0%}"]
open(P_(outp), "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
