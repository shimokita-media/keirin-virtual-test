"""学習サイクル用の共通データ（3連単・2025/2〜2026/11・最終オッズ・L級除く・300倍以下）。
初回だけ大きな元データから作って out/angle_base.pkl に保存し、2回目からはそれを読む。
使い方: exec(open(".../research/angle_base.py", encoding="utf-8").read()) → T（全組）, B（3連単枠）, top（一番の目）, per(d)（期間ラベル）, summ(g)（回収率の要約）"""
import os, sqlite3, numpy as np, pandas as pd
from scipy.stats import norm
K = "C:/Users/take0/.claude/keirin/"
SP = "C:/Users/take0/AppData/Local/Temp/claude/a37ab707dae15896/7b6bdcb5-d7a9-44e7-8208-87d25e059855/scratchpad/"
CACHE = os.environ.get("ANGLE_CACHE", K + "out/angle_base.pkl")
exec(open(K + "research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
if os.path.exists(CACHE):
    T = pd.read_pickle(CACHE)
else:
    A0 = pd.concat([pd.read_pickle(SP + "tri3_all.pkl"), pd.read_pickle(SP + "tri3_new.pkl")] +
                   [pd.read_pickle(K + f"out/{f}/tri.pkl") for f in ("fresh", "fresh2", "fresh3", "fresh4", "fresh5", "fresh6", "fresh7")])
    A0 = A0[A0.date >= "20250201"].drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
    T = prep(A0); del A0
    T = T[(T["class"] != "L級") & (T.odds <= 300)].reset_index(drop=True)
    con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro&immutable=1", uri=True)
    R = pd.read_sql("SELECT race_id, race_type, venue, venue_id, cup_id, close_at, start_at FROM races", con).set_index("race_id")
    for c in R.columns: T[c] = T.race_id.map(R[c])
    s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12
    order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2); nine, d2 = T.entries_number >= 9, T.day_index >= 2
    RL = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
          order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
    T["nr"] = sum(r.astype(int) for r in RL)
    X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
    T["in_B"] = False; T.loc[X.groupby("race_id").head(6).index, "in_B"] = True
    T["is_top"] = False; T.loc[X.groupby("race_id").head(1).index, "is_top"] = True
    T.to_pickle(CACHE)
B, top = T[T.in_B], T[T.is_top]
def per(d):
    return np.select([d.between("20251012", "20260114"), d >= "20260901"], ["③", "⑥"], "探す")
rng = np.random.default_rng(0)
def summ(g):
    """{'探す': (点数, 回収率, t値), '③': (...), '⑥': (...)}"""
    out = {}
    p = per(g.date)
    for k in ("探す", "③", "⑥"):
        x = g.ret[p == k].to_numpy()
        if len(x) < 2: out[k] = (len(x), np.nan, np.nan); continue
        out[k] = (len(x), x.mean(), (x.mean() - 1) / (x.std(ddof=1) / np.sqrt(len(x))))
    return out
def fmt(s):
    return " / ".join(f"{s[k][1]:.0%}({s[k][0]})" if s[k][0] else "−" for k in ("探す", "③", "⑥"))
def combo_parts(D):
    """3連単の組番を 1着・2着・3着の車番に分ける"""
    p = D.combo.str.split("-", expand=True).astype(int); return p[0], p[1], p[2]
def report(path, title, note, conds, D=None):
    """conds: {条件名: T と同じ index の真偽 Series}。全部・30倍以下・3連単枠・一番の目 の表と候補を path に書く"""
    D = T if D is None else D
    Bx, tx = D[D.in_B], D[D.is_top]
    rows = []
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 切り口：{title}\n\n{note}\n\n回収率（点数）は 探す / ③ / ⑥。最終オッズ・各100円。\n\n")
        f.write("| 条件 | 3連単全部 | 30倍以下 | 3連単枠 | 一番の目 |\n|---|---|---|---|---|\n")
        for nm, m in conds.items():
            m = m.reindex(D.index, fill_value=False).astype(bool)
            gs = [D[m], D[m & (D.odds <= 30)], Bx[m[Bx.index]], tx[m[tx.index]]]
            f.write(f"| {nm} | " + " | ".join(fmt(summ(g)) for g in gs) + " |\n")
            for lab, g in zip(("全部", "30倍以下", "3連単枠", "一番の目"), gs): rows.append((nm, lab, summ(g)))
        ok = lambda s: all((s[k][0] or 0) >= 30 and s[k][1] > 1 for k in ("探す", "③", "⑥"))
        # 3連単枠・一番の目は、それ自体が探す期間で120%超なので「100%との比較」だけだと大きな部分集合は何でも候補になる。
        # → 残り（その条件に当てはまらない枠・一番の目）との差も、3期間とも上回り・探す期間の差の t値≥2.5 を求める（2026-11-09 15:55 追加）
        f.write("\n## 3連単枠・一番の目：当てはまる／当てはまらないの差（探す / ③ / ⑥、差の t値は探す期間）\n")
        diff = {}
        for nm, m in conds.items():
            m = m.reindex(D.index, fill_value=False).astype(bool)
            for lab, G in (("3連単枠", Bx), ("一番の目", tx)):
                mm = m[G.index]; a_, b_ = summ(G[mm]), summ(G[~mm])
                x, y = G[mm & (per(G.date) == "探す")].ret, G[~mm & (per(G.date) == "探す")].ret
                tdiff = (x.mean() - y.mean()) / np.sqrt(x.var(ddof=1) / max(len(x), 1) + y.var(ddof=1) / max(len(y), 1)) if len(x) > 1 and len(y) > 1 else np.nan
                beats = all((a_[k][0] or 0) >= 30 and (b_[k][0] or 0) >= 30 and a_[k][1] > b_[k][1] for k in ("探す", "③", "⑥"))
                diff[(nm, lab)] = (tdiff, beats)
                f.write(f"- {nm} × {lab}: 当てはまる {fmt(a_)} ／ 当てはまらない {fmt(b_)} ／ 差のt={tdiff:.1f}{' ／ 3期間とも上' if beats else ''}\n")
        def is_cand(a, b, s):
            if not (ok(s) and s["探す"][2] >= 2.5): return False
            if b in ("3連単枠", "一番の目"):
                t_, bt = diff[(a, b)]; return bool(bt and t_ >= 2.5)
            return True
        c = [(a, b, s) for a, b, s in rows if is_cand(a, b, s)]
        f.write("\n## 候補（探す t≥2.5 かつ 3期間とも100%超・各30点以上）\n" + ("\n".join(f"- {a} × {b}: {fmt(s)}（t={s['探す'][2]:.1f}）" for a, b, s in c) or "- なし") + "\n")
        c2 = [(a, b, s) for a, b, s in rows if ok(s)]
        f.write("\n## 参考：3期間とも100%超（tは問わない）\n" + ("\n".join(f"- {a} × {b}: {fmt(s)}（t={s['探す'][2]:.1f}）" for a, b, s in c2) or "- なし") + "\n")
    return c, c2
