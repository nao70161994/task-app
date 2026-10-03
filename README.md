# タスク管理 TaskApp

Kivy / python-for-android のAndroidタスク管理アプリ。アプリIDは既存と同じ
`com.example.taskmanager`。今回の更新候補は `1.2.0` / versionCode `10200`。

## タスク保存と旧データの引き継ぎ

- 保存先は Kivy `App.user_data_dir/tasks.json`（Androidではアプリ専用領域）。
  以前の作業ディレクトリ内 `tasks.json` は、新しい保存先とバックアップが両方ない初回だけ読み込む。
  移行時は元のJSONのバイト列を新しい保存先と `.bak` にコピーし、旧ファイルを削除しない。
  新保存先が空配列でも、それを優先して削除済みタスクを復活させない。
- 保存は同じディレクトリ内の一時ファイルに書き、flush / fsync後 `os.replace`。
  有効な直前の保存内容を先に `tasks.json.bak` にatomic保存する。
  バックアップ保存が失敗すれば本体保存も中止。一時ファイルは通常の例外時に削除する。
  プロセスが強制終了して残った `.tmp` は読まない。
- 本体が破損・欠落した場合は有効な `.bak` を復元する。破損本体は
  `tasks.json.corrupt-<ランダムID>` にそのまま保管し、復旧を画面に表示する。
  元データとバックアップの両方が無効なら、空の画面を表示するが**保存は停止**する。
  不正なタスクだけを黙って削除して残りを上書きすることはない。
- 最小の旧形式 `[{'text': ..., 'done': ...}]` を引き継ぎ、欠落している追加項目を補完する。
  `done` の欠落は `False`。タグ、繰り返し、サブタスク、順序、未知の追加項目を維持する。
  JSONのルート配列・既知項目の型を検証する。既存の期限文字列を強制変換しない。
- 保存に失敗した場合はメモリ上の編集も直前に保存できた状態へ戻し、画面にエラーを表示する。
  複数プロセスで同じファイルを同時編集する用途は対象外。
  ファイルのfsyncと、対応環境でのディレクトリfsyncを行うが、ストレージ自体の故障は防げない。

### 手動復旧

アプリを終了し、新保存先の `tasks.json`、`.bak`、`.corrupt-*` と旧保存先を全て保管する。
有効なJSONを確認して新保存先の `tasks.json` に復元してから再起動する。
Androidのアプリ専用領域は通常のファイルマネージャーでは見えないため、利用可能な端末の
バックアップ手段・開発用端末の `run-as` / adb等が必要。アンインストールや「ストレージを消去」は
アプリデータを削除するため、復旧方法として行わない。
`tasks.json*` はgit管理・APKへの同梱から除外する。

## 検証

Kivyなしで実行可能な回帰テスト:

```sh
python -m unittest discover -s tests -v
python tools/check_release.py
python -m compileall -q main.py task_storage.py updates.py app_version.py
```

テスト対象: atomic置換失敗、fsync失敗、バックアップ失敗、破損・欠落・復旧失敗、
旧データ移行、空配列優先、未知の項目、バージョン正規化、不正タグ、API失敗、APK署名・メタデータ判定。
GitHub ActionsはPython 3.10 / 3.12でテストしてからdebug APKをビルドする。
PR・main push・手動実行は検証用Artifactsのみを生成し、Releaseを作成しない。

## 安全な更新配布

`app_version.py` がversionNameの唯一の定義元。
`VERSION_CODE = major * 10000 + minor * 100 + patch`（minor / patchは0〜99）を使い、
`buildozer.spec` の `android.numeric_version` を同時に更新する。
`1.1` と `1.1.0` は同じバージョン。数値比較なので `1.10 > 1.9`。
不正形式・プレリリース・draft・APKのないReleaseは通知しない。
通信障害・API制限時は通知をスキップし、タスク管理を継続する。
通知先は検証済みのこのリポジトリのRelease URLに限定する。

### 署名設定（公開前に必要）

既存のv1.1 APKは毎回生成されるdebug鍵で署名されていた。
Androidの上書き更新には同じアプリIDと署名鍵が必要で、APKから秘密鍵は復元できない。
**実際に配布したAPKの元の署名鍵を取得できるまで、新しいReleaseの公開は停止する。**
新しいランダム鍵で署名してアンインストールを促す運用にはしない。

Repository Secrets:

| 名前 | 内容 |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | 既存APKと同じ署名鍵のkeystoreをbase64化した値 |
| `ANDROID_KEYSTORE_PASSWORD` | keystoreパスワード |
| `ANDROID_KEY_ALIAS` | 鍵のalias |
| `ANDROID_KEY_PASSWORD` | 鍵のパスワード |

Repository Variable `ANDROID_SIGNING_SHA256` に実際に配布したAPKの署名証明書SHA-256を設定する。
`apksigner verify --print-certs old.apk` で確認できる（APKファイルのSHA-256とは別）。
秘密鍵はgit・APK・Artifactsに保存しない。CIは一時領域のkeystoreを処理終了時に削除する。

旧方式は同じタグのAPKを再作成していたので、端末によって署名が異なる可能性がある。
最新公開APKとの署名一致だけでは全端末との互換性は保証できない。
実際に利用している旧APKでも証明書とversionCodeを確認し、
`adb install -r new.apk` の前後で既存タスク・サブタスク・タグ・順序・完了状態を確認する。
元の鍵が残っていない場合、既存アプリ側でのデータ書き出し／バックアップが必要であり、
今回の新APKだけで旧アプリの専用データを読み出して移行することはできない。

### リリース手順

1. 修正PRをレビューし、検証用APKの動作を確認してmainへマージ。
2. バージョンとversionCodeを増やし、テストを通す。署名設定と旧APKでの更新検証を完了する。
3. main上の該当コミットに一致するタグを作る（例: `v1.2.0`）。
4. タグpushでテスト・debugビルド後、release APKを別途ビルドして固定鍵で署名する。
   前回の最新公開APKを取得し、apksignerによる署名検証、証明書一致、アプリID一致、
   versionCode増加、versionNameとソースの一致を確認する。設定不足や不一致は公開前に失敗する。
5. draft Releaseを作り、検証済みAPKと `SHA256SUMS` をアップロード後に公開する。
   既存Release/tag/assetを削除・上書きしない。

同じタグの再実行で既存Releaseがある場合は明示的に失敗する。
アップロード中に失敗したdraftも残して調査できるようにし、自動削除しない。
既に公開した内容の修正は新しいバージョンと新しいタグで配布する。
検証用debug Artifactは毎回の署名が異なり得るので、既存ユーザー向け更新には使用しない。

## 公式仕様

- [Buildozer バージョン取得設定](https://buildozer.readthedocs.io/en/latest/specifications/)
- [Buildozer Android設定](https://github.com/kivy/buildozer/blob/master/buildozer/default.spec)
- [Android アプリ署名と更新の互換性](https://developer.android.com/studio/publish/app-signing)
- [gh release create](https://cli.github.com/manual/gh_release_create)
