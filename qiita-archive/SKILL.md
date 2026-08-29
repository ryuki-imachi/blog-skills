---
name: qiita-archive
description: Qiita投稿後の後片付け。元下書きの frontmatter を published 状態に更新（qiita_id / published_at 追記）し、articles/published/ に移動して board.md を更新する
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

`/qiita-publish-prep` で変換し、`npx qiita publish` で本公開（`private: false`）した後の **後片付け** を行うスキル。

## 何をするか

1. 元下書きファイルの frontmatter を **published 状態**に更新する
   - `status: ready` → `status: published`
   - `qiita_id` を追記（Qiita CLI が `public/<slug>.md` の `id:` に書いた値）
   - `published_at` に今日の日付を追記
2. 元ファイルを `~/Desktop/work/articles/published/` に移動
3. 同じディレクトリに同名のレビューレポート（`/review-blog` が生成する `<元ファイル名（拡張子除く）>.review.md`）があれば、記事本体とセットで `published/` に移動する
4. `~/Desktop/work/articles/board.md` の該当行をボードから消し、「完了ログ」に1行追記する（Artifactの再発行も行う）

これにより、再投稿（記事更新）時に slug / qiita_id を引き継いで `/qiita-publish-prep` が再実行できる。

## 前提

- 直前に `/qiita-publish-prep` で `~/Desktop/work/qiita/public/<slug>.md` が生成されていること
- そのファイルが `npx qiita publish` で本公開済み（=Qiita CLI により `id:` に Qiita ID が書き込まれている）

## スキルの引数

`$ARGUMENTS` は次のいずれか：

1. **元下書き Markdown の絶対パス**（推奨）
   - 例: `~/Desktop/work/articles/drafts/40_限定公開/【Codex】pet が見切れる問題を解決する.md`
2. **slug**（フォールバック）
   - 例: `codex-pet-offscreen-fix`
   - この場合、articles/（見つからなければ旧obsidian/memo/）を grep して frontmatter に `slug: <値>` を持つファイルを特定する

引数が無ければ中止し、ユーザーにパスか slug を指示する。

## 実行フロー

### Step 0. 引数解釈

- 引数がパスならそれを元ファイルとして扱う
- 引数が slug らしき文字列（`[a-z0-9-]+`）なら、Vault を検索して元ファイルを特定：
  ```bash
  grep -rlE "^slug:\s*<slug>\s*$" \
    ~/Desktop/work/articles \
    ~/Desktop/work/obsidian/memo \
    --include="*.md"
  ```
- 複数ヒット or 0 ヒット → ユーザーに知らせて中止

### Step 1. 入力検証

1. 元ファイルを Read して frontmatter を取得
2. `slug:` を取得（無ければ中止、`/qiita-publish-prep` を先に走らせるよう指示）
3. 既に `status: published` であれば、ユーザーに「既に published 済みです。再実行しますか？」と確認
4. 元ファイルが既に `articles/published/`（または旧 `memo/99_投稿済み/`）にあれば、移動はスキップして frontmatter 更新のみ行う

### Step 2. Qiita ID の取得

`~/Desktop/work/qiita/public/<slug>.md` を Read して frontmatter の `id:` を取得：

```bash
~/Desktop/work/qiita/public/<slug>.md
```

- ファイルが存在しない → `/qiita-publish-prep` を先に走らせるよう指示して中止
- `id:` が `null` または空 → 「未投稿状態です。`npx qiita publish <slug>` を実行してから再度このスキルを呼んでください」と伝えて中止
- `private: true` のままなら警告（限定共有のままでアーカイブして良いか確認）

### Step 3. 元ファイル frontmatter の更新

D-18 規約に沿って次の状態に整える：

```yaml
---
slug: <既存値>
status: published
qiita_id: <Step 2 で取得した id>
published_at: YYYY-MM-DD     # 今日の日付（`date +%Y-%m-%d`）
---
```

- 既存のキー（`slug`、その他独自キー）は残す
- `status` を更新
- `qiita_id` / `published_at` が無ければ追記、あれば更新

Edit ツールで frontmatter ブロックを書き換える。

### Step 4. ファイル移動

元ファイルが `articles/published/` にまだ無ければ移動。移動先に同名ファイルが既にある場合は中止し、ユーザーに重複確認を促す：

```bash
src="<元ファイル>"
dest=~/Desktop/work/articles/published/"$(basename "$src")"
if [ -e "$dest" ]; then echo "ERROR: 移動先に同名ファイルあり"; else mv "$src" "$dest"; fi
```

- ファイル名はそのまま

続いて、同じディレクトリに **同名のレビューレポート**（`/review-blog` が生成する `<元ファイル名（拡張子除く）>.review.md`）があれば、これも一緒に `published/` に移動する。中間生成物なので、存在すれば記事本体とセットで移動（無ければスキップ）：

```bash
review="${src%.md}.review.md"
rdest=~/Desktop/work/articles/published/"$(basename "$review")"
if [ -e "$review" ]; then
  if [ -e "$rdest" ]; then echo "ERROR: review.md の移動先に同名ファイルあり"; else mv "$review" "$rdest"; fi
fi
```

- review.md の移動先に同名ファイルが既にある場合は中止し、ユーザーに確認

### Step 5. 結果サマリ出力

```
✅ qiita-archive 完了

📂 移動:
  Before: <元ファイルパス>
  After:  ~/Desktop/work/articles/published/<filename>
  （review.md も移動した場合は併記。無ければこの行は出さない）
  board.md: 該当行を完了ログへ移動済み

📝 frontmatter 更新:
  - status: ready → published
  - qiita_id: <id>
  - published_at: YYYY-MM-DD

🔗 Qiita 記事:
  https://qiita.com/items/<id>

🚀 次のアクション:
  - 記事を更新したくなったら、published/ から元ファイルを編集して
    再度 /qiita-publish-prep → npx qiita publish <slug> でOK
    （slug / qiita_id を引き継ぐので URL は変わらない）
```

## エラーハンドリング

- 元ファイルが見つからない → ユーザーに正しいパスを指示してもらう
- `~/Desktop/work/qiita/public/<slug>.md` が存在しない → `/qiita-publish-prep` を先に走らせる
- `id:` が null → publish が未完了。`npx qiita publish <slug>` を案内
- published/ に同名ファイル → 重複している可能性あり、ユーザーに確認

## やってはいけないこと

- **本文を書き換えない**（frontmatter のみ更新）
- **`articles/published/` 以外の場所に移動しない**
- **元ファイルを削除しない**（移動のみ）
- **slug を変更しない**（既存の S3 prefix が無効になる）

## 関連ファイル・スキル

- 前段スキル: `qiita-publish-prep`（投稿前の変換）
- 設計判断: `~/Desktop/work/blog-pipeline/DECISIONS.md`（D-18 frontmatter 規約）
- 記事リポジトリの運用ルール: `~/Desktop/work/articles/README.md`
