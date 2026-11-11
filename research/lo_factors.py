"""探す段階（Fable）：ライン順×3着の得点順位7位以下×10倍以下 の中で、さらに当たりやすくなる条件を、見た3期間とも同じ向きのものだけ探す。
y4（out/y4/cache.pkl）・2024年（out/y2024full/cache.pkl）・2025/2〜（out/angle_base.pkl）。y5・y6 は見ない。
最初にライン順×3着7位以下×15倍以下の部分だけを out/lo_sub_<期間>.pkl に保存（2回目からはそれを読む）。見込み p＝確定オッズ 1/odds をレースの中で合計1（300倍以下）。
使い方: python -I -X utf8 research/lo_factors.py reports/lo_factors.md"""
import sys, os, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10)
SRC = {"y4": "out/y4/cache.pkl", "2024年": "out/y2024full/cache.pkl", "2025/2〜": "out/angle_base.pkl"}
def build(nm):
    f = K + f"out/lo_sub_{nm.replace('/', '').replace('〜', '')}.pkl"
    if os.path.exists(f): return pd.read_pickle(f)
    d = pd.read_pickle(K + SRC[nm]); d = d[d.odds <= 300]
    if nm == "2025/2〜": d = d[d.date <= "20261105"]
    q = 1 / d.odds; d = d.assign(pn=q / q.groupby(d.race_id).transform("sum"), hit=(d.ret > 0).astype(float))
    # 当日の流れ：同じ場・同じ日の、それより前のレースで「1着が先頭」だった割合
    W = d[d.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
    R = d.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
    R["lw"] = R.race_id.map(W).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
    R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan)
    d["flow"] = d.race_id.map(R.set_index("race_id").flow); d["n_prev"] = d.race_id.map(R.set_index("race_id").n_prev)
    d["fav"] = d.groupby("race_id").odds.transform("min")
    s = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.r2_pt_rank >= 7) & (d.odds <= 15)].copy()
    s.to_pickle(f); return s
PER = {nm: build(nm) for nm in SRC}
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
def cell(g): return f"{len(g):,}・{g.hit.sum() / g.pn.sum():.2f}・**{g.ret.mean():.0%}**" if len(g) >= 40 else f"{len(g)}（少）"
rt = lambda d: d.race_type.fillna("").astype(str)
F = {
 "1着の得点順位": lambda d: pd.cut(d.r0_pt_rank, [0, 1, 3, 99], labels=["1位", "2〜3位", "4位以下"]),
 "2着の得点順位": lambda d: pd.cut(d.r1_pt_rank, [0, 1, 3, 99], labels=["1位", "2〜3位", "4位以下"]),
 "1着の脚質": lambda d: d.r0_style.fillna("?"),
 "2着の脚質": lambda d: d.r1_style.fillna("?"),
 "ラインの数": lambda d: pd.cut(d.nlines, [0, 2, 3, 99], labels=["二分戦", "三分戦", "四分戦〜"]),
 "ラインの人数": lambda d: np.where(d.r0_ls >= 4, "4人以上", "3人"),
 "開催の何日目": lambda d: pd.cut(d.day_index, [0, 1, 2, 99], labels=["1日目", "2日目", "3日目〜"]),
 "グレード": lambda d: np.where(d.G == 1, "G戦", "F戦"),
 "当日の流れ（前のレースで先頭が勝った割合）": lambda d: pd.cut(d.flow, [-1, 0.3, 0.6, 1.01], labels=["〜30%", "30〜60%", "60%〜"]),
 "1着の予想印": lambda d: d.r0_prediction_mark.fillna(-1).astype(int).astype(str),
 "強い逃げの人数": lambda d: pd.cut(d.n_strong_nige, [-1, 0, 1, 9], labels=["0", "1", "2〜"]),
 "3着の年齢": lambda d: pd.cut(d.r2_age, [0, 30, 40, 99], labels=["〜30", "31〜40", "41〜"]),
 "3着の3連対率": lambda d: pd.cut(d.r2_third_rate, [-1, 20, 35, 101], labels=["〜20%", "20〜35%", "35%〜"]),
 "この目の人気順位": lambda d: pd.cut(d.popularity, [0, 1, 3, 999], labels=["1番人気", "2〜3番人気", "4番人気〜"]),
 "3連複から見て割安（g_tf>0）": lambda d: np.where(d.g_tf > 0, "割安", "それ以外"),
 "2車単から見て割安（g_ex>0）": lambda d: np.where(d.g_ex > 0, "割安", "それ以外"),
 "一番人気の倍率": lambda d: pd.cut(d.fav, [0, 3, 5, 99], labels=["〜3倍", "3〜5倍", "5倍〜"]),
 "レースの種類": lambda d: np.select([rt(d).str.contains("予選"), rt(d).str.contains("準決勝"), rt(d).str.contains("決勝"), rt(d).str.contains("特選|選抜"), rt(d).str.contains("一般")], ["予選", "準決勝", "決勝", "特選・選抜", "一般"], "その他"),
 "時間帯": lambda d: pd.cut(pd.to_datetime(d.start_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo").dt.hour, [-1, 11, 16, 20, 24], labels=["朝", "昼", "夕方", "夜"]),
 "3着の最近5走の平均着順": lambda d: pd.cut(d.r2_ro_last5, [0, 4, 5.5, 10], labels=["〜4", "4〜5.5", "5.5〜"]),
 "1着の最近5走の平均着順": lambda d: pd.cut(d.r0_ro_last5, [0, 3, 4.5, 10], labels=["〜3", "3〜4.5", "4.5〜"]),
 "番手（2着）の1着見込み r1_p1": lambda d: pd.cut(d.r1_p1, [-1, 0.15, 0.3, 1.01], labels=["〜15%", "15〜30%", "30%〜"]),
}
P("# 探す段階：ライン順×3着7位以下×10倍以下 の中で効く条件（各セル：点数・当たり÷見込み・回収率）" + NL)
base = {k: d[d.odds <= 10] for k, d in PER.items()}
P("全部： " + " ／ ".join(f"{k} {cell(d)}" for k, d in base.items()) + NL)
good = []
for nm, fn in F.items():
    P(f"## {nm}" + NL + "| 区分 | " + " | ".join(base) + " | 3期間とも100%超 |" + NL + "|---|---|---|---|---|")
    cats = {k: fn(d) for k, d in base.items()}
    keys = sorted(set().union(*[set(pd.Series(c).dropna().astype(str).unique()) for c in cats.values()]))
    for key in keys:
        gs = [d[pd.Series(np.asarray(cats[k]).astype(str), index=d.index) == key] for k, d in base.items()]
        ok = all(len(g) >= 100 and g.ret.mean() > 1.0 for g in gs)
        strong = all(len(g) >= 100 and g.ret.mean() > 1.10 for g in gs)
        if strong: good.append((nm, key, [f"{len(g)}点 {g.ret.mean():.0%}" for g in gs]))
        P(f"| {key} | " + " | ".join(cell(g) for g in gs) + f" | {'◎' if strong else ('○' if ok else '')} |")
    P("")
P("## 3期間とも110%超（各100点以上）だった区分" + NL)
for nm, key, v in good: P(f"- {nm}＝{key}：" + "／".join(v))
print("done", len(good))
