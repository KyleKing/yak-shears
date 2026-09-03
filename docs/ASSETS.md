# Asset Budget

What ships to the browser, what it costs, and what it would take to make it cost less.
`tests/test_assets.py` holds the only enforced number. Everything below the first
section is unbuilt work, kept here so the reasoning survives.

## Where the numbers come from

DESIGN.md used to claim a 14KB asset budget and a 90% CSS rule coverage gate in the
e2e suite. Neither was real. No coverage test existed, and the budget was never met by
any measure: `htmx.min.js` alone is 16.3KB gzipped. Both claims entered in `80ce219`,
the commit that recorded the design system, so they were aspirations written as fact
and read as fact for months afterward.

Measured 2026-07-27, gzipped:

| asset | size |
| --- | --- |
| `css/main.css` | 20.1KB |
| `js/htmx.min.js` | 16.2KB (vendored) |
| `js/editor.js` | 10.8KB |
| `js/search.js` | 2.7KB |
| `js/codejar.min.js` | 2.6KB (vendored) |
| `js/highlight.js` | 1.5KB |
| `js/nav.js` | 0.8KB |
| everything static | 53.3KB |

`main.css` is the one asset that blocks first paint on every route, which is why it is
the one under test. 14KB is the interesting figure for exactly that reason: it is
roughly the first TCP congestion window, so it is what arrives in the first round
trip. As a cap on *all* assets it never meant anything.

## The enforced number

`tests/test_assets.py` fails when `main.css` exceeds **22KB gzipped**. It is 21.3KB
today, roughly 700 bytes under the ceiling, so the next stylesheet of any size breaks
the build. Raise the constant deliberately, in its own commit, with a reason.

## Over the wire

**Cloudflare is the edge, not Caddy.** The zone is proxied (orange cloud), so
Cloudflare terminates TLS, caches, and picks the response encoding. Origin headers
carry `via: 1.1 Caddy` behind `server: cloudflare`. DEPLOYMENT.md's setup section
recommends "DNS only" for first provisioning and treats proxying as the later option;
production took the later option, and any measurement that ignores that is measuring
the wrong hop. Cache-bust with a junk query parameter (`?cb=…`) when testing, or you
will measure a `cf-cache-status: HIT` from before your change.

Compression levels still matter at origin, because Cloudflare fetches through them.
Caddy's stock zstd is level 3, which on this file is worse than its own gzip:

| zstd level | size | | gzip level | size |
| --- | --- | --- | --- | --- |
| 3 (Caddy default) | 22.1KB | | 9 | 20.0KB |
| 7 (`better`) | 19.9KB | | | |
| 11 (`best`) | 19.2KB | | | |
| 19 | 18.4KB | | | |

The Caddyfile now sets `zstd best` and `gzip 9` explicitly. Measured browser-facing
result on a cache miss: **19.9KB**, down from 22.0KB.

Offline `brotli -q 11` on the same file is **16.9KB**, so precompressed assets are
worth about 3KB over anything produced on the fly. That needs a build step, which is
the whole question below.

## Getting to 14KB

Reaching 14KB gzipped means cutting roughly 30% of the hand-written CSS. In rough
order of value per unit of risk:

1. **Precompress at high quality** (−3.0KB, to ~16.9KB). Brotli `-q 11` at build time,
   served with `file_server precompressed br gzip`. No CSS changes, no design risk.
   Requires a build step and a `.br` artifact per asset.
2. **Split the editor off the critical path** (−2.0KB on non-editor routes). Editor,
   preview, toolbar, metadata, and action-bar rules are 7.8KB raw, about 10% of the
   file. Smaller than it feels, because the shared base (tokens, materials, buttons,
   forms, nav, header) dominates. Costs a second `<link>` on `/edit` or a build step.
3. **Retire the legacy alias token layer** (unmeasured, likely 1–2KB). `main.css`
   carries a full set of `--color-*` aliases pointing at the material tokens, with a
   comment noting "2600 lines and three JS files read these names". Migrating
   components to the material names and deleting the aliases touches every component
   and all three JS files. Highest risk here by a wide margin.
4. **Delete genuinely dead rules** (unknown). Blocked on real coverage data; see
   below. The dead `.yaks-head__title` font-size found in `903e830` is proof there is
   something to find, and proof that finding it by hand does not scale.

Steps 1 and 2 both want a build step, which ADR 0001 explicitly rejected Tailwind
over: "requires a build process, makes HTML less semantic". That ADR was about a CSS
framework, not about compression, so a build step confined to minify-and-precompress
does not contradict it. It does contradict the spirit of "there is no build step to
tree-shake", so it deserves its own ADR rather than arriving as a side effect of a
size cleanup.

**Recommendation:** do not chase 14KB. It is a ~30% refactor of the design system's
implementation across five surfaces, for a single-user app, to save ~6KB on a
render-blocking asset that is already cached immutably after first paint. Step 1 is
the only one that pays for itself, and only alongside a production build worth having
for other reasons.

## Production build, if it happens

Minimum useful shape, in dependency order:

- Minify `main.css` (strip comments and whitespace). The file carries a lot of
  rationale in comments; those are worth keeping in source and worth dropping from the
  wire. Expect a large raw-size win and a modest gzipped one, since gzip already
  handles repetitive prose well.
- Precompress to `.br` and `.gz`, serve with `file_server precompressed br gzip`.
- Keep `static_url`'s content hashing as the cache-busting mechanism; it already works
  and does not need the build step.
- Do **not** add a CSS framework or a class-generating step. ADR 0001 stands.

## Unfinished: a CSS coverage gate

DESIGN.md claimed one existed. Building it properly hit a real obstacle worth
recording, because the obvious implementation looks like it works and does not.

Chrome DevTools Protocol's `CSS.stopRuleUsageTracking` returns **only the rules that
were used**, not every rule with a used flag. So `used / reported` is 100% by
construction and the assertion can never fail. A gate that cannot fail is worse than
no gate, so none shipped.

A real one needs:

- A denominator parsed from the stylesheet itself, excluding comments and whitespace,
  since a comment can never be "used" and this file is heavily commented. Dividing by
  raw file length reports ~27%, which measures prose, not dead CSS.
- Tracking restarted per navigation. Rule usage resets on document change, so a single
  start/stop around several `goto` calls only ever measures the last page.
- A matrix, not a route list: every route including `/edit` and the login page, both
  color schemes, mobile and desktop viewports, and interaction states. Hover, focus,
  and `prefers-color-scheme: dark` rules are dead to a naive desktop crawl and would
  be deleted by anyone trusting the number.

Until that exists, the 22KB budget is the only automated defense, and dead rules are
found by hand.
