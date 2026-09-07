# export-drawio（drawio 図の PNG 書き出し）

プロジェクト内の `.drawio` ファイルを draw.io デスクトップアプリの CLI で高解像度 PNG に変換します。記事や README に貼る図を作るときに単発で呼ぶ小物で、他のスキルとは独立しています。

## 動き

- 引数にファイルを指定すればそのファイルだけ、省略すればプロジェクト内の全 `.drawio` を対象にします
- 3倍スケールで、入力ファイルと同じディレクトリに `.png` を書き出します
- 既定は白背景（余白 20px）で、`--transparent` を付けたときだけ透過にします。透過 PNG は Discord や暗いテーマのビューアで読めないことがあるので、貼る先が決まっていなければ白背景にしておく方が無難です
- 書き出した PNG を開いて、はみ出しや重なりが無いか目視してから報告します

## 必要なもの

draw.io デスクトップアプリ（`brew install --cask drawio`）。`/opt/homebrew/bin/drawio` が無ければ `/Applications/draw.io.app/Contents/MacOS/draw.io` を直接呼びます。設定値は使いません。
