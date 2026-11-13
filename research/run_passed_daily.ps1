# 合格した2手法の本番記録を毎日つける（仮想の記録だけ。実際の購入はしない）。
# ①1分前の表が古ければ research/daily_forward.py で最新にする → ②research/passed_forward.py → ③記録の2ファイルだけコミットして push
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\take0\AppData\Local\Programs\Python\Python313\python.exe'
$log = Join-Path $root ("logs\passed_forward_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
Set-Location $root
function Say([string]$m) { Add-Content -LiteralPath $log -Encoding utf8 -Value ("{0} {1}" -f (Get-Date -Format s), $m) }
$yesterday = (Get-Date).AddDays(-1).ToString('yyyyMMdd')
$have = (& $python -I -X utf8 -c "import pandas as pd; print(pd.read_pickle('out/angle_base_t1.pkl').date.max())" 2>$null | Select-Object -Last 1)
Say "table max date=$have yesterday=$yesterday"
if (-not $have -or $have -lt $yesterday) {
    & $python -I -X utf8 research\daily_forward.py *>> $log
    Say "daily_forward exit=$LASTEXITCODE"
}
& $python -I -X utf8 research\passed_forward.py *>> $log
if ($LASTEXITCODE -ne 0) { Say "passed_forward failed exit=$LASTEXITCODE"; exit 1 }
git add reports/passed_forward.md reports/passed_forward_picks.csv *>> $log
git diff --cached --quiet -- reports/passed_forward.md reports/passed_forward_picks.csv
if ($LASTEXITCODE -ne 0) {
    $msg = "passed_forward {0}`n`nCo-Authored-By: Claude <noreply@anthropic.com>" -f (Get-Date -Format 'yyyy-MM-dd HH:mm')
    git commit -m $msg -- reports/passed_forward.md reports/passed_forward_picks.csv *>> $log
    git pull --rebase --autostash *>> $log
    if ($LASTEXITCODE -eq 0) { git push *>> $log; Say "push exit=$LASTEXITCODE" } else { Say "pull failed; push skipped" }
} else { Say "no change" }
Say "done"
