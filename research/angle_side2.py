"""side データ（races・entries・results）を、好きなDB・期間で月ごとに短く読んで書き出す（angle_side.py の引数つき版）。
使い方: python -I -X utf8 research/angle_side2.py DBのパス 開始日 終了日 出力の接尾辞
例: ... keirin.sqlite 20240201 20240708 y2024a → out/side_races_y2024a.pkl など"""
import sys, time, sqlite3, pandas as pd
K = "C:/Users/take0/.claude/keirin/"
db, d0, d1, suf = sys.argv[1:5]
con = sqlite3.connect("file:" + db + "?mode=ro", uri=True, timeout=30)
months = pd.period_range(pd.Timestamp(d0).to_period("M"), pd.Timestamp(d1).to_period("M"), freq="M")
R, E, S = [], [], []
for m in months:
    a, b = max(m.start_time.strftime("%Y%m%d"), d0), min(m.end_time.strftime("%Y%m%d"), d1)
    r = pd.read_sql("SELECT race_id, date, venue, venue_id, cup_id, day_index, race_no, race_type, grade, class, entries_number, line_json, close_at, start_at FROM races WHERE date BETWEEN ? AND ?", con, params=(a, b))
    R.append(r); ids = r.race_id.tolist(); time.sleep(0.5)
    for i in range(0, len(ids), 300):
        ch = ids[i:i + 300]; ph = ",".join("?" * len(ch))
        E.append(pd.read_sql(f"SELECT race_id, number, player_id, prefecture, term, age, class, grp, style, gear, race_point, prediction_mark, first_rate, second_rate, third_rate, n_front, n_stalker, n_closer, n_marker, recent_orders, absent, n_standing, n_back, agari_avg FROM entries WHERE race_id IN ({ph})", con, params=ch))
        S.append(pd.read_sql(f"SELECT race_id, rank, number, player_id, factor FROM results WHERE race_id IN ({ph})", con, params=ch))
        time.sleep(0.2)
    print(m, len(r), flush=True)
pd.concat(R).to_pickle(K + f"out/side_races_{suf}.pkl"); pd.concat(E).to_pickle(K + f"out/side_entries_{suf}.pkl"); pd.concat(S).to_pickle(K + f"out/side_results_{suf}.pkl")
print("saved")
