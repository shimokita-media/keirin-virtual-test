"""本番の締切1分前（T1）の倍率で、ライン順の機械の E1〜E3（KNOWLEDGE 2026-11-12 19:55 の事前登録と同じ式・同じ係数）を拾う。前向きの確認用（2026-11-12 夜）。
①1分前の倍率で pn・比・期待値を作り、E1（期待値≥1.2）・E2（≥1.3）・E3（比≥1.2、賭け金∝(比−1)²）の目を out/lo_t1_picks.pkl に残す
②同じレースの確定オッズ（本番DBの POST）でも作り、選ばれる目がどれだけ変わるかを比べる（当たり外れは使わない）
③成績は E3 の点数が 500点たまるまで出さない（途中でのぞいて判断を変えないため）。たまったら 回収率・95%の範囲を出す
入力：out/angle_base_t1.pkl（research/daily_forward.py が作る。先に回して最新にする）、out/live_db/keirin.sqlite（読むだけ）
使い方: python -I -X utf8 research/lo_forward_t1.py reports/lo_forward_t1.md"""
import sys, json, sqlite3, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"; NL = chr(10); NEED = 500
exec(open(K + "research/lo_feats.py", encoding="utf-8").read())
C = json.load(open(K + "research/lo_model_coef_4yr.json", encoding="utf-8")); assert C["cols"] == ["const"] + LO_COLS
T = pd.read_pickle(K + "out/angle_base_t1.pkl").reset_index(drop=True)
con = sqlite3.connect("file:" + K + "out/live_db/keirin.sqlite?mode=ro", uri=True)
days = sorted(T.date.unique()); F = []
for dy in days:   # 確定オッズ（日ごとの短い読み込み）
    F.append(pd.read_sql("SELECT race_id, combo, odds AS odds_f, fetched_at FROM odds WHERE phase='POST' AND bet_type='3連単' AND race_id LIKE ?", con, params=("%" + dy,)))
F = pd.concat(F).sort_values("fetched_at").drop_duplicates(["race_id", "combo"], keep="last").drop(columns="fetched_at")
T = T.merge(F, on=["race_id", "combo"], how="left")
# 当日の流れ（その日その場のそれまでのレースで、当たり目の1着が先頭だった割合）。レースの前に分かる情報
T["hit"] = (T.ret > 0).astype(float)
Wn = T[T.hit > 0].drop_duplicates("race_id").set_index("race_id").r0_pos.eq(0).astype(float)
R = T.drop_duplicates("race_id")[["race_id", "venue", "date", "race_no"]].sort_values(["venue", "date", "race_no"]).copy()
R["lw"] = R.race_id.map(Wn).fillna(0); g = R.groupby(["venue", "date"]); R["n_prev"] = g.cumcount()
R["flow"] = (g.lw.cumsum() - R.lw) / R.n_prev.replace(0, np.nan); R = R.set_index("race_id")
T["flow"] = T.race_id.map(R.flow); T["n_prev"] = T.race_id.map(R.n_prev)
def pick(d, oc):
    d = d[d[oc] <= 300].copy(); q = 1 / d[oc]; d["pn"] = q / q.groupby(d.race_id).transform("sum"); d["odds"] = d[oc]
    lo = d[(d.s01 == 1) & (d.s12 == 1) & (d.r0_pos == 0) & (d.r1_pos == 1) & (d.r2_pos == 2) & (d.odds <= 15)].copy()
    lo["ratio"] = lo_ratio(C["coef"], lo); lo["ev"] = lo.ratio * lo.pn * lo.odds; return lo
T["odds_t1"] = T.odds
A = pick(T, "odds_t1"); B = pick(T[T.odds_f.notna()], "odds_f")
A[["race_id", "date", "combo", "odds_t1", "odds_f", "pn", "ratio", "ev", "ret"]].to_pickle(K + "out/lo_t1_picks.pkl")
key = lambda d: set(zip(d.race_id, d.combo))
RULE = {"E1 期待値≥1.2": lambda d: d[d.ev >= 1.2], "E2 期待値≥1.3": lambda d: d[d.ev >= 1.3], "E3 比≥1.2": lambda d: d[d.ratio >= 1.2]}
nR = T.race_id.nunique(); nd = len(days)
L = [f"# ライン順の機械 E1〜E3 を本番の締切1分前の倍率で拾う（{days[0]}〜{days[-1]}・{nd}日・{nR}R）", "",
     f"ライン順×15倍以下：1分前 {len(A)}点 ／ 確定オッズ {len(B)}点。成績は E3 が {NEED}点たまるまで出さない", "",
     "## 選ばれる目の数と、確定オッズで選んだ目との重なり（当たり外れは使っていない）", "",
     "| 買い方 | 1分前で選ぶ | 1日あたり | 確定で選ぶ | 両方で選ばれる | 1分前の目のうち確定でも残る割合 | 1分前→確定の倍率の動き（中央値） |", "|---|---|---|---|---|---|---|"]
for k, f in RULE.items():
    a, b = f(A), f(B); both = len(key(a) & key(b)); ch = (a.odds_f / a.odds_t1 - 1).median() if len(a) else float("nan")
    L.append(f"| {k} | {len(a)}点 | {len(a) / nd:.1f}点 | {len(b)}点 | {both}点 | {both / max(len(a), 1):.0%} | {ch:+.0%} |")
a3 = RULE["E3 比≥1.2"](A)
L += ["", "## 1分前で選んだ目を、確定オッズで見直したときの期待値", "",
      "| 買い方 | 1分前の比・期待値（平均） | 同じ目を確定オッズで作り直した比・期待値（平均。確定で15倍以下に残った目だけ） | 1分前は15倍超で、確定で15倍以下に入って選ばれた目 |", "|---|---|---|---|"]
Bk = B.set_index(["race_id", "combo"]); Ak = key(A)
for k, f in RULE.items():
    a = f(A); m = a.merge(B[["race_id", "combo", "ratio", "ev"]], on=["race_id", "combo"], suffixes=("", "_f")); late = sum(1 for x in key(f(B)) if x not in Ak)
    L.append(f"| {k} | {a.ratio.mean():.2f}・{a.ev.mean():.2f} | {m.ratio_f.mean():.2f}・{m.ev_f.mean():.2f}（{len(m)}点） | {late}点 |" if len(a) else f"| {k} | — | — | {late}点 |")
L += ["", "## 成績", ""]
if len(a3) < NEED: L.append(f"E3 が {len(a3)}点（{NEED}点までは出さない。今の速さだとあと約 {(NEED - len(a3)) / max(len(a3) / nd, 0.1):.0f}日）")
else:
    rng = np.random.default_rng(0)
    L += ["| 買い方 | 点数 | 回収率（確定の払戻） | 95%の範囲 |", "|---|---|---|---|"]
    for k, f in RULE.items():
        a = f(A); w = (a.ratio - 1) ** 2 if k.startswith("E3") else pd.Series(1.0, index=a.index)
        for nm, ww in ((k, pd.Series(1.0, index=a.index)),) + (((k + "・賭け金∝(比−1)²", w),) if k.startswith("E3") else ()):
            x = pd.DataFrame({"r": a.race_id.to_numpy(), "a": (ww * a.ret).to_numpy(), "w": ww.to_numpy()}).groupby("r").sum()
            if len(x) < 20: L.append(f"| {nm} | {len(a)}点 | （少ない） | |"); continue
            ii = rng.integers(0, len(x), (4000, len(x))); bs = x.a.to_numpy()[ii].sum(1) / x.w.to_numpy()[ii].sum(1)
            L.append(f"| {nm} | {len(a)}点 | **{x.a.sum() / x.w.sum():.0%}** | {np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%} |")
open(sys.argv[1], "w", encoding="utf-8").write(NL.join(L) + NL); print("done")
