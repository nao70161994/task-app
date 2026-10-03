# 開発ガイド

詳細は [README.md](README.md) を参照。

## 構成

- `main.py`: Kivy UI、ユーザー操作、保存失敗時のメモリ状態復元・通知。
- `task_storage.py`: 旧JSON互換性、atomic保存、バックアップ・破損復旧、初回移行。
- `app_version.py`: versionNameの定義元、versionCode。
- `updates.py`: 安定版バージョン比較、GitHub Release応答検証、通信。
- `tools/check_release.py`: バージョン・タグ・アプリIDの整合性検証。
- `tools/verify_apk.py`: 公開前のAPK署名と旧APKとの互換性検証。
- `tests/`: Kivy不要のunittest回帰テスト。

## テスト・ビルド

```sh
python -m unittest discover -s tests -v
python tools/check_release.py
```

GitHub ActionsのPR / main push / workflow_dispatchでテストとdebug APKビルド。
検証用Artifactsは `task-app-test-debug`。通常のpushではReleaseを作成しない。
署名設定・更新互換性確認後、main上のコミットにバージョンと一致する新タグを付けて配布する。
既存Release・tagは削除しない。既存ユーザーにアンインストールを要求しない。

## データを維持すること

旧作業ディレクトリの `tasks.json` を新しい `App.user_data_dir` へ非破壊コピーする。
アプリIDを変更しない。旧形式、未知の追加項目、タグ、サブタスクを維持する。
破損時に空リストを保存して元データを消さない。`.bak` と破損原本を保持する。
タスクデータ・署名秘密鍵をコミットしたりAPKに含めたりしない。
