---
name: qiita-archive
description: Qiita投稿後の後片付け。元下書きの frontmatter を published 状態に更新（qiita_id / published_at 追記）し、レビューレポートごと articles/published/ に移動して board.md を更新する
user-invocable: true
argument-hint: "<元下書きファイルパス または slug>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# qiita-archive

`/qiita-publish-prep` で変換し `npx qiita publish` で本公開した後の後片付け。

frontmatter の更新とファイル移動は `scripts/qiita_archive.py` が決定論的に行う。
このスキルの仕事は **board.md の更新**で、そこは記事ごとに書く内容が違うので自動化しない。

これを済ませておくと、記事を更新したくなったときに slug / qiita_id を引き継いで
`/qiita-publish-prep` を再実行でき、URL が変わらない。

## 手順

### 1. 確認

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/qiita-archive/scripts/qiita_archive.py" inspect <下書きパス | slug> <共通オプション>
```

`<共通オプション>` は、プラグインの設定（userConfig）から受け取る環境固有の値で、毎回まとめて渡す。

```
--articles-dir "${user_config.articles_dir}" --qiita-dir "${user_config.qiita_dir}" \
--obsidian-dir "${user_config.obsidian_dir}"
```

値が空でスクリプトが「環境固有の値が未設定です」と止まったら、`/plugin configure blog-skills@ryuki-blog-skills`
で設定するよう案内して中止する。

引数はパスでも slug でもよい。slug のときは記事リポジトリ（と旧置き場が設定されていればそこも）を
検索して下書きを特定する。候補が複数・ゼロなら中止するので、リュウキに知らせる。

`✗` が出たら、その原因を伝えて止まる。よくあるのは次の2つ。

- `id: null` → まだ publish されていない。`npx qiita publish <slug>` を案内する
- `qiita/public/<slug>.md` が無い → 先に `/qiita-publish-prep`

`private: true` のままなら本公開前なので、リュウキに本公開が済んだか確認する。
限定共有のままアーカイブしたい意図があるなら `--allow-private` を付ける。

### 2. 実行

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/qiita-archive/scripts/qiita_archive.py" apply <下書きパス | slug> <共通オプション> [--dry-run]
```

`status: published` / `qiita_id` / `published_at` を下書きの frontmatter に反映し、
下書きとレビューレポート（`*.review.md`）を `articles/published/` へ移動する。
`published_at` は既存値があればそれを残す（再実行で公開日を上書きしない）。

### 3. board.md の更新（このスキルの本体）

`${user_config.articles_dir}/board.md` を次の3点で更新する。ボードは記事の進行状態の正なので、
ファイル移動とセットで必ず更新する。

1. **ボードの表から該当行を削除する**
2. **「完了ログ（直近）」の先頭に1行追記する** — 日付、記事タイトル、経緯を1行にまとめる。
   既存のログを2〜3件読んで、粒度と書きぶりを合わせる。限定共有から本公開までの日付、
   qiita_id、画像の有無、mcks.log への移植状況、残作業などを入れることが多い
3. ヘッダーの `最終更新:` を今日の日付と一行要約に更新する

更新したら、board.md の Artifact を同じ URL で再発行する。

## やってはいけないこと

- 本文を書き換えない（frontmatter のみ）
- `articles/published/` 以外の場所へ移動しない
- 元ファイルを削除しない（移動のみ）
- slug を変更しない（S3 プレフィックスが無効になり画像 URL が切れる）
- 完了ログの過去のエントリを書き換えない（追記のみ）

## 関連

- 前段: `qiita-publish-prep`（投稿前の変換）
- 下書きの frontmatter 規約や運用ルールが記事リポジトリ（`${user_config.articles_dir}`）の README にあれば、それに従う
