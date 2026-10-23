"""Post-build checks: internal links and anchors, duplicate ids, banned phrases, UK spellings (English pages).
Run from the repo root after `python build.py`:  python tools/check_site.py"""
import pathlib, re, sys
from html.parser import HTMLParser
DIST = pathlib.Path(__file__).resolve().parent.parent / "dist"
BANNED = ["AS9100", "ITAR", "oporabitelj", "Oporabitelj", "EU Taxonomy", "CSRD", "Airbus", "Embraer", "Petrobras",
          "85–95", "Heather", "foundingDate", "YOUR_FORM_ID", "HiTec", "Ultraflon", "certified compound"]
UK = ["fibre", "moulding", "moulded", "characteris", "programme", "authorised", "armour", "colour", "homogenis", "stabilis", "specialis(?!t)", "organis", "imidis", "optimis", "centre "]

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = []; self.links = []; self.text = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"): self.skip += 1
        if "id" in a: self.ids.append(a["id"])
        if tag == "a" and a.get("href"): self.links.append(a["href"])
        if tag in ("link", "img", "script", "source") and (a.get("href") or a.get("src")):
            u = a.get("href") or a.get("src")
            if u.startswith("/") and not u.startswith("//"): self.links.append(u)
    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.text.append(d)

pages = {}
for f in DIST.rglob("*.html"):
    p = P(); p.feed(f.read_text(encoding="utf-8"))
    rel = "/" + str(f.relative_to(DIST)).replace("index.html", "")
    pages[rel] = (p, f)
errors = []
for url, (p, f) in pages.items():
    dup = {i for i in p.ids if p.ids.count(i) > 1}
    if dup: errors.append(f"{url}: duplicate ids {sorted(dup)}")
    for href in p.links:
        if href.startswith(("http", "mailto:", "tel:")): continue
        path, _, frag = href.partition("#")
        if not path: target = url
        else:
            target = path if path.endswith("/") or "." in path.rsplit("/", 1)[-1] else path + "/"
        if path and "." in target.rsplit("/", 1)[-1]:
            if not (DIST / target.lstrip("/")).exists(): errors.append(f"{url}: missing file {href}")
            continue
        if target not in pages:
            if path.startswith("/api/"): continue
            errors.append(f"{url}: broken link {href}"); continue
        if frag and frag not in pages[target][0].ids:
            errors.append(f"{url}: missing anchor {href}")
    text = " ".join(p.text)
    for b in BANNED:
        if b in text: errors.append(f"{url}: banned phrase '{b}'")
    lang = re.search(r'<html lang="([^"]+)"', f.read_text(encoding="utf-8")).group(1)
    if lang == "en":
        for w in UK:
            for m in re.finditer(w, text, re.I):
                ctx = text[max(0, m.start()-30): m.end()+30].replace("\n", " ")
                errors.append(f"{url}: UK spelling '{w}': …{ctx}…")
print(f"Checked {len(pages)} pages")
print("\n".join(errors) if errors else "No problems found")
sys.exit(1 if errors else 0)
