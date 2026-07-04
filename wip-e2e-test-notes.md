# E2E Test Suite: Reliability Notes

**Date**: 2026-07-04

## Problem

The Playwright e2e suite (`tests/e2e/`) is flaky in this environment. Running it standalone frequently produces `pytest-timeout` (>10s) failures that don't reproduce as assertion failures, and the failures aren't consistent across runs. This was hit twice today while verifying an unrelated ruff lint cleanup: a clean, mechanical diff with 238/238 non-e2e tests passing still showed dozens of e2e timeouts, and rerunning against the pre-change baseline commit reproduced the same timeouts. That comparison is what confirmed the flakiness isn't caused by the code under test, but it took real effort to establish, and would need to be redone by hand for every future change unless something changes here.

Contributing factors observed:

- The `serve` fixture spawns a background server process per test session on a fixed local port. If a previous pytest process is killed abnormally (crash, manual `kill -9`, an agent/CI job cancelled mid-run), the server child isn't cleaned up and silently holds the port. The next run then hangs waiting to bind, with no clear error pointing at the real cause.
- `pytest-timeout = 10` (from `pyproject.toml`) is short relative to real headless Chromium startup cost observed locally (browser process spin-up alone took upwards of a minute in a loaded environment), so slow-but-healthy runs and genuinely stuck runs both present the same way: a timeout with a thread dump.
- No isolation between concurrent runs: two pytest processes (e.g. a human running tests locally while an agent verifies a worktree) contend for the same port and can't run side by side.

## Options considered

**Increase the timeout.** Cheap, but just hides the port-conflict failure mode longer instead of fixing it, and slows down genuine hang detection.

**Make the port dynamic per test session** (bind to port 0, read back the assigned port, pass it to the fixture and to Playwright's `base_url`). Removes the single biggest source of cross-run interference and enables concurrent runs. This is probably the highest-leverage fix relative to effort.

**Add a pre-test cleanup step** that kills any stale process still holding the expected port before starting a new server. A safety net rather than a fix — worth having in addition to dynamic ports, not instead of.

**Separate the timeout budget for browser startup vs. per-test execution**, e.g. a longer session-scoped timeout for the server/browser fixtures and a tighter one for the actual test body. Would make the thread dumps more informative (a fixture-stage timeout vs. a test-stage timeout are different problems) without just inflating the number.

**Run e2e in CI only, treat local e2e runs as best-effort.** No code change, but doesn't fix the actual reliability problem — CI has the same port/timeout mechanics if it ever runs jobs concurrently, and it doesn't help agents (or humans) trying to verify a change locally before pushing.

## Suggested next step

Start with dynamic ports for the `serve` fixture — it directly addresses the failure mode actually observed twice today and unblocks running e2e tests locally while something else (a dev server, another test run) is using the default port. Pair it with a short-lived best-effort cleanup of orphaned processes on the old fixed port, since existing local setups may still have one lingering.

Splitting the timeout budget is worth doing next but is lower urgency — it's a diagnostics improvement, not a reliability fix.
