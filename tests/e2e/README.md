# Playwright E2E Testing

## Screenshot Capture

By default, tests do **not** capture screenshots to avoid test variability and unintended file modifications.

To capture screenshots for documentation:

```sh
CAPTURE_SCREENSHOTS=true mise run test:e2e
# or when running specific tests:
CAPTURE_SCREENSHOTS=true pytest tests/e2e/test_yaks.py
```

Screenshots are saved to `.github/screenshots/` and should only be updated intentionally.

## Resources

- [Pytest Fixtures Source Code](https://github.com/microsoft/playwright-pytest/blob/c1af305a0026b506919448d2d85ed51a20e5d37f/pytest-playwright-asyncio/pytest_playwright_asyncio/pytest_playwright.py)
- Python Docs
    - https://playwright.dev/python/docs/api/class-browsercontext
    - https://playwright.dev/python/docs/input (Actions)
    - https://playwright.dev/python/docs/debug#run-in-debug-mode (`PWDEBUG=1 mise run test:e2e:debug`)
    - https://playwright.dev/python/docs/navigations
    - https://playwright.dev/python/docs/test-assertions
    - And more guides on Aria snapshots, trace viewing, etc.
