---
name: export-drawio
description: プロジェクト内の .drawio ファイルを高解像度PNG（3倍スケール・透過背景）にエクスポートします
argument-hint: "[ファイルパス（省略時は全drawioファイル）]"
allowed-tools: Bash, Glob, Read
---

# drawio → PNG エクスポート

プロジェクト内の `.drawio` ファイルを draw.io CLI で高解像度PNGに変換する。

## 手順

1. 引数でファイルパスが指定されていればそのファイルのみ、省略されていればプロジェクト内の全 `.drawio` ファイルを Glob で検索する
2. 各ファイルに対して以下のコマンドを実行する:
   ```
   /opt/homebrew/bin/drawio --export --format png --scale 3 --transparent --output <出力先.png> <入力.drawio>
   ```
   - 出力先は入力ファイルと同じディレクトリ、拡張子を `.png` に変更したもの
   - スケール: 3倍
   - 背景: 透過
3. エクスポート結果をユーザーに報告する（ファイル名と成功/失敗）
