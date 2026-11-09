"""切り口：開催の中での位置（最終日・何日制の開催か・最終日の一般戦＝勝ち上がれなかった選手どうし）。やる気や疲れの差を市場が織り込んでいるか。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
con = sqlite3.connect("file:" + K + "keirin.sqlite?mode=ro", uri=True)
C = pd.read_sql("SELECT cup_id, MAX(day_index) AS nd FROM races GROUP BY cup_id", con).set_index("cup_id").nd
T["nd"] = T.cup_id.map(C)
last = T.day_index == T.nd; prelast = T.day_index == T.nd - 1
rtx = T.race_type.fillna("").astype(str)
ippan = rtx.str.contains("一般|選抜|特一般|特選") & ~rtx.str.contains("決勝")
conds = {"2日制": T.nd == 2, "3日制": T.nd == 3, "4日制以上": T.nd >= 4, "最終日": last, "最終日の前日": prelast & (T.nd >= 3), "中日（初日と最終日以外）": (T.day_index > 1) & ~last,
         "最終日×決勝以外": last & ~rtx.str.contains("決勝"), "最終日×一般戦・選抜": last & ippan, "最終日×決勝": last & rtx.str.contains("決勝") & ~rtx.str.contains("準"),
         "3日制の2日目": (T.nd == 3) & (T.day_index == 2), "4日制以上の3日目": (T.nd >= 4) & (T.day_index == 3)}
c, c2 = report(sys.argv[1], "開催の中での位置（最終日・何日制）", "nd＝その開催の日数（races の day_index の最大）。最終日の一般戦・選抜は、勝ち上がれなかった選手どうしのレースが多い。", conds)
print("候補", len(c), "参考", len(c2))
