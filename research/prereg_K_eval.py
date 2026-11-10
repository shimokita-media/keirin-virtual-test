"""★事前登録K の判定（KNOWLEDGE 2026-11-10 12:20 の登録どおり。結果を見てから変えない）。
選手：recent_orders の 1〜9 の着順が10走以上、最近5走の平均がそれより前の平均より1.5着以上良い、得点の順位4位以下（欠場を除く・同点は小さい順位）、2人以上のラインの先頭。
買い目：その選手1着・同じラインの番手2着の3連単、確定300倍以下を全部100円。
合格：期間内で ①回収率100%以上 かつ ②「それ以外の先頭→番手」の組との、レースごとの平均回収率の差の t（ウェルチ）≥ +2.0。
使い方: python -I -X utf8 research/prereg_K_eval.py 出力.md 名前（side_*_名前.pkl・out/名前/cache.pkl） 開始日 終了日"""
import sys, json, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
outp, tag, d0, d1 = sys.argv[1:5]
OUT = open(K + outp, "w", encoding="utf-8"); NL = chr(10)
def P(*a): print(*a, file=OUT, flush=True)
RA = pd.read_pickle(K + f"out/side_races_{tag}.pkl").drop_duplicates("race_id")
E = pd.read_pickle(K + f"out/side_entries_{tag}.pkl"); E = E[E.absent == 0].drop_duplicates(["race_id", "number"])
C = pd.read_pickle(K + f"out/{tag}/cache.pkl")[["race_id", "combo", "odds", "ret"]]
RA = RA[RA.date.between(d0, d1)]
E = E[E.race_id.isin(set(RA.race_id))]
E["pt_rank"] = E.groupby("race_id").race_point.rank(ascending=False, method="min")
def mom(s):
    try: v = [x for x in (json.loads(s) if isinstance(s, str) else s) if isinstance(x, (int, float)) and 1 <= x <= 9]
    except Exception: return np.nan
    return np.mean(v[:-5]) - np.mean(v[-5:]) if len(v) >= 10 else np.nan
E["dm"] = E.recent_orders.map(mom)
L = {}
for rid, lj in RA[["race_id", "line_json"]].itertuples(index=False):
    try:
        for l in json.loads(lj or "[]"):
            ns = [n for x in l["entries"] for n in x["numbers"]]
            if len(ns) >= 2: L[(rid, ns[0])] = ns
    except Exception: pass
E["lead"] = [(r, n) in L for r, n in zip(E.race_id, E.number)]
E["isK"] = E.lead & (E.dm >= 1.5) & (E.pt_rank >= 4)
C = C[C.race_id.isin(set(RA.race_id)) & (C.odds <= 300) & (C.combo.str.len() == 5)].copy()
C["a"] = C.combo.str[0].astype(int); C["b"] = C.combo.str[2].astype(int)
C["lb"] = [(L.get((r, a)) or [0, 0])[1] == b if (r, a) in L else False for r, a, b in zip(C.race_id, C.a, C.b)]
C = C[C.lb].merge(E[["race_id", "number", "isK"]].rename(columns={"number": "a"}), on=["race_id", "a"], how="left")
C["isK"] = C.isK.fillna(False).astype(bool)
k, o = C[C.isK], C[~C.isK]
rk, ro = k.groupby("race_id").ret.mean(), o.groupby("race_id").ret.mean()
t = (rk.mean() - ro.mean()) / np.sqrt(rk.var() / len(rk) + ro.var() / len(ro)) if len(rk) > 1 else float("nan")
rng = np.random.default_rng(0); g = k.groupby("race_id").agg(s=("ret", "sum"), n=("ret", "size"))
bs = [g.s.to_numpy()[i].sum() / g.n.to_numpy()[i].sum() for i in rng.integers(0, len(g), (1000, len(g)))] if len(g) else [np.nan]
roi = k.ret.mean() if len(k) else float("nan")
ok1, ok2 = roi >= 1.0, t >= 2.0
P(f"# ★事前登録K の判定（{d0}〜{d1}、{RA.race_id.nunique():,}R）" + NL)
P("| 項目 | 結果 | 基準 | 判定 |" + NL + "|---|---|---|---|")
P(f"| ①回収率（勢いのある先頭→番手、{len(k):,}点・{k.race_id.nunique():,}R・当たり{int((k.ret > 0).sum())}） | **{roi:.0%}**［{np.percentile(bs, 2.5):.0%}〜{np.percentile(bs, 97.5):.0%}］ | 100%以上 | {'○' if ok1 else '×'} |")
P(f"| ②それ以外の先頭→番手（{len(o):,}点・{o.ret.mean():.0%}）との差の t | **{t:+.2f}** | +2.0 以上 | {'○' if ok2 else '×'} |")
P(NL + f"**判定：{'合格' if ok1 and ok2 else '不合格'}**" + NL)
k3 = k.copy(); k3["c"] = k3.combo.str[4].astype(int)
k3["line3"] = [len(L.get((r, a)) or []) >= 3 and L[(r, a)][2] == c for r, a, c in zip(k3.race_id, k3.a, k3.c)]
P("参考（合否に使わない）：" + f"ライン丸ごと {int(k3.line3.sum())}点 {k3[k3.line3].ret.mean():.0%}／" +
  "／".join(f"{lab} {len(x)}点 {x.ret.mean():.0%}" for lab, x in k.assign(ob=pd.cut(k.odds, [0, 30, 100, 300], labels=["〜30倍", "30〜100倍", "100〜300倍"])).groupby("ob", observed=True)))
print("done", roi, t)
