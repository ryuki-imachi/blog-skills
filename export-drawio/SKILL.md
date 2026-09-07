---
name: export-drawio
description: プロジェクト内の .drawio ファイルを高解像度PNG（3倍スケール・白背景。--transparent で透過）にエクスポートします
argument-hint: "[ファイルパス（省略時は全drawioファイル）] [--transparent]"
allowed-tools: Bash, Glob, Read
---

# drawio → PNG エクスポート

プロジェクト内の `.drawio` ファイルを draw.io CLI で高解像度PNGに変換する。

## 手順

1. 引数を解釈する
   - ファイルパスが指定されていればそのファイルのみ、省略されていればプロジェクト内の全 `.drawio` ファイルを Glob で検索する
   - `--transparent` が付いていれば透過背景、無ければ白背景（既定）。README や Discord に貼る図は白背景にする（透過だと暗い背景で読めない。2026-09-06 リュウキ指定）
2. 各ファイルに対して以下のコマンドを実行する:
   ```
   # 白背景（既定）
   /opt/homebrew/bin/drawio --export --format png --scale 3 --border 20 --output <出力先.png> <入力.drawio>
   # 透過（--transparent 指定時）
   /opt/homebrew/bin/drawio --export --format png --scale 3 --transparent --output <出力先.png> <入力.drawio>
   ```
   - 出力先は入力ファイルと同じディレクトリ、拡張子を `.png` に変更したもの
   - スケール: 3倍。白背景のときは余白 20px
   - `/opt/homebrew/bin/drawio` が無ければ `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -s 3 -b 20 -o <出力先.png> <入力.drawio>` を使う（透過は `-t` を足す）
3. 書き出したPNGを Read で開いて、はみ出しや重なりが無いか目視する
4. エクスポート結果をユーザーに報告する（ファイル名、背景の種類、成功/失敗）。背景が意図どおりかは `sips -g hasAlpha <png>` で確認できる（白背景なら no）
