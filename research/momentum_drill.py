"""勢いの絞り込み：「直近がかなり良化（最近5走の平均着順がそれより前より1.5着以上良い）× 得点4位以下」の選手が1着の3連単（300倍以下）。
〜2025 で探して、2026 で確かめる（2026 は探すときに見ない）。使い方: python -I -X utf8 research/momentum_drill.py 出力.md"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
OUT = open(K + sys.argv[1], "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
RA = pd.read_pickle(K + "out/side_races_full.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + "out/side_entries_full.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
T = pd.read_pickle(K + "out/tri_compact.pkl")
E = E.merge(RA[["race_id", "date", "day_index", "class", "grade", "entries_number", "line_json", "race_type"]].rename(columns={"class": "rclass"}), on="race_id")
E["pt_rank"] = E.groupby("race_id").race_point.rank(ascending=False, method="min")
def mom(s):
    try: v = [x for x in (json.loads(s) if isinstance(s, str) else s) if isinstance(x, (int, float)) and 1 <= x <= 9]
    except Exception: return np.nan, np.nan, 0
    if len(v) < 10: return np.nan, np.nan, len(v)
    return np.mean(v[-5:]), np.mean(v[:-5]), len(v)
mm = E.recent_orders.map(mom); E["r5"] = [m[0] for m in mm]; E["rold"] = [m[1] for m in mm]; E["dm"] = E.rold - E.r5
E["r3"] = E.recent_orders.map(lambda s: np.mean([x for x in (json.loads(s) if isinstance(s, str) else s) if 1 <= x <= 9][-3:]) if s is not None and len(s) else np.nan)
# ライン内の位置
def pos(row):
    try:
        for l in json.loads(row.line_json or "[]"):
            ns = [n for x in l["entries"] for n in x["numbers"]]
            if row.number in ns: return ("単騎" if len(ns) == 1 else ["先頭", "番手", "3番手", "3番手"][min(ns.index(row.number), 3)])
    except Exception: pass
    return "不明"
E["lpos"] = [pos(r) for r in E[["line_json", "number"]].itertuples()]
F = E[(E.dm >= 1.5) & (E.pt_rank >= 4)][["race_id", "number", "dm", "r5", "pt_rank", "style", "lpos", "date", "day_index", "rclass", "grade", "entries_number", "race_type"]]
X = T.merge(F.rename(columns={"number": "a"}), on=["race_id", "a"])
X["half"] = np.where(X.date < "20260101", "探す(〜2025)", "確かめ(2026)")
X["ob"] = pd.cut(X.odds, [0, 30, 60, 100, 200, 300], labels=["〜30倍", "30〜60", "60〜100", "100〜200", "200〜300"])
X["dmb"] = pd.cut(X.dm, [1.5, 2.0, 2.5, 9], labels=["1.5〜2.0着", "2.0〜2.5", "2.5以上"], include_lowest=True)
X["ptb"] = pd.cut(X.pt_rank, [3, 5, 7, 9], labels=["4〜5位", "6〜7位", "8〜9位"])
X["day"] = np.where(pd.to_numeric(X.day_index, errors="coerce") == 1, "1日目", "2日目以降")
X["n9"] = np.where(pd.to_numeric(X.entries_number, errors="coerce") >= 9, "9車", "7車以下")
def show(col, lab):
    P(NL + f"### {lab}" + NL + "| 区分 | 探す 点数 | 探す 回収率 | 確かめ 点数 | 確かめ 回収率 |" + NL + "|---|---|---|---|---|")
    for k, g in X.groupby(col, observed=True):
        a = g[g.half.str.startswith("探す")]; b = g[g.half.str.startswith("確かめ")]
        P(f"| {k} | {len(a):,} | {a.ret.mean():.0%} | {len(b):,} | {b.ret.mean():.0%} |")
P("# 勢いの絞り込み（かなり良化×得点4位以下の選手が1着の3連単300倍以下・全部100円）" + NL)
P(f"全部：探す {len(X[X.half.str.startswith('探す')]):,}点 {X[X.half.str.startswith('探す')].ret.mean():.0%}／確かめ {len(X[X.half.str.startswith('確かめ')]):,}点 {X[X.half.str.startswith('確かめ')].ret.mean():.0%}（参考：3連単全部 {T.ret.mean():.0%}）")
for col, lab in (("ob", "倍率の帯"), ("dmb", "良化の大きさ"), ("ptb", "得点の順位"), ("style", "脚質"), ("lpos", "ライン内の位置"), ("rclass", "級"),
                 ("day", "何日目"), ("n9", "車立て"), ("grade", "グレード")):
    show(col, lab)
print("done")
# 追加：先頭の選手（かなり良化×得点4位以下）が1着で、2着が同じラインの番手の組（ラインで決まる形）
L = {}
for rid, lj in RA[["race_id", "line_json"]].itertuples(index=False):
    try:
        for l in json.loads(lj or "[]"):
            ns = [n for x in l["entries"] for n in x["numbers"]]
            if len(ns) >= 2: L[(rid, ns[0])] = ns
    except Exception: pass
Y = X[X.lpos == "先頭"].copy()
Y["b2"] = [(L.get((r, a)) or [0, 0])[1] == b for r, a, b in zip(Y.race_id, Y.a, Y.b)]
Y["b3"] = [len(L.get((r, a)) or []) >= 3 and (L.get((r, a)) or [0, 0, 0])[2] == c for r, a, c in zip(Y.race_id, Y.a, Y.c)]
P(NL + "### 先頭（かなり良化×得点4位以下）が1着 × 2着・3着の形" + NL + "| 形 | 探す 点数 | 探す 回収率 | 確かめ 点数 | 確かめ 回収率 |" + NL + "|---|---|---|---|---|")
for lab, m in (("2着が同じラインの番手", Y.b2), ("2着が番手×3着が3番手（ライン丸ごと）", Y.b2 & Y.b3), ("2着が番手以外", ~Y.b2), ("全部", Y.b2 | ~Y.b2)):
    g = Y[m]; a = g[g.half.str.startswith("探す")]; b = g[g.half.str.startswith("確かめ")]
    P(f"| {lab} | {len(a):,} | {a.ret.mean():.0%} | {len(b):,} | {b.ret.mean():.0%} |")
print("done2")
# 比べる：勢いに関係なく、すべての先頭→番手（2着）の組
E2 = E.copy(); E2["mom"] = (E2.dm >= 1.5) & (E2.pt_rank >= 4)
Z = T.merge(E2[["race_id", "number", "lpos", "mom", "dm", "pt_rank", "date"]].rename(columns={"number": "a"}), on=["race_id", "a"])
Z = Z[Z.lpos == "先頭"]
Z["b2"] = [(L.get((r, a)) or [0, 0])[1] == b for r, a, b in zip(Z.race_id, Z.a, Z.b)]
Z = Z[Z.b2]; Z["half"] = np.where(Z.date < "20260101", "探す", "確かめ")
def ci(g):
    rr = g.groupby("race_id").agg(s=("ret", "sum"), n=("ret", "size")); m = rr.s.sum() / rr.n.sum()
    rng = np.random.default_rng(0); idx = rng.integers(0, len(rr), (1000, len(rr)))
    bs = rr.s.to_numpy()[idx].sum(1) / rr.n.to_numpy()[idx].sum(1)
    return f"{m:.0%}［{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}］"
P(NL + "### 比べる：先頭が1着・同じラインの番手が2着の組（300倍以下・全部100円）、レースごとのブートストラップ95%範囲" + NL)
P("| 先頭の選手 | 探す 点数 | 探す 回収率 | 確かめ 点数 | 確かめ 回収率 |" + NL + "|---|---|---|---|---|")
for lab, m in (("かなり良化×得点4位以下", Z.mom), ("それ以外の先頭すべて", ~Z.mom), ("良化1.0〜1.5着×得点4位以下", Z.dm.between(1.0, 1.5, inclusive="left") & (Z.pt_rank >= 4)),
               ("かなり良化×得点1〜3位", (Z.dm >= 1.5) & (Z.pt_rank <= 3)), ("全部", Z.b2)):
    g = Z[m]; a = g[g.half == "探す"]; b = g[g.half == "確かめ"]
    P(f"| {lab} | {len(a):,} | {ci(a)} | {len(b):,} | {ci(b)} |")
print("done3")
