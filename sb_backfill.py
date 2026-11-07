"""過去のレースの S（スタート取り）・B（バック）の回数だけを出走表から取り直して entries に書き込む。
オッズや結果は触らない。既に記録済みのレースは飛ばす。アクセス間隔は kr.REQ_INTERVAL のまま。
使い方: python sb_backfill.py 20261001 20261031"""
import sqlite3
import sys

import kr


def main(d0, d1):
    # 取り直しの間だけ、Windows のアイドルスリープを止める（終われば元に戻る。蓋を閉じた・手動スリープは止めない）
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass
    con = kr.db()
    con.row_factory = sqlite3.Row
    rs = con.execute("""SELECT * FROM races r WHERE date BETWEEN ? AND ?
                        AND EXISTS (SELECT 1 FROM entries e WHERE e.race_id=r.race_id AND e.agari_n IS NULL)
                        ORDER BY date, close_at""", (d0, d1)).fetchall()
    print(len(rs), "races", flush=True)
    for i, r in enumerate(rs, 1):
        try:
            q, _ = kr.wt_state(kr.race_url(r))
            recs = {x["playerId"]: x for x in q["FETCH_KEIRIN_RACE"]["records"]}
            for pid, x in recs.items():
                con.execute("""UPDATE entries SET n_standing=?, n_back=?, agari_avg=?, agari_best=?, agari_n=?
                               WHERE race_id=? AND player_id=?""",
                            (x.get("standing"), x.get("back"), *kr.agari(x), r["race_id"], pid))
            con.commit()
        except Exception as e:
            print("ERR", r["race_id"], repr(e)[:150], flush=True)
        if i % 100 == 0 or i == len(rs):
            print(r["date"], f"{i}/{len(rs)}", kr.now().strftime("%H:%M:%S"), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
