#!/usr/bin/env python3
"""Qiita 本公開後の後片付けの決定論パート。

使い方:
    qiita_archive.py inspect <下書きパス | slug>
    qiita_archive.py apply   <下書きパス | slug> [--date YYYY-MM-DD]
                             [--allow-private] [--dry-run]

inspect はファイルを変更しない。下書きの特定・qiita_id の取得・投稿状態の
検証だけを行う。apply は frontmatter 更新（status/qiita_id/published_at）と
published/ への移動（レビューレポートも同時に）を行う。

board.md の完了ログは記事ごとに書く内容が違う判断仕事なので、このスクリプトは
触らない。SKILL.md 側（Claude）が担当する。

frontmatter ヘルパは qiita_prep.py と重複しているが、スキルは Codex へ個別に
同期されるため、各スキルで自己完結させている。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from dataclasses import dataclass
import shutil
import subprocess
import sys
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# ------------------------------------------------------------------- 環境

def _pick(value, env_name):
    v = value if value is not None else os.environ.get(env_name, "")
    v = v.strip()
    return v or None


def _require(pairs):
    missing = [name for name, v in pairs if not v]
    if missing:
        sys.exit("環境固有の値が未設定です: " + ", ".join(missing)
                 + "\n  プラグインの設定（/plugin configure blog-skills@ryuki-plugins）で入力するか、"
                 "引数または BLOG_SKILLS_* 環境変数で指定してください")


@dataclass(frozen=True)
class Env:
    """環境固有の値。引数（無ければ BLOG_SKILLS_* 環境変数）から組み立て、必要な関数に渡す。"""
    articles: Path          # 記事リポジトリ(published/ board.md)
    qiita_dir: Path         # Qiita CLI ワークスペース(public/ を参照する)
    obsidian: Path | None   # 旧置き場(任意。slug で下書きを探すときの探索先に加える)

    @property
    def published(self) -> Path:
        return self.articles / "published"

    @property
    def board(self) -> Path:
        return self.articles / "board.md"

    @property
    def qiita_public(self) -> Path:
        return self.qiita_dir / "public"

    @classmethod
    def from_args(cls, args) -> "Env":
        articles = _pick(args.articles_dir, "BLOG_SKILLS_ARTICLES_DIR")
        qiita = _pick(args.qiita_dir, "BLOG_SKILLS_QIITA_DIR")
        obsidian = _pick(args.obsidian_dir, "BLOG_SKILLS_OBSIDIAN_DIR")
        _require([("--articles-dir", articles), ("--qiita-dir", qiita)])
        return cls(
            articles=Path(articles).expanduser().resolve(),
            qiita_dir=Path(qiita).expanduser().resolve(),
            obsidian=Path(obsidian).expanduser().resolve() if obsidian else None,
        )


# ---------------------------------------------------------------- frontmatter

def split_frontmatter(text: str):
    if not text.startswith("---\n"):
        return "", text, False
    end = text.find("\n---\n", 3)
    if end == -1:
        return "", text, False
    return text[4:end + 1], text[end + 5:], True


def parse_fm(fm: str) -> dict:
    data, key = {}, None
    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            item = line.strip()
            if item.startswith("- ") and key:
                data.setdefault(key, [])
                if isinstance(data[key], list):
                    data[key].append(unquote_scalar(item[2:].strip()))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        data[key] = [] if raw == "" else unquote_scalar(raw)
    return data


def unquote_scalar(v: str):
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1].replace("''", "'") if v[0] == "'" else v[1:-1]
    if v in ("null", "~", ""):
        return None
    if v in ("true", "false"):
        return v == "true"
    return v


def quote_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    if s == "":
        return "''"
    if re.search(r":\s|\s#|^[-?:,\[\]{}#&*!|>'\"%@`]", s) or s.strip() != s:
        return "'" + s.replace("'", "''") + "'"
    return s


def fm_upsert(fm: str, key: str, value) -> str:
    """1キーだけを差し替える。他のキーの順序・引用形式を保つ。"""
    lines = fm.splitlines()
    out, replaced, i = [], False, 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", lines[i])
        if m and m.group(1) == key:
            out.append(f"{key}: {quote_scalar(value)}")
            i += 1
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                i += 1
            replaced = True
            continue
        out.append(lines[i])
        i += 1
    if not replaced:
        out.append(f"{key}: {quote_scalar(value)}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------- 解決

def resolve_draft(env: Env, arg: str):
    """引数（パス or slug）から下書きファイルを1つに特定する。"""
    p = Path(arg).expanduser()
    if p.is_file():
        return p.resolve(), None
    if not SLUG_RE.match(arg):
        return None, f"パスとして存在せず、slug の形式でもありません: {arg}"
    roots = [str(d) for d in (env.articles, env.obsidian) if d is not None and d.is_dir()]
    hits = subprocess.run(
        ["grep", "-rlE", rf"^slug:\s*['\"]?{re.escape(arg)}['\"]?\s*$",
         "--include=*.md", "--exclude-dir=.obsidian", "--exclude-dir=.trash",
         "--exclude-dir=.git", *roots],
        capture_output=True, text=True).stdout.split()
    hits = [Path(h) for h in hits if not h.endswith(".review.md")]
    if not hits:
        return None, f"slug '{arg}' を持つ下書きが見つかりません"
    if len(hits) > 1:
        return None, "候補が複数あります:\n  " + "\n  ".join(str(h) for h in hits)
    return hits[0].resolve(), None


def review_report_for(draft: Path):
    """review-blog が出すレビューレポート。2通りの命名を両方見る。"""
    for cand in (draft.with_suffix("").with_suffix(".review.md"),
                 Path(str(draft) + ".review.md"),
                 draft.with_name(draft.stem + ".review.md")):
        if cand.is_file():
            return cand
    return None


def analyze(env: Env, arg: str):
    draft, err = resolve_draft(env, arg)
    if err:
        return {"error": err}
    text = draft.read_text(encoding="utf-8")
    fm_text, body, has_fm = split_frontmatter(text)
    fm = parse_fm(fm_text)
    slug = fm.get("slug")

    info = {"draft": draft, "fm": fm, "fm_text": fm_text, "body": body,
            "slug": slug, "review": review_report_for(draft),
            "in_published": env.published in draft.parents, "blockers": [], "warns": []}
    if not has_fm or not slug:
        info["blockers"].append("下書きに slug がありません → 先に /qiita-publish-prep を実行")
        return info

    out = env.qiita_public / f"{slug}.md"
    info["qiita_file"] = out
    if not out.is_file():
        info["blockers"].append(f"{out} がありません → 先に /qiita-publish-prep を実行")
        return info
    qfm = parse_fm(split_frontmatter(out.read_text(encoding="utf-8"))[0])
    info["qiita_id"] = qfm.get("id")
    info["private"] = qfm.get("private")
    info["qiita_title"] = qfm.get("title")
    if not info["qiita_id"]:
        info["blockers"].append(
            f"id が null です → `cd {env.qiita_dir} && npx qiita publish {slug}` を先に実行")
    if info["private"]:
        info["warns"].append("private: true のままです（限定共有）。本公開後にアーカイブするのが本来の順序")
    if fm.get("status") == "published":
        info["warns"].append("下書きは既に status: published です（再実行）")
    if info["in_published"]:
        info["warns"].append("下書きは既に published/ にあります（移動はスキップ）")
    dest = env.published / draft.name
    if not info["in_published"] and dest.exists():
        info["blockers"].append(f"移動先に同名ファイルがあります: {dest}")
    if info["review"] and not info["in_published"]:
        rdest = env.published / info["review"].name
        if rdest.exists():
            info["blockers"].append(f"レビューレポートの移動先に同名ファイル: {rdest}")
    return info


# --------------------------------------------------------------------- 実行

def show(env: Env, info):
    print(f"下書き   : {info['draft']}")
    print(f"slug     : {info.get('slug') or '(なし)'}")
    print(f"status   : {info['fm'].get('status')}  →  published")
    print(f"qiita_id : {info.get('qiita_id') or '(なし)'}")
    print(f"private  : {info.get('private')}")
    print(f"Qiita側  : {info.get('qiita_file') or '(なし)'}")
    print(f"レビュー : {info['review'] or '(なし)'}")
    print(f"移動先   : {env.published / info['draft'].name}"
          f"{'  (既に published/ にあるため移動しない)' if info['in_published'] else ''}")
    for w in info["warns"]:
        print(f"  ⚠ {w}")
    for b in info["blockers"]:
        print(f"  ✗ {b}")


def cmd_inspect(env: Env, args):
    info = analyze(env, args.target)
    if "error" in info:
        print(f"ERROR: {info['error']}", file=sys.stderr)
        return 1
    show(env, info)
    print()
    print("■ 次のアクション")
    if info["blockers"]:
        print("  - 上の ✗ を解消してから apply")
    else:
        print("  - apply 可能")
        print("  - apply 後、board.md の該当行を消して完了ログに1行追記（Claude が担当）")
    return 1 if info["blockers"] else 0


def cmd_apply(env: Env, args):
    info = analyze(env, args.target)
    if "error" in info:
        print(f"ERROR: {info['error']}", file=sys.stderr)
        return 1
    if info["blockers"]:
        print("ERROR: 先に解消してください:", file=sys.stderr)
        for b in info["blockers"]:
            print(f"  - {b}", file=sys.stderr)
        return 1
    if info.get("private") and not args.allow_private:
        print("ERROR: private: true のままです。本公開後に実行するか --allow-private を付けてください。",
              file=sys.stderr)
        return 1

    draft, dry = info["draft"], args.dry_run
    date = args.date or info["fm"].get("published_at") or dt.date.today().isoformat()

    fm_text = info["fm_text"]
    fm_text = fm_upsert(fm_text, "status", "published")
    fm_text = fm_upsert(fm_text, "qiita_id", info["qiita_id"])
    fm_text = fm_upsert(fm_text, "published_at", date)
    print("■ frontmatter 更新")
    print(f"  status: {info['fm'].get('status')} -> published")
    print(f"  qiita_id: {info['qiita_id']}")
    print(f"  published_at: {date}")
    if not dry:
        draft.write_text("---\n" + fm_text + "---\n" + info["body"], encoding="utf-8")

    moved = []
    if info["in_published"]:
        print("■ 移動: 既に published/ にあるためスキップ")
    else:
        env.published.mkdir(parents=True, exist_ok=True)
        for src in [draft] + ([info["review"]] if info["review"] else []):
            dest = env.published / src.name
            print(f"■ 移動: {src}\n        -> {dest}")
            if not dry:
                shutil.move(str(src), str(dest))
            moved.append(dest)

    final = moved[0] if moved else draft
    print()
    print("■ サマリ")
    print(f"  記事   : {info.get('qiita_title')}")
    print(f"  slug   : {info['slug']}")
    print(f"  最終位置: {final}")
    if len(moved) > 1:
        print(f"  レビュー: {moved[1]}")
    print(f"  Qiita  : https://qiita.com/items/{info['qiita_id']}")
    for w in info["warns"]:
        print(f"  ⚠ {w}")
    print()
    print("■ 残作業（Claude が担当・スクリプトは触らない）")
    print(f"  - {env.board} の該当行をボードから削除し、完了ログの先頭に1行追記する")
    if dry:
        print("\n  (--dry-run のため実際の書き込みは行っていません)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("環境固有の値（未指定なら BLOG_SKILLS_* 環境変数を使う）")
    g.add_argument("--articles-dir", help="記事リポジトリ（drafts/ published/ board.md がある場所）")
    g.add_argument("--qiita-dir", help="Qiita CLI ワークスペース（public/ を参照する）")
    g.add_argument("--obsidian-dir", help="旧置き場（任意。slug で下書きを探すときの探索先に加える）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect", parents=[common], help="特定・検証のみ（変更しない）")
    i.add_argument("target", help="下書きの絶対パス、または slug")
    i.set_defaults(func=cmd_inspect)
    a = sub.add_parser("apply", parents=[common], help="frontmatter 更新とファイル移動を実行")
    a.add_argument("target", help="下書きの絶対パス、または slug")
    a.add_argument("--date", help="published_at（既定は既存値、無ければ今日）")
    a.add_argument("--allow-private", action="store_true",
                   help="private: true のままでもアーカイブする")
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=cmd_apply)
    args = ap.parse_args()
    env = Env.from_args(args)
    return args.func(env, args)


if __name__ == "__main__":
    sys.exit(main())
