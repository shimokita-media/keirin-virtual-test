"""法則枠の買い目を、Windows の通知と「今日の買い目」ファイル（デスクトップ）で知らせる。"""
import base64
import os
import sqlite3
import subprocess
import sys

import kr

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")


def toast(title, body):
    """Windows 標準のトースト通知（追加インストール不要）。失敗しても処理は止めない"""
    if sys.platform != "win32":
        return
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "''")
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{esc(title)}</text><text>{esc(body)}</text></binding></visual></toast>')
$n = [Windows.UI.Notifications.ToastNotification]::new($x)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($n)
"""
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                       capture_output=True, timeout=20)
    except Exception:
        pass


def write_today(con, day):
    """その日の法則枠の買い目と結果を、デスクトップの「競輪 今日の買い目.txt」に書き出す"""
    con.row_factory = sqlite3.Row
    rows = con.execute("""SELECT p.*, r.venue, r.race_no, r.grade FROM predictions p JOIN races r USING(race_id)
                          WHERE p.phase='B1R' AND r.date=? ORDER BY r.close_at, p.pred_id""", (day,)).fetchall()
    L = [f"競輪 今日の買い目（法則枠） {day[:4]}/{day[4:6]}/{day[6:]}  更新 {kr.now():%H:%M}",
         "※ 仮想記録と同じ内容です。実際に買うかどうか・金額はご自身の判断で、遊べる範囲で。",
         "※ 法則: 7車立て・本命の1着見込み30〜60%・二分戦か三分戦のレースで、",
         "   3連単の売れ方から見て割安な 2車複 / 3連複 / ワイド を各100円。締切4〜7分前の倍率で判断。", ""]
    inv = ret = 0
    by = {}
    for r in rows:
        by.setdefault(r["race_id"], []).append(r)
    for rid, rs in by.items():
        r0 = rs[0]
        res = [x[0] for x in con.execute("SELECT number FROM results WHERE race_id=? AND rank BETWEEN 1 AND 3 ORDER BY rank", (rid,))]
        head = f"■ {r0['venue']}{r0['race_no']}R（{r0['grade']}） 締切 {r0['close_at'][11:16]}"
        if res:
            head += f"  結果 {'-'.join(map(str, res))}"
        buys = [x for x in rs if x["stake"]]
        if not buys:
            continue
        L.append(head)
        for x in buys:
            inv += x["stake"]
            p = con.execute("SELECT payout FROM payouts WHERE race_id=? AND bet_type=? AND combo=?",
                            (rid, x["bet_type"], x["combo"])).fetchone()
            mark = ""
            if res:
                mark = f"  → 的中 {p[0]:,}円" if p else "  → 外れ"
                ret += p[0] if p else 0
            L.append(f"   {x['bet_type']} {x['combo']}  {x['ref_odds']}倍  100円{mark}")
        L.append("")
    n_skip = sum(1 for rs in by.values() if not any(x["stake"] for x in rs))
    L.append(f"判断したレース {len(by)}（うち条件外・見送り {n_skip}）／ 買い目 {inv // 100}点 {inv:,}円 ／ 確定分の払戻 {ret:,}円")
    txt = "\n".join(L)
    for path in (os.path.join(DESKTOP, "競輪 今日の買い目.txt"), os.path.join(kr.BASE, "out", f"today_{day}.txt")):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8-sig").write(txt)
        except Exception:
            pass
    return txt
