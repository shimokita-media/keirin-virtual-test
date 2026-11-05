#!/bin/bash
# Google Cloud の VM（Debian 12 / e2-micro）上で1回だけ実行する導入スクリプト
#   bash install.sh      （ホームに keirin_deploy.tar.gz と install.sh を置いた状態で）
set -euo pipefail
APP="$HOME/keirin"

echo "== 1/6 タイムゾーンを日本時間に"
sudo timedatectl set-timezone Asia/Tokyo

echo "== 2/6 必要なパッケージ"
sudo apt-get update -y -q
sudo apt-get install -y -q python3-venv python3-pip sqlite3 curl

echo "== 3/6 メモリ不足対策のスワップ 2GB（e2-micro はメモリ1GBのため）"
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "== 4/6 プログラムとデータを展開"
mkdir -p "$APP/logs"
tar xzf "$HOME/keirin_deploy.tar.gz" -C "$APP"
chmod +x "$APP/run_daily.sh"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

echo "== 5/6 データ取得元への接続確認（200 なら OK。403 等なら海外からの接続が拒否されている）"
for u in "https://www.winticket.jp/keirin/racecard/" "https://keirin.netkeiba.com/race/race_list/"; do
  echo "  $u -> $(curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0' "$u")"
done
cd "$APP" && ./.venv/bin/python -c "import kr;con=kr.db();print('  開催一覧の取得テスト:', kr.fetch_daily(con))"

echo "== 6/6 毎朝 7:30 の自動起動を登録（systemd timer）"
sudo tee /etc/systemd/system/keirin.service >/dev/null <<UNIT
[Unit]
Description=Keirin virtual test daily loop (no real betting)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP
ExecStart=$APP/run_daily.sh
TimeoutStartSec=0
RuntimeMaxSec=20h
UNIT
sudo tee /etc/systemd/system/keirin.timer >/dev/null <<UNIT
[Unit]
Description=Start keirin loop every morning 07:30 JST

[Timer]
OnCalendar=*-*-* 07:30:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now keirin.timer
systemctl list-timers keirin.timer --no-pager
echo
echo "導入完了。今日の分を今すぐ始める場合: sudo systemctl start keirin.service"
echo "状態確認: tail -f ~/keirin/logs/run_daily.log"
