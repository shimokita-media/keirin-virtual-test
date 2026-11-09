"""切り口：開催の時間帯（モーニング・デイ・ナイター・ミッドナイト）。ミッドナイトは無観客・ネット投票中心で7車立てが多く、買う人の層が違う＝市場の歪み方が違うか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
st = pd.to_datetime(T.start_at, unit="s", utc=True).dt.tz_convert("Asia/Tokyo")  # 発走時刻は UNIX 秒
h = st.dt.hour + st.dt.minute / 60
cuph = T.assign(h=h).groupby("cup_id").h.agg(["min", "max"])
cmin, cmax = T.cup_id.map(cuph["min"]), T.cup_id.map(cuph["max"])
kind = np.select([cmax >= 21.5, cmin >= 14.5, cmax <= 13.5], ["ミッドナイト", "ナイター", "モーニング"], "デイ")
T["kind"] = kind
conds = {"モーニング開催": T.kind == "モーニング", "デイ開催": T.kind == "デイ", "ナイター開催": T.kind == "ナイター", "ミッドナイト開催": T.kind == "ミッドナイト",
         "ミッドナイト×7車以下": (T.kind == "ミッドナイト") & (T.entries_number <= 7), "デイ・ナイター×7車以下": T.kind.isin(["デイ", "ナイター"]) & (T.entries_number <= 7),
         "その日の最初の3レース": T.race_no <= 3, "その日の最後の2レース": T.race_no >= T.groupby(["cup_id", "date"]).race_no.transform("max") - 1}
c, c2 = report(sys.argv[1], "開催の時間帯（モーニング・デイ・ナイター・ミッドナイト）",
               f"開催ごとに発走時刻の最小・最大で分類（最終発走21:30以降＝ミッドナイト、最初が14:30以降＝ナイター、最終が13:30まで＝モーニング、他＝デイ）。発走時刻が分かる割合 {h.notna().mean():.0%}。", conds)
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write("\n## 時間帯ごとのレース数（探す期間）\n" + T[per(T.date) == "探す"].drop_duplicates("race_id").kind.value_counts().to_string() + "\n")
print("候補", len(c), "参考", len(c2))
