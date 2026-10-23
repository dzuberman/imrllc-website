"""Render the default Open Graph image (src/static/img/og-default.png). Requires Playwright + Chromium.
Run from the repo root:  python tools/make_og.py [--chromium /path/to/chrome]"""
import asyncio, pathlib, sys
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
async def main():
    exe = sys.argv[sys.argv.index("--chromium") + 1] if "--chromium" in sys.argv else None
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto((ROOT / "tools" / "og.html").as_uri())
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(ROOT / "src" / "static" / "img" / "og-default.png"))
        await b.close()
asyncio.run(main())
