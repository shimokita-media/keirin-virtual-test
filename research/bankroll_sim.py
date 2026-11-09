"""④ 資金管理のシミュレーション（モンテカルロ）：一番の目を1日6点・1年（360日）買い続けたら、資金と月ごとの成績はどうなるか。
払戻の形は一番の目の実績（2025/2〜2026/11 の全3,808点の払戻）をそのまま使い、平均だけを「本当の回収率」に合わせる（大穴頼みの偏りを保つ）。
使い方: python -I -X utf8 research/bankroll_sim.py 出力.md"""
import sys, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
T = pd.read_pickle(K + "out/angle_base.pkl")[["ret", "is_top"]]
base = T[T.is_top].ret.to_numpy(); base = base / base.mean()
rng = np.random.default_rng(0)
DAYS, PER_DAY, NSIM = 360, 6, 4000
P("# ④ 資金管理のシミュレーション（一番の目・1日6点・1年・4000回）" + NL)
P(f"払戻の形は一番の目の実績 {len(base)}点（当たり率 {(base > 0).mean():.1%}、当たったときの払戻の中央値 {np.median(base[base > 0]) * 100 / base.mean():.0f}円/100円あたりは倍率どおり）。" + NL)
def run(roi, bank0, mode, unit=100, frac=0.005):
    n = DAYS * PER_DAY
    x = rng.choice(base, (NSIM, n)) * roi  # 1点100円あたりの払戻倍率
    bank = np.full(NSIM, float(bank0)); peak = bank.copy(); mdd = np.zeros(NSIM); ruined = np.zeros(NSIM, bool)
    month_in = np.zeros((NSIM, 12)); month_out = np.zeros((NSIM, 12))
    for i in range(n):
        if mode == "flat": stake = np.full(NSIM, float(unit))
        else: stake = np.maximum(100, np.floor(bank * frac / 100) * 100)  # 資金の frac（100円単位、最低100円）
        stake = np.where(ruined | (bank < stake), 0, stake)
        ret = stake * x[:, i]
        bank += ret - stake
        ruined |= bank < 100
        m = min(i // (PER_DAY * 30), 11); month_in[:, m] += stake; month_out[:, m] += ret
        peak = np.maximum(peak, bank); mdd = np.maximum(mdd, (peak - bank) / peak)
    mroi = np.where(month_in > 0, month_out / np.maximum(month_in, 1), np.nan)
    return bank, mdd, ruined, mroi
P("## A. 1点100円で固定（資金5万円から）" + NL + NL + "| 本当の回収率 | 1年後の資金（中央値） | 資金が増えた割合 | 途中で資金が半分を割った割合 | 最大のへこみ（中央値） | 月の回収率 5%/25%/50%/75%/95% | 100%超えの月 | 130%超えの月 |" + NL + "|---|---|---|---|---|---|---|---|")
for roi in (0.95, 1.00, 1.05, 1.10, 1.20, 1.30):
    bank, mdd, ruined, mroi = run(roi, 50000, "flat")
    half = mdd >= 0.5
    q = np.nanpercentile(mroi, [5, 25, 50, 75, 95])
    P(f"| {roi:.0%} | {np.median(bank):,.0f}円 | {(bank > 50000).mean():.0%} | {half.mean():.0%} | {np.median(mdd):.0%} | {' / '.join(f'{v:.0%}' for v in q)} | {(mroi > 1).mean():.0%} | {(mroi >= 1.3).mean():.0%} |")
P(NL + "## B. 資金に合わせて賭け金を変える（資金の0.5%・1%・2%、100円単位、資金10万円から、本当の回収率110%・120%）" + NL + NL + "| 本当の回収率 | 1点の賭け金 | 1年後の資金（中央値） | 5%の悪い場合 | 破産（100円未満） | 資金が半分を割った割合 |" + NL + "|---|---|---|---|---|---|")
for roi in (1.10, 1.20):
    for fr in (0.005, 0.01, 0.02):
        bank, mdd, ruined, mroi = run(roi, 100000, "frac", frac=fr)
        P(f"| {roi:.0%} | 資金の{fr:.1%} | {np.median(bank):,.0f}円 | {np.percentile(bank, 5):,.0f}円 | {ruined.mean():.1%} | {(mdd >= 0.5).mean():.0%} |")
var = base.var(); P(NL + f"参考：1点あたりの分散 {var:.1f}（回収率で）。ケリー基準の賭け金の割合 ≒ 上乗せ÷分散：110%なら {0.10 / var:.2%}、120%なら {0.20 / var:.2%}、130%なら {0.30 / var:.2%}（実際はその1/2〜1/4が安全）")
print("done")
