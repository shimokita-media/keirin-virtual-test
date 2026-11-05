@echo off
rem 競輪 仮想試験（PCのログオン時にスタートアップから起動。二重起動は自動で防止）
rem 1) 前日分の結果取りこぼしを補完  2) 当日ループ(B0/B1/結果)  3) 終了時に export.py と history.py を自動実行
cd /d C:\Users\take0\.claude\keirin
set PYTHONIOENCODING=utf-8
set PY=C:\Users\take0\AppData\Local\Programs\Python\Python313\python.exe
if not exist logs mkdir logs
echo ===== %date% %time% start >> logs\run_daily.log
"%PY%" -c "import backfill,datetime as d;y=(d.date.today()-d.timedelta(1)).strftime('%%Y%%m%%d');backfill.main(y,y)" >> logs\run_daily.log 2>&1
"%PY%" run_day.py >> logs\run_daily.log 2>&1
echo ===== %date% %time% end >> logs\run_daily.log
