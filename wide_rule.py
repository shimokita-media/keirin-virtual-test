"""ワイドの様子見用の2つ（2026-11-09〜、通知なし・記録のみ）。どちらも4期間すべてで回収率100%超え（最終オッズ）
B3A ワイドA：3連単から見た割安度1.0以上 × 20倍未満 × 同じラインの2人 × 本命が強くない（一番人気のワイドの見込み60%未満）
B3K 形のワイド：同じラインの先頭と3番手 × 3〜20倍 × 9車立てかG戦（割安度は見ない＝締切前でも崩れにくい）"""
import json

LABELS = {"B3A": "ワイドA（割安×同ライン×本命が強くない）", "B3K": "形のワイド（同ライン先頭-3番手×3〜20倍×9車かG戦）"}


def _pw(odds):
    q = {c: 1.0 / v[0] for c, v in odds.get("3連単", {}).items() if v and v[0] and v[0] > 0}
    s = sum(q.values()); pw = {}
    if not s:
        return pw
    for c, x in q.items():
        a, b, d = map(int, c.split("-"))
        for i, j in ((a, b), (a, d), (b, d)):
            k = f"{min(i, j)}-{max(i, j)}"; pw[k] = pw.get(k, 0) + x / s
    return pw


def picks(con, row, odds):
    """戻り値 {"B3A": [...], "B3K": [...]}（各100円、最大5点）"""
    out = {"B3A": [], "B3K": []}
    if (row["class"] or "") == "L級" or not odds.get("ワイド"):
        return out
    lines = [[n for x in l["entries"] for n in x["numbers"]] for l in json.loads(row["line_json"] or "[]")]
    where = {n: (i, l.index(n)) for i, l in enumerate(lines) for n in l}
    pw = _pw(odds); fav = max(pw.values()) if pw else 1
    nine = (row["entries_number"] or 0) >= 9; G = str(row["grade"] or "").startswith("G")
    for c, (o, _mx, _pop) in odds["ワイド"].items():
        if not o or o > 50:
            continue
        a, b = map(int, c.split("-"))
        if a not in where or b not in where or where[a][0] != where[b][0]:
            continue
        ev0 = pw.get(c, 0) * o
        if ev0 >= 1.0 and o < 20 and fav < 0.6:
            out["B3A"].append({"bet_type": "ワイド", "combo": c, "odds": o, "p": pw.get(c), "ev": ev0})
        if sorted((where[a][1], where[b][1])) == [0, 2] and 3 <= o <= 20 and (nine or G):
            out["B3K"].append({"bet_type": "ワイド", "combo": c, "odds": o, "p": pw.get(c), "ev": ev0})
    out["B3A"] = sorted(out["B3A"], key=lambda r: -r["ev"])[:5]
    out["B3K"] = sorted(out["B3K"], key=lambda r: r["odds"])[:5]
    return out
