# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ビルド方法

APKのビルドはGitHub Actionsで行う（Termux上では直接buildできない）。

```bash
git add .
git commit -m "変更内容"
git push origin main
```

pushすると `.github/workflows/build.yml` が自動実行される。完了後、GitHub ActionsのArtifactsから `task-app-debug.zip` をダウンロードして `.apk` をインストール。

手動トリガーも可能（GitHub → Actions → Build APK → Run workflow）。

## ローカル動作確認（Termux）

```bash
pip install kivy
python main.py
```

## アーキテクチャ

単一ファイル構成（`main.py`）。`TaskApp` クラスがUIとデータ管理を両方担う。

- `build()` — UIを構築し `_render()` で初期描画
- `_render()` — `self.tasks` リストを全消去→再描画（状態変化のたびに呼ぶ）
- `_load()` / `_save()` — `tasks.json` をJSONで読み書き（実行ディレクトリに保存）

タスクのデータ構造：`{"text": str, "done": bool}`

## buildozer.spec の主要設定

- `requirements = python3,kivy` — 依存追加時はここに書く
- `android.minapi = 21` — Android 5.0以上対応
- `version` — APK更新時はバージョンを上げること
