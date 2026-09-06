#!/usr/bin/env python3
"""recipes/ 配下の全レシピMarkdownを1冊に結合し、表紙・目次つきの
レシピ本（PDF / Word）を 出力/ に生成するスクリプト。

使い方:
    python3 build/build.py              # PDFとWordの両方
    python3 build/build.py --format pdf
    python3 build/build.py --format docx

必要ツール:
    brew install pandoc typst
    （typstはPDF生成にのみ必要。無い場合はWordだけ生成する）

標準ライブラリのみで動く（追加のpip installは不要）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = ROOT / "recipes"
OUT_DIR = ROOT / "出力"
BOOK_TITLE = "マイレシピ本"

# 本文中の画像記法 ![alt](path) を拾う
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# 先頭のfrontmatter( --- ... --- )を取り出す
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """先頭の --- ... --- を辞書にし、本文と分けて返す。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_block, body = m.group(1), m.group(2)
    meta: dict[str, str] = {}
    for line in meta_block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


def collect_recipes() -> list[Path]:
    """recipes/*.md を（アンダースコア始まりを除き）ファイル名順で返す。
    ファイル名の先頭が日付なので、これで訪問日の古い順に並ぶ。"""
    return sorted(p for p in RECIPES_DIR.glob("*.md") if not p.name.startswith("_"))


def fix_image_links(body: str) -> str:
    """画像パスを ROOT 基準に直し、ファイルが無いものは注記に置き換える。"""

    def repl(m: re.Match[str]) -> str:
        alt, path = m.group(1), m.group(2).strip()
        # 「画像/xxx」を「recipes/画像/xxx」に補正（レシピ内ではrecipes/を省略）
        rel = path
        if rel.startswith("画像/"):
            rel = "recipes/" + rel
        if (ROOT / rel).exists():
            return f"![{alt}]({rel})"
        return f"*（写真未登録: {path}）*"

    return IMG_RE.sub(repl, body)


def build_combined_markdown(files: list[Path]) -> str:
    today = dt.date.today().isoformat()
    lines = [
        "---",
        f"title: {BOOK_TITLE}",
        f"date: {today}",
        "lang: ja",
        "toc-title: 目次",
        "---",
        "",
    ]
    for path in files:
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        title = meta.get("title") or path.stem

        info_bits: list[str] = []
        if meta.get("date"):
            info_bits.append(f"訪問日 {meta['date']}")
        if meta.get("restaurant"):
            info_bits.append(f"店名 {meta['restaurant']}")
        if meta.get("category"):
            info_bits.append(f"カテゴリ {meta['category']}")

        lines.append(f"# {title}")
        lines.append("")
        if info_bits:
            lines.append("*" + " ／ ".join(info_bits) + "*")
            lines.append("")
        lines.append(fix_image_links(body).strip())
        lines.append("")
    return "\n".join(lines)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="レシピ本をビルドする")
    parser.add_argument(
        "--format",
        choices=["pdf", "docx", "both"],
        default="both",
        help="生成する形式（既定: both）",
    )
    args = parser.parse_args()

    if not shutil.which("pandoc"):
        print(
            "pandoc が見つかりません。次を実行してください:\n"
            "    brew install pandoc typst",
            file=sys.stderr,
        )
        return 1

    files = collect_recipes()
    if not files:
        print("recipes/ にレシピ(.md)がありません。", file=sys.stderr)
        return 1

    print(f"{len(files)} 件のレシピをまとめます:")
    for path in files:
        print(f"  - {path.name}")

    OUT_DIR.mkdir(exist_ok=True)
    combined_md = OUT_DIR / "_結合.md"
    combined_md.write_text(build_combined_markdown(files), encoding="utf-8")

    common = [
        str(combined_md),
        "--toc",
        "--toc-depth=1",
        "--resource-path=.",
        "--metadata=lang:ja",
    ]

    want_pdf = args.format in ("pdf", "both")
    want_docx = args.format in ("docx", "both")

    if want_pdf:
        if not shutil.which("typst"):
            print(
                "typst が無いためPDFはスキップします（`brew install typst` で有効化）。",
                file=sys.stderr,
            )
        else:
            run(
                [
                    "pandoc",
                    *common,
                    "--pdf-engine=typst",
                    "-V",
                    "mainfont=Hiragino Sans",
                    "-o",
                    str(OUT_DIR / f"{BOOK_TITLE}.pdf"),
                ]
            )

    if want_docx:
        run(["pandoc", *common, "-o", str(OUT_DIR / f"{BOOK_TITLE}.docx")])

    print("\n完了 →", OUT_DIR)
    for f in sorted(OUT_DIR.glob(f"{BOOK_TITLE}.*")):
        print("  ", f.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
