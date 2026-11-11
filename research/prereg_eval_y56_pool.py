"""★事前登録「5・6年目まとめて」の判定（2026-11-11 14:50 登録・y5/y6 の結果を見る前に固定。ユーザー依頼。結果を見てから変えない）。
対象（y4 で 116〜129% だった一番の目の絞り込み4つ。定義は y4 の判定スクリプトをそのまま実行して使う＝書き直さない）：
 1 一番の目×割高な目を外す   … research/prereg_eval_y4_avoid.py の G
 2 最終日前日の一番の目（V）  … research/prereg_eval_y4.py の V
 3 400mの一番の目×弱い3着   … research/prereg_eval_y4_weak3.py の 2つ目
 4 級班混ざりの一番の目（U）  … research/prereg_eval_y4.py の U
期間：y5（20211108〜20221107）と y6（20201108〜20211107）を足した2年分。y4 は結果を見たので入れない
合格＝2年分まとめた95%の範囲（レース単位ブートストラップ）の下限95%以上 かつ y5・y6 それぞれ100%超 かつ BH補正（この4つ、q=0.05）で有意
（参考に「下限100%超」も表に出す）
使い方: python -I -X utf8 research/prereg_eval_y56_pool.py 表A.pkl 接尾辞A 開始A 終了A 表B.pkl 接尾辞B 開始B 終了B 出力.md
ふつう: research/prereg_y56_pool_run.py が y5・y6 の表を作ってからこれを呼ぶ"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
a = sys.argv[1:]; outp = a[8]
def groups(fT, suf, d0, d1):
    half = d1  # 前半・後半は使わない（年ごとに見る）
    out = {}
    ns = {"__name__": "x"}; sys.argv = ["x", fT, suf, d0, d1, half, "NUL"]
    src = open(K + "research/prereg_eval_y4_avoid.py", encoding="utf-8").read().split("rng = np.random")[0]; exec(src, ns); out["一番の目×割高な目を外す"] = ns["G"]
    ns = {"__name__": "x"}; sys.argv = ["x", fT, suf, "NUL", d0, d1, half, "NUL"]
    src = open(K + "research/prereg_eval_y4.py", encoding="utf-8").read().split("Zg = ")[0].replace('Z = pd.read_pickle(P_(fZ)); Z = Z[Z.date.between(d0, d1)].copy()', '')
    exec(src, ns); out["最終日前日の一番の目"] = ns["V"]; out["級班混ざりの一番の目"] = ns["U"]
    ns = {"__name__": "x"}; sys.argv = ["x", fT, suf, d0, d1, half, "NUL"]
    src = open(K + "research/prereg_eval_y4_weak3.py", encoding="utf-8").read().split("rng = np.random")[0]; exec(src, ns); out["400mの一番の目×弱い3着"] = ns["G"]["400mの一番の目×弱い3着"]
    return out
GA, GB = groups(*a[0:4]), groups(*a[4:8])
names = ["一番の目×割高な目を外す", "最終日前日の一番の目", "400mの一番の目×弱い3着", "級班混ざりの一番の目"]
rng = np.random.default_rng(0); R = {}
for k in names:
    g = pd.concat([GA[k].assign(yr="A"), GB[k].assign(yr="B")], ignore_index=True)
    by = g.groupby("race_id").ret.agg(["sum", "size"]); s, n = by["sum"].to_numpy(), by["size"].to_numpy()
    ii = rng.integers(0, len(by), (4000, len(by))); bs = s[ii].sum(1) / n[ii].sum(1); r = g.ret
    R[k] = dict(n=len(g), hits=int((r > 0).sum()), roi=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), p=(bs <= 1.0).mean(),
                rA=GA[k].ret.mean(), nA=len(GA[k]), rB=GB[k].ret.mean(), nB=len(GB[k]), t=(r.mean() - 1) / (r.std() / np.sqrt(len(r))))
pv = np.array([R[k]["p"] for k in names]); m = 4; order = np.argsort(pv)
kmax = max([i + 1 for i, j in enumerate(order) if pv[j] <= 0.05 * (i + 1) / m], default=0); bh = {names[j]: i < kmax for i, j in enumerate(order)}
L = [f"# 事前登録「5・6年目まとめて」の判定（A＝{a[2]}〜{a[3]}／B＝{a[6]}〜{a[7]}）", "",
     "最終オッズ・確定の払戻・各100円。合格＝2年分の下限95%以上・A・B それぞれ100%超・BH補正（4つ）で有意。", "",
     "| 呼び名 | 判定 | 回収率（2年分） | 点数・当たり | 95%の範囲 | A / B | t | p値（BH） | 下限100%超 |", "|---|---|---|---|---|---|---|---|---|"]
for k in names:
    s = R[k]; ok = s["lo"] >= 0.95 and s["rA"] > 1 and s["rB"] > 1 and bh[k]
    L.append(f"| {k} | {'**合格**' if ok else '不合格'} | **{s['roi']:.0%}** | {s['n']}点・{s['hits']}本 | {s['lo']:.0%}〜{s['hi']:.0%} | {s['rA']:.0%}（{s['nA']}）/ {s['rB']:.0%}（{s['nB']}） | {s['t']:+.2f} | {s['p']:.3f}（{'有意' if bh[k] else '有意でない'}） | {'はい' if s['lo'] > 1 else 'いいえ'} |")
open(outp, "w", encoding="utf-8").write("\n".join(L) + "\n"); print("done", outp)
