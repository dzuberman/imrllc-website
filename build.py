#!/usr/bin/env python3
"""IRM website build.

Renders Markdown + YAML content in src/ into a static site in dist/.

    python build.py            # production build (drafts excluded)
    python build.py --drafts   # include draft pages (lab, proof) for preview only
    IRM_DRAFTS=1 python build.py   # same as --drafts (for preview deployments)

Requires: Jinja2, Markdown, PyYAML (see requirements.txt).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
CONTENT = SRC / "content"
TEMPLATES = SRC / "templates"
STATIC = SRC / "static"
DATA = SRC / "data"

FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Page:
    def __init__(self, lang: str, rel: Path, meta: dict, body_md: str):
        self.lang = lang
        self.rel = rel
        self.meta = meta
        self.body_md = body_md
        self.body_html = Markup("")
        self.toc = []
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "index":
            parts = parts[:-1]
        prefix = [] if lang == "en" else [lang]
        segs = prefix + parts
        self.url = "/" + "/".join(segs) + ("/" if segs else "")
        self.key = meta.get("key") or ("/" + "/".join(parts) + ("/" if parts else ""))

    def __getattr__(self, item):
        # convenient template access to front matter: page.title, page.description …
        meta = self.__dict__.get("meta", {})
        if item in meta:
            return meta[item]
        raise AttributeError(item)

    @property
    def draft(self) -> bool:
        return bool(self.meta.get("draft"))

    @property
    def template(self) -> str:
        return self.meta.get("template", "page") + ".html"


def wrap_tables(html_text: str) -> str:
    """Make every Markdown table horizontally scrollable and keyboard-focusable."""
    def repl(match):
        table = match.group(0)
        cap = re.search(r"<caption>(.*?)</caption>", table, re.S)
        label = re.sub(r"<[^>]+>", "", cap.group(1)).strip() if cap else "Table"
        return f'<div class="table-wrap" role="region" tabindex="0" aria-label="{html.escape(label)}">{table}</div>'
    return re.sub(r"<table>.*?</table>", repl, html_text, flags=re.S)


def render_markdown(text: str):
    md = markdown.Markdown(
        extensions=["tables", "attr_list", "md_in_html", "toc", "fenced_code", "sane_lists", "smarty", "abbr"],
        extension_configs={"toc": {"permalink": False, "toc_depth": "2"}, "smarty": {"smart_angled_quotes": False}},
        output_format="html",
    )
    out = md.convert(text)
    toc = [(t["id"], t["name"]) for t in getattr(md, "toc_tokens", [])]
    return Markup(wrap_tables(out)), toc


def fingerprint(src: Path, dest_dir: Path, url_dir: str) -> str:
    data = src.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:10]
    name = f"{src.stem}.{digest}{src.suffix}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_bytes(data)
    return f"{url_dir}/{name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", action="store_true", help="include draft pages (never for production)")
    ap.add_argument("--out", default=str(DIST))
    args = ap.parse_args()
    include_drafts = args.drafts or os.environ.get("IRM_DRAFTS") == "1"
    out = Path(args.out)

    site = load_yaml(DATA / "site.yaml")
    site["build_date"] = dt.date.today().isoformat()
    site["year"] = dt.date.today().year
    nav = load_yaml(DATA / "nav.yaml")
    materials = load_yaml(DATA / "materials.yaml")
    faq = load_yaml(DATA / "faq.yaml")
    network = load_yaml(DATA / "network.yaml")
    i18n = {p.stem: load_yaml(p) for p in sorted((DATA / "i18n").glob("*.yaml"))}
    langs = [l["code"] for l in site["languages"]]
    lang_meta = {l["code"]: l for l in site["languages"]}

    # ── clean output ────────────────────────────────────────────────
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # ── static assets ───────────────────────────────────────────────
    assets = {}
    for sub in ("fonts", "img"):
        if (STATIC / sub).exists():
            shutil.copytree(STATIC / sub, out / "assets" / sub)
    assets["css/site.css"] = fingerprint(STATIC / "css" / "site.css", out / "assets" / "css", "/assets/css")
    assets["js/site.js"] = fingerprint(STATIC / "js" / "site.js", out / "assets" / "js", "/assets/js")
    for f in ("favicon.ico",):
        if (STATIC / f).exists():
            shutil.copy2(STATIC / f, out / f)

    def asset(path: str) -> str:
        return assets.get(path, "/assets/" + path)

    # ── content ─────────────────────────────────────────────────────
    pages: list[Page] = []
    for lang in langs:
        base = CONTENT / lang
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            raw = path.read_text(encoding="utf-8")
            m = FRONT_MATTER.match(raw)
            meta, body = (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, raw)
            page = Page(lang, path.relative_to(base), meta, body)
            if page.draft and not include_drafts:
                continue
            pages.append(page)

    by_url = {p.url: p for p in pages}
    by_key: dict[str, dict[str, Page]] = {}
    for p in pages:
        by_key.setdefault(p.key, {})[p.lang] = p

    def url_for(key: str, lang: str = "en") -> str:
        """URL of the page with this key in this language, falling back to English."""
        variants = by_key.get(key, {})
        page = variants.get(lang) or variants.get("en")
        if page is None:
            raise KeyError(f"No page with key {key!r}")
        return page.url

    def alternates(page: Page):
        variants = by_key.get(page.key, {})
        return [(lang_meta[l]["hreflang"], variants[l].url) for l in langs if l in variants]

    def library_articles():
        arts = [p for p in pages if p.lang == "en" and p.url.startswith("/library/") and p.url != "/library/"]
        return sorted(arts, key=lambda p: (p.meta.get("order", 99), p.meta.get("title", "")))

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    def md_inline(text: str) -> Markup:
        html_out, _ = render_markdown(text or "")
        html_out = str(html_out).strip()
        if html_out.startswith("<p>") and html_out.endswith("</p>") and html_out.count("<p>") == 1:
            html_out = html_out[3:-4]
        return Markup(html_out)

    def md_block(text: str) -> Markup:
        return render_markdown(text or "")[0]

    def jsonld(obj) -> Markup:
        s = json.dumps(obj, ensure_ascii=False, indent=1, default=str)
        s = s.replace("</", "<\\/")
        return Markup(s)

    env.filters["md"] = md_inline
    env.filters["mdblock"] = md_block
    env.filters["jsonld"] = jsonld
    env.globals.update(
        site=site, nav=nav, materials=materials, faq=faq, network=network,
        i18n=i18n, langs=langs, lang_meta=lang_meta, asset=asset, url_for=url_for,
        by_key=by_key, library_articles=library_articles, include_drafts=include_drafts,
    )

    # Render Markdown bodies first so templates can use them.
    for p in pages:
        p.body_html, p.toc = render_markdown(p.body_md)

    sitemap_entries = []
    for p in pages:
        tmpl = env.get_template(p.template)
        t = i18n.get(p.lang, i18n["en"])
        html_out = tmpl.render(page=p, t=t, lang=p.lang, alternates=alternates(p))
        dest = out / p.url.lstrip("/") / "index.html" if p.url != "/" else out / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html_out, encoding="utf-8")
        if not p.draft and not p.meta.get("noindex"):
            sitemap_entries.append(p)

    # ── 404 ─────────────────────────────────────────────────────────
    t404 = env.get_template("404.html")
    (out / "404.html").write_text(t404.render(t=i18n["en"], lang="en", alternates=[]), encoding="utf-8")

    # ── sitemap.xml ─────────────────────────────────────────────────
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for p in sorted(sitemap_entries, key=lambda x: x.url):
        lines.append("  <url>")
        lines.append(f"    <loc>{site['base_url']}{p.url}</loc>")
        lastmod = p.meta.get("updated") or site["build_date"]
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        alts = alternates(p)
        if len(alts) > 1:
            for hl, u in alts:
                lines.append(f'    <xhtml:link rel="alternate" hreflang="{hl}" href="{site["base_url"]}{u}"/>')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{site["base_url"]}{url_for(p.key, "en")}"/>')
        lines.append("  </url>")
    lines.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── robots.txt ──────────────────────────────────────────────────
    (out / "robots.txt").write_text(
        "# IRM LLC — robots.txt\n"
        "# All crawlers, including AI search and assistant crawlers, are welcome.\n"
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n\n"
        f"Sitemap: {site['base_url']}/sitemap.xml\n",
        encoding="utf-8",
    )

    # ── _headers (Cloudflare Pages) ─────────────────────────────────
    (out / "_headers").write_text(
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()\n"
        "  X-Frame-Options: SAMEORIGIN\n"
        "  Strict-Transport-Security: max-age=31536000; includeSubDomains\n"
        "  Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self'; font-src 'self'; form-action 'self'; base-uri 'self'; frame-ancestors 'self'\n"
        "/assets/css/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        "/assets/js/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        "/assets/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        "/assets/img/*\n  Cache-Control: public, max-age=2592000\n",
        encoding="utf-8",
    )

    # ── _redirects (Cloudflare Pages) ───────────────────────────────
    redirects = load_yaml(DATA / "redirects.yaml").get("redirects", []) if (DATA / "redirects.yaml").exists() else []
    lines = []
    for r in redirects:
        sources = [r["from"]] if r["from"].endswith("/") else [r["from"], r["from"] + "/"]
        lines += [f"{s} {r['to']} {r.get('status', 301)}\n" for s in sources]
    (out / "_redirects").write_text("".join(lines), encoding="utf-8")

    # ── web manifest ────────────────────────────────────────────────
    (out / "site.webmanifest").write_text(json.dumps({
        "name": site["name"], "short_name": site["brand"], "start_url": "/", "display": "browser",
        "background_color": "#08090a", "theme_color": "#08090a",
        "icons": [{"src": "/assets/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/img/icon-512.png", "sizes": "512x512", "type": "image/png"}],
    }, indent=1), encoding="utf-8")

    n_draft = sum(1 for p in pages if p.draft)
    print(f"Built {len(pages)} pages ({n_draft} drafts) into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
