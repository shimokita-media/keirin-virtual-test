"""★事前登録（y5）「ライン順×最下位級の3着」の判定（KNOWLEDGE.md 2026-11-11 18:00 の登録どおり。結果を見てから変えない）。
表（build_cache_period.py の出力＝angle_base 形式・確定オッズ300倍以下・L級除く）から：
  もと＝同じライン3人で先頭→番手→3番手（s01==1・s12==1・r0_pos==0・r1_pos==1・r2_pos==2）× r2_pt_rank>=7 × odds<=10
  L1＝もと全部
  L2＝もと ×（g_tf>0 または 当日の流れ30%以下）
  当日の流れ＝同じ場（venue）・同じ日（date）で race_no がそれより小さい、表にあるレースのうち、当たり目（ret>0）の1着がライン先頭（r0_pos==0）だったレースの割合
            （300倍以下に当たり目がないレースは「先頭の勝ちでない」に数える）。前のレースが1つ以上あり、割合が0.3以下
合格（それぞれ）：95%の範囲（レース単位ブートストラップ4,000回・種0）の下限95%以上／前半・後半とも100%超／BH（m=2、q=0.05、p＝ブートストラップで100%以下になる割合）
使い方: python -I -X utf8 research/prereg_eval_y5_lo.py 表.pkl 開始日 終了日 前半の最終日 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
fT, d0, d1, half, outp = sys.argv[1:6]
P_ = lambda f: f if f.startswith(("C:", "/")) else K + f
d = pd.read_pickle(P_(fT)); d = d[d.date.between(d0, d1) & (d.odds <= 300)].copy().reset_index(drop=True)
d["hit"] = (d.ret > 0).astype(float)
W = d[d.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
R = d.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
R["lw"] = R.race_id.map(W).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R = R.set_index("race_id")
d["flow"] = d.race_id.map(R.flow); d["n_prev"] = d.race_id.map(R.n_prev)
base = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.r2_pt_rank >= 7) & (d.odds <= 10)]
lowf = (base.n_prev >= 1) & (base.flow <= 0.3)
G = {"L1 ライン順×最下位級の3着（全部）": base, "L2 ライン順×最下位級の3着×（3連複から見て割安 または 流れ30%以下）": base[(base.g_tf > 0) | lowf],
     "L3 ライン順×最下位級の3着×流れ30%以下（締切前に分かる情報だけ）": base[lowf]}  # L3 は 2026-11-11 19:00 に追加（y5 を見る前）。g_tf は締切1分前には分からないため
# L4（2026-11-11 20:40 に追加・y5 を見る前）：ライン順の機械。対象＝ライン順×確定オッズ15倍以下。research/lo_model_coef.json（y4・2024年・2025/2〜 で学んで固定）の「機械の見込み÷市場の見込み」が1.3以上
import json
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
q_ = 1 / d.odds; d["pn"] = q_ / q_.groupby(d.race_id).transform("sum")
lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy()
COEF = json.load(open(K + "research/lo_model_coef.json", encoding="utf-8"))
assert COEF["cols"] == ["const"] + LO_COLS, "係数の並びが特徴量と合わない"
lo["ratio"] = lo_ratio(COEF["coef"], lo)
G["L4 ライン順の機械（機械の見込み÷市場の見込み 1.3以上・締切前に分かる情報だけ）"] = lo[lo.ratio >= 1.3]
# L5（2026-11-11 21:10 に追加・y5 を見る前）：9車立て（entries_number>=9）×ライン順×3着の得点順位7位以下×確定オッズ20倍以下
G["L5 9車×ライン順×最下位級の3着×20倍以下（締切前に分かる情報だけ）"] = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.r2_pt_rank >= 7) & (d.entries_number >= 9) & (d.odds <= 20)]
rng = np.random.default_rng(0)
def st(g):
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1)
    h1, h2 = g[g.date <= half].ret, g[g.date > half].ret; r = g.ret
    return dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                h1=h1.mean() if len(h1) else np.nan, h2=h2.mean() if len(h2) else np.nan, sd=r.std(), t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))))
R_ = {k: st(g) for k, g in G.items() if len(g) >= 2}
names = list(R_); pv = np.array([R_[k]["p"] for k in names]); m = 5; order = np.argsort(pv)  # L1〜L5 の5つ
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = [f"# 事前登録（y5）「ライン順×最下位級の3着」の判定（{d0}〜{d1}・前半〜{half}）", "",
     f"{d.date.nunique()}日・{d.race_id.nunique():,}R。最終オッズ・確定の払戻・各100円。合格＝下限95%以上・前半後半とも100%超・BH（m=5）で有意。L2 の「3連複から見て割安」は確定オッズで作るので締切前には使えない（本番で使えるのは L1・L3・L4・L5）。", "",
     "| 候補 | 判定 | 回収率 | 点数・当たり | 95%の範囲 | 前半 / 後半 | 標準偏差・t | p値（BH） |", "|---|---|---|---|---|---|---|---|"]
for k in G:
    if k not in R_: L.append(f"| {k} | 判定不可（{len(G[k])}点） | − | − | − | − | − | − |"); continue
    s = R_[k]; ok = s["lo"] >= 0.95 and s["h1"] > 1 and s["h2"] > 1 and bh[k]
    L.append(f"| {k} | {'**合格**' if ok else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['h1']:.0%} / {s['h2']:.0%} | {s['sd']:.2f}・{s['t']:+.2f} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） |")
rest = base[~((base.g_tf > 0) | lowf)]
L += ["", f"参考（合否に使わない）：L2 に当たらない残り {rest.ret.mean() if len(rest) else float('nan'):.0%}（{len(rest)}点）／3連複から見て割安だけ {base[base.g_tf > 0].ret.mean():.0%}（{int((base.g_tf > 0).sum())}点）／流れ30%以下だけ {base[lowf].ret.mean() if lowf.sum() else float('nan'):.0%}（{int(lowf.sum())}点）／3連単全部 {d.ret.mean():.0%}"]
open(P_(outp), "w", encoding="utf-8").write(NL.join(L) + NL); print("done", outp)
