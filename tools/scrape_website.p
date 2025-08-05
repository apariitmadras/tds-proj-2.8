# tools/scrape_website.py
# Playwright-based scraper. Saves page HTML to a file.
# Usable as a module (import) and as a CLI script: 
#   python -m tools.scrape_website --url https://example.com --out outputs/scraped.html

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Any

from playwright.async_api import async_playwright


async def scrape_website(
    url: str,
    output_file: str = "outputs/scraped_content.html",
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 60_000,
    extra_wait_ms: int = 0,
) -> Dict[str, Any]:
    """
    Scrape a URL with headless Chromium and save HTML to output_file.
    Returns a small JSON-serializable dict: {"ok": bool, "file": str, "url": str}
    """
    launch_args = ["--no-sandbox", "--disable-setuid-sandbox"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if extra_wait_ms > 0:
                await page.wait_for_timeout(extra_wait_ms)
            html = await page.content()
            out = Path(output_file)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            return {"ok": True, "file": str(out), "url": url}
        finally:
            await browser.close()


def scrape_website_sync(
    url: str,
    output_file: str = "outputs/scraped_content.html",
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 60_000,
    extra_wait_ms: int = 0,
) -> Dict[str, Any]:
    """Synchronous wrapper around `scrape_website` for quick scripts."""
    return asyncio.run(
        scrape_website(url, output_file, wait_until, timeout_ms, extra_wait_ms)
    )


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Scrape a URL and save HTML.")
    parser.add_argument("--url", required=True, help="Page URL to scrape")
    parser.add_argument("--out", default="outputs/scraped_content.html", help="Output HTML file path")
    parser.add_argument("--wait-until", default="domcontentloaded", choices=["load", "domcontentloaded", "networkidle"])
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    parser.add_argument("--extra-wait-ms", type=int, default=0, help="Optional extra wait after navigation")
    args = parser.parse_args()

    result = scrape_website_sync(
        url=args.url,
        output_file=args.out,
        wait_until=args.wait_until,
        timeout_ms=args.timeout_ms,
        extra_wait_ms=args.extra_wait_ms,
    )
    print(json.dumps(result, ensure_ascii=False))
