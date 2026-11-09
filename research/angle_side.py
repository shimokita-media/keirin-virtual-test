"""分析用の副データ（2025/2〜の races・entries・results）を、取り込み中のDBを固めないよう「月ごとの短い読み込み」で out/side_*.pkl に書き出す。
1回の読み込みは1秒以内に終わる大きさなので、取り込み（backfill.py）の書き込み待ち（5秒）を超えない。各月の間に少し休む。
使い方: python -I -X utf8 research/angle_side.py   （作り直すときだけ。分析は pd.read_pickle("out/side_entries.pkl") などで読む）"""
import sqlite3, time, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True, timeout=30)
months = pd.period_range("2025-02", "2026-11", freq="M")
R, E, S = [], [], []
for m in months:
    a, b = m.start_time.strftime("%Y%m%d"), m.end_time.strftime("%Y%m%d")
    r = pd.read_sql("SELECT race_id, date, venue, venue_id, cup_id, day_index, race_no, race_type, grade, class, entries_number, line_json, close_at, start_at FROM races WHERE date BETWEEN ? AND ?", con, params=(a, b))
    R.append(r); ids = r.race_id.tolist(); time.sleep(0.5)
    for i in range(0, len(ids), 400):
        ch = ids[i:i + 400]; ph = ",".join("?" * len(ch))
        E.append(pd.read_sql(f"SELECT race_id, number, player_id, prefecture, term, age, class, grp, style, gear, race_point, prediction_mark, first_rate, second_rate, third_rate, n_front, n_stalker, n_closer, n_marker, recent_orders, absent, n_standing, n_back, agari_avg FROM entries WHERE race_id IN ({ph})", con, params=ch))
        S.append(pd.read_sql(f"SELECT race_id, rank, number, player_id, factor FROM results WHERE race_id IN ({ph})", con, params=ch))
        time.sleep(0.2)
    print(m, len(r), flush=True)
pd.concat(R).to_pickle(K + "out/side_races.pkl"); pd.concat(E).to_pickle(K + "out/side_entries.pkl"); pd.concat(S).to_pickle(K + "out/side_results.pkl")
print("saved")
