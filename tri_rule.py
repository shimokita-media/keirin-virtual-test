"""3連単枠 B3T（2026-11-09〜）。3つの期間（探した期間・未使用2期間）すべてで回収率100%超えだった「形の法則」5つ（KNOWLEDGE ★事前登録G の 2・3・4・6・8）。
締切2〜3分前の倍率で判断。各100円、1レース最大6点（重複は1点にまとめる）"""
import json, math, re

RULES = {
    "R2": "9車・2日目以降・3着が同じラインの3番手・30倍以下",
    "R3": "9車・2日目以降・3人とも同じライン・30倍以下",
    "R4": "9車・3人とも同じライン・3連複から割安・30倍以下",
    "R6": "ライン順・1着が◎・割安（3連複と2車単）・60倍以下",
    "R8": "G戦・1着が一番人気の選手・3着が同じラインの3番手・10倍以下",
}


def _norm(d):
    q = {c: 1.0 / v[0] for c, v in d.items() if v and v[0] and v[0] > 0}
    s = sum(q.values())
    return {c: x / s for c, x in q.items()} if s else {}


def picks(con, row, odds, cap=6):
    if (row["class"] or "") == "L級" or not odds.get("3連単"):
        return []
    rid = row["race_id"]
    marks = dict(con.execute("SELECT number, prediction_mark FROM entries WHERE race_id=? AND absent=0", (rid,)).fetchall())
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(row["line_json"] or "[]")]
    where = {n: (i, l.index(n)) for i, l in enumerate(lines) for n in l}  # 番号 → (ライン番号, ライン内の位置 0=先頭)
    P = _norm(odds["3連単"]); TF = _norm(odds.get("3連複", {})); EX = _norm(odds.get("2車単", {}))
    p3, xy, st = {}, {}, {}
    for c, p in P.items():
        a, b, d = map(int, c.split("-"))
        for n in (a, b, d):
            p3[n] = p3.get(n, 0) + p
        if odds["3連単"][c][0] <= 300:  # 検証と同じく、割安度の分母は300倍以下の目だけで計算
            xy[(a, b)] = xy.get((a, b), 0) + p
            k = tuple(sorted((a, b, d))); st[k] = st.get(k, 0) + p
    top = max(p3.values()) if p3 else 0
    nine = (row["entries_number"] or 0) >= 9
    d2 = (row["day_index"] or 0) >= 2
    G = str(row["grade"] or "").startswith("G")
    out = {}
    for c, (o, _mx, _pop) in odds["3連単"].items():
        if not o or o > 60:
            continue
        a, b, d = map(int, c.split("-"))
        if a not in where or b not in where or d not in where:
            continue
        (la, pa), (lb, pb), (ld, pd_) = where[a], where[b], where[d]
        s01, s12 = la == lb, lb == ld
        third = s12 and pd_ == 2
        same3 = s01 and s12
        order = same3 and (pa, pb, pd_) == (0, 1, 2)
        k = tuple(sorted((a, b, d)))
        g_tf = math.log(max(TF.get("-".join(map(str, k)), 0), 1e-9)) - math.log(max(st.get(k, 0), 1e-9))
        g_ex = math.log(max(EX.get(f"{a}-{b}", 0), 1e-9)) - math.log(max(xy.get((a, b), 0), 1e-9))
        hit = []
        if third and o <= 30 and nine and d2: hit.append("R2")
        if same3 and o <= 30 and nine and d2: hit.append("R3")
        if same3 and o <= 30 and nine and g_tf > 0: hit.append("R4")
        if order and o <= 60 and (marks.get(a) or 0) >= 3 and g_tf > 0 and g_ex > 0: hit.append("R6")
        if third and o <= 10 and G and p3.get(a, 0) >= top - 1e-12: hit.append("R8")
        if hit:
            out[c] = {"bet_type": "3連単", "combo": c, "odds": o, "rules": hit, "p": P.get(c)}
    res = sorted(out.values(), key=lambda r: (-len(r["rules"]), r["odds"]))
    return res[:cap]


def card_score(con, row, combo):
    """出走表の点数（2026-11-09 追加、KNOWLEDGE 参照）：先頭のBが一番多い・先頭34歳以上・3番手のコメントがはっきりしない・
    ラインの得点がいちばん強いほかのラインより低い・3着の選手の上がりがレース1〜2位 を各+1、4人ラインは-1"""
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(row["line_json"] or "[]")]
    E = {r[0]: r for r in con.execute("SELECT number, COALESCE(n_back,0), age, comment, race_point, agari_avg, name FROM entries WHERE race_id=? AND absent=0", (row["race_id"],))}
    d = int(combo.split("-")[2]); main = next((l for l in lines if d in l), None)
    if not main or len(main) < 2: return 0
    sc = 0
    if E.get(main[0], (0, 0))[1] >= max(E.get(l[0], (0, 0))[1] for l in lines): sc += 1
    if (E.get(main[0], (0, 0, 0))[2] or 0) >= 34: sc += 1
    cm3 = str(E[main[2]][3] or "") if len(main) >= 3 and main[2] in E else ""
    sur = str(E[main[1]][6] or "")[:2] if main[1] in E else ""
    if len(main) < 3 or not (re.search(r"[3３]番手", cm3) or (sur and sur in cm3)): sc += 1
    rp = lambda l: (lambda v: sum(v) / len(v) if v else float('nan'))([E[n][4] for n in l if n in E and E[n][4] is not None])
    oth = [rp(l) for l in lines if l is not main and len(l) >= 2]
    if oth and rp(main) < max(oth): sc += 1
    ad = E.get(d, (None,) * 6)[5]  # 3着の選手の上がりがレースで1〜2位（同タイムは上の順位に数える）
    if ad is not None and sum(1 for n in E if E[n][5] is not None and E[n][5] < ad) <= 1: sc += 1
    if len(main) >= 4: sc -= 1
    return sc




def stake_hint(score):
    """点数ごとの金額の目安（2026-11-09 ユーザー指定：5点=500円、3〜4点=100円）。実際に買うかどうかはユーザーの判断"""
    return 500 if score >= 5 else (100 if score >= 3 else 0)
