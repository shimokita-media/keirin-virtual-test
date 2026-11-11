"""探す段階（Fable）：3連単の全部の目を「形」で細かく分け、2024年だけで割安な形を機械的に選び、y4 と 2025/2〜 で確かめる（選ぶ年と確かめる年を分ける）。
形＝1-2着が同じラインか（s01）×2-3着が同じラインか（s12）×1・2・3着のライン内の位置（0先頭・1番手・2三番手以降）×1着の得点順位（1位・2〜3位・4位以下）×3着の得点順位（1〜2・3〜4・5〜6・7位以下）×倍率の帯。
見込み p＝1/odds をレースの中で合計1（300倍以下）。期間ごとの集計を out/cell_agg.pkl に保存（2回目からはそれを読む）。y5・y6 は見ない。
使い方: python -I -X utf8 research/cell_calib.py reports/cell_calib.md"""
import sys, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SRC = {"y4": "out/y4/cache.pkl", "2024年": "out/y2024full/cache.pkl", "2025/2〜": "out/angle_base.pkl"}
KEYS = ["s01", "s12", "p0", "p1", "p2", "a_rk", "c_rk", "band"]
AGG = K + "out/cell_agg.pkl"
if os.path.exists(AGG): A = pd.read_pickle(AGG)
else:
    out = []
    for nm, f in SRC.items():
        d = pd.read_pickle(K + f)[["race_id", "date", "odds", "ret", "s01", "s12", "r0_pos", "r1_pos", "r2_pos", "r0_pt_rank", "r2_pt_rank"]]
        d = d[d.odds <= 300]
        if nm == "2025/2〜": d = d[d.date <= "20261105"]
        q = 1 / d.odds; d = d.assign(p=q / q.groupby(d.race_id).transform("sum"), hit=(d.ret > 0).astype(float))
        d["p0"] = d.r0_pos.clip(upper=2); d["p1"] = d.r1_pos.clip(upper=2); d["p2"] = d.r2_pos.clip(upper=2)
        d["a_rk"] = pd.cut(d.r0_pt_rank, [0, 1, 3, 99], labels=["1", "2-3", "4+"]).astype(str)
        d["c_rk"] = pd.cut(d.r2_pt_rank, [0, 2, 4, 6, 99], labels=["1-2", "3-4", "5-6", "7+"]).astype(str)
        d["band"] = pd.cut(d.odds, [0, 10, 20, 40, 100, 300], labels=["〜10", "10〜20", "20〜40", "40〜100", "100〜300"]).astype(str)
        g = d.groupby(KEYS, observed=True).agg(n=("ret", "size"), h=("hit", "sum"), e=("p", "sum"), r=("ret", "sum"), r2=("ret", lambda x: (x ** 2).sum())).reset_index(); g["per"] = nm; out.append(g); del d
    A = pd.concat(out); A.to_pickle(AGG)
W = A.pivot_table(index=KEYS, columns="per", values=["n", "h", "e", "r", "r2"], aggfunc="sum", fill_value=0)
def roi(per, idx): return W["r"][per].loc[idx].sum() / max(W["n"][per].loc[idx].sum(), 1)
def he(per, idx): return W["h"][per].loc[idx].sum() / max(W["e"][per].loc[idx].sum(), 1e-9)
def npts(per, idx): return int(W["n"][per].loc[idx].sum())
def se(per, idx):
    n = W["n"][per].loc[idx].sum(); m = W["r"][per].loc[idx].sum() / max(n, 1); v = W["r2"][per].loc[idx].sum() / max(n, 1) - m * m
    return np.sqrt(max(v, 0) / max(n, 1))
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
P("# 探す段階：形ごとの割安さを2024年で選び、y4・2025/2〜で確かめる" + NL)
P(f"形の数 {len(W):,}。2024年だけで選ぶ → ほかの2期間で確かめる（選ぶのに使っていない）。各100円・確定の払戻。±は点ごとの標準誤差（同じレースの目のつながりは無視＝少し甘い）" + NL)
P("## 2024年で選んだ形をまとめて買うと" + NL + "| 選び方（2024年） | 形の数 | 2024年（選んだ年） | y4（確かめ） | 2025/2〜（確かめ） |" + NL + "|---|---|---|---|---|")
tr = "2024年"; n24 = W["n"][tr]; roi24 = W["r"][tr] / n24.replace(0, np.nan); he24 = W["h"][tr] / W["e"][tr].replace(0, np.nan)
for nm, sel in (("回収率100%以上・300点以上", (roi24 >= 1.0) & (n24 >= 300)), ("回収率105%以上・300点以上", (roi24 >= 1.05) & (n24 >= 300)), ("回収率110%以上・200点以上", (roi24 >= 1.10) & (n24 >= 200)),
                ("当たり÷見込み1.2以上・300点以上", (he24 >= 1.2) & (n24 >= 300)), ("当たり÷見込み1.3以上・200点以上", (he24 >= 1.3) & (n24 >= 200)), ("当たり÷見込み1.2以上・1000点以上", (he24 >= 1.2) & (n24 >= 1000))):
    idx = W.index[sel.fillna(False)]
    P(f"| {nm} | {len(idx)} | " + " | ".join(f"{npts(p, idx):,}点・{he(p, idx):.2f}・**{roi(p, idx):.0%}**±{se(p, idx):.0%}" for p in ("2024年", "y4", "2025/2〜")) + " |")
# 逆向きの確かめ：y4 で選んで 2024年・2025/2〜で確かめる
P(NL + "## 逆向き：y4 で選んだ形をまとめて買うと" + NL + "| 選び方（y4） | 形の数 | y4（選んだ年） | 2024年（確かめ） | 2025/2〜（確かめ） |" + NL + "|---|---|---|---|---|")
n4 = W["n"]["y4"]; roi4 = W["r"]["y4"] / n4.replace(0, np.nan); he4 = W["h"]["y4"] / W["e"]["y4"].replace(0, np.nan)
for nm, sel in (("回収率105%以上・300点以上", (roi4 >= 1.05) & (n4 >= 300)), ("当たり÷見込み1.2以上・300点以上", (he4 >= 1.2) & (n4 >= 300))):
    idx = W.index[sel.fillna(False)]
    P(f"| {nm} | {len(idx)} | " + " | ".join(f"{npts(p, idx):,}点・{he(p, idx):.2f}・**{roi(p, idx):.0%}**±{se(p, idx):.0%}" for p in ("y4", "2024年", "2025/2〜")) + " |")
# 3期間とも100%超の形（300点以上）
P(NL + "## 3期間とも回収率100%以上・各200点以上の形" + NL + "| 1-2同ライン | 2-3同ライン | 1着位置 | 2着位置 | 3着位置 | 1着得点 | 3着得点 | 倍率 | y4 | 2024年 | 2025/2〜 |" + NL + "|---|---|---|---|---|---|---|---|---|---|---|")
ok = pd.Series(True, index=W.index)
for p in SRC: ok &= (W["n"][p] >= 200) & (W["r"][p] / W["n"][p].replace(0, np.nan) >= 1.0)
for idx in W.index[ok.fillna(False)]:
    P("| " + " | ".join(str(x) for x in idx) + " | " + " | ".join(f"{int(W['n'][p].loc[idx]):,}点・{W['h'][p].loc[idx] / W['e'][p].loc[idx]:.2f}・{W['r'][p].loc[idx] / W['n'][p].loc[idx]:.0%}" for p in SRC) + " |")
tot = {p: (W["n"][p] >= 200).sum() for p in SRC}
# 偶然だけで何個出るかの目安：各形・各期間で「回収率が100%以上になる確率」を、その形の点ごとのばらつきから正規近似で出し（本当の回収率は全体の平均と仮定）、3期間の積を足す
from math import erf, sqrt
exp_n = 0.0
for idx in W.index[(W["n"]["y4"] >= 200) & (W["n"]["2024年"] >= 200) & (W["n"]["2025/2〜"] >= 200)]:
    pr = 1.0
    for p in SRC:
        n = W["n"][p].loc[idx]; m = W["r"][p].loc[idx] / n; sd = sqrt(max(W["r2"][p].loc[idx] / n - m * m, 1e-9)); base = W["r"][p].sum() / W["n"][p].sum()
        z = (1.0 - base) / (sd / sqrt(n)); pr *= 0.5 * (1 - erf(z / sqrt(2)))
    exp_n += pr
P(NL + f"（3期間とも200点以上ある形のうち、全部の形の本当の回収率が全体の平均（約75%）だとしても、偶然だけで3期間とも100%以上になる形は約 {exp_n:.1f} 個出る見込み。実際は {int(ok.sum())} 個。倍率100〜300倍の形はばらつきが大きく偶然で出やすい）")
print("done", int(ok.sum()))
