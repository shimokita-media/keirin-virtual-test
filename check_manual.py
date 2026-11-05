"""チャットで提示した手動の買い目（out/manual_picks_YYYYMMDD.json）を確定結果と照合する。各100円で計算。"""
import json
import sqlite3
import sys

import kr


def main(day):
    d = json.load(open(f"{kr.BASE}/out/manual_picks_{day}.json", encoding="utf-8"))
    c = kr.db()
    def res(rid):
        r = [x[0] for x in c.execute("SELECT number FROM results WHERE race_id=? AND rank BETWEEN 1 AND 3 ORDER BY rank", (rid,))]
        return "-".join(map(str, r)) if r else None
    def pay(rid, bt, cb):
        p = c.execute("SELECT payout FROM payouts WHERE race_id=? AND bet_type=? AND combo=?", (rid, bt, cb)).fetchone()
        return p[0] if p else 0
    def fin(rid, bt, cb):
        o = c.execute("SELECT odds FROM odds WHERE race_id=? AND bet_type=? AND combo=? AND phase='POST' AND source='winticket' "
                      "ORDER BY fetched_at DESC LIMIT 1", (rid, bt, cb)).fetchone()
        return o[0] if o else None
    out = []
    for name, items in [("先行型", [(x["race_id"], x["レース"], [[x["bet_type"], x["combo"]]]) for x in d["先行型"]]),
                        ("万車券", d["万車券"])]:
        inv = ret = n_settled = 0
        out.append(f"\n## {name}")
        for rid, label, bets in items:
            r = res(rid)
            if not r:
                out.append(f"- {label}: 未確定")
                continue
            n_settled += 1
            line = []
            for bt, cb in bets:
                p = pay(rid, bt, cb)
                inv += 100; ret += p
                line.append(f"{bt}{cb}{'◎' + str(p) + '円' if p else '×'}(確定{fin(rid, bt, cb)}倍)")
            tri = pay(rid, "3連単", r)
            out.append(f"- {label} 着順 {r}（3連単 {tri:,}円）: " + " / ".join(line))
        out.append(f"→ {n_settled}レース確定 投資 {inv:,}円 / 払戻 {ret:,}円 / 損益 {ret - inv:+,}円")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else kr.now().strftime("%Y%m%d"))
