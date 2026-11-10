"""y5（2021/11/08〜2022/11/07）で判定する3連単の候補（reports/y5_prereg_draft.md の下書き）の判定スクリプト。**まだ正式な登録ではない**：
ユーザーが下書きを確認して KNOWLEDGE.md に ★事前登録 として書いてから、y5 に使う。それまでは使い終わった期間（2024年）で数字が再現するかの確認だけに使う。
候補（下書きの ①②③。④ワイド枠は別のスクリプト）：
  ① 一番の目（全体）           合格＝下限95%以上・前半後半とも100%超・BH で有意
  ② 400m・欠場なしの一番の目   合格＝回収率120%以上・下限100%以上・前半後半とも100%超・333m系の一番の目より高い・BH で有意（分岐A のときだけ）
  ③ 本命3連単×弱い3着（T）    合格＝下限95%以上・前半後半とも100%超・BH で有意
BH の p値＝レース単位ブートストラップで回収率が100%以下になる割合（y4 の登録と同じ決まり）。m は引数で渡す（登録で決めた数。未判定のものも数に入れる）
使い方: python -I -X utf8 research/prereg_eval_y5.py 表.pkl sideの接尾辞 開始日 終了日 前半の最終日 m 出力.md [--no-Y]"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
fT, suf, d0, d1, half, m, outp = args[:7]; m = int(m); USE_Y = "--no-Y" not in sys.argv
P_ = lambda f: f if f.startswith(("C:", "/")) else K + f
T = pd.read_pickle(P_(fT)); T = T[T.date.between(d0, d1)].copy().reset_index(drop=True)
E = pd.read_pickle(K + f"out/side_entries{suf}.pkl"); ab = set(E[E.absent == 1].race_id)
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
top = T[T.is_top]
G = {"① 一番の目（全体）": top}
if USE_Y: G["② 400m・欠場なしの一番の目"] = top[~top.venue.isin(S333 | S500) & ~top.race_id.isin(ab)]
G["③ 本命3連単×弱い3着"] = T[(T.odds <= 10) & ((T.G == 1) | (T.entries_number >= 9)) & (T.r2_pt_rank >= 5)]
rng = np.random.default_rng(0)
def st(g):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    h1, h2 = g[g.date <= half].ret, g[g.date > half].ret; r = g.ret
    return dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                h1=h1.mean() if len(h1) else np.nan, h2=h2.mean() if len(h2) else np.nan, sd=r.std(), t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))))
R = {k: st(g) for k, g in G.items() if len(g) >= 2}
names = list(R); pv = np.array([R[k]["p"] for k in names]); order = np.argsort(pv)
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
w333 = top[top.venue.isin(S333)].ret.mean() if len(top[top.venue.isin(S333)]) else 9
def ok(k, s):
    if k.startswith("①") or k.startswith("③"): base = s["lo"] >= 0.95 and s["h1"] > 1 and s["h2"] > 1
    else: base = s["roi"] >= 1.2 and s["lo"] >= 1.0 and s["h1"] > 1 and s["h2"] > 1 and s["roi"] > w333
    return base and bh[k]
L = [f"# y5 の3連単の候補の判定（{d0}〜{d1}・前半〜{half}・BH の m={m}）", "",
     f"{T.date.nunique()}日・{T.race_id.nunique():,}R。最終オッズ・確定の払戻・各100円。**下書きの条件**（正式な登録の後に y5 に使う）。", "",
     "| 候補 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | 標準偏差・t | p値（BH） |", "|---|---|---|---|---|---|---|---|"]
for k in G:
    if k not in R: L.append(f"| {k} | 判定不可（{len(G[k])}点） | − | − | − | − | − | − |"); continue
    s = R[k]
    L.append(f"| {k} | {'**合格**' if ok(k, s) else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%} / {s['h2']:.0%} | {s['sd']:.2f}・{s['t']:+.2f} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） |")
L += ["", f"参考：333m系の一番の目 {w333:.0%}／3連単全部 {T.ret.mean():.0%}"]
open(P_(outp), "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
