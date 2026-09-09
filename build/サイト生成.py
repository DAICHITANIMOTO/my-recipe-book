#!/usr/bin/env python3
"""recipes/ 配下の全レシピMarkdownから、静的HTMLサイトを docs/ に生成する。

- docs/index.html        表紙＋訪問日順の一覧（最新の1品は大きく、残りはリスト）
- docs/<日付_料理名>.html  1レシピ1ページ（材料と作り方はPCで横並び、スマホで縦）
- docs/画像/              recipes/画像/ から必要な画像をコピー（Pagesはdocs/配下のみ配信）
- docs/robots.txt / .nojekyll   検索避けとJekyll無効化

デザイン方針：外食の「また食べたい」を書き留める私的な記録帖。
見出しは明朝、本文は角ゴシック。差し色はバジルの緑。装飾は最小限。

標準ライブラリのみ（pandoc不要。クラウドの夜間環境でも動く）。
"""
from __future__ import annotations

import datetime as dt
import html
import re
import shutil
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
RECIPES_DIR = ROOT / "recipes"
DOCS_DIR = ROOT / "docs"
DOCS_IMG_DIR = DOCS_DIR / "画像"
SITE_TITLE = "マイレシピ本"
SITE_TAGLINE = "外食で、また食べたいと思ったもの。"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
PLACEHOLDER_RE = re.compile(r"^（.*）$")  # 「（食べたときの感想をここに書く）」など未記入の目印

INGREDIENT_SEPS = (" … ", " ... ", "：", ": ", " — ")


# ---------- 解析 ----------

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


def parse_recipe_body(body: str) -> tuple[str, str, list[tuple[str, list[str]]]]:
    """本文を (推定レシピの注記, 画像ファイル名, [(見出し, 行リスト), ...]) に分解。"""
    note_parts: list[str] = []
    image_name = ""
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None

    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith(">"):
            note_parts.append(re.sub(r"^>\s?", "", line).lstrip("※ ").strip())
            continue
        m_img = IMG_RE.match(line.strip())
        if m_img and not image_name:
            image_name = m_img.group(2).strip().split("/")[-1]
            continue
        if line.startswith("## "):
            current = []
            sections.append((line[3:].strip(), current))
            continue
        if current is not None:
            current.append(line)

    note = " ".join(p for p in note_parts if p).strip()
    return note, image_name, sections


def section_is_empty(lines: list[str]) -> bool:
    text = "\n".join(l for l in lines if l.strip()).strip()
    if not text:
        return True
    return all(PLACEHOLDER_RE.match(l.strip()) for l in text.splitlines())


def split_ingredient(s: str) -> tuple[str, str]:
    for sep in INGREDIENT_SEPS:
        if sep in s:
            i = s.rfind(sep)
            return s[:i].strip(), s[i + len(sep):].strip()
    return s.strip(), ""


def inline(text: str) -> str:
    return BOLD_RE.sub(r"<strong>\1</strong>", html.escape(text))


def paras_html(lines: list[str]) -> str:
    """空行区切りの段落。箇条書き等は想定しない（説明・メモ用）。"""
    blocks: list[str] = []
    buf: list[str] = []
    for l in lines:
        if l.strip():
            buf.append(l.strip())
        elif buf:
            blocks.append(" ".join(buf))
            buf = []
    if buf:
        blocks.append(" ".join(buf))
    return "\n".join(f"<p>{inline(b)}</p>" for b in blocks)


def jp_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
        return f"{d.year}年{d.month}月{d.day}日"
    except ValueError:
        return iso


def date_range_label(dates: list[str]) -> str:
    ds = sorted(d for d in dates if re.match(r"\d{4}-\d{2}-\d{2}", d))
    if not ds:
        return ""
    a, b = dt.date.fromisoformat(ds[0]), dt.date.fromisoformat(ds[-1])
    if a == b:
        return f"{a.year}年{a.month}月"
    if a.year == b.year:
        return f"{a.year}年{a.month}月〜{b.month}月"
    return f"{a.year}年{a.month}月〜{b.year}年{b.month}月"


# ---------- レシピ読み込み ----------

class Recipe:
    def __init__(self, path: Path):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        self.stem = path.stem
        self.title = meta.get("title") or path.stem
        self.date = meta.get("date", "")
        self.restaurant = meta.get("restaurant", "").strip()
        self.category = meta.get("category", "").strip()
        self.note, self.image, self.sections = parse_recipe_body(body)
        self.page = f"{path.stem}.html"

    @property
    def has_image(self) -> bool:
        return bool(self.image) and (DOCS_IMG_DIR / self.image).exists()

    def summary(self, n: int = 70) -> str:
        for head, lines in self.sections:
            if head.startswith("説明"):
                t = " ".join(l.strip() for l in lines if l.strip() and not PLACEHOLDER_RE.match(l.strip()))
                t = re.split(r"(?<=[。！？])", t)[0]
                return html.escape(t[:n])
        return ""

    def place_line(self) -> str:
        d = jp_date(self.date) if self.date else ""
        if d and self.restaurant:
            return f"{d}、{html.escape(self.restaurant)}にて。"
        if d:
            return f"{d}。"
        return html.escape(self.restaurant)


def collect() -> list[Recipe]:
    return [Recipe(p) for p in sorted(RECIPES_DIR.glob("*.md")) if not p.name.startswith("_")]


def copy_images(recipes: list[Recipe]) -> None:
    DOCS_IMG_DIR.mkdir(parents=True, exist_ok=True)
    wanted: set[str] = set()
    for r in recipes:
        if r.image:
            wanted.add(r.image)
            src = RECIPES_DIR / "画像" / r.image
            if src.exists():
                shutil.copy2(src, DOCS_IMG_DIR / r.image)
    for f in DOCS_IMG_DIR.iterdir():
        if f.is_file() and f.name not in wanted:
            f.unlink()


# ---------- HTML ----------

CSS = """
:root{
  --paper:#fbfaf6; --ink:#26221c; --ink-soft:#6b6357;
  --hair:#e4dfd3; --accent:#2e5a44; --field:#fff;
  --serif:"Shippori Mincho","Hiragino Mincho ProN","Yu Mincho",serif;
  --sans:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",system-ui,sans-serif;
}
*,*::before,*::after{box-sizing:border-box}
html{overscroll-behavior-y:none;-webkit-text-size-adjust:100%}
html,body{overflow-x:hidden}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.8;font-weight:400;
  -webkit-font-smoothing:antialiased;overflow-wrap:anywhere}
img{display:block;max-width:100%;height:auto}
a{color:inherit}
.wrap{max-width:720px;margin:0 auto;padding:0 22px 96px}

/* 表紙 */
.masthead{padding:60px 0 26px;border-bottom:1px solid var(--hair)}
.masthead h1{font-family:var(--serif);font-weight:600;font-size:2.3rem;
  letter-spacing:.06em;margin:0 0 10px;line-height:1.3}
.masthead .tag{color:var(--ink-soft);font-size:.95rem;margin:0}
.masthead .count{color:var(--ink-soft);font-size:.8rem;margin:6px 0 0;letter-spacing:.04em}

/* 一覧：先頭の1品を大きく */
.feature{display:block;text-decoration:none;padding:34px 0;border-bottom:1px solid var(--hair)}
.feature .shot{width:100%;aspect-ratio:3/2;object-fit:cover;background:#efeadf;border:1px solid var(--hair)}
.feature h2{font-family:var(--serif);font-weight:600;font-size:1.6rem;margin:20px 0 6px;line-height:1.4}
.feature .meta{color:var(--ink-soft);font-size:.85rem;margin:0 0 8px}
.feature .lead{color:var(--ink-soft);font-size:.92rem;margin:0;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

/* 一覧：残り */
.list{list-style:none;margin:0;padding:0}
.list li{border-bottom:1px solid var(--hair)}
.entry{display:grid;grid-template-columns:96px minmax(0,1fr);gap:16px;align-items:center;
  padding:18px 0;text-decoration:none}
.entry > div{min-width:0}
.entry .thumb{width:96px;height:72px;object-fit:cover;background:#efeadf;border:1px solid var(--hair)}
.entry .thumb.none{display:flex;align-items:center;justify-content:center;
  color:#b7ac97;font-size:.62rem;letter-spacing:.08em}
.entry h3{font-family:var(--serif);font-weight:600;font-size:1.12rem;margin:0 0 3px;line-height:1.4}
.entry .meta{color:var(--ink-soft);font-size:.78rem;margin:0}

/* レシピページ */
.back{display:inline-block;color:var(--ink-soft);font-size:.82rem;text-decoration:none;
  margin:34px 0 22px}
.recipe-title{font-family:var(--serif);font-weight:600;font-size:2rem;line-height:1.35;margin:0}
.est{margin:14px 0 22px;padding-left:14px;border-left:2px solid var(--accent);
  color:var(--ink-soft);font-size:.82rem;line-height:1.7}
.facts{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 18px;
  margin:0 0 26px;padding:16px 0;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);
  font-size:.86rem}
.facts dt{color:var(--accent);font-size:.74rem;letter-spacing:.06em;align-self:center}
.facts dd{margin:0;min-width:0;overflow-wrap:anywhere}
.hero{width:100%;aspect-ratio:3/2;object-fit:cover;background:#efeadf;border:1px solid var(--hair)}
.hero.none{display:flex;align-items:center;justify-content:center;color:#b7ac97;font-size:.8rem}

.sec{margin:38px 0 0;min-width:0}
.sec > h2{display:flex;align-items:center;gap:10px;font-family:var(--sans);
  font-weight:700;font-size:1.02rem;letter-spacing:.02em;margin:0 0 14px}
.sec > h2::before{content:"";width:4px;height:1.05em;background:var(--accent);flex:none}
.sec p{margin:0 0 1em}

/* 説明の直後、材料と作り方をPCでは横並び */
.cook{display:grid;grid-template-columns:minmax(0,1fr);gap:0}
.cook > div{min-width:0}
@media(min-width:680px){
  .cook{grid-template-columns:minmax(0,43fr) minmax(0,57fr);gap:44px;align-items:start}
  .cook .sec{margin-top:0}
}

.ing{list-style:none;margin:0;padding:0}
.ing li{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;
  gap:2px 14px;padding:7px 0;border-bottom:1px solid var(--hair);font-size:.94rem}
.ing li > span:first-child{flex:1 1 auto;min-width:0;word-break:keep-all;overflow-wrap:anywhere}
.ing li .amt{flex:0 0 auto;color:var(--ink-soft);text-align:right}

.steps{list-style:none;margin:0;padding:0;counter-reset:step}
.steps li{counter-increment:step;position:relative;padding:0 0 16px 34px;font-size:.96rem}
.steps li::before{content:counter(step);position:absolute;left:0;top:0;
  font-family:var(--serif);color:var(--accent);font-size:1.05rem;line-height:1.7}

.colophon{margin:56px 0 0;padding-top:20px;border-top:1px solid var(--hair);
  color:var(--ink-soft);font-size:.76rem;line-height:1.8}

@media(prefers-color-scheme:dark){
  :root{--paper:#1c1a16;--ink:#ece5d8;--ink-soft:#a99f8c;--hair:#3a352c;
    --accent:#8fbf9f;--field:#232019}
  .feature .shot,.entry .thumb,.hero{background:#2a271f}
}
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Shippori+Mincho:wght@500;600&'
    'family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">'
)


def doc(title: str, body: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"ja\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"robots\" content=\"noindex, nofollow\">\n"
        f"<title>{html.escape(title)}</title>\n"
        f"{FONT_LINK}\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"<div class=\"wrap\">\n{body}\n</div>\n</body>\n</html>\n"
    )


def href(page: str) -> str:
    return quote(page, safe="")


def render_index(recipes: list[Recipe]) -> str:
    by_date = sorted(recipes, key=lambda r: (r.date, r.stem), reverse=True)
    rng = date_range_label([r.date for r in recipes])
    parts = [
        "<header class=\"masthead\">",
        f"<h1>{html.escape(SITE_TITLE)}</h1>",
        f"<p class=\"tag\">{html.escape(SITE_TAGLINE)}</p>",
        f"<p class=\"count\">全{len(recipes)}品／{html.escape(rng)}</p>",
        "</header>",
    ]

    if by_date:
        f = by_date[0]
        shot = (f'<img class="shot" src="画像/{html.escape(f.image)}" alt="">'
                if f.has_image else '<div class="shot"></div>')
        parts += [
            f'<a class="feature" href="{href(f.page)}">',
            shot,
            f"<h2>{html.escape(f.title)}</h2>",
            f'<p class="meta">{f.place_line()}</p>',
            f'<p class="lead">{f.summary()}</p>',
            "</a>",
        ]

    if len(by_date) > 1:
        parts.append('<ul class="list">')
        for r in by_date[1:]:
            if r.has_image:
                thumb = f'<img class="thumb" src="画像/{html.escape(r.image)}" alt="">'
            else:
                thumb = '<span class="thumb none">写真なし</span>'
            meta = jp_date(r.date) if r.date else ""
            if r.restaurant:
                meta += f"　{html.escape(r.restaurant)}"
            parts += [
                "<li>",
                f'<a class="entry" href="{href(r.page)}">',
                thumb,
                f"<div><h3>{html.escape(r.title)}</h3>"
                f'<p class="meta">{meta}</p></div>',
                "</a>",
                "</li>",
            ]
        parts.append("</ul>")

    parts.append(
        '<p class="colophon">材料・作り方はいずれも写真からの推定です。'
        "実際に作って気づいたことは各レシピに書き足していきます。</p>"
    )
    return doc(SITE_TITLE, "\n".join(parts))


def render_recipe(r: Recipe) -> str:
    hero = (f'<img class="hero" src="画像/{html.escape(r.image)}" alt="{html.escape(r.title)}">'
            if r.has_image else '<div class="hero none">写真なし</div>')

    facts = ['<dl class="facts">']
    if r.date:
        facts += [f"<dt>訪問日</dt><dd>{jp_date(r.date)}</dd>"]
    facts += [f"<dt>店名</dt><dd>{html.escape(r.restaurant) if r.restaurant else '—'}</dd>"]
    if r.category:
        facts += [f"<dt>カテゴリ</dt><dd>{html.escape(r.category)}</dd>"]
    facts.append("</dl>")

    desc_html = ""
    ing_html = ""
    step_html = ""
    extra: list[str] = []
    for head, lines in r.sections:
        if section_is_empty(lines):
            continue
        if head.startswith("説明"):
            desc_html = paras_html(lines)
        elif head.startswith("材料"):
            items = []
            for l in lines:
                s = l.strip()
                if s.startswith(("-", "*")):
                    name, amt = split_ingredient(s.lstrip("-* ").strip())
                    amt_html = f'<span class="amt">{inline(amt)}</span>' if amt else ""
                    items.append(f"<li><span>{inline(name)}</span>{amt_html}</li>")
            ing_html = (f'<div class="sec"><h2>{html.escape(head)}</h2>'
                        f'<ul class="ing">{"".join(items)}</ul></div>')
        elif head.startswith("作り方"):
            steps = []
            for l in lines:
                s = l.strip()
                m = re.match(r"^\d+[.、)]\s*(.*)$", s)
                if m:
                    steps.append(f"<li>{inline(m.group(1))}</li>")
                elif s.startswith(("-", "*")):
                    steps.append(f"<li>{inline(s.lstrip('-* ').strip())}</li>")
            step_html = (f'<div class="sec"><h2>{html.escape(head)}</h2>'
                         f'<ol class="steps">{"".join(steps)}</ol></div>')
        else:
            extra.append(f'<div class="sec"><h2>{html.escape(head)}</h2>{paras_html(lines)}</div>')

    body = [
        '<a class="back" href="index.html">← 一覧</a>',
        f'<h1 class="recipe-title">{html.escape(r.title)}</h1>',
    ]
    if r.note:
        body.append(f'<p class="est">{html.escape(r.note)}</p>')
    body += ["\n".join(facts), hero]
    if desc_html:
        body.append(f'<div class="sec"><h2>説明</h2>{desc_html}</div>')
    body.append(f'<div class="cook">{ing_html}{step_html}</div>')
    body += extra
    body.append('<a class="back" href="index.html">← 一覧に戻る</a>')
    return doc(f"{r.title}｜{SITE_TITLE}", "\n".join(body))


def main() -> int:
    recipes = collect()
    DOCS_DIR.mkdir(exist_ok=True)
    copy_images(recipes)

    # 古いレシピHTMLを掃除（index/robots/.nojekyll と 画像/ は残す）
    keep = {"index.html", "robots.txt", ".nojekyll"}
    for f in DOCS_DIR.glob("*.html"):
        if f.name not in keep:
            f.unlink()

    (DOCS_DIR / "index.html").write_text(render_index(recipes), encoding="utf-8")
    for r in recipes:
        (DOCS_DIR / r.page).write_text(render_recipe(r), encoding="utf-8")
    (DOCS_DIR / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"サイト生成完了: {len(recipes)} 品 → {DOCS_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
