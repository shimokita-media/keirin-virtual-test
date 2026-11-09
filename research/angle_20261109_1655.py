"""切り口（構造の違う⑨）：欠場で崩れたライン。欠場した選手が並び（line_json）にいたレースで、残された選手（先頭を失った番手、単騎になった選手）を市場が正しく評価しているか。"""
import sys, json
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
RA = pd.read_pickle(K + "out/side_races.pkl")[["race_id", "line_json"]]
E = pd.read_pickle(K + "out/side_entries.pkl")
ab = E[E.absent == 1].groupby("race_id").number.apply(set).to_dict()
info = {}  # (race_id, number) -> 状態
nrace = {"欠場あり": 0, "並びにいた": 0}
for rid, lj in zip(RA.race_id, RA.line_json):
    if rid not in ab: continue
    nrace["欠場あり"] += 1
    try: lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(lj or "[]")]
    except Exception: continue
    hit = False
    for ln in lines:
        gone = [n for n in ln if n in ab[rid]]
        if not gone: continue
        hit = True
        rest = [n for n in ln if n not in ab[rid]]
        for n in rest:
            st = "先頭を失った" if ln[0] in ab[rid] and n == rest[0] else ("単騎になった" if len(rest) == 1 else "ラインが減った")
            info[(rid, n)] = st
    nrace["並びにいた"] += hit
races_ab = set(ab)
a, b, c = combo_parts(T)
# 欠場者を含む目は実際は返還（払戻0ではなく元返し）なので集計から外す
has_absent = pd.Series([any(x in ab.get(r, ()) for x in (p, q_, s)) for r, p, q_, s in zip(T.race_id, a, b, c)], index=T.index)
n_abs = int(has_absent.sum()); n_abs_B = int((has_absent & T.in_B).sum()); n_abs_top = int((has_absent & T.is_top).sum())
T = T[~has_absent].copy(); a, b, c = combo_parts(T)
st = {i: pd.Series([info.get((r, x), "") for r, x in zip(T.race_id, n)], index=T.index) for i, n in enumerate((a, b, c))}
hasab = T.race_id.isin(races_ab)
broken = T.race_id.isin({r for (r, _) in info})
anyst = lambda s: (st[0] == s) | (st[1] == s) | (st[2] == s)
conds = {"欠場なしのレース": ~hasab, "欠場ありのレース": hasab, "欠場で並びが崩れたレース": broken, "欠場はあるが並びは崩れていない": hasab & ~broken,
         "1着が先頭を失った選手": st[0] == "先頭を失った", "先頭を失った選手を含む": anyst("先頭を失った"),
         "1着が単騎になった選手": st[0] == "単騎になった", "単騎になった選手を含む": anyst("単騎になった"), "1着がラインが減った選手": st[0] == "ラインが減った"}
c, c2 = report(sys.argv[1], "欠場で崩れたライン",
               f"欠場ありのレース {nrace['欠場あり']:,}R、うち欠場者が並び（line_json）に入っていた {nrace['並びにいた']:,}R。欠場者を含む目（返還）{n_abs:,}点は除外（うち3連単枠 {n_abs_B}点・一番の目 {n_abs_top}点）。", conds, D=T)
print("候補", len(c), "参考", len(c2), nrace)
