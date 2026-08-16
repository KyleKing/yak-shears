# 0007: Observability Strategy — Logs, Metrics, and Alerting

## Status

Accepted (2026-08-16), for Option E below, which was assembled after the menu was written and takes the local-first half of Option A without the hand-rolled error grep, and none of Option C's SaaS telemetry. The options survive as the tradeoff record.

## Context

The app (ADR 0005) runs single-user on a Hetzner CPX11 (2 vCPU/2GB) behind Caddy and Cloudflare. When this was written the only log sink was journald: persistent across reboots (`/var/log/journal` exists, 11.9MB used as of the first deploy) but not backed up off the box and with no push notification of any kind. Hetzner's console already gives free CPU/network/disk graphs with no setup. `fail2ban` and `ufw` already handle the security-log side; this ADR is about the app's own errors and uptime.

Hard requirement: get notified when the app logs an error, or when it's unexpectedly down. Nice to have, roughly in this order of usefulness: CPU/memory visibility, searchable logs, backed-up logs, metrics, a cloud dashboard.

## Options considered

### Option 0: status quo (baseline, not a real option)

Nothing changes: `journalctl -f` over SSH when something feels off. Doesn't meet the hard requirement (nothing pushes a notification), so it's here only as the zero-cost baseline the other options are measured against.

### Option A: TUI + SSH + Termius, plus minimal push alerting

Termius is the SSH client (desktop and mobile) used to reach the box; it isn't itself a monitoring tool. Pair it with a TUI for ad hoc digging: `lnav` (structured journald/syslog viewer with SQL-style queries and error highlighting) or plain `journalctl -f`, and `htop`/`btop` for CPU/memory, both already available with no new install.

SSH/TUI access is pull-only, so it can't satisfy the hard requirement by itself — something has to push. Layer two small scripts on top:

- Uptime: a free Healthchecks.io account (20 checks on the free tier) as a dead-man's-switch. A cron job or systemd timer on the VPS pings a Healthchecks.io URL on an interval; if the ping doesn't arrive within the grace period, Healthchecks.io alerts (email, ntfy, Pushover, and others). Because the alert fires on silence rather than on a response, it still fires if the whole VPS goes unreachable, not just the app.
- Errors: a systemd timer that greps `journalctl --since <last run>` for `ERROR`/`CRITICAL` and `curl`s a one-line summary to ntfy.sh (free, no signup needed for the public instance, self-hostable, iOS/Android apps, as simple as `curl -d "message" ntfy.sh/your-topic`).

Cheapest and fewest new services of any option that actually satisfies the hard requirement, keeps everything on the box (no telemetry leaves), and matches how the VPS is already operated day to day. Costs: the alerting logic is hand-rolled and has to be written and maintained, log retention doesn't extend past journald's local disk budget, and there's no metrics history or dashboard beyond a live `htop` snapshot. Low effort.

### Option B: self-hosted stack (Grafana + Loki + Promtail + node_exporter, uptime hosted elsewhere)

Promtail ships journald into Loki; Grafana gives LogQL search and alerting on log patterns. `node_exporter` plus Prometheus (or Grafana Agent) gives CPU/memory history. Uptime monitoring (Uptime Kuma, for a status page and alerting) has to run somewhere other than the VPS being monitored, since a monitor that dies with its target can't alert on the target dying.

Full ownership and the most powerful option (real search, dashboards, retained history), but the heaviest: four or five more services competing for RAM on a 2GB box already running the app, Caddy, and Syncthing, plus the ongoing maintenance of running an observability stack. Log backup off the box is still a separate problem Loki doesn't solve by itself. High effort.

### Option C: cloud SaaS composition (Sentry + Healthchecks.io/UptimeRobot + optional log/metrics SaaS)

Sentry's free Developer plan (5,000 errors + 10,000 performance units/month, 30-day retention) plugs in via `sentry-sdk`'s Starlette/ASGI integration, a few lines at server startup. It captures exceptions with full stack traces, groups recurring issues instead of spamming one alert per occurrence, and emails/Slacks on new issues — real error tracking, not a grep script.

For uptime, Healthchecks.io (free: 20 checks, the dead-man's-switch model from Option A) or UptimeRobot (free: 50 monitors, 5-minute interval, HTTP/keyword checks, a more classic "hit the URL and see if it answers" checker) both work externally to the VPS.

For the searchable/backed-up-logs and metrics nice-to-haves, any of Grafana Cloud (free: 50GB Loki logs/month, 10k Prometheus series, Grafana Alerting, 14-day retention), Better Stack (free: ~3GB logs, 10 uptime monitors, 100k exceptions/month, uptime+logs+alerting in one product), or Axiom (free: 500GB ingest/month, 30-day retention) adds a real cloud dashboard with no new services to run.

Purpose-built tools with real error grouping, real alert routing, and mobile push, free tiers sized well past what a single-user app will produce, and near-zero maintenance since the SaaS vendor owns the uptime of the monitoring tool itself. The tradeoff is that error contents and stack traces (and possibly note titles that end up in a log line) leave the VPS to third parties, worth a moment's thought for a personal notes app even with reputable vendors, plus another set of accounts and API keys to manage. Low-to-medium effort — mostly account setup and SDK wiring.

### Option D: hybrid (recommended)

Combine the sharpest piece of Option A with the sharpest piece of Option C, and skip the rest of both:

- Healthchecks.io or UptimeRobot (free tier) for downtime alerting, external to the VPS, so it still fires in a total-outage scenario.
- Sentry (free tier) wired into the app for error alerting, turning "notified on logged errors" into real exception tracking instead of a grep script, at close to zero engineering cost given the Starlette integration already exists.
- Keep using Termius/SSH/`journalctl`/`lnav`/`htop` for ad hoc CPU, memory, and log digging once something fires. No new infrastructure for that; it's already how the box is operated.

This satisfies the hard requirement twice over through two independent, externally-hosted notification paths, and picks up part of "cloud app" and "metrics" for free through Sentry's issue dashboard and the uptime tool's status page, without committing to Option B's heavier stack before there's evidence it's needed. Low effort: SDK plus a DSN env var, an uptime account, and one `curl` in a timer, roughly 30-60 minutes of setup.

### Option E: journald over Syncthing, ntfy on deploys, uptime where it already lives (chosen)

Three pieces, none of them a new service to operate:

- A daily `export-logs.timer` reshapes `journalctl -o json` for `yak-shears`, `caddy`, and `gitops-update` into one file per finished day, written to `~/logs` on the VPS. That directory is a send-only Syncthing folder replicated to the laptop as receive-only with 90-day staggered versioning, so the VPS's 30-day prune frees disk there without erasing local history. Reading is `tail-jsonl` and `jq` against a local directory, no server round trip, and the records carry `timestamp`, `level`, `message`, and `unit` rather than journald's twenty metadata fields
- The deploy script pushes its outcome to an ntfy topic, so a failed start or a rollback reaches the phone. This is the alert that matters most in practice, because a bad deploy is the most likely way this app goes down
- Uptime rides the external monitor that already watches `kyleking.me`, with `yak-shears.kyleking.me` added as its own check. Off-box, so it survives a total outage, and it introduces no account that did not already exist

What it gives up against the recommended Option D is Sentry's exception grouping: a repeated 500 appears as N tracebacks in a day file rather than one issue with a count, and nothing pushes on the first occurrence. What it buys is that no note title, stack trace, or request path leaves the VPS for a third party, and there is no free-tier quota or vendor account in the loop. Logs land on a machine that is already trusted with the notes themselves.

## Comparison

| | Meets hard requirement | CPU/memory | Searchable logs | Backed-up logs | Metrics | Cloud dashboard | New services on the VPS | Cost |
|---|---|---|---|---|---|---|---|---|
| 0: status quo | No | ad hoc (`htop`) | journald only | No | No | No | 0 | $0 |
| A: TUI+SSH+Termius+DIY push | Yes, hand-rolled | ad hoc (`htop`/`btop`) | journald/`lnav` | No | No | No | 2 (uptime ping + error-grep timers) | $0 |
| B: self-hosted stack | Yes, if uptime runs off-box | Yes (Prometheus) | Yes (Loki) | Depends on shipping logs elsewhere | Yes | Yes (self-hosted Grafana) | 4-5 (Loki, Promtail, Prometheus, Grafana, Kuma) | $0 (VPS resources only) |
| C: cloud SaaS composition | Yes | Only with an add-on | Only with an add-on | Yes | Only with an add-on | Yes | 0 | $0 (free tiers) |
| D: hybrid (originally recommended) | Yes, twice over | ad hoc (`htop`/Termius) | journald + Sentry issues | Sentry only (errors) | Sentry issue trends only | Yes (Sentry + uptime tool) | ~1 (uptime ping timer) | $0 |
| E: journald over Syncthing (chosen) | Deploys yes, errors no | ad hoc (`htop`/Termius) | `tail-jsonl`/`jq` on the laptop | Yes, on every paired device | No | No | 1 (daily export timer) | $0 |

## Decision

Option E. Option D's advantage over it is Sentry, and Sentry is the one piece that sends note-adjacent data off the box for a benefit (error grouping) that a single-user app with roughly one exception a week does not yet need. Everything Option D gets from Sentry's dashboard, a day file and `jq` also get, a few hours later.

The deliberate gap is push-on-error. Deploy failures push, downtime pushes, and a 500 does not. Close it when a 500 goes unnoticed long enough to matter, either with Sentry as Option D describes or with the Option A error-grep timer against the same journal the export already reads.

## Consequences

- `export-logs.timer` runs daily at 00:20 and writes `~/logs/YYYY-MM-DD.jsonl` on the VPS, pruning past 30 days. `journal-to-jsonl.py` owns the record shape, including the fact that everything the app prints arrives at syslog severity 6, so its `ERROR:`/`WARNING:` prefixes are what actually set the level
- The log folder sits at `~/logs`, outside `~/Sync`, because Syncthing refuses to nest one folder inside another and `~/Sync` is already shared whole
- The laptop copy is receive-only with 90-day staggered versioning, so the VPS prune reclaims disk on the server while the local archive keeps its own retention
- Logs replicate to the laptop only. The iPhone shares `~/Sync` but is deliberately not on the log folder
- The ntfy topic lives in `/etc/yak-shears/deploy.env`, out of git, the same way the SSH key is
- `fail2ban` and `journalctl` remain the tool for security-incident forensics, and nothing here replaces them
- Revisit Option B if historical CPU and memory graphs are wanted, or Option D's Sentry half if unnoticed 500s become the problem
