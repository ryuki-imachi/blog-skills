---
name: qiita-publish-prep
description: articles/の下書きをQiita CLI用に変換。画像をS3+CloudFrontに同期し、Markdown内のパスをCDN URLに置換、Wikilinks/Callouts/frontmatterをQiita仕様に整形して ~/Desktop/work/qiita/public/<slug>.md に出力する
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

リュウキが articles リポジトリで書いた下書きを、Qiita CLI が読める形に整形しつつ、
画像を S3 (`<your-bucket>`) + CloudFront (`<your-cdn-domain>`) に同期する。

## 前提

- 画像配信基盤は CDK で構築済み（`~/Desktop/work/blog-pipeline/cdk`）
- Qiita CLI ワークスペース: `~/Desktop/work/qiita/`
- 記事リポジトリ: `~/Desktop/work/articles/`（下書きは drafts/ 配下、画像原本は images/<slug>/。2026-07-12運用開始）
- 旧置き場（互換用）: `~/Desktop/work/obsidian/`（過去記事の下書き・画像はここに残っている）
- AWS 認証は SSO（リュウキが事前に `aws login`）

## スキルの引数

`$ARGUMENTS` = 下書き Markdown ファイルの絶対パス。
引数が無い・ファイルが存在しない場合は中止し、ユーザーに「対象ファイルパスを指定してください」と伝える。

## 元ファイルの frontmatter 規約（DECISIONS.md D-18）

このスキルは元ファイルの frontmatter を **状態に応じて読み書き**する：

```yaml
---
slug: <S3プレフィックス、英数ハイフンのみ>
status: ready          # draft / reviewing / ready / published
---
```

- 投稿前のスキル実行時、frontmatter に `slug:` が無ければ **追記する**（後述 Step 1）
- 投稿後（`qiita-archive` スキル）には `qiita_id` / `published_at` も追記される
- これらは **再投稿時に同じ S3 prefix を保つ** ために必須

## 実行フロー

### Step 0. 事前チェック

1. `aws sts get-caller-identity` で AWS 認証確認。失敗時は「`aws login` を実行してください」と伝えて中止
2. 対象ファイルを Read
3. frontmatter をパース（YAML）

### Step 1. slug（S3 プレフィックス）の決定 + 元ファイル frontmatter 補完

S3 バケット内の画像格納パスとして使う。優先順：

1. frontmatter に `slug:` があればそれを使う（既存）
2. なければ **記事内容を読んで slug 候補を 2〜4 個提案** し、ユーザーに選んでもらう
   - 例: 「Codex pet が見切れる」記事 → `codex-pet-offscreen-fix`, `codex-pet-display-fix`, `codex-pet-cache-reset` など
   - slug は `[a-z0-9-]+` のみ。タイトル直訳は避け、症状ベース or 解決手段ベースで意味のある名前を提案する
3. 選択された slug を **元ファイルに追記する**（既存 frontmatter があれば追加、無ければ新規作成）

```yaml
---
slug: codex-pet-offscreen-fix
status: ready
---
```

slug は publish 後も**絶対に変えてはいけない**（画像URLが切れる）。

### Step 2. 画像の検出と所在確認

Markdown 内の画像参照を全て検出する：

| パターン | 例 | 処理 |
|---|---|---|
| 相対パス | `![alt](./images/foo.png)` | ローカル画像として処理 |
| Vault内パス | `![alt](画像置き場/foo.png)` | ローカル画像として処理 |
| 絶対パス | `![alt](/Users/<user>/.../foo.png)` | ローカル画像として処理 |
| Obsidian Wikilink画像 | `![[foo.png]]` | ローカル画像として処理（Vault内検索） |
| 既CDN URL | `![alt](https://<your-cdn-domain>/...)` | スキップ |
| 外部URL | `![alt](https://...)` | スキップ |

#### 所在検索（B-4 強化）

画像は以下の順で検索する：

```bash
# 1. 記事リポジトリの画像原本（新運用の起点）
find ~/Desktop/work/articles/images -type f -name '<filename>'
# 2. 旧置き場（過去記事の画像はここ）
find ~/Desktop/work/obsidian -type f -name '<filename>' \
  -not -path '*/.obsidian/*' -not -path '*/.trash/*'
```

- 見つかった場所を必ずユーザーに提示
- 旧置き場で見つかった場合は「`articles/images/<slug>/` にコピーして今後の起点にしますか？」と提案（新運用への寄せ）
- 見つからない画像はエラーにせず、警告としてリストアップしてユーザー確認を取る

### Step 3. 画像の集約 + 変名提案（B-1 強化）

#### 集約

- 集約先: `~/Desktop/work/articles/images/<slug>/<filename>`（画像原本の置き場そのもの。ここがS3同期の起点）
- 既に同名ファイルが存在する場合は上書きしない（衝突警告）

#### 変名提案（必須プロセス）

ファイル名に **日本語・スペース・連続ピリオド・記号** が含まれる場合、変名を **必ず**提案する：

1. **記事文脈から意味のある英語ファイル名を提案**
   - 「pet が見切れる」記事のスクリーンショット → `pet-restored.png`, `pet-displayed.png`, `pet-fixed.png`
   - スクリーンショットの場合、撮影日付ではなく**画像内容や記事文脈に即した名前**を優先
   - 候補は2〜4個、それぞれの意図（症状/解決後/手順 etc）を添える
2. ユーザーが選択 or 別案を提示 → 確定後：
   - 原本ファイル（`articles/images/<slug>/`、旧記事なら `obsidian/画像置き場/`）も同じ名前にリネーム（`mv`）
   - 元 Markdown 内の参照も書き換える（`![[old.png]]` → `![[new.png]]`）

→ 原本と元 Markdown を同期させることで、リンク切れを起こさない。

### Step 4. S3 同期

```bash
aws s3 sync \
  ~/Desktop/work/articles/images/<slug>/ \
  s3://<your-bucket>/<slug>/ \
  --exclude '.DS_Store' \
  --size-only
```

- `--size-only` でタイムスタンプ差分による無駄な再アップロードを防ぐ
- sync 後、`curl -sI https://<your-cdn-domain>/<slug>/<filename>` で1件だけ200応答を確認するのが望ましい
- 失敗したら中止して原因報告

### Step 5. Markdown 変換

元ファイルの本文をコピーして変換用バッファとし、以下を順に置換：

#### 5-1. 画像パスを CDN URL に置換

各ローカル画像参照を `https://<your-cdn-domain>/<slug>/<filename>` に書き換える：

- `![alt](./images/foo.png)` → `![alt](https://<your-cdn-domain>/<slug>/foo.png)`
- `![[foo.png]]` → `![](https://<your-cdn-domain>/<slug>/foo.png)`
- `![[foo.png|代替テキスト]]` → `![代替テキスト](https://<your-cdn-domain>/<slug>/foo.png)`

#### 5-2. Wikilinks（非画像）の変換

- `[[note-name]]` → `note-name`（プレーンテキスト化、Qiita では Vault 内ノートを参照できないため）
- `[[note-name|表示名]]` → `表示名`
- 削除でなくテキスト化を選ぶ理由: 文脈が壊れにくいため
- 件数を最後にユーザーに報告

#### 5-3. Obsidian Callouts → Qiita 記法

```
> [!note]
> 本文
```
↓
```
:::note info
本文
:::
```

| Obsidian | Qiita |
|---|---|
| `> [!note]` / `> [!info]` / `> [!tip]` | `:::note info` |
| `> [!warning]` / `> [!caution]` | `:::note warn` |
| `> [!danger]` / `> [!error]` / `> [!failure]` | `:::note alert` |
| `> [!success]` / `> [!example]` / `> [!quote]` | （通常の引用 `>` のまま） |

複数行のコールアウト本文は全て `:::` ブロック内に格納する。

#### 5-4. コードブロック・リンクの Qiita 互換チェック

- コメント（`//` など）を含む ` ```json ` ブロックがあれば ` ```js ` に変更する（`json` のままだと Qiita のシンタックスハイライトが壊れる）
- 言語指定の無いコードブロックがあれば警告としてサマリに載せる（変換はしない）
- リンクカードにすべき単独URLがインラインリンクになっていないか確認し、疑わしい箇所は警告としてサマリに載せる

#### 5-5. H1 削除

Qiita CLI の frontmatter `title:` が記事タイトルになるため、本文先頭の `# タイトル` は **削除する**
（Qiita 上でタイトル重複表示を避けるため）。

#### 5-6. frontmatter 生成（Qiita CLI 仕様）

出力ファイル用の frontmatter を以下で生成：

```yaml
---
title: 記事タイトル                # 元ファイルのH1から取得
tags:
  - tag1
  - tag2
private: true                       # 初回は必ずtrueで限定共有
updated_at: ''                       # Qiita CLI が自動管理
id: null                             # 新規記事はnull、既存は既存ID
organization_url_name: null          # 必要に応じて 'your-org' 等。ユーザー確認必須
slide: false
ignorePublish: false
---
```

- 元ファイルの Obsidian 用 frontmatter（`slug`, `status`, `created`, `qiita_id`, `published_at` 等）は **出力に含めない**
- `tags:` は配列形式に正規化（カンマ区切り `tag1, tag2` を配列に変換）
- **タグは1個以上必須・最大5個・`/` 不可**。違反していたらユーザーに教えて修正を促す
- **`private: true` を強く推奨**（テスト投稿後に `false` に変更する運用、D-12のテスト方針）

### Step 6. 出力ファイルの決定

**ファイル名は常に `<slug>.md` 固定**（Qiita CLI publish 後も変わらない）：

- 既存記事更新（元ファイルに `qiita_id` がある）→ `~/Desktop/work/qiita/public/<slug>.md` を上書き
  - frontmatter の `id:` を `qiita_id` の値で埋める（`null` ではなく）
- 新規記事 → `~/Desktop/work/qiita/public/<slug>.md` を新規作成
  - frontmatter の `id:` は `null`
- 同名ファイルが既に存在する場合は上書き確認をユーザーに促す

### Step 7. 結果サマリ出力

ターミナルに以下を簡潔に：

```
✅ qiita-publish-prep 完了

📂 入力: <元ファイルパス>
📂 出力: ~/Desktop/work/qiita/public/<slug>.md
🪣 S3 prefix: s3://<your-bucket>/<slug>/
🌐 CDN base: https://<your-cdn-domain>/<slug>/

📊 変換サマリ:
  - 画像アップロード: N件 (新規 X / スキップ Y)
  - 画像変名: K件
  - 画像パス置換: M件
  - Wikilink テキスト化: P件
  - Callout 変換: Q件
  - H1 削除: 1件
  - frontmatter: 整形済み（private: true, id: null/既存）

⚠️  警告 (あれば):
  - 見つからない画像: <相対パス>
  - 画像置き場/ 以外で発見: <絶対パス> （移動推奨）
  - 言語指定なしコードブロック: N箇所
  - リンクカード化候補のインラインリンク: N箇所

🚀 次のステップ（投稿フロー全体）:

  1. ローカルプレビュー
     cd ~/Desktop/work/qiita
     npx qiita preview                          # localhost:8888

  2. 限定共有で投稿（必ず private: true で）
     npx qiita publish <slug>

  3. ブラウザで Qiita 上の表示を確認
     ※限定共有中のURLは https://qiita.com/<user>/private/<id> 形式
     （/items/<id> は本公開後。限定共有中に /items/ リンクを案内しない）
     - タイトル・本文・画像（CloudFront 経由）
     - X 等の埋め込みリンクカード

  4. 本公開に切り替え
     ~/Desktop/work/qiita/public/<slug>.md の private: false に変更
     npx qiita publish <slug>                   # 同コマンドで更新

  5. 後片付け（qiita-archive スキル）
     /qiita-archive <元ファイルパス>
     → qiita_id / published_at を元ファイルに追記
     → 元ファイルを articles/published/ に移動し、board.md を更新
```

## エラーハンドリング

- AWS 認証エラー → `aws login` を促して中止
- 画像が見つからない → 警告として続行（ユーザーが意図的に外部画像を使っている可能性）
- S3 sync 失敗 → 中止、エラー出力を表示
- frontmatter パース失敗 → 該当行を示してユーザーに修正を促す

## やってはいけないこと

- **`npx qiita publish` を勝手に実行しない**（ユーザーが手動で行う）
- **S3 上のファイルを削除しない**（過去記事の画像URLが死ぬため、追加・更新のみ）
- **`private: false` を勝手に設定しない**（必ずユーザーに確認）
- **元ファイルの本文を書き換えない**（frontmatter の追記、画像参照ファイル名の更新のみ許可）

## 関連ファイル・スキル

- 後片付けスキル: `qiita-archive`（投稿後に呼ぶ）
- インフラ: `~/Desktop/work/blog-pipeline/cdk/lib/blog-assets-stack.ts`
- 設計判断: `~/Desktop/work/blog-pipeline/DECISIONS.md`（D-18 frontmatter 規約）
- 記事リポジトリの運用ルール: `~/Desktop/work/articles/README.md`
