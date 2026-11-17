#!/usr/bin/env python3
"""
Builds the website into the _site folder.

It reads:
  settings.txt               name, year labels, colours and the contact form key
  home.txt                   the paragraph on the Home page
  about.txt                  the title and text of the About page
  photo.jpg (or .png/.heic)  your photo for the About page
  year-7/, year-8/, year-9/  one folder per project, each with project.txt and photos

It checks every project first. If something is missing, it lists the problems
and stops, so the site that is already online stays as it is.

You never need to run this yourself: GitHub runs it every time you change something.
"""

import argparse
import hashlib
import html
import io
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

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
PROJECT_KEYS = {"title", "keyword", "skills", "subject", "school year"}
IMAGE_VERSION = "v1"   # change to force all photos to be converted again

# Sizes made from every photo (longest side, in pixels)
SIZES = {"f": 2000, "m": 1200, "t": 400}
SQUARE = 600           # square thumbnail for the project tile

FONT_DIR = ENGINE / "og-fonts"
DEFAULTS = {
    "name": "",
    "site address": "",
    "home title": "Student Work",
    "subjects": "Art · Design · Computing",
    "year 7": "", "year 8": "", "year 9": "",
    "year 7 colour": "#FF5A36",
    "year 8 colour": "#FF7D34",
    "year 9 colour": "#FFB536",
    "main colour": "#FF5A36",
    "background colour": "#111111",
    "text colour": "#F5F3EE",
    "contact form key": "",
}
COLOUR_KEYS = ["year 7 colour", "year 8 colour", "year 9 colour", "main colour", "background colour", "text colour"]

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
    s = dict(DEFAULTS)
    if not path.exists():
        problem("settings.txt", "the file is missing.")
        return s
    for line in read_text(path).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"\s+", " ", key.strip().lower().replace("color", "colour"))
        if key == "accent colour":          # older name for the main colour
            key = "main colour"
        s[key] = value.strip()
    if not s["name"]:
        problem("settings.txt", "the 'name:' line is empty.")
    for key in COLOUR_KEYS:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", s[key]):
            problem("settings.txt", f"'{key}' must be a colour code like #FF5A36 (it is '{s[key]}').")
            s[key] = DEFAULTS[key]
    addr = s["site address"].strip().rstrip("/")
    if not addr and os.environ.get("GITHUB_REPOSITORY_OWNER"):
        addr = f"https://{os.environ['GITHUB_REPOSITORY_OWNER'].lower()}.github.io"
    if addr and not addr.startswith("http"):
        addr = "https://" + addr
    s["site address"] = addr
    if not s["home title"].strip():
        s["home title"] = DEFAULTS["home title"]
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


def read_labelled(path, keys):
    """Reads 'label: value' lines at the top of a file, then the paragraphs."""
    fields, body, in_body = {}, [], False
    for line in read_text(path).split("\n"):
        m = re.match(r"^\s*([A-Za-z ]+?)\s*:\s*(.*)$", line)
        if not in_body and m and m.group(1).strip().lower() in keys:
            fields[m.group(1).strip().lower()] = m.group(2).strip()
            continue
        if line.strip():
            in_body = True
        body.append(line)
    return fields, read_paragraphs("\n".join(body))


# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(s, quote=True)


def typeset(s):
    """Escapes text and keeps one-letter words ('I', 'a') and numbers on the same line as the next word."""
    s = re.sub(r"(?<![\w'’])([A-Za-z]|\d+) (?=\S)", "\\1\u00A0", s)
    return esc(s)


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


def on_colour(c):
    return "#111111" if contrast(c, "#111111") >= contrast(c, "#FFFFFF") else "#FFFFFF"


def theme_css(s, accent):
    bg, text = s["background colour"], s["text colour"]
    v = {
        "--bg": bg,
        "--text": text,
        "--accent": accent,
        "--on-accent": on_colour(accent),
        "--panel": mix(bg, text, 0.06),
        "--panel-2": mix(bg, text, 0.09),
        "--line": mix(bg, text, 0.17),
        "--line-soft": mix(bg, text, 0.10),
        "--muted": mix(bg, text, 0.70),
        "--soft": mix(bg, text, 0.84),
        "--muted-2": mix(bg, text, 0.40),
        # the photo is brightened behind the keyword, so these are darker to keep the same look
        "--tile-dark": "#171717",
        "--tile-dark-touch": "#2E2E2E",
    }
    scheme = "dark" if luminance(bg) < 0.4 else "light"
    return ":root{" + ";".join(f"{k}:{val}" for k, val in v.items()) + f";color-scheme:{scheme}}}"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def subjects_sentence(subjects):
    parts = [p.strip() for p in re.split(r"[·,|/]", subjects) if p.strip()]
    if len(parts) <= 1:
        return subjects.strip()
    return ", ".join(parts[:-1]) + " and " + parts[-1]


# ---------------------------------------------------------------- fonts (for measuring and preview cards)

_fonts = {}


def font(weight, size):
    key = (weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_DIR / f"Archivo-{weight}.ttf"), size)
    return _fonts[key]


def em_width(text, weight=900, tracking=-0.03):
    """Width of upper-case text in 'em' units (as on the site, with its letter spacing)."""
    t = text.upper()
    return font(weight, 1000).getlength(t) / 1000 + tracking * len(t)


def keyword_size(words):
    # shrink long keywords so they always fit inside the square tile
    n = max(len(w) for w in words)
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


def make_versions(src, out_dir, stem, kinds, square=False):
    """Makes web versions of one photo (cached, so unchanged photos are quick)."""
    data = src.read_bytes()
    digest = hashlib.sha1(data).hexdigest()
    kinds = dict(kinds)
    if square:
        kinds["sq"] = SQUARE
    out, todo = {}, {}
    for kind in kinds:
        cached = CACHE / f"{digest}-{kind}-{IMAGE_VERSION}.webp"
        out[kind] = cached
        if not cached.exists():
            todo[kind] = cached
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
    first = "m" if "m" in result else next(iter(result))
    with Image.open(result[first]) as m:
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
        fields, paras = read_labelled(txt, PROJECT_KEYS)
        title = fields.get("title", "")
        keyword = fields.get("keyword", "").strip()
        words = keyword.split()
        if not title:
            problem(where + "/project.txt", "the 'title:' line is missing or empty.")
        if not keyword:
            problem(where + "/project.txt", "the 'keyword:' line is missing or empty.")
        elif len(words) > 2:
            problem(where + "/project.txt", f"the keyword can be one or two words (it is '{keyword}').")
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
            "title": title, "keyword_words": words, "paras": paras, "skills": skills,
            "subject": fields.get("subject", "").strip(),
            "school_year": fields.get("school year", ""), "photos": photos,
        })
    projects.sort(key=lambda p: (-p["number"], natural_key(p["folder"].name)))
    return projects


def process_photos(project, out_root):
    out_dir = out_root / "media" / f"year-{project['year']}" / project["slug"]
    items = []
    for k, f in enumerate(project["photos"], start=1):
        try:
            files, dims = make_versions(f, out_dir, f"{k:02d}", SIZES, square=(k == 1))
        except Exception as e:  # unreadable or damaged file
            problem(f"{project['where']}/{f.name}", f"this photo could not be opened ({e.__class__.__name__}).")
            continue
        items.append({"files": files, "dims": dims})
    project["items"] = items


def find_photo():
    for f in sorted(ROOT.iterdir()):
        if f.is_file() and f.stem.lower() == "photo" and f.suffix.lower() in PHOTO_EXT:
            return f
    return None


# ---------------------------------------------------------------- preview cards (link previews)

OG_W, OG_H, OG_PAD = 1200, 630, 64


def draw_tracked(draw, xy, text, fnt, fill, tracking_em):
    """Draws text with letter spacing (Pillow has none built in)."""
    x, y = xy
    size = fnt.size
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="ls")
        x += fnt.getlength(ch) + tracking_em * size
    return x


def tracked_width(text, fnt, tracking_em):
    return sum(fnt.getlength(ch) for ch in text) + tracking_em * fnt.size * len(text)


def fit_size(text, weight, max_w, cap, tracking_em):
    w1000 = tracked_width(text, font(weight, 1000), tracking_em)
    return max(10, min(cap, int(max_w * 1000 / max(1, w1000))))


def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    return mask


def preview_card(s, accent, covers, kind, year=None, course=""):
    """Draws a 1200×630 link-preview image: text on the left, up to 4 square covers on the right."""
    bg, text_col = hex_rgb(s["background colour"]), hex_rgb(s["text colour"])
    acc = hex_rgb(accent)
    im = Image.new("RGB", (OG_W, OG_H), bg)
    d = ImageDraw.Draw(im)
    grid_w = OG_H - 2 * OG_PAD                    # 502: a square block of 2 × 2 tiles
    gap = 14
    tile = (grid_w - gap) // 2
    left_w = OG_W - 2 * OG_PAD - grid_w - 56

    # name, top left
    name = s["name"].upper()
    nf = font(900, fit_size(name + ".", 900, left_w, 26, 0.01))
    x = draw_tracked(d, (OG_PAD, OG_PAD + nf.size * 0.75), name, nf, text_col, 0.01)
    d.text((x, OG_PAD + nf.size * 0.75), ".", font=nf, fill=acc, anchor="ls")

    base = OG_H - OG_PAD
    if kind == "year":
        sub = s["subjects"].upper()
        sf = font(500, fit_size(sub, 500, left_w, 22, 0.0))
        draw_tracked(d, (OG_PAD, base), s["subjects"], sf, hex_rgb(mix(s["background colour"], s["text colour"], 0.84)), 0.0)
        big = f"YEAR {year}"
        bf = font(900, fit_size(big, 900, left_w, 128, -0.03))
        y_big = base - sf.size - 22
        draw_tracked(d, (OG_PAD, y_big), big, bf, text_col, -0.03)
        if course:
            cf = font(800, 24)
            draw_tracked(d, (OG_PAD, y_big - bf.size * 0.72 - 20), course.upper(), cf, acc, 0.12)
    else:
        words = s["home title"].upper().split()
        sub = s["subjects"].upper()
        sub_size = fit_size(sub, 900, left_w, 40, -0.03)
        big_size = min(fit_size(w, 900, left_w, 110, -0.03) for w in words)
        sf, bf = font(900, sub_size), font(900, big_size)
        draw_tracked(d, (OG_PAD, base), sub, sf, acc, -0.03)
        y = base - sf.size - 14
        for w in reversed(words):
            draw_tracked(d, (OG_PAD, y), w, bf, text_col, -0.03)
            y -= bf.size * 0.9

    # tiles, right
    gx = OG_W - OG_PAD - grid_w
    for i in range(4):
        tx = gx + (i % 2) * (tile + gap)
        ty = OG_PAD + (i // 2) * (tile + gap)
        if i < len(covers):
            with Image.open(covers[i]) as c:
                t = c.convert("RGB").resize((tile, tile), Image.LANCZOS)
            im.paste(t, (tx, ty), rounded(t, 16))
        else:
            d.rounded_rectangle((tx, ty, tx + tile - 1, ty + tile - 1), radius=16, fill=acc)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    return buf.getvalue()


# ---------------------------------------------------------------- HTML

ICON = {
    "prev": '<svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M11 18l-6-6 6-6"/></svg>',
    "next": '<svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>',
    "up": '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg>',
    "full": '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>',
    "close": '<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg>',
    "check": '<svg aria-hidden="true" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>',
}

CONTACT_TOPICS = ["A job opportunity", "A question about a project", "A collaboration", "Something else"]


class Pages:
    def __init__(self, settings, out, explicit_index, asset_version, demo_form):
        self.s = settings
        self.out = out
        self.explicit = explicit_index
        self.v = asset_version
        self.demo_form = demo_form

    def href(self, root, page):
        """page is '' for home or 'year-7' / 'about'."""
        if self.explicit:
            return f"{root}{page + '/' if page else ''}index.html"
        return f"{root}{page + '/' if page else ''}" or "./"

    def rel(self, root, path):
        return root + path.relative_to(self.out).as_posix()

    def absolute(self, path):
        rel = path.relative_to(self.out).as_posix()
        addr = self.s["site address"]
        return f"{addr}/{rel}" if addr else rel

    def page_url(self, page):
        addr = self.s["site address"]
        return f"{addr}/{page + '/' if page else ''}" if addr else ""

    def write_card(self, name, data):
        h = hashlib.sha1(data).hexdigest()[:10]
        path = self.out / "previews" / f"{name}-{h}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def layout(self, root, current, accent, title, description, card, body, footer_extra="", tail=""):
        s = self.s
        nav = [("", "Home"), ("year-7", "Year 7"), ("year-8", "Year 8"), ("year-9", "Year 9"), ("about", "About")]
        links = "\n".join(
            f'<a href="{self.href(root, p)}"{" aria-current=\"page\"" if p == current else ""}>{label}</a>'
            for p, label in nav)
        meta = [
            f'<meta name="description" content="{esc(description)}">',
            '<meta property="og:type" content="website">',
            f'<meta property="og:title" content="{esc(title)}">',
            f'<meta property="og:description" content="{esc(description)}">',
            f'<meta property="og:site_name" content="{esc(s["name"])}">',
            '<meta name="twitter:card" content="summary_large_image">',
        ]
        if current is not None and self.page_url(current):
            meta.append(f'<meta property="og:url" content="{esc(self.page_url(current))}">')
        if card is not None:
            meta += [
                f'<meta property="og:image" content="{esc(self.absolute(card))}">',
                f'<meta property="og:image:width" content="{OG_W}">',
                f'<meta property="og:image:height" content="{OG_H}">',
                f'<meta property="og:image:alt" content="{esc(s["name"])}: student work">',
            ]
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noimageindex">
<title>{esc(title)}</title>
{chr(10).join(meta)}
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/style.css?v={self.v}">
<style>{theme_css(s, accent)}</style>
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
        s = self.s
        accent = s[f"year {year} colour"]
        course = s.get(f"year {year}", "")
        covers = [p["items"][0]["files"]["sq"] for p in projects[:4]]
        card = self.write_card(f"year-{year}", preview_card(s, accent, covers, "year", year, course))
        title = f"Year {year}{' · ' + course if course else ''} — {s['name']}"
        description = (f"{plural(len(projects), 'student project')} in {subjects_sentence(s['subjects'])}."
                       if projects else f"Student work in {subjects_sentence(s['subjects'])}.")
        head = f"""<section class="wrap page-head">
{f'<p class="eyebrow">{esc(course)}</p>' if course else ''}
<h1 class="page-title">Year {year}</h1>
</section>"""
        if not projects:
            body = head + '\n<section class="wrap"><p class="empty">Projects coming soon.</p></section>'
            self.write(f"year-{year}", self.layout(root, f"year-{year}", accent, title, description, card, body))
            return

        tiles = []
        for k, p in enumerate(projects):
            sq = self.rel(root, p["items"][0]["files"]["sq"])
            loading = "eager" if k < 6 else "lazy"
            words = "".join(f"<span>{esc(w)}</span>" for w in p["keyword_words"])
            tiles.append(
                f'<li><a class="tile" href="#{p["slug"]}">'
                f'<img src="{sq}" alt="" width="{SQUARE}" height="{SQUARE}" loading="{loading}">'
                f'<span class="cut" style="--kw:{keyword_size(p["keyword_words"])}cqw" aria-hidden="true">{words}</span>'
                f'<span class="sr-only">{esc(p["title"])}</span></a></li>')

        sections = []
        for p in projects:
            n = len(p["items"])
            data = [{"m": self.rel(root, it["files"]["m"]), "f": self.rel(root, it["files"]["f"]),
                     "alt": f"Student work {i} of {n}: {p['title']}"} for i, it in enumerate(p["items"], start=1)]
            data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
            first = p["items"][0]
            w, h = first["dims"]
            paras = "\n".join(f"<p>{typeset(x)}</p>" for x in p["paras"])
            skills = ("<ul class=\"skills\">" + "".join(f"<li>{esc(x)}</li>" for x in p["skills"]) + "</ul>") if p["skills"] else ""
            subject = f'<p class="eyebrow project-subject">{esc(p["subject"])}</p>' if p["subject"] else ""
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
{subject}
<h2 class="project-title" id="{p['slug']}-title">{esc(p['title'])}</h2>
<div class="cols">
<div class="about-box">
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
        self.write(f"year-{year}", self.layout(root, f"year-{year}", accent, title, description, card,
                                               body, footer, viewer))

    # ---- home page
    def home_page(self, by_year, card):
        root = ""
        s = self.s
        words = s["home title"].split()
        big = min(98 / em_width(w) for w in words)
        sub = 98 / em_width(s["subjects"])
        title = "".join(
            f'<span class="ht-big" style="font-size:min({big:.2f}cqi,120px)">{esc(w)}</span>' for w in words)
        title += f'<span class="ht-sub" style="font-size:min({sub:.2f}cqi,44px)">{esc(s["subjects"])}</span>'
        path = ROOT / "home.txt"
        paras = read_paragraphs(read_text(path)) if path.exists() else []
        text = "\n".join(f"<p>{typeset(x)}</p>" for x in paras)
        rows = []
        for y in YEARS:
            colour = s[f"year {y} colour"]
            course = s.get(f"year {y}", "")
            if by_year[y]:
                img = (f'<img src="{self.rel(root, by_year[y][0]["items"][0]["files"]["m"])}" alt="" '
                       f'loading="eager">')
            else:
                img = '<span class="yr-soon">Coming soon</span>'
            rows.append(f"""<a class="yr" href="{self.href(root, 'year-' + y)}" style="--yc:{colour};--on-yc:{on_colour(colour)}">
<span class="yr-label"><span><strong>Year {y}</strong><small>{esc(course)}</small></span>{ICON['next']}</span>
<span class="yr-img">{img}</span>
</a>""")
        body = f"""<div class="wrap home">
<section class="home-intro">
<h1 class="home-title">{title}</h1>
{text}
<p class="home-cta">Choose a year group {ICON['next']}</p>
</section>
<nav class="home-years" aria-label="Year groups">
{chr(10).join(rows)}
</nav>
</div>"""
        page_title = f"{s['name']} · Student work"
        description = f"Projects in {subjects_sentence(s['subjects'])} from Years 7 to 9."
        self.write("", self.layout(root, "", s["main colour"], page_title, description, card, body))

    # ---- about page
    def about_page(self, card, photo):
        root = "../"
        s = self.s
        path = ROOT / "about.txt"
        fields, paras = read_labelled(path, {"title"}) if path.exists() else ({}, [])
        heading = fields.get("title") or f"About {s['name']}"
        if not paras:
            paras = ["This page is coming soon."]
        lead, rest = paras[0], paras[1:]
        text = f'<p class="lead">{typeset(lead)}</p>\n' + "\n".join(f"<p>{typeset(x)}</p>" for x in rest)
        if photo is not None:
            pic = f'<img src="{self.rel(root, photo["files"]["f"])}" alt="{esc(s["name"])}" width="{photo["dims"][0]}" height="{photo["dims"][1]}">'
        else:
            pic = '<span class="blob-empty">Photo coming soon</span>'
        key = s["contact form key"].strip()
        options = "".join(f"<option>{esc(t)}</option>" for t in CONTACT_TOPICS)
        if key or self.demo_form:
            form_attrs = f'data-key="{esc(key)}"' + (" data-demo" if self.demo_form else "")
            disabled, notice = "", ""
        else:
            form_attrs, disabled = "", " disabled"
            notice = '<p class="form-error" role="status">The contact form isn\'t set up yet.</p>'
        body = f"""<section class="wrap about-me">
<div class="me-text">
<p class="eyebrow">About me</p>
<h1 class="about-title">{esc(heading)}</h1>
{text}
</div>
<div class="me-photo">
<span class="blob-bg" aria-hidden="true"></span>
<span class="blob">{pic}</span>
</div>
</section>
<section class="wrap contact" id="contact" aria-labelledby="contact-title">
<div class="contact-grid">
<div class="contact-intro">
<p class="eyebrow">Contact</p>
<h2 class="contact-title" id="contact-title">Say hello</h2>
<p>Have a question about a project, or an opportunity you'd like to talk about? Send me a message and I'll reply by email.</p>
</div>
<div>
<form class="contact-form" id="contact-form" {form_attrs}>
<div class="pair">
<div class="field"><label for="c-name">Name</label><input id="c-name" name="name" type="text" autocomplete="name" required></div>
<div class="field"><label for="c-email">Email</label><input id="c-email" name="email" type="email" autocomplete="email" required></div>
</div>
<div class="field"><label for="c-topic">What is it about?</label>
<select id="c-topic" name="topic" required><option value="">Choose a subject</option>{options}</select></div>
<div class="field"><label for="c-message">Message</label><textarea id="c-message" name="message" rows="6" required></textarea></div>
<input type="checkbox" name="botcheck" class="botcheck" tabindex="-1" autocomplete="off" aria-hidden="true">
{notice}
<p class="form-error" id="contact-error" role="alert" hidden></p>
<div class="form-foot">
<p class="form-note">Your name and email are only used to reply to your message.</p>
<button class="send" type="submit"{disabled}><span>Send message</span>{ICON['next']}</button>
</div>
</form>
<div class="form-done" id="contact-done" tabindex="-1" hidden>
{ICON['check']}
<h3>Message sent</h3>
<p>Thank you for getting in touch. I'll reply to you by email soon.</p>
<button class="again" id="contact-again" type="button">Send another message</button>
</div>
</div>
</div>
</section>"""
        first = re.split(r"(?<=[.!?])\s", lead, maxsplit=1)[0]
        description = first if len(first) <= 160 else first[:157].rsplit(" ", 1)[0] + "…"
        tail = f'<script src="{root}assets/contact.js?v={self.v}" defer></script>'
        self.write("about", self.layout(root, "about", s["main colour"], f"About {s['name']}", description,
                                        card, body, tail=tail))

    # ---- page not found
    def not_found(self):
        # GitHub shows this page for any address that doesn't exist; absolute links so it works anywhere
        body = """<section class="wrap page-head">
<h1 class="page-title">Not found</h1>
</section>
<section class="wrap"><div class="prose"><p>This page doesn't exist. <a href="/">Go to the home page</a>.</p></div></section>"""
        content = self.layout("/", None, self.s["main colour"], f"Page not found — {self.s['name']}",
                              "This page doesn't exist.", None, body)
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
    ap.add_argument("--demo-form", action="store_true", help="contact form pretends to send (for previews)")
    args = ap.parse_args()
    out = Path(args.out)

    settings = read_settings()
    by_year = {y: read_projects(y) for y in YEARS}
    photo_src = find_photo()
    if errors:
        report_and_stop()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for y in YEARS:
        for p in by_year[y]:
            process_photos(p, out)
    photo = None
    if photo_src is not None:
        try:
            files, dims = make_versions(photo_src, out / "media" / "about", "photo", {"f": 1600})
            photo = {"files": files, "dims": dims}
        except Exception as e:
            problem(photo_src.name, f"your photo could not be opened ({e.__class__.__name__}).")
    if errors:
        report_and_stop()

    # assets
    shutil.copytree(ENGINE / "assets", out / "assets")
    h = hashlib.sha1()
    for f in sorted((ENGINE / "assets").rglob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    pages = Pages(settings, out, args.explicit_index, h.hexdigest()[:8], args.demo_form)

    # link-preview card for Home and About: newest project of each year, in turn
    mixed, depth = [], 0
    while len(mixed) < 4 and any(len(by_year[y]) > depth for y in YEARS):
        for y in YEARS:
            if len(by_year[y]) > depth and len(mixed) < 4:
                mixed.append(by_year[y][depth]["items"][0]["files"]["sq"])
        depth += 1
    main_card = pages.write_card("home", preview_card(settings, settings["main colour"], mixed, "home"))

    pages.home_page(by_year, main_card)
    for y in YEARS:
        pages.year_page(y, by_year[y])
    pages.about_page(main_card, photo)
    pages.not_found()
    initial = esc((settings["name"].strip()[:1] or "S").upper())
    (out / "favicon.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
        f'fill="{settings["main colour"]}"/><text x="32" y="46" text-anchor="middle" '
        f'font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="40" '
        f'fill="{on_colour(settings["main colour"])}">{initial}</text></svg>', encoding="utf-8")

    total = sum(len(v) for v in by_year.values())
    photos = sum(len(p["items"]) for v in by_year.values() for p in v)
    print(f"Site built: {total} projects, {photos} photos.")
    for y in YEARS:
        for p in by_year[y]:
            print(f"  Year {y}: {p['title']} ({len(p['items'])} photos)")
    if photo is None:
        print("  Note: no photo.jpg found, so the About page shows a placeholder.")
    for n in notes:
        print("  Note: " + n)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::notice::{n}")


if __name__ == "__main__":
    main()
