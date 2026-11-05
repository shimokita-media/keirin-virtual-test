# PCなしで動かして Discord に通知する手順

所要時間は約10分です。終われば、PCを消していても毎日自動で動き、Discord に通知が届きます。

## 1. Discord で通知用の連携URLを作る（約3分）
1. Discord で、左側の「＋」から**サーバーを作成**する（「オリジナルの作成」→「自分と友達のため」→ 名前は例：`競輪`）
2. できたサーバーの `#一般` チャンネル名の横にある**歯車マーク**を押す
3. 「**連携サービス**」→「**ウェブフック**」→「**新しいウェブフック**」を押す
4. 作られたウェブフックを開き、「**ウェブフックURLをコピー**」を押す

※ このURLを知っている人は、そのチャンネルに投稿できてしまいます。チャットなどに貼らず、次の手順4でだけ使ってください。

## 2. コマンドを実行する（約5分）
右側のターミナルで、上から順に1つずつ実行します。

① データベースを圧縮する
```
cd C:/Users/take0/.claude/keirin && python deploy/make_db_gz.py
```
② 非公開のリポジトリを作ってアップロードする
```
cd C:/Users/take0/.claude/keirin && gh repo create shimokita-media/keirin-virtual-test --private --source . --remote origin --push
```
③ データベースをアップロードする
```
cd C:/Users/take0/.claude/keirin && gh release create db keirin.sqlite.gz --repo shimokita-media/keirin-virtual-test --title db --notes "keirin database"
```
④ Discord の URL を登録する（実行すると入力待ちになるので、手順1でコピーしたURLを貼り付けて Enter）
```
gh secret set DISCORD_WEBHOOK --repo shimokita-media/keirin-virtual-test
```
⑤ 接続テストを動かす
```
gh workflow run keirin.yml --repo shimokita-media/keirin-virtual-test -f mode=test
```

## 3. 結果を確認する（2〜3分後）
- **Discord に「【接続テスト】GitHub から競輪サイトに接続できました」と届けば成功**
- 届かない場合は Claude に「テストどうだった？」と聞いてください（実行記録を確認します）

## 4. 毎日動かすための公開切り替え（テスト成功後）
非公開のままだと、無料で動かせる時間を2〜3日で使い切って止まります（課金はされず、止まるだけ）。毎日続けるには公開に切り替えます。
```
gh repo edit shimokita-media/keirin-virtual-test --visibility public --accept-visibility-change-consequences
```
- 公開されるのは、プログラムと仮想記録のデータです。Discord の URL はシークレットに入っているので公開されません。
- **shimokita-media（メディアのアカウント）で公開してよいか**は、ご判断ください。

## 5. 以後の使い方
- 毎日 7:00 / 12:45 / 18:30 に自動で動きます。PCは消しておいて大丈夫です。
- Discord に、**買い目（締切4〜7分前）**、**結果**、**本日のまとめ**が届きます。
- **PCのデスクトップの「競輪 仮想試験」アイコンは押さないでください**（記録が二重になります）。
