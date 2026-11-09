"""切り口：人気の割れ方（レースの一番人気の3連単の倍率＝人気の集中度）。本命がはっきりしたレースと混戦で、市場の歪み方が違うか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
OUT = open(sys.argv[1], "w", encoding="utf-8")
def P(*a): print(*a, file=OUT, flush=True)
fav = T.groupby("race_id").odds.min(); T["fav_odds"] = T.race_id.map(fav)
bins = [0, 3, 5, 8, 12, 20, 1e9]; labs = ["一番人気〜3倍（大本命）", "3〜5倍", "5〜8倍", "8〜12倍", "12〜20倍", "20倍超（大混戦）"]
T["conc"] = pd.cut(T.fav_odds, bins, labels=labs)
B2, top2 = T[T.in_B], T[T.is_top]
P("# 切り口：人気の割れ方（レースの一番人気の3連単の倍率）\n")
P("回収率（点数）を 探す / ③ / ⑥ の順に。最終オッズ・各100円。\n")
P("| 人気の割れ方 | レース数 | 3連単全部 | 30倍以下 | 30倍以下×ライン3人 | 3連単枠 | 一番の目 |")
P("|---|---|---|---|---|---|---|")
same3 = (T.s01 == 1) & (T.s12 == 1)
rows = []
for lb in labs:
    m = T.conc == lb
    cells = [fmt(summ(T[m])), fmt(summ(T[m & (T.odds <= 30)])), fmt(summ(T[m & (T.odds <= 30) & same3])), fmt(summ(B2[B2.conc == lb])), fmt(summ(top2[top2.conc == lb]))]
    P(f"| {lb} | {T[m].race_id.nunique()} | " + " | ".join(cells) + " |")
    for nm, g in (("30倍以下", T[m & (T.odds <= 30)]), ("30倍以下×ライン3人", T[m & (T.odds <= 30) & same3]), ("3連単枠", B2[B2.conc == lb]), ("一番の目", top2[top2.conc == lb])):
        s = summ(g); rows.append((lb, nm, s))
P("\n## 候補（探す t≥2.5 かつ 3期間とも100%超）")
c = [(a, b, s) for a, b, s in rows if s["探す"][2] >= 2.5 and all(s[k][1] > 1 for k in ("探す", "③", "⑥"))]
P("\n".join(f"- {a} × {b}: {fmt(s)}（t={s['探す'][2]:.1f}）" for a, b, s in c) or "- なし")
P("\n## 参考：3期間とも100%超（tは問わない）")
c2 = [(a, b, s) for a, b, s in rows if all(s[k][1] > 1 for k in ("探す", "③", "⑥"))]
P("\n".join(f"- {a} × {b}: {fmt(s)}（t={s['探す'][2]:.1f}）" for a, b, s in c2) or "- なし")
