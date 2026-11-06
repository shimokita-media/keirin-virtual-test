"""毎日の一覧（レース・選手・全オッズ）ができたことを Discord に知らせる。
使い方: python notify_tables.py "20261106 20261107" https://github.com/.../releases/tag/tables"""
import sys

import notify

days = sys.argv[1].split()
url = sys.argv[2]
label = "・".join(f"{d[4:6]}/{d[6:]}" for d in days)
notify.discord("\n".join([f"📂 **毎日の一覧ができました**（{label}分）",
                          "　レース一覧・選手一覧・全オッズ（Excelで開けます）",
                          f"　{url}"]))
