# qiita-archive（投稿後の後片付け）

本公開が済んだ記事の下書きに `status` / `qiita_id` / `published_at` を書き込み、レビューレポートごと記事リポジトリの `published/` へ移します。

![qiita-archiveの仕組み](../images/qiita-archive-flow.png)

## なぜ slug と qiita_id を下書きに残すか

記事を更新したくなったとき、slug と qiita_id を引き継いで qiita-publish-prep を再実行できるようにするためです。同じ URL、同じ画像パスのまま再投稿できます。

## スクリプトとスキルの分担

frontmatter の更新とファイル移動は `scripts/qiita_archive.py` が行います。`inspect` で対象と公開状態を確かめ（Qiita CLI ワークスペースの `public/<slug>.md` に `id` が無ければ未公開として止まる）、`apply` で frontmatter を書き込んでファイルを移動します。`published_at` は既存値があればそれを残すので、再実行しても公開日が上書きされません。

スキルに残したのはステータスボード（記事リポジトリの `board.md`）の更新だけです。ボードから該当行を消し、完了ログの先頭に1行追記します。記事ごとに書く内容が違うので自動化していません。

## やらないこと

- 本文の書き換え（frontmatter のみ）
- `published/` 以外への移動、元ファイルの削除
- slug の変更（S3 プレフィックスが無効になり画像 URL が切れる）
- 完了ログの過去エントリの書き換え（追記のみ）
