---
name: qiita-publish-prep
description: 記事リポジトリの下書きをQiita CLI用に変換。画像をS3+CloudFrontに同期し、Markdown内のパスをCDN URLに置換、Wikilinks/Callouts/Obsidianコメント/frontmatterをQiita仕様に整形して Qiita CLI ワークスペースの public/<slug>.md に出力する
user-invocable: true
argument-hint: "<下書きMDファイルパス>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# qiita-publish-prep

記事リポジトリの下書きを Qiita CLI が読める形に変換し、画像を
S3 (`${user_config.bucket}`) + CloudFront (`${user_config.cdn_domain}`) へ同期する。

変換・検証・ファイル操作は `scripts/qiita_prep.py` が決定論的に行う。
このスキルの仕事は、スクリプトが自力で決められない3つの判断だけ。

## 前提

環境固有の値はプラグインの設定（userConfig）から受け取る。

- 記事リポジトリ: `${user_config.articles_dir}`（下書きは drafts/ 配下、画像原本は images/<slug>/）
- Qiita CLI ワークスペース: `${user_config.qiita_dir}`（public/ に出力する）
- 旧置き場（記事リポジトリへ移す前の画像・下書き。任意）: `${user_config.obsidian_dir}`
- 画像配信基盤: S3 バケット `${user_config.bucket}` + CloudFront `${user_config.cdn_domain}`（構築済みであること）
- AWS 認証が切れていればスクリプトが検出して止まるので、ログインし直すよう案内する

上の値が空のときはスクリプトが「環境固有の値が未設定です」と止まる。その場合は
`/plugin configure blog-skills@ryuki-plugins` で設定するよう案内して中止する。

スクリプトには毎回、次の共通オプションをまとめて渡す（以下 `<共通オプション>` と書く）。

```
--articles-dir "${user_config.articles_dir}" --qiita-dir "${user_config.qiita_dir}" \
--obsidian-dir "${user_config.obsidian_dir}" --bucket "${user_config.bucket}" \
--cdn-domain "${user_config.cdn_domain}"
```

## 手順

### 1. 解析

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/qiita-publish-prep/scripts/qiita_prep.py" inspect <下書きパス> <共通オプション>
```

frontmatter、画像参照とその所在、変換対象の件数、警告が出る。ファイルは変更されない。
`--json` で機械可読。引数が無い・ファイルが無い場合は対象パスを聞いて中止する。

### 2. 判断（ここがこのスキルの本体）

inspect の出力を見て、次の3つを決める。

**slug** — frontmatter に無い場合のみ。S3 プレフィックスになるので publish 後は変更できない。
記事を読んで候補を2〜4個提案し、リュウキに選んでもらう。タイトルの直訳ではなく、
症状ベースか解決手段ベースで意味の分かる名前にする。`[a-z0-9-]` のみ。

**画像の変名** — inspect が `[要変名]` と印を付けたもの（日本語・スペース・記号を含むファイル名）。
記事の文脈から意味のある英語名を2〜4個提案する。スクリーンショットは撮影日付ではなく、
画像の内容や記事中での役割に即した名前にする。確定したら `--rename OLD=NEW` で渡すと、
原本と下書き内の参照を同時に書き換える。

**organization_url_name** — 付けるかどうかはリュウキに確認する。気まぐれに付ける方針なので、
既存の出力ファイルがあればその値が引き継がれる。

所在不明の画像が出たら、外部画像を意図して使っている可能性もあるので、消さずにリュウキに確認する。

### 3. 実行

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/qiita-publish-prep/scripts/qiita_prep.py" apply <下書きパス> <共通オプション> \
  [--slug SLUG] [--rename OLD=NEW]... [--organization NAME] [--skip-sync] [--dry-run]
```

slug の書き戻し → 画像の集約 → S3 同期 → 本文変換 → `qiita/public/<slug>.md` 出力までを行う。
`--out` で出力先を差し替えれば、上書き前にプレビューできる。副作用なしで変換結果だけ
見たいときは `--out /tmp/x.md --skip-sync --no-copy` を使う。

`private` は既存の出力ファイルの値を引き継ぎ、無ければ `true`（限定共有）。
公開済みの記事を作り直しても勝手に限定共有へ戻らない。

### 4. 警告の扱い

apply が出す `⚠` は、変換はせずに知らせるだけの項目。中身を見て判断する。

- 言語指定なしのコードブロック → 言語を足すべきか本人に確認
- リンクカード化候補（単独行のインラインリンク） → 素の URL 行にするか確認
- 画像が見つかりません → 所在を一緒に探す

### 5. 完了報告

出力先、S3 プレフィックス、CDN ベース URL、apply のサマリをそのまま伝えたうえで、次の流れを案内する。

```
1. プレビュー   cd ${user_config.qiita_dir} && npx qiita preview   # localhost:8888
2. 限定共有投稿  npx qiita publish <slug>                          # private: true のまま
3. Qiita 上で表示確認（限定共有中の URL は https://qiita.com/<user>/private/<id> 形式。
   /items/<id> は本公開後なので、限定共有中にこのリンクを案内しない）
4. 本公開        public/<slug>.md の private: false に変えて npx qiita publish <slug>
5. 後片付け      /qiita-archive <下書きパス>
```

## やってはいけないこと

- `npx qiita publish` を実行しない（リュウキが手で行う）
- `private: false` を勝手に設定しない（`--public` はリュウキの明示的な指示があるときだけ）
- S3 上のファイルを削除しない（過去記事の画像 URL が死ぬ。追加・更新のみ）
- slug を後から変える提案をしない（S3 プレフィックスが変わり画像 URL が切れる）
- 下書きの本文を書き換えない（スクリプトが触るのは frontmatter の slug 追記と、
  変名に伴う画像参照の更新だけ）
- 画像を差し替えるときはファイル名も変える（Qiita の imgix が差し替え前をキャッシュする）

## スクリプトが決定論的にやること

判断の材料として把握しておく。ここに挙げた変換は手作業で追わなくてよい。

| 処理 | 内容 |
|---|---|
| frontmatter 検証 | slug の形式、title、タグ 1〜5個・`/` 不可 |
| 画像の所在解決 | 記事リポジトリの images/ → 旧置き場の順に探索。相対・絶対・Wikilink 記法すべて |
| 画像の集約 | 記事リポジトリの `images/<slug>/` へコピー（既存は上書きしない） |
| S3 同期 | `aws s3 sync --size-only`、直後に CDN の応答コードを1件確認 |
| 画像パス | ローカル参照を `https://${user_config.cdn_domain}/<slug>/<file>` に置換 |
| Wikilink | `[[a]]` → `a`、`[[a\|b]]` → `b`（削除ではなくテキスト化） |
| Callout | `> [!note\|info\|tip]` → `:::note info`、`warning\|caution` → `warn`、`danger\|error\|failure` → `alert`。対応表に無い種別は素の引用のまま |
| Obsidian コメント | `%% ... %%`（ブロック・インライン）を除去。執筆メモを Qiita に漏らさない |
| コードブロック | コメントを含む ` ```json ` を ` ```js ` に変更（Qiita のハイライトが壊れるため） |
| H1 削除 | frontmatter の title が記事タイトルになるため先頭の `# ` 行を削除 |
| フェンス保護 | コードブロックの中身は一切変換しない |
| Qiita frontmatter | 生成。`updated_at` / `posting_campaign_uuid` / `agreed_posting_campaign_term` は既存出力から引き継ぐ |

## 関連

- 後片付け: `qiita-archive`（本公開後に呼ぶ）
- 下書きの frontmatter 規約や運用ルールが記事リポジトリ（`${user_config.articles_dir}`）の README にあれば、それに従う
