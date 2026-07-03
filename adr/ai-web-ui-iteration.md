# AI-Assisted Web UI Iteration: Tools, Patterns, and Recommendations

> State of the ecosystem as of March 2026, tailored to this repository.

## The Core Problem

Claude Code (and similar AI coding assistants) fails at CSS/layout/interactivity work because it
operates blind. It reads source code, infers intent, proposes changes, and has no way to verify
what actually renders. Multiple iteration cycles often make things worse: each failed attempt adds
complexity (calc() → ResizeObserver → useEffect), and the AI accumulates bad context that frames
the next attempt poorly.

The community diagnosis, documented across HN threads, DEV Community posts, and practitioner blogs
through 2025-2026, is consistent: **AI doesn't fail because it isn't smart enough; it fails because
it can't see what you see.** The fix is giving it eyes.

---

## Tool Categories

### 1. MCP Servers for Browser Access

**Microsoft Playwright MCP** — current community consensus pick

```sh
claude mcp add playwright npx @playwright/mcp@latest
```

- 25 tools: navigation, screenshots, DOM/accessibility snapshots, console messages, network
  monitoring, click/type/drag, test generation
- Uses the browser accessibility tree rather than pixel-based screenshots, giving the model
  structured data to reason about (roles, labels, bounding positions)
- Cross-browser (Chrome, Firefox, WebKit); actively maintained by Microsoft
- Token cost warning: full-page DOM snapshots can exceed ~26,000 tokens. Scope snapshots to the
  specific component being debugged via `browser_evaluate` + querySelector

**Chrome DevTools MCP** — best for computed-style debugging

```sh
# Google's official offering, public preview September 2025
# github.com/ChromeDevTools/chrome-devtools-mcp
```

- Full Chrome DevTools Protocol: computed CSS, DOM inspection, JS console, network, performance
  traces, viewport emulation
- Works with Claude Code, Cursor, Copilot, and Gemini
- Best when the issue involves specificity wars, inherited styles, or layout overflow — it can
  read `getComputedStyle()` on the actual rendered element
- Apache 2.0 license

**Browser MCP** (`browsermcp.io`) — Chrome extension + MCP bridge

- Runs inside your existing authenticated Chrome session
- Useful for pages that require login without managing headless session state

**Deprecated:** `@modelcontextprotocol/server-puppeteer` (Anthropic's original MCP package) was
archived in 2025. Do not use it.

---

### 2. CLI Tools

**`claude --chrome`** — direct Claude.ai Chrome extension integration

- Run `claude --chrome` with the Claude browser extension installed
- Enables: screenshot capture, click/scroll, viewport resize, GIF recording
- Works with hot reload; auth-gated pages work since you are already logged in
- Limitation: cannot refresh the browser tab; requires a running dev server

**Vercel Labs `agent-browser`** — headless browser as a bash-callable CLI

```sh
# Install the binary (pick one)
npm install -g agent-browser && agent-browser install
brew install agent-browser && agent-browser install
cargo install agent-browser && agent-browser install  # builds from source

# Add the Claude Code skill to this project
npx skills add vercel-labs/agent-browser
```

This installs the skill at `.claude/skills/agent-browser/SKILL.md`, which teaches Claude the
full command vocabulary without requiring `--help` lookups.

**How it differs from Playwright MCP:**

- Not an MCP server — Claude invokes it as a bash tool. No `claude mcp add` config needed.
- Written in Rust; ships a self-contained binary with bundled Chrome (downloaded from Google's
  Chrome for Testing channel on first install). No Node.js required at runtime.
- Commands are composable CLI calls: `agent-browser snapshot`, `agent-browser click @e2`, etc.
- Works in any environment where bash tools are available, including CI

**Key features:**

- `agent-browser snapshot -i --json` — outputs the accessibility tree with element refs (`@e1`,
  `@e2`, ...). The recommended pattern for AI interaction: snapshot → identify ref → act → re-snapshot.
- `agent-browser screenshot --annotate` — overlays numbered labels on interactive elements,
  one label per ref. Lets Claude reason about visual layout and click unlabeled elements by
  their visible position.
- `agent-browser get text @e1`, `agent-browser click @e2` — deterministic interaction using
  refs rather than brittle CSS selectors.
- Full coverage: fill, type, hover, scroll, keyboard input, clipboard, network interception,
  HAR recording, cookie/storage management, device emulation, geolocation, WebSocket streaming,
  tab/window control, batch JSON piping.

**Recommended workflow for this repo:**

```
# In Claude Code:
# 1. Start dev server: mise run dev
# 2. Navigate and snapshot
agent-browser navigate http://localhost:8000/search
agent-browser snapshot -i --json

# 3. Interact using refs from snapshot output
agent-browser fill @e3 "search term"
agent-browser screenshot --annotate

# 4. After code changes, re-snapshot to verify fix
agent-browser snapshot -i --json
```

**Limitations:**
- Requires Chrome (auto-installed)
- Not useful for pages requiring an existing authenticated browser session (use Browser MCP
  extension for that); `agent-browser` manages its own isolated Chrome instance

---

### 3. Python/Agent-Context Tools

**`browser-use`** (78k+ GitHub stars as of 2026)

- The dominant Python library for AI agents interacting with browsers
- Connects Python AI agents directly to a browser session
- Relevant if this project ever adds agentic features that need browser automation
- Not directly applicable for Claude Code sessions, but worth knowing

**Stagehand v3** (Browserbase) — production browser agent infrastructure

- Self-healing automation: adapts when DOM changes rather than breaking
- Drops Playwright dependency in v3, uses CDP directly
- Better for deploying browser automation in production than for local dev iteration

---

### 4. Screenshot Feedback Loops

The workflow that practitioners report actually works:

1. Start dev server with hot reload (`mise run dev`)
2. Ask Claude to navigate to the running app and take an initial snapshot **before** writing code
3. Claude makes a targeted change
4. Claude takes another snapshot and compares
5. Claude identifies remaining issues and iterates
6. Repeat until the rendered result matches the desired state

Key implementation detail: prefer `browser_snapshot` (accessibility tree) over raw screenshots when
possible. It is faster, cheaper (no image token cost), and gives the model structural information
that pixel images don't — element roles, labels, and positions.

When pixel-level visual inspection is needed (e.g., spacing feels off, borders are misaligned),
screenshots via Playwright MCP work. The accessibility tree snapshot cannot reveal that a margin is
2px too wide.

---

### 5. Visual Regression Testing

**Playwright built-in** — lowest friction for this project

- `page.screenshot()` with `expect(page).toHaveScreenshot()` pixel-diffing
- Free, no external service, already in the project's test stack
- Captures baseline on first run, diffs on subsequent runs
- Useful as a CI gate against unintended visual regressions

**ZeroStep** — natural language assertions for Playwright

```ts
await ai('Assert that the editor toolbar is visible above the preview pane', { page, test })
```

- Fills the gap where traditional assertions cannot express visual intent
- Helpful for testing HTMX-driven layout changes

**Applitools Eyes** — AI-powered visual diff (commercial)

- Ignores irrelevant differences (anti-aliasing, dynamic timestamps), focuses on real regressions
- Better suited if this project ever needs cross-browser visual CI
- Overkill for current scope

---

## Community Discussion (2025-2026)

**The CSS loop problem is widely documented.** A representative DEV Community post describes a
three-day struggle where Claude kept proposing increasingly complex fixes (calc() → ResizeObserver
→ multi-page useEffect) for a simple centering issue solvable with `position: fixed` + flex. The AI
confidently announced "Now I see the problem!" each time while making things worse.

**HN consensus** from "Ask HN: Top AI vibe coding tools of 2025" and the "Vibe Coding Creates
Fatigue" thread: vibe coding (Andrej Karpathy's term, popularized mid-2025) works well for backend
logic and API wiring, poorly for layout nuance.

**Karsten Biedermann's Medium post** "CSS and vibe coding: Why good frontend devs still matter"
argues AI can suggest utility combinations but has no taste — it cannot feel what a human feels
when something "looks off."

**LinkedIn thread** from 2025: "The AI coding tools really struggle with CSS, they need a design
system." Constraining the AI to a finite CSS vocabulary (Tailwind, utility classes) reduces
hallucinated values.

---

## Common Hacks and Workarounds

**Give the AI eyes before asking it to fix anything.** Set up Playwright MCP or Chrome DevTools MCP
so it can inspect computed styles rather than guessing from source. This is the highest-leverage
single change.

**Reduce snapshot scope.** Full-page DOM snapshots hit token limits. Strip to the relevant
component:

```js
// Have Claude run this via browser_evaluate before snapshotting
document.querySelector('.search__sidebar').outerHTML
```

**Reset and reframe when looping.** When the AI is escalating complexity, kill the conversation and
start fresh. Paste a screenshot with annotated arrows pointing to the specific problem. Say
explicitly: "The previous approach failed. Use a completely different approach. Propose only the
simplest possible change and explain why it will work before implementing."

**The simplicity heuristic.** If the proposed CSS fix spans more than 10 lines, it is almost
certainly wrong. The correct fix is usually 3–5 lines. Push back: "That's too complex. Try a
simpler approach."

**The cascade audit.** When AI is stuck, ask it to write out the full CSS cascade for the specific
element (all rules, ordered by specificity) before proposing a fix. This forces reasoning about the
actual problem rather than pattern-matching to a solution.

**Use `!important` as a diagnostic, not a fix.** Temporarily add it to isolate which styles are
being overridden by specificity, then fix the specificity properly.

**Batch visual feedback.** Collect all visual issues, paste a screenshot with annotations, and ask
for all fixes in one prompt. Reduces context resets and compound errors.

**Document your design system.** AI performs significantly better when it knows which CSS framework
is in use, component file locations, spacing conventions, and color tokens. Without this, it
invents values.

---

## Recommendations for This Repository

### Stack Context

This project uses Starlette + Jinja2 for server-side rendering, HTMX for interactivity, and BEM
CSS. Playwright is already in the test stack (`mise run test:e2e`). Assets are intentionally kept
under 14KB. The relevant templates are in `yak_shears/_templates/` and static files in
`yak_shears/static/`.

### Immediate Setup

**Option A — Playwright MCP (recommended)**

```sh
claude mcp add playwright npx @playwright/mcp@latest
```

Then start every UI fix session with:

```
Navigate to http://localhost:8000, take a browser snapshot of the [specific component],
identify layout issues, then make targeted changes. After each change, take a new snapshot
and verify the fix before moving on.
```

The Playwright MCP integrates naturally with the existing `mise run dev` server. Since the project
already has Playwright for e2e tests, the mental model is consistent.

**Option B — Chrome DevTools MCP**

Better when the issue involves computed styles or inherited CSS that is hard to trace from source:

```sh
# Install from github.com/ChromeDevTools/chrome-devtools-mcp
```

Use `browser_evaluate` to call `window.getComputedStyle(element)` on the specific broken element
rather than asking Claude to guess from source CSS.

**Option C — `claude --chrome`**

Lowest setup cost if the Claude browser extension is already installed. Best for quick visual
checks without MCP configuration overhead.

### Per-Component Guidance

**Search page (`/search`) — sidebar/preview layout**

The 40/60 split and modal behavior on mobile (`≤768px`) are prime candidates for layout iteration
failures. The modal z-index, overflow, and scroll-to-match behavior are all interaction patterns
that are invisible to source-only analysis.

Recommended approach:
1. Use Playwright MCP to capture the search page at both 375px (iPhone 14) and 1280px viewports
2. Interact with it (type in search box, select a result) to trigger HTMX-driven updates
3. Check `browser_console_messages` — most HTMX interactivity failures are JS exceptions, not CSS

**Yak editor (`/edit`) — CodeJar + toolbar + view mode toggles**

The three-mode toggle (Editor-only, Side-by-side, Preview-only) and mobile keyboard extension
buttons are complex interaction states. Screenshot-based iteration is essential here because the
behavior is state-dependent.

Recommended approach:
1. Navigate to a yak, screenshot in each of the three modes
2. Resize viewport to mobile dimensions and screenshot toolbar behavior
3. For CodeJar-specific issues, use `browser_evaluate` to inspect the editor DOM directly

**HTMX interactions generally**

Use `mcp__playwright__browser_console_messages` to capture errors before asking Claude to fix
interactivity. HTMX logs failed requests to the console with useful detail. Source-only analysis
of HTMX bugs is unreliable.

### AGENTS.md Additions to Consider

```markdown
## Web UI Iteration

When fixing layout or interactivity issues:

1. Start with `mise run dev` to run the dev server
2. Use Playwright MCP (`claude mcp add playwright npx @playwright/mcp@latest`) to capture
   live screenshots before writing any code
3. Check `browser_console_messages` first for HTMX/JS errors before inspecting CSS
4. Scope DOM snapshots to the specific component — full-page snapshots hit token limits
5. For computed-style issues (specificity, inheritance), use `browser_evaluate` with
   `getComputedStyle()` rather than reading source CSS
6. Prefer the simplest possible CSS fix (3-5 lines); push back if proposed fix exceeds 10 lines
7. Test at both 375px (mobile) and 1280px (desktop) viewports — responsive behavior is
   invisible from source

BEM CSS conventions: `.block__element--modifier`. Keep changes scoped to the relevant component.
```

### Existing Playwright Tests as a Foundation

The project already has `mise run test:e2e`. This is underused for UI iteration. Consider:

- Adding `--screenshot` assertions to existing e2e tests as visual baselines
- Using `toHaveScreenshot()` for the search layout and editor mode toggles
- Treating test failures as the authoritative signal that a visual fix worked, rather than
  asking Claude to verify by inspection

This closes the loop: Claude makes a change, runs `mise run test:e2e`, and gets a binary
pass/fail signal with screenshot diffs rather than relying on its own visual judgment.

---

## Decision Summary

| Situation | Tool |
|-----------|------|
| Starting a new UI fix session | Playwright MCP — navigate + snapshot before writing code |
| CSS specificity / inheritance mystery | Chrome DevTools MCP — `getComputedStyle()` via `browser_evaluate` |
| Auth-gated page or existing session | `claude --chrome` or Browser MCP extension |
| HTMX interactivity failure | `browser_console_messages` first, then inspect DOM |
| CI visual regression gate | Playwright built-in `toHaveScreenshot()` |
| AI stuck in complexity loop | New conversation + annotated screenshot + simplicity constraint |
| Mobile layout (375px) testing | Playwright MCP viewport resize before any responsive CSS change |

---

## Sources

- [Using Playwright MCP with Claude Code — Simon Willison](https://til.simonwillison.net/claude-code/playwright-mcp-claude-code)
- [GitHub: microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)
- [How to Use Playwright MCP Server with Claude Code — builder.io](https://www.builder.io/blog/playwright-mcp-server-claude-code)
- [Chrome DevTools MCP — Chrome for Developers](https://developer.chrome.com/blog/chrome-devtools-mcp)
- [Give your AI eyes: Introducing Chrome DevTools MCP — Addy Osmani](https://addyosmani.com/blog/devtools-mcp/)
- [Visual Feedback Loop — Agentic Coding Handbook (Tweag)](https://tweag.github.io/agentic-coding-handbook/WORKFLOW_VISUAL_FEEDBACK/)
- [A Visual Feedback Loop for Electron Apps with Claude Code — juri.dev](https://juri.dev/articles/visual-feedback-loop-electron-apps-claude-code/)
- [The Eyes Have It: Closing the Agentic Design Loop — DEV Community](https://dev.to/ashmortar/the-eyes-have-it-closing-the-agentic-design-loop-3819)
- [Debugging CSS with Claude Code — gouthamve.dev](https://www.gouthamve.dev/debugging-css-with-claude-code/)
- [When AI Gets Stuck in a Loop: A CSS Nightmare — DEV Community](https://dev.to/info_vertex/when-ai-gets-stuck-in-a-loop-a-css-nightmare-and-lessons-learned-3mn6)
- [GitHub: vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
- [GitHub: browser-use/browser-use](https://github.com/browser-use/browser-use)
- [CSS and vibe coding: Why good frontend devs still matter — Karsten Biedermann](https://medium.com/@karstenbiedermann/css-and-vibe-coding-why-good-frontend-devs-still-matter-in-the-age-of-ai-09797a7f1287)
- [Ask HN: Top AI Vibe coding tools of 2025](https://news.ycombinator.com/item?id=43708538)
- [Vibe coding creates fatigue? — Hacker News](https://news.ycombinator.com/item?id=46292365)
- [Making Claude Code into an autonomous frontend dev — upvalue.io](https://upvalue.io/posts/claude-code-as-a-frontend-developer/)
- [Stagehand v3 — Browserbase](https://www.browserbase.com/blog/stagehand-v3)
- [AI Visual Testing Tools — BrowserStack](https://www.browserstack.com/guide/ai-visual-testing-tools)
