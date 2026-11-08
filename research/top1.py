"""一番の目1点：①5つ目の未使用期間（2025/9/12〜9/27）②細かい選び方を6つの期間で比べる（最終オッズ）"""
import numpy as np, pandas as pd
exec(open("C:/Users/take0/.claude/keirin/research/tri_live.py", encoding="utf-8").read().split("def rules")[0])
K = "C:/Users/take0/.claude/keirin/out/"
A = pd.concat([pd.read_pickle("tri3_all.pkl"), pd.read_pickle("tri3_new.pkl")] + [pd.read_pickle(K + f + "/tri.pkl") for f in ("fresh", "fresh2", "fresh3", "fresh4")]).drop_duplicates(["race_id", "combo"]).reset_index(drop=True)
T = prep(A); T = T[(T["class"] != "L級") & (T.date <= "20260831") & ~((T.date >= "20250928") & (T.date < "20260101"))].copy()
s01, s12 = T.s01 == 1, T.s12 == 1; third = (T.r2_pos == 2) & s12; same3 = s01 & s12; order = same3 & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
nine, d2 = T.entries_number >= 9, T.day_index >= 2
R = [third & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & d2, same3 & (T.odds <= 30) & nine & (T.g_tf > 0),
     order & (T.odds <= 60) & (T.r0_prediction_mark >= 3) & (T.g_tf > 0) & (T.g_ex > 0), third & (T.odds <= 10) & (T.G == 1) & (T.r0_mk_rank == 1)]
T["nr"] = sum(r.astype(int) for r in R)
X = T[T.nr > 0].sort_values(["race_id", "nr", "odds"], ascending=[True, False, True])
B = X.groupby("race_id").head(6).copy(); top = X.groupby("race_id").head(1).copy()
blk = lambda d: np.select([d.between("20250201", "20250529"), d.between("20250530", "20250705"), d.between("20250706", "20250803"), d.between("20250804", "20250822"), d.between("20250823", "20250911"), d.between("20250912", "20250927"), d < "20260601"],
                          ["探す25", "未①", "未②", "未③", "未④", "★未⑤", "探す26前"], "探す26後")
order_ = ["探す25", "探す26前", "探す26後", "未①", "未②", "未③", "未④", "★未⑤"]
def row(g, lab):
    bb = blk(g.date); cells = " ｜ ".join(f"{p} {g[bb == p].ret.mean():.0%}" if (bb == p).sum() else f"{p} −" for p in order_)
    print(f"- {lab}: 通し **{g.ret.mean():.0%}**（{len(g)}点） ｜ {cells}")
print(f"★未⑤ {T[blk(T.date)=='★未⑤'].date.nunique()}日・{T[blk(T.date)=='★未⑤'].race_id.nunique()}R、3連単全部 {T[blk(T.date)=='★未⑤'].ret.mean():.0%}")
row(B, "今の3連単枠（最大6点）"); row(top, "⭐一番の目1点")
print("\n## 一番の目の細かい選び方（全部の期間で比べる。期間ごとにブレないものが良い）")
for lab, m in [("一番の目・20倍以下だけ", top.odds <= 20), ("一番の目・15倍以下だけ", top.odds <= 15), ("一番の目・法則2つ以上だけ", top.nr >= 2), ("一番の目・法則3つ以上だけ", top.nr >= 3),
               ("一番の目・9車だけ", top.entries_number >= 9), ("一番の目・2日目以降だけ", top.day_index >= 2), ("一番の目・1着が一番人気の選手以外", top.r0_mk_rank != 1),
               ("一番の目・ライン順(先→番→3)", (top.r0_pos == 0) & (top.r1_pos == 1) & (top.r2_pos == 2)), ("一番の目・番→先→3", (top.r0_pos == 1) & (top.r1_pos == 0) & (top.r2_pos == 2))]:
    row(top[m], lab)
