#!/usr/bin/env python3
"""recipes/ 配下の全レシピMarkdownから、静的HTMLサイトを docs/ に生成する。

GitHub Pages の「main ブランチ / docs フォルダ」をソースにすると、
写真をアップ → 夜間エージェントがレシピ生成＆このスクリプト実行 → サイト自動更新、
という流れになる（PDFのように毎回ビルドして送り直す必要がない）。

- 出力: docs/index.html（表紙＋一覧カード＋全レシピ本文の1ページ）
- 画像: recipes/画像/ から docs/画像/ にコピー（Pagesはdocs/配下しか配信しないため）
- 検索避け: 全ページに noindex メタ＋ docs/robots.txt

標準ライブラリのみ（pandoc不要。クラウドの夜間環境でも動く）。
"""
from __future__ import annotations

import datetime as dt
import html
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = ROOT / "recipes"
DOCS_DIR = ROOT / "docs"
DOCS_IMG_DIR = DOCS_DIR / "画像"
SITE_TITLE = "マイレシピ本"
SITE_SUBTITLE = "外食で美味しかったものの再現記録"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, m.group(2)


def inline(text: str) -> str:
    """HTMLエスケープ＋**bold**だけ処理する。"""
    esc = html.escape(text)
    return BOLD_RE.sub(r"<strong>\1</strong>", esc)


def body_to_html(body: str) -> str:
    """レシピ本文（frontmatter除去済み）を、雛形で使う範囲のMarkdownだけHTML化する。"""
    lines = body.splitlines()
    out: list[str] = []
    para: list[str] = []
    quote: list[str] = []
    list_type: str | None = None  # "ul" or "ol"

    def flush_para() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_quote() -> None:
        if quote:
            out.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
            quote.clear()

    def flush_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    def flush_all() -> None:
        flush_para()
        flush_quote()
        flush_list()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_all()
            continue

        m_img = IMG_RE.match(line.strip())
        if m_img:
            flush_all()
            alt, src = m_img.group(1), m_img.group(2).strip()
            name = src.split("/")[-1]
            out.append(
                f'<figure><img src="画像/{html.escape(name)}" '
                f'alt="{html.escape(alt)}" loading="lazy"></figure>'
            )
            continue

        if line.startswith(">"):
            flush_para()
            flush_list()
            quote.append(line.lstrip("> ").strip())
            continue

        if line.startswith("## "):
            flush_all()
            out.append("<h3>" + inline(line[3:].strip()) + "</h3>")
            continue

        m_ol = re.match(r"^\d+\.\s+(.*)$", line)
        m_ul = re.match(r"^[-*]\s+(.*)$", line)
        if m_ol or m_ul:
            flush_para()
            flush_quote()
            want = "ol" if m_ol else "ul"
            if list_type != want:
                flush_list()
                out.append(f"<{want}>")
                list_type = want
            item = (m_ol or m_ul).group(1).strip()
            out.append("<li>" + inline(item) + "</li>")
            continue

        flush_quote()
        flush_list()
        para.append(line.strip())

    flush_all()
    return "\n".join(out)


def first_sentence(body: str) -> str:
    """説明セクションの最初の1文をカード用に取り出す。"""
    m = re.search(r"##\s*説明\s*\n(.+?)(\n##|\Z)", body, re.DOTALL)
    if not m:
        return ""
    text = " ".join(l.strip() for l in m.group(1).splitlines() if l.strip())
    text = re.sub(r"^>.*", "", text).strip()
    parts = re.split(r"(?<=[。！？])", text)
    return html.escape(parts[0][:80]) if parts else ""


def collect() -> list[tuple[Path, dict[str, str], str]]:
    items = []
    for p in sorted(RECIPES_DIR.glob("*.md")):
        if p.name.startswith("_"):
            continue
        meta, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        items.append((p, meta, body))
    return items


def copy_images(items) -> None:
    DOCS_IMG_DIR.mkdir(parents=True, exist_ok=True)
    wanted: set[str] = set()
    for _p, _meta, body in items:
        for _alt, src in IMG_RE.findall(body):
            name = src.strip().split("/")[-1]
            wanted.add(name)
            srcpath = RECIPES_DIR / "画像" / name
            if srcpath.exists():
                shutil.copy2(srcpath, DOCS_IMG_DIR / name)
    # 使われなくなった画像は消す
    for f in DOCS_IMG_DIR.iterdir():
        if f.is_file() and f.name not in wanted:
            f.unlink()


CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: #faf7f2; color: #2b2621;
  font-family: "Hiragino Sans", "Yu Gothic", system-ui, sans-serif; line-height: 1.75; }
.wrap { max-width: 760px; margin: 0 auto; padding: 0 20px 80px; }
header.cover { text-align: center; padding: 56px 20px 40px; }
header.cover h1 { font-family: "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 2.2rem; margin: 0 0 8px; letter-spacing: .04em; }
header.cover p { margin: 4px 0; color: #7a6f61; font-size: .95rem; }
h2.section { font-family: "Hiragino Mincho ProN", serif; font-size: 1.1rem;
  color: #9a8c76; border-bottom: 1px solid #e5ddcf; padding-bottom: 6px; margin: 48px 0 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 18px; }
.card { display: block; background: #fff; border: 1px solid #ece4d5; border-radius: 12px;
  overflow: hidden; text-decoration: none; color: inherit; transition: transform .12s ease; }
.card:hover { transform: translateY(-2px); }
.card .ph { aspect-ratio: 4 / 3; background: #f0eadd center/cover no-repeat; display: flex;
  align-items: center; justify-content: center; color: #c3b79f; font-size: .8rem; }
.card .body { padding: 12px 14px 14px; }
.card .body h3 { margin: 0 0 4px; font-size: 1.02rem; }
.card .body .meta { color: #8c8072; font-size: .78rem; margin-bottom: 6px; }
.card .body .lead { color: #5c5346; font-size: .85rem; margin: 0;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
article.recipe { border-top: 1px solid #e5ddcf; padding-top: 40px; margin-top: 40px; }
article.recipe h2 { font-family: "Hiragino Mincho ProN", serif; font-size: 1.7rem; margin: 0 0 6px; }
article.recipe .meta { color: #8c8072; font-size: .85rem; margin-bottom: 18px; }
article.recipe figure { margin: 0 0 20px; }
article.recipe img { width: 100%; border-radius: 12px; display: block; }
article.recipe h3 { font-size: 1.05rem; margin: 26px 0 8px; color: #3a332b;
  border-left: 3px solid #cbb98f; padding-left: 10px; }
article.recipe blockquote { margin: 0 0 16px; padding: 10px 14px; background: #f3ede0;
  border-radius: 8px; font-size: .88rem; color: #6b6152; }
article.recipe ul, article.recipe ol { padding-left: 1.4em; }
article.recipe li { margin: 4px 0; }
.toplink { display: inline-block; margin-top: 16px; font-size: .8rem; color: #9a8c76; text-decoration: none; }
footer { text-align: center; color: #a99e8c; font-size: .78rem; margin-top: 64px; }
"""


def page(items) -> str:
    today = dt.date.today().isoformat()
    cards = []
    articles = []
    for p, meta, body in items:
        slug = p.stem
        title = html.escape(meta.get("title") or slug)
        bits = []
        if meta.get("date"):
            bits.append(html.escape(meta["date"]))
        if meta.get("restaurant"):
            bits.append(html.escape(meta["restaurant"]))
        if meta.get("category"):
            bits.append(html.escape(meta["category"]))
        meta_line = " ・ ".join(bits)

        m_img = IMG_RE.search(body)
        img_name = m_img.group(2).split("/")[-1] if m_img else ""
        has_img = bool(img_name) and (DOCS_IMG_DIR / img_name).exists()
        ph_style = f' style="background-image:url(画像/{html.escape(img_name)})"' if has_img else ""
        ph_text = "" if has_img else "写真なし"

        cards.append(
            f'<a class="card" href="#{html.escape(slug)}">'
            f'<div class="ph"{ph_style}>{ph_text}</div>'
            f'<div class="body"><h3>{title}</h3>'
            f'<div class="meta">{meta_line}</div>'
            f'<p class="lead">{first_sentence(body)}</p></div></a>'
        )
        articles.append(
            f'<article class="recipe" id="{html.escape(slug)}">'
            f"<h2>{title}</h2>"
            f'<div class="meta">{meta_line}</div>'
            f"{body_to_html(body)}"
            f'<a class="toplink" href="#top">▲ 一覧へ戻る</a></article>'
        )

    count = len(items)
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{html.escape(SITE_TITLE)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap" id="top">
<header class="cover">
<h1>{html.escape(SITE_TITLE)}</h1>
<p>{html.escape(SITE_SUBTITLE)}</p>
<p>収録 {count} 品 ・ 最終更新 {today}</p>
</header>
<h2 class="section">一覧</h2>
<div class="grid">
{"".join(cards)}
</div>
{"".join(articles)}
<footer>写真をアップすると自動で追加されます。材料・作り方は写真からの推定です。</footer>
</div>
</body>
</html>
"""


def main() -> int:
    items = collect()
    DOCS_DIR.mkdir(exist_ok=True)
    copy_images(items)
    (DOCS_DIR / "index.html").write_text(page(items), encoding="utf-8")
    (DOCS_DIR / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n", encoding="utf-8"
    )
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"サイト生成完了: {len(items)} 品 → {DOCS_DIR}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
