"""一番の目×割高な目を外す の目で、市場の見込み pn と実際の当たりの関係（そのレースの当たる確率を出すための補正）。
prereg_eval_y4_avoid.py と同じ選び方を y4・y5・y6 に当てる"""
import gc, numpy as np, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
out = []
for tag, f in (("y4", "out/y4/cache.pkl"), ("y5", "out/y5/cache.pkl"), ("y6", "out/y6/cache.pkl")):
    T = pd.read_pickle(K + f)
    T = T[T.odds <= 300].reset_index(drop=True)
    q = 1 / T.odds; T["pn"] = q / q.groupby(T.race_id).transform("sum")
    T["fav"] = T.groupby("race_id").odds.transform("min")
    top = T[T.is_top & (T.odds <= 30)][["race_id", "date", "combo", "odds", "ret", "pn", "fav", "race_type", "s01", "s12", "r0_pos", "r1_pos"]].copy()
    del T; gc.collect()
    E = pd.read_pickle(K + f"out/side_entries_{tag}.pkl"); R = pd.read_pickle(K + f"out/side_races_{tag}.pkl").drop_duplicates("race_id")
    E = E.merge(R[["race_id", "date", "cup_id"]], on="race_id", how="left")
    ab = set(E[E.absent == 1].race_id); EA = E[E.absent != 1].copy()
    EA["rp"] = pd.to_numeric(EA.race_point, errors="coerce"); EA["ptr"] = EA.groupby("race_id").rp.rank(ascending=False, method="min")
    EA["term"] = pd.to_numeric(EA.term, errors="coerce"); EA["ym"] = EA.date.str[:6]; EA["tgap"] = EA.groupby("ym").term.transform("max") - EA.term
    EA["d"] = pd.to_datetime(EA.date)
    cup = EA.groupby(["player_id", "cup_id"]).d.agg(["min", "max"]).reset_index().sort_values(["player_id", "min"])
    cup["rest"] = (cup["min"] - cup.groupby("player_id")["max"].shift()).dt.days - 1
    EA = EA.merge(cup[["player_id", "cup_id", "rest"]], on=["player_id", "cup_id"], how="left")
    look = EA.set_index(["race_id", "number"])
    for j, nm in ((0, "a"), (2, "c")):
        sub = look.reindex(list(zip(top.race_id, top.combo.str.split("-").str[j].astype(int))))
        top[f"{nm}_ptr"] = sub.ptr.to_numpy(); top[f"{nm}_rest"] = sub.rest.to_numpy(); top[f"{nm}_tgap"] = sub.tgap.to_numpy()
    rt = top.race_type.fillna("").astype(str)
    bad = (top.race_id.isin(ab) | (top.fav <= 3) | (top.a_ptr == 1) | (top.a_rest >= 21) | (top.c_tgap <= 1)
           | (rt.str.contains("決勝") & ~rt.str.contains("準") & (top.s01 == 1) & (top.s12 == 1))
           | (rt.str.contains("準決勝") & (top.r0_pos == 1) & (top.r1_pos == 0) & (top.s01 == 1)))
    G = top[~bad].copy(); G["yr"] = tag; out.append(G)
    print(tag, len(G), round(G.ret.mean(), 3), flush=True)
A = pd.concat(out); A["hit"] = A.ret > 0
A.to_pickle(K + "out/av_y456.pkl")
print("全部", len(A), "見込みの平均", round(A.pn.mean(), 4), "実際", round(A.hit.mean(), 4), "倍率", round(A.hit.sum() / A.pn.sum(), 3))
for y, g in A.groupby("yr"):
    print(y, len(g), "見込み", round(g.pn.mean(), 4), "実際", round(g.hit.mean(), 4), "倍率", round(g.hit.sum() / g.pn.sum(), 3))
A["ob"] = pd.cut(A.odds, [0, 7, 10, 15, 20, 30])
print(A.groupby("ob", observed=True).agg(n=("hit", "size"), pn=("pn", "mean"), act=("hit", "mean"), roi=("ret", "mean")).assign(k=lambda d: d.act / d.pn).round(3))
