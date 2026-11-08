"""点数の手がかりを決めた後に入ったデータ（2025/10/12〜11/21）で、決めた買い方をそのまま答え合わせ（最終オッズ）"""
import sys, sqlite3, numpy as np, pandas as pd
sys.path.insert(0, "C:/Users/take0/.claude/keirin")
import tri_rule
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
T = prep(pd.read_pickle("C:/Users/take0/.claude/keirin/out/fresh6/tri.pkl")); T = T[(T["class"] != "L級") & (T.date <= "20251121")].copy()
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True]); B = X.groupby("race_id").head(6); top = X.groupby("race_id").head(1).copy()
con = sqlite3.connect("file:C:/Users/take0/.claude/keirin/keirin.sqlite?mode=ro", uri=True); con.row_factory = sqlite3.Row
top["sc"] = [max(tri_rule.card_score(con, con.execute("SELECT * FROM races WHERE race_id=?", (r,)).fetchone(), cb), 0) for r, cb in zip(top.race_id, top.combo)]
pay3 = dict(((r, c), p / 100) for r, c, p in con.execute(f"SELECT race_id, combo, payout FROM payouts WHERE bet_type='3連複' AND race_id IN ({','.join('?' * top.race_id.nunique())})", tuple(top.race_id.unique())))
top["trio_ret"] = [pay3.get((r, "-".join(sorted(c.split("-"), key=int))), 0) for r, c in zip(top.race_id, top.combo)]
def st(g, lab):
    if not len(g): print(f"- {lab}: 0点"); return
    by = g.groupby("race_id").agg(i=("ret", "size"), x=("ret", "sum")); i = np.random.default_rng(0).integers(0, len(by), (2000, len(by))); bs = by.x.to_numpy()[i].sum(1) / by.i.to_numpy()[i].sum(1)
    print(f"- {lab}: **{g.ret.mean():.0%}**［{np.percentile(bs,2.5):.0%}〜{np.percentile(bs,97.5):.0%}］ {len(g)}点・当たり{int((g.ret>0).sum())} 月: " + " ".join(f"{m[4:]}月{x.ret.mean():.0%}" for m, x in g.groupby(g.date.str[:6])))
print(f"★本当の答え合わせ 2025/10/12〜11/21（{T.date.nunique()}日・{T.race_id.nunique()}R）3連単全部 {T.ret.mean():.0%}")
st(B, "3連単枠"); st(top, "一番の目"); st(top[top.nr >= 3], "一番の目×法則3つ以上")
for k in range(0, 6):
    g = top[top.sc == k]
    if len(g): print(f"  点数{k}: {g.ret.mean():.0%}（{len(g)}点・当たり{int((g.ret>0).sum())}）")
st(top[top.sc >= 3], "⭐一番の目×点数3以上"); st(top[top.sc >= 2], "一番の目×点数2以上")
S = top[top.sc >= 3]; w = S.sc.map(lambda s: 5 if s >= 5 else 1)
inv = (w * 100 + 100).sum(); back = (S.ret * w * 100 + S.trio_ret * 100).sum()
print(f"- 🏆最強枠（3連単 5点500円・3〜4点100円＋3連複100円）: {back/inv:.0%}（投資{inv:,.0f}円→払戻{back:,.0f}円）")
