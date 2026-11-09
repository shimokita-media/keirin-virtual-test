"""箱ひげ図：買い方ごとの「月ごとの回収率」のばらつき（2025/2〜2026/11、最終オッズ・各100円）。
点＝1か月。青＝法則を探すときに見た月、オレンジ＝見ていない月（③ 25/10/12〜26/1/14 と ⑥ 26/9〜）。機械の期待値で分けた2つは meta_model_v1 の学習期間外（止めどころ・③・⑥）だけ。"""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
K = "C:/Users/take0/.claude/keirin/"
plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic"]
T = pd.read_pickle(K + "out/angle_base.pkl")[["race_id", "date", "odds", "ret", "in_B", "is_top"]]
M = pd.read_pickle(K + "out/meta_pred_v1.pkl")[["race_id", "date", "ret", "ev", "is_top"]]
unseen = lambda d: d.between("20251012", "20260114") | (d >= "20260901")
heldout = lambda d: unseen(d) | d.between("20260616", "20260831")
groups = {"3連単を全部": T, "3連単枠": T[T.in_B], "一番の目": T[T.is_top],
          "一番の目×機械の\n期待値1.0以上": M[M.is_top & (M.ev >= 1.0) & heldout(M.date)], "一番の目×機械の\n期待値1.0未満": M[M.is_top & (M.ev < 1.0) & heldout(M.date)]}
data, cols = [], []
for nm, g in groups.items():
    mo = g.assign(ym=g.date.str[:6]).groupby("ym").agg(r=("ret", "mean"), n=("ret", "size"))
    mo = mo[mo.n >= 15]; mo["unseen"] = [unseen(pd.Series([ym + "15"])).iloc[0] for ym in mo.index]
    if "機械" in nm: mo["unseen"] = True  # 機械の学習に使っていない月だけを集めた列
    data.append(mo)
fig, ax = plt.subplots(figsize=(10, 5.6), dpi=150)
fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
ax.boxplot([d.r * 100 for d in data], widths=0.5, showfliers=False, patch_artist=True,
           boxprops=dict(facecolor="#e8e7e3", edgecolor="#52514e", linewidth=1), medianprops=dict(color="#0b0b0b", linewidth=2),
           whiskerprops=dict(color="#52514e"), capprops=dict(color="#52514e"))
rng = np.random.default_rng(0)
for i, d in enumerate(data, start=1):
    x = i + rng.uniform(-0.15, 0.15, len(d))
    ax.scatter(x[~d.unseen.to_numpy()], d.r[~d.unseen] * 100, s=28, color="#2a78d6", edgecolor="#fcfcfb", linewidth=1, zorder=3)
    ax.scatter(x[d.unseen.to_numpy()], d.r[d.unseen] * 100, s=28, color="#eb6834", edgecolor="#fcfcfb", linewidth=1, zorder=3)
ax.axhline(100, color="#0b0b0b", linewidth=1, linestyle=(0, (4, 3)))
ax.text(0.55, 103, "100%（とんとん）", fontsize=8.5, color="#0b0b0b", va="bottom", ha="left")
NL = chr(10)
labs = [nm + NL + NL + f"{len(d)}か月・平均 {d.r.mean():.0%}" + NL + f"中央値 {d.r.median():.0%}・標準偏差 {d.r.std() * 100:.0f}" for nm, d in zip(groups, data)]
ax.set_xticks(range(1, len(groups) + 1)); ax.set_xticklabels(labs, fontsize=9, color="#0b0b0b")
ax.set_ylabel("月ごとの回収率（%）", color="#52514e"); ax.set_ylim(-5, max(d.r.max() for d in data) * 100 + 20)
ax.grid(axis="y", color="#e8e7e3", linewidth=0.8); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#c3c2b7")
ax.tick_params(colors="#52514e")
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker="o", ls="", color="#2a78d6", label="法則を探すときに見た月"), Line2D([], [], marker="o", ls="", color="#eb6834", label="見ていない月（③・⑥、機械の2列は学習に使っていない月）")],
          loc="upper left", frameon=False, fontsize=9)
ax.set_title("買い方ごとの月ごとの回収率（2025/2〜2026/11・最終オッズ・各100円）", fontsize=12, color="#0b0b0b", loc="left")
plt.subplots_adjust(bottom=0.27, left=0.08, right=0.98)
plt.savefig(K + "reports/boxplot_monthly.png", facecolor=fig.get_facecolor())
for nm, d in zip(groups, data):
    print(nm.replace(chr(10), ""), f"{len(d)}か月 平均{d.r.mean():.0%} 中央値{d.r.median():.0%} 標準偏差{d.r.std():.0%} 100%超の月{(d.r > 1).mean():.0%}")
