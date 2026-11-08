"""4つ目の未使用期間 2025/8/23〜9/11（最終オッズ、賭け方は払戻×0.95も）"""
import numpy as np, pandas as pd
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
K = "C:/Users/take0/.claude/keirin/out/fresh3/"
T = prep(pd.read_pickle(K + "tri.pkl")); T = T[(T["class"] != "L級") & (T.date <= "20250911")].copy()
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
TB = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]).groupby("race_id").head(6).copy()
TB["bad"] = (TB.nr == 1) & (TB.r0_mk_rank == 1)
W = pd.read_pickle(K + "wide.pkl"); W = W[(W["class"] != "L級") & (W.odds <= 50) & (W.date <= "20250911")].copy()
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0); W["ev0"] = W.pw * W.odds; W["fav_pw"] = W.groupby("race_id").pw.transform("max")
lo, hi = W[["a_pos", "b_pos"]].min(axis=1), W[["a_pos", "b_pos"]].max(axis=1); G = W.grade.astype(str).str.startswith("G")
WS = W[W.same & (lo == 0) & (hi == 2) & W.odds.between(3, 20) & ((W.entries_number >= 9) | G)]
WA = W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (W.fav_pw < 0.6)]
WW = W[W.odds.between(6, 10)]  # 今のワイド枠は割安度0.85（α補正込み）なので近い形で参考
def s(g, w=None):
    if not len(g): return "0点"
    w = pd.Series(1.0, index=g.index) if w is None else w
    by = pd.DataFrame({"r": g.race_id, "i": w, "x": w * g.ret}).groupby("r").sum()
    i = np.random.default_rng(0).integers(0, len(by), (1000, len(by))); bs = by.x.to_numpy()[i].sum(1) / by.i.to_numpy()[i].sum(1)
    return f"**{(w*g.ret).sum()/w.sum():.0%}**［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ {len(g)}点・{g.race_id.nunique()}R・当たり{int((g.ret>0).sum())} 収支{((g.ret-1)*w).sum()*100:+,.0f}円"
print(f"期間 {T.date.min()}〜{T.date.max()}（{T.date.nunique()}日・{T.race_id.nunique()}R） 3連単全部 {T.ret.mean():.0%} ワイド全部 {W.ret.mean():.0%}")
print("- 🎰3連単枠（今の通知）:", s(TB))
print("- 　外す:", s(TB[~TB.bad]))
w = pd.Series(np.where(TB.day_index == 2, 2.0, 1.0), index=TB.index)[~TB.bad]
print("- 　外す＋2日目2倍:", s(TB[~TB.bad], w))
print("- 　日目別:", " ｜ ".join(f"{d}日目 {g.ret.mean():.0%}({len(g)})" for d, g in TB.groupby(TB.day_index.clip(upper=4))))
for i, nm in enumerate(["①9車2日目〜3着3番手30倍", "②9車2日目〜3人同ライン30倍", "③9車3人同ライン割安30倍", "④ライン順◎割安60倍", "⑤G戦一番人気1着3着3番手10倍"]):
    g = T[R[i]]; print(f"- 　{nm}: {g.ret.mean():.0%}（{len(g)}点・当たり{int((g.ret>0).sum())}）")
print("- 👀形のワイド:", s(WS)); print("- 👀ワイドA:", s(WA))
print("- 3連単枠を払戻5%減で:", f"{(TB.ret*0.95).mean():.0%}", " 外す＋2日目2倍で:", f"{((TB[~TB.bad].ret*0.95)*w).sum()/w.sum():.0%}")
