exec(open("top1.py", encoding="utf-8").read().split("blk = lambda")[0].replace('("fresh", "fresh2", "fresh3", "fresh4")', '("fresh", "fresh2", "fresh3", "fresh4", "fresh5")').replace('(T.date >= "20250928")', '(T.date >= "20251012")'))
N = lambda d: d.between("20250928", "20251011")
print(f"★未⑥ 2025/9/28〜10/11 {T[N(T.date)].date.nunique()}日・{T[N(T.date)].race_id.nunique()}R 3連単全部 {T[N(T.date)].ret.mean():.0%}")
for nm, g in (("3連単枠", B), ("一番の目1点", top), ("一番の目×法則3つ以上", top[top.nr >= 3]), ("一番の目×ライン順", top[(top.r0_pos == 0) & (top.r1_pos == 1) & (top.r2_pos == 2)])):
    x = g[N(g.date)]; print(f"- {nm}: {x.ret.mean():.0%}（{len(x)}点・当たり{int((x.ret>0).sum())}） ｜ 通し {g.ret.mean():.0%}")
W = pd.read_pickle("C:/Users/take0/.claude/keirin/out/fresh5/wide.pkl"); W = W[(W["class"] != "L級") & (W.odds <= 50) & (W.date <= "20251011")].copy()
W["same"] = (W.a_line_idx == W.b_line_idx) & (W.a_line_idx >= 0); W["ev0"] = W.pw * W.odds; W["fav_pw"] = W.groupby("race_id").pw.transform("max")
lo, hi = W[["a_pos", "b_pos"]].min(axis=1), W[["a_pos", "b_pos"]].max(axis=1); G = W.grade.astype(str).str.startswith("G")
for nm, g in (("形のワイド", W[W.same & (lo == 0) & (hi == 2) & W.odds.between(3, 20) & ((W.entries_number >= 9) | G)]), ("ワイドA", W[(W.ev0 >= 1.0) & (W.odds < 20) & W.same & (W.fav_pw < 0.6)])):
    print(f"- {nm}: {g.ret.mean():.0%}（{len(g)}点・当たり{int((g.ret>0).sum())}）")
print("ワイド全部", f"{W.ret.mean():.0%}")
