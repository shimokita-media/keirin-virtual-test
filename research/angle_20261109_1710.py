"""切り口（構造の違う⑫）：同じ3人の並べ替え6通りの中の歪み。ある3人の組の中で、市場が「どの順番か」をどう割り振っているか（その目の見込み ÷ 同じ3人の6通りの見込みの合計＝並び順の取り分）。
取り分が大きい順番（本命の順番）と小さい順番（ひっくり返った順番）で、回収率に差があるか＝市場は「3人が誰か」より「順番」を読み違えているか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
q = 1.0 / T.odds; T["pm"] = q / q.groupby(T.race_id).transform("sum")
a, b, c = combo_parts(T)
srt = np.sort(np.column_stack([a, b, c]), axis=1)
T["trio"] = T.race_id + ":" + pd.Series([f"{x}-{y}-{z}" for x, y, z in srt], index=T.index)
g = T.groupby("trio").pm
T["nperm"] = g.transform("size"); T["share"] = T.pm / g.transform("sum")
T["rank_in_trio"] = g.rank(ascending=False, method="first")
full = T.nperm == 6
conds = {"6通りそろう×取り分1位（本命の順番）": full & (T.rank_in_trio == 1), "6通りそろう×取り分2位": full & (T.rank_in_trio == 2),
         "6通りそろう×取り分3〜4位": full & T.rank_in_trio.between(3, 4), "6通りそろう×取り分5〜6位（ひっくり返った順番）": full & (T.rank_in_trio >= 5),
         "取り分50%以上（順番がほぼ決まっている）": full & (T.share >= 0.5), "取り分10%未満": full & (T.share < 0.1),
         "取り分1位×30倍以下": full & (T.rank_in_trio == 1) & (T.odds <= 30), "取り分5〜6位×30倍以下": full & (T.rank_in_trio >= 5) & (T.odds <= 30)}
c1, c2 = report(sys.argv[1], "同じ3人の並べ替え6通りの中の歪み（並び順の取り分）",
                "取り分＝その目の見込み ÷ 同じ3人の6通りの見込みの合計（300倍以下の目だけで6通りそろう組で比べる）。", conds)
# 3人で決まったときの順番の当たり方（較正）
W = T[full & T.trio.isin(set(T[T.ret > 0].trio))].copy(); W["hit"] = (W.ret > 0).astype(float)
W["sb"] = pd.cut(W.share, [0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0])
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 3人が当たったとき、どの順番だったか（取り分ごとの 実際の割合 ÷ 取り分）\n\n| 取り分 | 探す | ③ | ⑥ |\n|---|---|---|---|\n")
    for k, x in W.groupby("sb", observed=True):
        f.write(f"| {k} | " + " | ".join(f"{x[per(x.date)==p].hit.mean() / x[per(x.date)==p].share.mean():.2f}（{(per(x.date)==p).sum()}）" for p in ("探す", "③", "⑥")) + " |\n")
print("候補", len(c1), "参考", len(c2))
