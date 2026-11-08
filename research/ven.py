import sqlite3
exec(open("robust.py", encoding="utf-8").read().split("def per(d)")[0])
VEN = dict(sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True).execute("SELECT race_id, venue FROM races"))
def s(g):
    by = g.groupby("race_id").agg(inv=("ret", "size"), r=("ret", "sum"))
    i = np.random.default_rng(0).integers(0, len(by), (1000, len(by))); bs = by.r.to_numpy()[i].sum(1) / by.inv.to_numpy()[i].sum(1)
    return f"{g.ret.mean():.0%}［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］({len(g)}点)"
for lab, X in (("3連単枠", TB), ("形のワイド", WS), ("ワイドA", WA)):
    ven = X.race_id.map(VEN)
    v = X.groupby(ven).agg(n=("ret", "size"), r=("ret", "mean"), tot=("ret", "sum")); v["gain"] = v.tot - v.n; v = v.sort_values("gain", ascending=False)
    print(f"## {lab}: 競輪場 {len(v)}、100%超えの場 {(v.r >= 1).sum()}/{len(v)}（10点以上の場だけだと {(v[v.n>=10].r>=1).sum()}/{(v.n>=10).sum()}）")
    print("  もうけ上位5場:", " ".join(f"{k} {r:.0%}({n}点)" for k, (n, r) in v[["n", "r"]].head(5).iterrows()))
    print(f"  上位3場を除く {s(X[~ven.isin(v.index[:3])])} ／ 上位5場を除く {s(X[~ven.isin(v.index[:5])])}")
