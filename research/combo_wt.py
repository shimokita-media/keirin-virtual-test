"""ワイドと3連単の組み合わせ。2025/2〜8/3＋2026/2〜8（最終オッズ）"""
import numpy as np, pandas as pd
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
A = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl"), pd.read_pickle("C:/Users/take0/.claude/keirin/out/fresh/tri.pkl")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(A); T = T[(T["class"] != "L級") & (T.date < "20260901")].copy()
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
TB = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6)[["race_id", "date", "combo", "odds", "ret"]].assign(kind="3連単枠")
W = pd.concat([pd.read_pickle("wide_all3.pkl"), pd.read_pickle("C:/Users/take0/.claude/keirin/out/fresh/wide.pkl")]).drop_duplicates(["race_id", "combo"])
W = W[(W["class"] != "L級") & (W.odds <= 50) & (W.date < "20260901")].copy()
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0); W["ev0"] = W.pw * W.odds; W["fav_pw"] = W.groupby("race_id").pw.transform("max")
WA = W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (W.fav_pw < 0.6)][["race_id", "date", "combo", "odds", "ret"]].assign(kind="ワイドA")
days = set(T.date) & set(W.date)
TB, WA = TB[TB.date.isin(days)], WA[WA.date.isin(days)]
def stat(g, lab):
    by = g.groupby("race_id").agg(d=("date", "first"), inv=("ret", "size"), r=("ret", "sum")).sort_values("d")
    net = np.cumsum(by.r - by.inv).to_numpy() * 100; dd = (np.maximum.accumulate(np.r_[0, net]) - np.r_[0, net]).max()
    st = cur = 0
    for v in by.r.to_numpy(): cur = 0 if v > 0 else cur + 1; st = max(st, cur)
    dn = g.groupby("date").ret.agg(["sum", "size"]); losing = (dn["sum"] < dn["size"]).mean()
    mm = g.groupby(g.date.str[:6]).ret.mean()
    i = np.random.default_rng(0).integers(0, len(by), (2000, len(by))); bs = by.r.to_numpy()[i].sum(1) / by.inv.to_numpy()[i].sum(1)
    print(f"- {lab}: 1日{len(g)/len(days):.1f}点 回収率 **{g.ret.mean():.0%}**［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ 収支{int(net[-1]):+,}円 最大のへこみ−{int(dd):,}円 最大連敗{st}R 負けた日{losing:.0%} 100%超えの月{(mm>=1).sum()}/{len(mm)}")
print(f"対象 {len(days)}日")
stat(WA, "ワイドAだけ"); stat(TB, "3連単枠だけ"); stat(pd.concat([WA, TB]), "両方とも買う（そのまま足す）")
# 重なり
both = set(WA.race_id) & set(TB.race_id); print(f"  両方に買い目があるレース {len(both)}（ワイドA {WA.race_id.nunique()}R・3連単枠 {TB.race_id.nunique()}R）")
stat(pd.concat([WA[WA.race_id.isin(both)], TB[TB.race_id.isin(both)]]), "両方そろったレースだけ（両方買う）")
stat(TB[TB.race_id.isin(both)], "両方そろったレースの3連単だけ"); stat(WA[WA.race_id.isin(both)], "両方そろったレースのワイドだけ")
# 3連単枠の保険：3連単枠のレースで、買い目に含まれる同じラインの2人のワイドを足す
pairs = TB.assign(c=TB.combo.str.split("-")).explode("c")
P = []
for rid, g in TB.groupby("race_id"):
    for cb in g.combo:
        a, b, d = map(int, cb.split("-")); P += [(rid, f"{min(x,y)}-{max(x,y)}") for x, y in ((a, b), (b, d), (a, d))]
P = pd.DataFrame(P, columns=["race_id", "combo"]).drop_duplicates()
WW = W[["race_id", "date", "combo", "odds", "ret", "same", "ev0"]].merge(P, on=["race_id", "combo"])
stat(WW[WW.same], "3連単枠のレースで、買い目の同じライン2人のワイド（全部）")
stat(WW[WW.same & (WW.ev0 >= 1.0)], "同上・割安なものだけ")
stat(pd.concat([TB, WW[WW.same & (WW.ev0 >= 1.0)].drop(columns=["same", "ev0"])]), "3連単枠＋その割安ワイド")
# ワイドAのレースで、その2人を含むライン順の3連単を足す
