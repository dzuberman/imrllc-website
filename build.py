"""Cloudflare Pages build for the single-page site.

The Pages project is set up for the multi-page site on the `site-v4` branch:
    Build command:          pip install -r requirements.txt && python build.py
    Build output directory: dist
Until that branch is merged, this script copies the static files as they are
into dist/, so the current index.html deploys with those settings. When
site-v4 is merged, its own build.py and requirements.txt replace these files.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
SKIP = {"build.py", "requirements.txt", "README.md", "dist", "__pycache__", "node_modules"}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    copied = []
    for item in sorted(ROOT.iterdir()):
        if item.name.startswith(".") or item.name in SKIP:
            continue
        if item.is_dir():
            shutil.copytree(item, OUT / item.name)
        else:
            shutil.copy2(item, OUT / item.name)
        copied.append(item.name)
    if not (OUT / "index.html").is_file():
        raise SystemExit("build.py: index.html is missing from the repository root")
    print(f"Copied {len(copied)} items to dist/: {', '.join(copied)}")


if __name__ == "__main__":
    main()
