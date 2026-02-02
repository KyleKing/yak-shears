#!/usr/bin/env python3
"""Capture screenshots of the app for visual review."""

import asyncio
import logging
from pathlib import Path as SyncPath

from anyio import Path
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def capture_screenshots() -> None:
    """Capture screenshots of all major pages."""
    screenshots_dir_sync = SyncPath(".github/screenshots")
    screenshots_dir_sync.mkdir(parents=True, exist_ok=True)
    screenshots_dir = Path(".github/screenshots")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            storage_state=None,
        )
        page = await context.new_page()

        logger.info("📸 Starting screenshot capture...")

        # 1. Login page
        logger.info("  → Login page")
        await page.goto("http://localhost:8081/auth/login", wait_until="domcontentloaded")
        await page.wait_for_selector("input[name='email']")
        await page.screenshot(path=screenshots_dir / "1-login.png", full_page=True)

        # 2. Login page with error
        logger.info("  → Login page with error")
        await page.fill("input[name='email']", "wrong@example.com")
        await page.fill("input[name='password']", "wrongpass")
        await page.click("button[type='submit']")
        await page.wait_for_selector(".alert")
        await page.screenshot(path=screenshots_dir / "2-login-error.png", full_page=True)

        # 3. Login and get to yaks page
        logger.info("  → Logging in...")
        await page.goto("http://localhost:8081/auth/login", wait_until="domcontentloaded")
        await page.fill("input[name='email']", "test@example.com")
        await page.fill("input[name='password']", "secure123")
        await page.click("button[type='submit']")
        await page.wait_for_url("**/yaks")

        # 4. Yaks page
        logger.info("  → Yaks page (default view)")
        await page.screenshot(path=screenshots_dir / "3-yaks-default.png", full_page=True)

        # 5. Yaks page - sorted by name
        logger.info("  → Yaks page (sorted by name)")
        await page.click("a:has-text('Name')")
        await page.wait_for_url("**/yaks?sort_by=name")
        await page.screenshot(path=screenshots_dir / "4-yaks-sorted-name.png", full_page=True)

        # 6. Search page - empty state
        logger.info("  → Search page (empty state)")
        await page.goto("http://localhost:8081/search")
        await page.screenshot(path=screenshots_dir / "5-search-empty.png", full_page=True)

        # 7. Search page - with results
        logger.info("  → Search page (with results)")
        await page.fill("input[name='q']", "test")
        await page.press("input[name='q']", "Enter")
        await page.wait_for_timeout(500)
        await page.screenshot(path=screenshots_dir / "6-search-results.png", full_page=True)

        # 8. New yak page
        logger.info("  → New yak page")
        await page.goto("http://localhost:8081/new")
        await page.screenshot(path=screenshots_dir / "7-new-yak.png", full_page=True)

        # 9. Edit page - side by side view
        logger.info("  → Edit page (side-by-side)")
        await page.goto("http://localhost:8081/edit?yak=yak1.dj", wait_until="domcontentloaded")
        await page.wait_for_selector(".editor")
        await page.screenshot(path=screenshots_dir / "8-edit-sidebyside.png", full_page=True)

        # 10. Edit page - editor only
        logger.info("  → Edit page (editor only)")
        await page.click("button[data-view='editor']")
        await page.wait_for_timeout(300)
        await page.screenshot(path=screenshots_dir / "9-edit-editor.png", full_page=True)

        # 11. Edit page - preview only
        logger.info("  → Edit page (preview only)")
        await page.click("button[data-view='preview']")
        await page.wait_for_timeout(300)
        await page.screenshot(path=screenshots_dir / "10-edit-preview.png", full_page=True)

        # 12. Mobile viewport - yaks page
        logger.info("  → Mobile viewport - Yaks page")
        await page.set_viewport_size({"width": 375, "height": 667})
        await page.goto("http://localhost:8081/yaks")
        await page.screenshot(path=screenshots_dir / "11-mobile-yaks.png", full_page=True)

        # 13. Mobile viewport - edit page
        logger.info("  → Mobile viewport - Edit page")
        await page.goto("http://localhost:8081/edit?yak=yak1.dj", wait_until="domcontentloaded")
        await page.wait_for_selector(".editor")
        await page.screenshot(path=screenshots_dir / "12-mobile-edit.png", full_page=True)

        await browser.close()

        screenshot_files = [f async for f in screenshots_dir.glob("*.png")]
        logger.info(f"\n✅ Screenshots saved to {screenshots_dir}/")
        logger.info(f"   Total: {len(screenshot_files)} screenshots")


if __name__ == "__main__":
    asyncio.run(capture_screenshots())
