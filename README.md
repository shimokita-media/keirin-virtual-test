# 競輪 市場の歪み検出（仮想購入のみ）

| ファイル | 役割 |
|---|---|
| `kr.py` | 収集（WINTICKET レースページSSR / netkeirin オッズJSON）、SQLite、券種間整合モデル、6視点（ルールベース）、B0/B1 判断 |
| `run_day.py` | 当日ループ。B0 は締切45〜30分前、B1 は締切4〜1分前に自動で固定する。確定後は結果・払戻・確定オッズを回収 |
| `export.py` | `out/` に CSV（races / entries / odds / predictions / results / payouts / settlement / fetch_log）と `analysis_report.md` を出力 |
| `notion_rows.py` | Notion「競輪 仮想試験ログ」に書く行を JSON で出力（書き込みは Claude の Notion コネクタで行う） |
| `keirin.sqlite` | 正本。`predictions` はトリガーで UPDATE/DELETE を禁止した追記専用テーブル |

## 毎日の実行
```
cd C:\Users\take0\.claude\keirin
python run_day.py      # 最初のレースの締切90分前までに起動（最終レース確定後に自動終了。上限10時間）
python export.py       # 終了後
```

## 自動実行（設定済みのもの）
- `run_daily.bat`：前日の結果を補完 → 当日ループ → 終了時に `export.py` と `history.py` を実行。ログは `logs\run_daily.log`
- `run_day.py` は実行中だけスリープを抑止する（`SetThreadExecutionState`。システム設定は変更しない）
- 判断ルール v2（2026-11-05〜）
  - EV は「確定までの想定下落率」を掛けたオッズで評価する
  - 3連単300倍以上、ワイド10〜50倍、FIIのワイドは除外する
  - 先行型／番手型の判定を「展開」欄に記録する

タスクスケジューラへの登録は、本人が PowerShell で実行する（毎朝7:30・スリープ復帰あり）:
```
$a = New-ScheduledTaskAction -Execute 'C:\Users\take0\.claude\keirin\run_daily.bat' -WorkingDirectory 'C:\Users\take0\.claude\keirin'
$t = New-ScheduledTaskTrigger -Daily -At 07:30
$s = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 20) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'KeirinVirtualTest' -Action $a -Trigger $t -Settings $s -Force
```
解除: `Unregister-ScheduledTask -TaskName KeirinVirtualTest -Confirm:$false`

## 自動実行の案（旧メモ）
1. **Windows タスクスケジューラ**（推奨。PCが起動していれば Claude なしで動く）
   - 07:30 に `python run_day.py` を起動（朝の開催の B0 に間に合わせる）
   - 23:59 に `python export.py` を実行
2. **Claude のスケジュールタスク**: 翌朝に `export.py` の結果を読み、Notion への同期・読み戻し・レポートの要約を行う
3. 注意: PC がスリープすると B0/B1 の時刻窓を逃す。B0/B1 が欠けたレースは「欠損」として記録し、事後に補完しない

## モデルの前提（重要）
- 推定確率は、3連単・2車単・3連複の各プールから得た市場の暗黙確率です。独立に校正した勝率モデルではありません。
- α=1.0 と α=1.15（大穴を割り引く補正）の両方で EV を計算し、低い方（EVc）で評価しています。
- 2026-11-04 の初日検証では、確定オッズ時点の5券種はほぼ整合していました（EV中央値 0.60〜0.73、最大 1.07）。早い時間帯の歪みは締切までに縮む可能性が高く、B1 と確定オッズの差の追跡が最重要です。
