# ブログ執筆スキル一式

私が普段のブログ執筆で使っているClaude Codeのスキル4本です。記事執筆方法の共有会で配布したものを、公開用に一部プレースホルダーへ置き換えて公開しています。

| スキル | 役割 |
|---|---|
| review-blog | 投稿前レビュー。自分の過去記事を基準に、文体・構成・技術的正確性をチェック |
| qiita-publish-prep | Qiita投稿準備。下書きをQiita CLI用に変換し、画像をS3+CloudFrontへ同期 |
| qiita-archive | 投稿後の後片付け。frontmatter更新・アーカイブ移動・ステータスボード更新 |
| export-drawio | drawioの図を高解像度PNG（3倍・透過）に書き出し |

## 導入方法

フォルダごと `~/.claude/skills/` にコピーすると、Claude Codeで `/review-blog` のようにスラッシュコマンドとして呼べるようになります。

```
cp -R review-blog qiita-publish-prep qiita-archive export-drawio ~/.claude/skills/
```

## そのまま使えるか

私の環境（ファイルパス・過去記事の置き場・運用ルール）が手順書にそのまま書いてあるので、動かすには自分の環境向けの書き換えが必要です。

- review-blog … 過去記事のパスと `references/my-style.md`（文体ルール）を自分のものに差し替えれば使えます。まず自分の文体ルールを言語化するところから始めるのがおすすめです
- qiita-publish-prep … S3+CloudFrontの画像配信基盤が前提なので、そのままでは動きません。変換ルールや「どこで人間に確認を取るか」の設計の参考にしてください
- qiita-archive … パスを自分のリポジトリ構成に合わせれば使えます
- export-drawio … draw.ioデスクトップアプリ（`brew install --cask drawio`）があればそのまま動きます

## 取り扱いについて

個人環境のフォルダ構成や運用ルールは、実物の雰囲気が伝わるようあえてそのまま残しています。S3バケット名など環境固有の識別子だけ `<your-bucket>` のようなプレースホルダーに置き換えてあります。ライセンスはMITです。自由にコピーして、自分の環境に合わせて書き換えて使ってください。
