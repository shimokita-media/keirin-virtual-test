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

## 自動実行（PC起動時に開始する方式）
- PCにログオンすると、スタートアップの `keirin.lnk` から `run_daily.bat` が最小化状態で起動する
  - 前日の結果の取りこぼしを補完 → 当日ループ → 全レース確定後に `export.py` と `history.py` を実行。ログは `logs\run_daily.log`
- PCがスリープ・シャットダウンしたら止まる（電気代を増やさないため、スリープ抑止はしない）。抑止したい日だけ環境変数 `KEIRIN_KEEP_AWAKE=1` を設定する
- 1日に何度ログオンしても二重には起動しない（ローカルのポート47615で判定）
- 止めたいときは、タスクバーの最小化されたウィンドウを閉じる
- PCが止まっていた時間帯の B0/B1 は「欠損」として記録し、事後には補完しない

スタートアップへの登録（本人が PowerShell で1回だけ実行）:
```
$s=(New-Object -ComObject WScript.Shell).CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\keirin.lnk"); $s.TargetPath='C:\Users\take0\.claude\keirin\run_daily.bat'; $s.WorkingDirectory='C:\Users\take0\.claude\keirin'; $s.WindowStyle=7; $s.Save()
```
解除: `Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\keirin.lnk"`

判断ルール v2（2026-11-05〜）
- EV は「確定までの想定下落率」を掛けたオッズで評価する
- 3連単300倍以上、ワイド10〜50倍、FIIのワイドは除外する
- 先行型／番手型の判定を「展開」欄に記録する

（GitHub Actions / Google Cloud 用の設定も `.github/` と `deploy/` に残してあるが、現在は使っていない）

## モデルの前提（重要）
- 推定確率は、3連単・2車単・3連複の各プールから得た市場の暗黙確率です。独立に校正した勝率モデルではありません。
- α=1.0 と α=1.15（大穴を割り引く補正）の両方で EV を計算し、低い方（EVc）で評価しています。
- 2026-11-04 の初日検証では、確定オッズ時点の5券種はほぼ整合していました（EV中央値 0.60〜0.73、最大 1.07）。早い時間帯の歪みは締切までに縮む可能性が高く、B1 と確定オッズの差の追跡が最重要です。
