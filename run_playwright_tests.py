"""Standalone Playwright tests without pytest integration."""

import asyncio
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import async_playwright


@asynccontextmanager
async def server_lifecycle():
    """Context manager to start and stop the server."""
    # Start the server in the background
    process = subprocess.Popen(
        ["uv", "run", "serve", "--no-auth", "--reload", "--host", "localhost", "--port", "8080"],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(2)

    try:
        yield "http://localhost:8080"
    finally:
        # Clean up server process
        process.terminate()
        process.wait()


async def test_server_starts_and_serves_homepage(page):
    """Test that the server starts and serves the homepage."""
    async with server_lifecycle() as base_url:
        await page.goto(base_url)
        title = await page.title()
        assert title == "Notes in ./Sync/yak-shears"
        print("✓ Server starts and serves homepage")


async def test_login_page_loads(page):
    """Test that the login page loads correctly."""
    async with server_lifecycle() as base_url:
        await page.goto(f"{base_url}/auth/login")
        content = await page.content()
        assert "Login" in content
        print("✓ Login page loads correctly")


async def test_files_page_loads(page):
    """Test that the files page loads correctly."""
    async with server_lifecycle() as base_url:
        await page.goto(f"{base_url}/files")
        content = await page.content()
        assert "Notes" in content
        print("✓ Files page loads correctly")


async def main():
    """Run all Playwright tests."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            await test_server_starts_and_serves_homepage(page)
            await test_login_page_loads(page)
            await test_files_page_loads(page)
            print("\nAll tests passed! 🎉")
        except Exception as e:
            print(f"\nTest failed: {e}")
            sys.exit(1)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
