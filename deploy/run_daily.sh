#!/bin/bash
# 競輪 仮想試験の毎日実行（systemd timer から 07:30 JST に起動）
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
PY=./.venv/bin/python
mkdir -p logs
echo "===== $(date '+%F %T') start" >> logs/run_daily.log
# 前日分の結果の取りこぼしを補完
$PY -c "import backfill,datetime as d;y=(d.date.today()-d.timedelta(1)).strftime('%Y%m%d');backfill.main(y,y)" >> logs/run_daily.log 2>&1
# 当日ループ（終了時に export.py / history.py も実行）
$PY run_day.py >> logs/run_daily.log 2>&1
echo "===== $(date '+%F %T') end" >> logs/run_daily.log
