# irmllc.co

Source for the IRM LLC website. A small Python build (`build.py`) turns Markdown pages and YAML data into a static site in `dist/`, which Cloudflare Pages serves. One Pages Function (`functions/api/inquiry.js`) sends the contact form to Zoho CRM as a Lead.

## Build and preview locally

```bash
pip install -r requirements.txt
python build.py                 # production build → dist/
python build.py --drafts        # also builds draft pages (Laboratory, Proof) for preview
python -m http.server 8000 --directory dist
python tools/check_site.py      # links, anchors, duplicate ids, banned claims, UK spellings
```

`check_site.py` must report "No problems found" before anything is published.

## Where things live

| Path | What it holds |
| --- | --- |
| `src/content/en/*.md` | English pages. The file path is the URL: `peek-recycling.md` → `/peek-recycling/`, `library/peek-scrap-value.md` → `/library/peek-scrap-value/`. |
| `src/content/{de,fr,it,es,pt,zh,ja,ko}/` | Localized pages (home and Sell scrap). They are served under `/de/`, `/fr/` … and linked to their English counterpart with hreflang. |
| `src/data/site.yaml` | Company name, addresses, email, phone, social links, form endpoint, languages. Empty values (phone, WhatsApp, LinkedIn) are hidden on the site. |
| `src/data/nav.yaml` | Header menus and footer columns. |
| `src/data/materials.yaml` | The materials data reference (`/materials/`). Every row needs a source link to the datasheet it came from. |
| `src/data/faq.yaml` | FAQ questions. The FAQ page and its FAQPage structured data are generated from this one file. |
| `src/data/network.yaml` | Sites and offices on `/global-network/`. |
| `src/data/redirects.yaml` | Short URLs (`/sell`, `/psu-recycling` …) written to `dist/_redirects`. |
| `src/data/i18n/*.yaml` | Interface text (buttons, form labels, messages) per language. |
| `src/templates/` | Jinja2 templates. |
| `src/static/` | CSS, JS, self-hosted fonts (OFL, licenses included), icons and images. |
| `functions/api/inquiry.js` | Contact form → Zoho CRM. |
| `tools/` | Site checker and the Open Graph image generator. |

## Writing a page

Each page is Markdown with YAML front matter. The common fields:

```yaml
---
title: PEEK Scrap Recycling            # used for links and breadcrumbs
seo_title: PEEK Recycling USA — … | IRM # <title>; keep under ~60 characters
description: …                          # meta description; ~150 characters
h1: PEEK scrap recycling
lead: One or two sentences under the heading.
eyebrow: Polymer recycling
crumbs: [[Sell scrap, /sell-scrap/]]
facts_title: At a glance                # optional side panel
facts:
  - [Forms, "Swarf, rod ends, runners"]
related: [/library/peek-scrap-value/, /pei-ultem-recycling/]
published: 2026-10-23                   # library articles: date shown and used in structured data
updated: 2026-11-15                     # optional: set when an article is revised
draft: true                             # optional: only built with --drafts, never indexed
noindex: true                           # optional: built but kept out of search and the sitemap
---
```

Quote any YAML value that contains a comma, colon or `#`.

Library articles go in `src/content/en/library/` and appear on `/library/` automatically.

## Draft pages

`laboratory.md` and `proof.md` are marked `draft: true`. They contain placeholders (lab equipment, photos, case studies, figures) to fill in. Production builds skip them. To review them on a Cloudflare preview deployment, set `IRM_DRAFTS=1` for the **Preview** environment only. When a page is ready, fill the placeholders, remove `draft: true`, and add it to `nav.yaml` if it should appear in the menu.

## Deploying on Cloudflare Pages

The live site currently serves the old single `index.html` from the repository root. This version builds into `dist/` instead, so change the Pages settings **before** merging this branch into the production branch:

1. Cloudflare dashboard → Workers & Pages → the irmllc.co project → Settings → Build.
2. Build command: `pip install -r requirements.txt && python build.py`
3. Build output directory: `dist`
4. Environment variable (Production and Preview): `PYTHON_VERSION` = `3.12`
5. Preview environment only, if you want to see the drafts: `IRM_DRAFTS` = `1`
6. The `functions/` folder at the repository root is picked up automatically.

After the first deploy, check `https://irmllc.co/robots.txt`, `/sitemap.xml` and a deep page such as `/peek-recycling/`.

### Contact form → Zoho CRM

The form posts to `/api/inquiry`, which creates a Lead and uploads any attached photos to it. Until the secrets below are set, the form shows an error that points visitors to the email address.

1. Go to the Zoho API Console for your data center (https://api-console.zoho.com, or `.eu`, `.in` … — use the one that matches the address you sign in to CRM with) and create a **Self Client**.
2. Generate a code with the scopes `ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.attachments.CREATE`, then exchange it for a refresh token (Zoho's "Self Client" instructions show the one request needed).
3. In Pages → Settings → Variables and Secrets, add as **encrypted secrets**:
   - `ZOHO_CLIENT_ID`
   - `ZOHO_CLIENT_SECRET`
   - `ZOHO_REFRESH_TOKEN`
4. If your CRM is not on the US data center, also set `ZOHO_ACCOUNTS_URL` (e.g. `https://accounts.zoho.eu`) and `ZOHO_API_URL` (e.g. `https://www.zohoapis.eu`).
5. Optional:
   - `ZOHO_LEAD_SOURCE` — a value from the Leads "Lead Source" picklist, such as `Website` (add it to the picklist first if it is not there).
   - `ZOHO_OWNER_ID` — the Zoho user who should own new website leads.
   - `TURNSTILE_SECRET` plus `turnstile_site_key` in `site.yaml` — turns on Cloudflare Turnstile if spam gets through the built-in honeypot.
6. Send a test inquiry with a photo attached and confirm the Lead and attachment appear in CRM.

The Zoho org is on an Enterprise trial that ends on 5 November 2026; confirm API access on whichever edition you keep.

### Search engines

1. Google Search Console: add `irmllc.co` as a Domain property (DNS verification in Cloudflare), then submit `https://irmllc.co/sitemap.xml`.
2. Bing Webmaster Tools: import the property from Search Console.
3. Google Business Profile for the Sumter, SC plant (and South Jordan, UT if it receives visitors), using exactly the address shown on the site.

`robots.txt` allows all crawlers, including AI crawlers, and blocks only `/api/`.

## Content rules

- Technical values on the site come from published datasheets and carry a source link. If a value cannot be sourced, leave it out.
- No certification, registration or customer names unless the certificate or written permission is on file. `tools/check_site.py` flags the phrases that were removed.
- US spelling on English pages (fiber, color, center, -ize).
- Trade names belong to their owners; the footer disclaimer covers identification use.
