"""切り口：バンクの周長（333m系・400m・500m）。短いバンクは先行・番手有利、長いバンクは差し・追込が届きやすいと言われる。市場がそれを織り込んでいるか。
周長の分類は一般的な知識による（333m系：伊東・小田原・松戸・奈良・富山・防府・前橋(335m)、500m：宇都宮・大宮・高知、他は400m。熊本は新バンク400m扱い）。"""
import sys
exec(open("C:/Users/take0/.claude/keirin/research/angle_base.py", encoding="utf-8").read())
S333 = {"伊東", "小田原", "松戸", "奈良", "富山", "防府", "前橋"}; S500 = {"宇都宮", "大宮", "高知"}
bank = np.select([T.venue.isin(S333), T.venue.isin(S500)], ["333", "500"], "400")
order = (T.s01 == 1) & (T.s12 == 1) & (T.r0_pos == 0) & (T.r1_pos == 1) & (T.r2_pos == 2)
conds = {}
for bk in ("333", "400", "500"):
    m = pd.Series(bank == bk, index=T.index)
    conds[f"{bk}m"] = m
    conds[f"{bk}m×1着が先頭"] = m & (T.r0_pos == 0)
    conds[f"{bk}m×1着が番手"] = m & (T.r0_pos == 1)
    conds[f"{bk}m×1着が3番手か単騎"] = m & ((T.r0_pos >= 2) | (T.r0_single == 1))
    conds[f"{bk}m×ライン3人が並び順"] = m & order
c, c2 = report(sys.argv[1], "バンクの周長（333m系・400m・500m）", "周長は一般的な知識による分類（スクリプト冒頭に記載）。", conds)
print("候補", len(c), "参考", len(c2))
