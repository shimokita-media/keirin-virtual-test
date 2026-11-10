"""y4（2022/11/08〜2023/11/07）での事前登録「弱い3着」2つの判定（2026-11-11 0:50 登録・y4 の結果を見る前に固定。結果を見てから変えない）。
- 本命3連単×とても弱い3着：3連単 10倍以下 ×（G戦 または 9車立て）× 3着の選手の得点順位が6位以下（r2_pt_rank>=6）
- 400mの一番の目×弱い3着：一番の目 × 400mバンク（333m系・500m以外）× 欠場なし × 3着の得点順位5位以下（r2_pt_rank>=5）
合格＝95%の範囲（レース単位ブートストラップ）の下限95%以上 かつ 前半・後半とも100%超 かつ BH補正（この2つ、q=0.05）で有意
（2024年を見てから選んだ形なので、2024年の 114%・116% は判定に使わない）
使い方: python -I -X utf8 research/prereg_eval_y4_weak3.py 表.pkl sideの接尾辞 開始日 終了日 前半の最終日 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
fT, suf, d0, d1, half, outp = sys.argv[1:7]
P_ = lambda f: f if f.startswith(("C:", "/")) else K + f
T = pd.read_pickle(P_(fT)); T = T[T.date.between(d0, d1)].copy().reset_index(drop=True)
E = pd.read_pickle(K + f"out/side_entries{suf}.pkl"); ab = set(E[E.absent == 1].race_id)
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
w = ~T.venue.isin(S333 | S500)
G = {"本命3連単×とても弱い3着": T[(T.odds <= 10) & ((T.G == 1) | (T.entries_number >= 9)) & (T.r2_pt_rank >= 6)],
     "400mの一番の目×弱い3着": T[T.is_top & w & ~T.race_id.isin(ab) & (T.r2_pt_rank >= 5)]}
rng = np.random.default_rng(0)
def st(g):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    h1, h2 = g[g.date <= half].ret, g[g.date > half].ret; r = g.ret
    return dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                h1=h1.mean() if len(h1) else np.nan, h2=h2.mean() if len(h2) else np.nan, t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))))
R = {k: st(g) for k, g in G.items() if len(g) >= 2}
names = list(R); pv = np.array([R[k]["p"] for k in names]); m = 2; order = np.argsort(pv)
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = [f"# y4 での事前登録「弱い3着」2つの判定（{d0}〜{d1}・前半〜{half}）", "",
     f"{T.date.nunique()}日・{T.race_id.nunique():,}R。最終オッズ・確定の払戻・各100円。合格＝下限95%以上・前半後半とも100%超・BH補正（2つ）で有意。", "",
     "| 呼び名 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | t | p値（BH） |", "|---|---|---|---|---|---|---|---|"]
for k in names:
    s = R[k]; ok = s["lo"] >= 0.95 and s["h1"] > 1 and s["h2"] > 1 and bh[k]
    L.append(f"| {k} | {'**合格**' if ok else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%} / {s['h2']:.0%} | {s['t']:+.2f} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） |")
L += ["", f"参考：3連単全部 {T.ret.mean():.0%}／本命3連単×弱い3着（3着5位以下・登録T） {T[(T.odds <= 10) & ((T.G == 1) | (T.entries_number >= 9)) & (T.r2_pt_rank >= 5)].ret.mean():.0%}／400m・欠場なしの一番の目（登録Y） {T[T.is_top & w & ~T.race_id.isin(ab)].ret.mean():.0%}"]
open(P_(outp), "w", encoding="utf-8").write("\n".join(L) + "\n"); print("done", outp)
