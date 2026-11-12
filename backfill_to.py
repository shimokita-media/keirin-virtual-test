"""過去の年を、本体とは別のデータベースに取り込む（2026-11-12、ユーザー依頼「全速力で過去10年分」）。
本体の keirin.sqlite に何本も同時に書くと「database is locked」で落ちるので、年ごとに別のフォルダの keirin.sqlite に書く。
使い方: python -X utf8 backfill_to.py 出力フォルダ 開始 終了   （-I は付けない）"""
import os, sys
import kr
kr.BASE = os.path.abspath(sys.argv[1]); os.makedirs(kr.BASE, exist_ok=True)
import backfill
backfill.main(sys.argv[2], sys.argv[3])
