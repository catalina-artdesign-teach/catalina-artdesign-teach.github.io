#!/usr/bin/env python3
"""
Builds the website into the _site folder.

It reads:
  settings.txt               name, year labels and colours
  about.txt                  text for the About page
  year-7/, year-8/, year-9/  one folder per project, each with project.txt and photos

It checks every project first. If something is missing, it lists the problems
and stops, so the site that is already online stays as it is.

You never need to run this yourself: GitHub runs it every time you change something.
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_OK = True
except ImportError:  # HEIC photos will be reported as a problem
    HEIF_OK = False

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "site-engine"
CACHE = ROOT / ".cache" / "images"
YEARS = ["7", "8", "9"]
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
PROJECT_KEYS = {"title", "keyword", "skills", "school year"}
IMAGE_VERSION = "v1"   # change to force all photos to be converted again

# Sizes made from every photo (longest side, in pixels)
SIZES = {"f": 2000, "m": 1200, "t": 400}
SQUARE = 600           # square thumbnail for the project tile

errors = []
notes = []


def problem(where, message):
    errors.append(f"{where}: {message}")


# ---------------------------------------------------------------- reading text files

def read_text(path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_settings():
    path = ROOT / "settings.txt"
    s = {
        "name": "",
        "subtitle": "",
        "year 7": "", "year 8": "", "year 9": "",
        "accent colour": "#FF5A36",
        "background colour": "#111111",
        "text colour": "#F5F3EE",
    }
    if not path.exists():
        problem("settings.txt", "the file is missing.")
        return s
    for line in read_text(path).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace("color", "colour")
        s[key] = value.strip()
    if not s["name"]:
        problem("settings.txt", "the 'name:' line is empty.")
    for key in ("accent colour", "background colour", "text colour"):
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", s[key]):
            problem("settings.txt", f"'{key}' must be a colour code like #FF5A36 (it is '{s[key]}').")
            s[key] = {"accent colour": "#FF5A36", "background colour": "#111111", "text colour": "#F5F3EE"}[key]
    return s


def read_paragraphs(text):
    paras, cur = [], []
    for line in text.split("\n"):
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return paras


def read_project_txt(path):
    fields, body, in_body = {}, [], False
    for line in read_text(path).split("\n"):
        m = re.match(r"^\s*([A-Za-z ]+?)\s*:\s*(.*)$", line)
        if not in_body and m and m.group(1).strip().lower() in PROJECT_KEYS:
            fields[m.group(1).strip().lower()] = m.group(2).strip()
            continue
        if line.strip():
            in_body = True
        body.append(line)
    return fields, read_paragraphs("\n".join(body))


# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(s, quote=True)


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def natural_key(name):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name.lower())]


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def rgb_hex(c):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):
    a, b = hex_rgb(a), hex_rgb(b)
    return rgb_hex([a[i] + (b[i] - a[i]) * t for i in range(3)])


def luminance(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def theme_on_accent(accent):
    return "#111111" if contrast(accent, "#111111") >= contrast(accent, "#FFFFFF") else "#FFFFFF"


def theme_css(s):
    bg, text, accent = s["background colour"], s["text colour"], s["accent colour"]
    on_accent = theme_on_accent(accent)
    v = {
        "--bg": bg,
        "--text": text,
        "--accent": accent,
        "--on-accent": on_accent,
        "--panel": mix(bg, text, 0.06),
        "--line": mix(bg, text, 0.17),
        "--line-soft": mix(bg, text, 0.10),
        "--muted": mix(bg, text, 0.70),
        "--muted-2": mix(bg, text, 0.40),
        "--tile-dark": "#2A2A2A",
        "--tile-dark-touch": "#454545",
    }
    scheme = "dark" if luminance(bg) < 0.4 else "light"
    return ":root{" + ";".join(f"{k}:{val}" for k, val in v.items()) + f";color-scheme:{scheme}}}"


def keyword_size(word):
    # shrink long keywords so they always fit inside the square tile
    n = max(1, len(word))
    return round(min(17.0, 82.0 / (0.8 * n)), 2)


# ---------------------------------------------------------------- photos

def open_photo(src):
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    icc = im.info.get("icc_profile")
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    return im, icc


def make_versions(src, out_dir, stem, square=False):
    """Makes the web versions of one photo (cached, so unchanged photos are quick)."""
    data = src.read_bytes()
    digest = hashlib.sha1(data).hexdigest()
    kinds = dict(SIZES)
    if square:
        kinds["sq"] = SQUARE
    out = {}
    todo = {}
    for kind in kinds:
        cached = CACHE / f"{digest}-{kind}-{IMAGE_VERSION}.webp"
        out[kind] = cached
        if not cached.exists():
            todo[kind] = cached
    dims = None
    if todo:
        im, icc = open_photo(src)
        CACHE.mkdir(parents=True, exist_ok=True)
        for kind, cached in todo.items():
            if kind == "sq":
                side = min(im.size)
                left, top = (im.width - side) // 2, (im.height - side) // 2
                small = im.crop((left, top, left + side, top + side)).resize((SQUARE, SQUARE), Image.LANCZOS)
            else:
                small = im.copy()
                small.thumbnail((kinds[kind], kinds[kind]), Image.LANCZOS)
            # saved without the photo's metadata (no location, no camera details)
            small.save(cached, "WEBP", quality=80, method=5, icc_profile=icc)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for kind, cached in out.items():
        dest = out_dir / f"{stem}-{kind}.webp"
        shutil.copyfile(cached, dest)
        result[kind] = dest
    with Image.open(result["m"]) as m:
        dims = m.size
    return result, dims


# ---------------------------------------------------------------- reading projects

def read_projects(year):
    folder = ROOT / f"year-{year}"
    projects = []
    if not folder.exists():
        return projects
    used = set()
    for d in sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")):
        where = f"year-{year}/{d.name}"
        m = re.match(r"^(\d+)[\s._-]*(.*)$", d.name)
        if not m:
            problem(where, "the folder name must start with a number, for example 03-pop-art.")
            continue
        number = int(m.group(1))
        slug = slugify(m.group(2)) or f"project-{number}"
        base, k = slug, 2
        while slug in used:
            slug, k = f"{base}-{k}", k + 1
        used.add(slug)

        # accept Project.txt, PROJECT.TXT and project.txt.txt (a common Windows slip)
        txt = next((f for f in d.iterdir() if f.is_file() and f.name.lower() in ("project.txt", "project.txt.txt")),
                   d / "project.txt")
        if not txt.exists():
            alt = [f.name for f in d.iterdir() if f.suffix.lower() == ".txt"]
            hint = f" (found {', '.join(alt)}: it must be called exactly project.txt)" if alt else ""
            problem(where, "project.txt is missing" + hint + ".")
            continue
        fields, paras = read_project_txt(txt)
        title = fields.get("title", "")
        keyword = fields.get("keyword", "").strip()
        if not title:
            problem(where + "/project.txt", "the 'title:' line is missing or empty.")
        if not keyword:
            problem(where + "/project.txt", "the 'keyword:' line is missing or empty.")
        elif " " in keyword:
            problem(where + "/project.txt", f"the keyword must be one word (it is '{keyword}').")
        if not paras:
            problem(where + "/project.txt", "there is no text about the project (write it after the labelled lines).")
        skills = [x.strip() for x in fields.get("skills", "").split(",") if x.strip()]

        photos = [f for f in d.iterdir()
                  if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in PHOTO_EXT]
        if not photos:
            # not ready yet (text added, photos still to come): skip it quietly
            notes.append(f"{where}: no photos yet, so this project is not shown.")
            continue
        photos.sort(key=lambda f: (f.stem.lower() != "cover", natural_key(f.name)))
        if not HEIF_OK and any(f.suffix.lower() in (".heic", ".heif") for f in photos):
            problem(where, "HEIC photos can't be read because pillow-heif is not installed.")
            continue
        projects.append({
            "year": year, "folder": d, "where": where, "number": number, "slug": slug,
            "title": title, "keyword": keyword, "paras": paras, "skills": skills,
            "school_year": fields.get("school year", ""), "photos": photos,
        })
    projects.sort(key=lambda p: (-p["number"], natural_key(p["folder"].name)))
    return projects


def process_photos(project, out_root):
    out_dir = out_root / "media" / f"year-{project['year']}" / project["slug"]
    items = []
    for k, f in enumerate(project["photos"], start=1):
        try:
            files, dims = make_versions(f, out_dir, f"{k:02d}", square=(k == 1))
        except Exception as e:  # unreadable or damaged file
            problem(f"{project['where']}/{f.name}", f"this photo could not be opened ({e.__class__.__name__}).")
            continue
        items.append({"files": files, "dims": dims})
    project["items"] = items


# ---------------------------------------------------------------- HTML

ICON = {
    "prev": '<svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M11 18l-6-6 6-6"/></svg>',
    "next": '<svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>',
    "up": '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg>',
    "full": '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>',
    "close": '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg>',
}


class Pages:
    def __init__(self, settings, out, explicit_index, asset_version):
        self.s = settings
        self.out = out
        self.explicit = explicit_index
        self.v = asset_version
        self.theme = theme_css(settings)

    def href(self, root, page):
        """page is '' for home or 'year-7' / 'about'."""
        if self.explicit:
            return f"{root}{page + '/' if page else ''}index.html"
        return f"{root}{page + '/' if page else ''}" or "./"

    def rel(self, root, path):
        return root + path.relative_to(self.out).as_posix()

    def layout(self, root, current, title, body, footer_extra="", tail=""):
        s = self.s
        nav = [("", "Home"), ("year-7", "Year 7"), ("year-8", "Year 8"), ("year-9", "Year 9"), ("about", "About")]
        links = "\n".join(
            f'<a href="{self.href(root, p)}"{" aria-current=\"page\"" if p == current else ""}>{label}</a>'
            for p, label in nav)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noimageindex">
<title>{esc(title)}</title>
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/style.css?v={self.v}">
<style>{self.theme}</style>
<script>document.documentElement.className += " js";</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<div class="wrap">
<a class="brand" href="{self.href(root, '')}">{esc(s['name'])}<span>.</span></a>
<nav class="nav" aria-label="Main">
{links}
</nav>
</div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
<div class="wrap">
{footer_extra or '<span></span>'}
<p>Student work is shared without names or faces, to protect students' privacy.</p>
</div>
</footer>
{tail}
</body>
</html>
"""

    def write(self, page, content):
        path = self.out / page / "index.html" if page else self.out / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # ---- year page
    def year_page(self, year, projects):
        root = "../"
        course = self.s.get(f"year {year}", "")
        head = f"""<section class="wrap page-head">
{f'<p class="eyebrow">{esc(course)}</p>' if course else ''}
<h1 class="page-title">Year {year}</h1>
</section>"""
        if not projects:
            body = head + '\n<section class="wrap"><p class="empty">Projects coming soon.</p></section>'
            self.write(f"year-{year}", self.layout(root, f"year-{year}", f"Year {year} · {course} — {self.s['name']}", body))
            return

        tiles = []
        for k, p in enumerate(projects):
            sq = self.rel(root, p["items"][0]["files"]["sq"])
            loading = "eager" if k < 6 else "lazy"
            tiles.append(
                f'<li><a class="tile" href="#{p["slug"]}">'
                f'<img src="{sq}" alt="" width="{SQUARE}" height="{SQUARE}" loading="{loading}">'
                f'<span class="cut" style="--kw:{keyword_size(p["keyword"])}cqw" aria-hidden="true">{esc(p["keyword"])}</span>'
                f'<span class="sr-only">{esc(p["title"])}</span></a></li>')

        sections = []
        for p in projects:
            n = len(p["items"])
            data = [{"m": self.rel(root, it["files"]["m"]), "f": self.rel(root, it["files"]["f"]),
                     "alt": f"Student work {i} of {n}: {p['title']}"} for i, it in enumerate(p["items"], start=1)]
            data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
            first = p["items"][0]
            w, h = first["dims"]
            paras = "\n".join(f"<p>{esc(x)}</p>" for x in p["paras"])
            skills = ("<ul class=\"skills\">" + "".join(f"<li>{esc(x)}</li>" for x in p["skills"]) + "</ul>") if p["skills"] else ""
            thumbs = ""
            controls = ""
            if n > 1:
                thumbs = '<ul class="thumbs">' + "".join(
                    f'<li><a class="thumb" href="{self.rel(root, it["files"]["f"])}" aria-label="Show picture {i}" '
                    f'aria-current="{"true" if i == 1 else "false"}"><img src="{self.rel(root, it["files"]["t"])}" alt="" loading="lazy"></a></li>'
                    for i, it in enumerate(p["items"], start=1)) + "</ul>"
                controls = f"""<div class="controls">
<p class="counter" aria-live="polite"><b>01</b><span>/{n:02d}</span></p>
<div class="arrows">
<button class="arrow" type="button" data-prev aria-label="Previous picture">{ICON['prev']}</button>
<button class="arrow" type="button" data-next aria-label="Next picture">{ICON['next']}</button>
</div>
</div>"""
            sections.append(f"""<section class="wrap project" id="{p['slug']}" aria-labelledby="{p['slug']}-title">
<h2 class="project-title" id="{p['slug']}-title">{esc(p['title'])}</h2>
<div class="cols">
<div class="about">
<div class="about-head">
<h3>About the project</h3>
<a class="up" href="#projects" aria-label="Back to all Year {year} projects">{ICON['up']}</a>
</div>
{paras}
{skills}
</div>
<div class="gallery project-gallery" data-title="{esc(p['title'])}">
<script type="application/json" class="gallery-data">{data_json}</script>
<div class="stage-wrap">
<div class="stage"><img src="{data[0]['m']}" alt="{esc(data[0]['alt'])}" width="{w}" height="{h}" loading="lazy"></div>
<button class="fs-btn" type="button" aria-label="View fullscreen">{ICON['full']}</button>
</div>
{controls}
{thumbs}
</div>
</div>
</section>""")

        body = f"""{head}
<section class="wrap" aria-label="Year {year} projects">
<ul class="tiles" id="projects">
{chr(10).join(tiles)}
</ul>
</section>
{chr(10).join(sections)}"""
        viewer = f"""<div class="viewer" id="viewer" role="dialog" aria-modal="true" aria-label="Fullscreen picture" hidden>
<div class="viewer-bar">
<p class="viewer-info"></p>
<button class="viewer-close" type="button" aria-label="Close fullscreen">{ICON['close']}</button>
</div>
<div class="viewer-main">
<button class="arrow" type="button" data-viewer-prev aria-label="Previous picture">{ICON['prev']}</button>
<div class="viewer-img"><img alt=""></div>
<button class="arrow" type="button" data-viewer-next aria-label="Next picture">{ICON['next']}</button>
</div>
</div>
<script src="{root}assets/gallery.js?v={self.v}" defer></script>"""
        footer = '<a href="#projects">↑ Back to all projects</a>'
        self.write(f"year-{year}", self.layout(root, f"year-{year}", f"Year {year} · {course} — {self.s['name']}",
                                               body, footer, viewer))

    # ---- home page
    def home_page(self, by_year):
        root = ""
        cards = []
        for y in YEARS:
            course = self.s.get(f"year {y}", "")
            img = ""
            if by_year[y]:
                img = f'<img src="{self.rel(root, by_year[y][0]["items"][0]["files"]["m"])}" alt="" loading="lazy">'
            cards.append(f'<li><a class="year-card" href="{self.href(root, "year-" + y)}">{img}'
                         f'<strong>Year {y}</strong><span>{esc(course)}</span></a></li>')
        sub = self.s.get("subtitle", "")
        body = f"""<section class="wrap page-head">
{f'<p class="eyebrow">{esc(sub)}</p>' if sub else ''}
<h1 class="home-title">{esc(self.s['name'])}</h1>
</section>
<section class="wrap" aria-label="Year groups">
<ul class="year-cards">
{chr(10).join(cards)}
</ul>
</section>"""
        self.write("", self.layout(root, "", f"{self.s['name']} — Student work", body))

    # ---- about page
    def about_page(self):
        root = "../"
        path = ROOT / "about.txt"
        paras = read_paragraphs(read_text(path)) if path.exists() else []
        if not paras:
            paras = ["This page is coming soon."]
        text = "\n".join(f"<p>{esc(x)}</p>" for x in paras)
        body = f"""<section class="wrap page-head">
<h1 class="page-title">About</h1>
</section>
<section class="wrap"><div class="prose">
{text}
</div></section>"""
        self.write("about", self.layout(root, "about", f"About — {self.s['name']}", body))

    # ---- page not found
    def not_found(self):
        # GitHub shows this page for any address that doesn't exist; absolute links so it works anywhere
        body = """<section class="wrap page-head">
<h1 class="page-title">Not found</h1>
</section>
<section class="wrap"><div class="prose"><p>This page doesn't exist. <a href="/">Go to the home page</a>.</p></div></section>"""
        content = self.layout("/", None, f"Page not found — {self.s['name']}", body)
        (self.out / "404.html").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- main

def report_and_stop():
    print("\nThe site was NOT updated. Please fix these problems:\n")
    for e in errors:
        print("  ✗ " + e)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::{e}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## The site was not updated\n\nPlease fix these problems, then the site will update by itself:\n\n")
            for e in errors:
                f.write(f"- {e}\n")
            f.write("\nThe previous version of the site is still online.\n")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "_site"))
    ap.add_argument("--explicit-index", action="store_true", help="link to index.html files (for previews)")
    args = ap.parse_args()
    out = Path(args.out)

    settings = read_settings()
    by_year = {y: read_projects(y) for y in YEARS}
    if errors:
        report_and_stop()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for y in YEARS:
        for p in by_year[y]:
            process_photos(p, out)
    if errors:
        report_and_stop()

    # assets
    shutil.copytree(ENGINE / "assets", out / "assets")
    h = hashlib.sha1()
    for f in sorted((ENGINE / "assets").rglob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    pages = Pages(settings, out, args.explicit_index, h.hexdigest()[:8])

    pages.home_page(by_year)
    for y in YEARS:
        pages.year_page(y, by_year[y])
    pages.about_page()
    pages.not_found()
    initial = esc((settings["name"].strip()[:1] or "S").upper())
    (out / "favicon.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
        f'fill="{settings["accent colour"]}"/><text x="32" y="46" text-anchor="middle" '
        f'font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="40" '
        f'fill="{theme_on_accent(settings["accent colour"])}">{initial}</text></svg>', encoding="utf-8")

    total = sum(len(v) for v in by_year.values())
    photos = sum(len(p["items"]) for v in by_year.values() for p in v)
    print(f"Site built: {total} projects, {photos} photos.")
    for y in YEARS:
        for p in by_year[y]:
            print(f"  Year {y}: {p['title']} ({len(p['items'])} photos)")
    for n in notes:
        print("  Note: " + n)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::notice::{n}")


if __name__ == "__main__":
    main()
