# 0007: Observability Strategy — Logs, Metrics, and Alerting

## Status

Proposed (2026-07-22). Unlike the other ADRs in this repo, this one lays out options rather than recording a single choice — the deployment owner asked for a menu with tradeoffs, including at least one TUI/SSH option and one or more cloud options, to pick from directly. A recommendation is given below; update Status to Accepted once a choice is made and note it in PLAN.md/STATUS.md.

## Context

The app (ADR 0005) runs single-user on a Hetzner CPX11 (2 vCPU/2GB) behind Caddy and Cloudflare. Today the only log sink is journald: persistent across reboots (`/var/log/journal` exists, 11.9MB used as of the first deploy) but not backed up off the box and with no push notification of any kind. Hetzner's console already gives free CPU/network/disk graphs with no setup. `fail2ban` and `ufw` already handle the security-log side; this ADR is about the app's own errors and uptime.

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

## Comparison

| | Meets hard requirement | CPU/memory | Searchable logs | Backed-up logs | Metrics | Cloud dashboard | New services on the VPS | Cost |
|---|---|---|---|---|---|---|---|---|
| 0: status quo | No | ad hoc (`htop`) | journald only | No | No | No | 0 | $0 |
| A: TUI+SSH+Termius+DIY push | Yes, hand-rolled | ad hoc (`htop`/`btop`) | journald/`lnav` | No | No | No | 2 (uptime ping + error-grep timers) | $0 |
| B: self-hosted stack | Yes, if uptime runs off-box | Yes (Prometheus) | Yes (Loki) | Depends on shipping logs elsewhere | Yes | Yes (self-hosted Grafana) | 4-5 (Loki, Promtail, Prometheus, Grafana, Kuma) | $0 (VPS resources only) |
| C: cloud SaaS composition | Yes | Only with an add-on | Only with an add-on | Yes | Only with an add-on | Yes | 0 | $0 (free tiers) |
| D: hybrid (recommended) | Yes, twice over | ad hoc (`htop`/Termius) | journald + Sentry issues | Sentry only (errors) | Sentry issue trends only | Yes (Sentry + uptime tool) | ~1 (uptime ping timer) | $0 |

## Recommendation

Option D. It's the only option that meets the hard requirement without either hand-rolling the alerting logic end to end (Option A alone) or taking on a multi-service stack on a 2GB box before there's a demonstrated need for it (Option B). The nice-to-haves it skips (full metrics history, backed-up application logs, a unified dashboard) are exactly the ones this app hasn't needed yet; picking them up later is an incremental add (e.g. layering Grafana Cloud's free tier on top) rather than a re-architecture.

## Consequences (if Option D is adopted)

- Add `sentry-sdk` as a dependency; the DSN must stay out of git, following the same pattern as the users-file secret (env var via `cloud-config.yaml`'s `write_files`, not committed).
- A new systemd timer (parallel to `gitops-update.timer`) pings the chosen uptime service on an interval; document it in `cloud-config.yaml` and `DEPLOYMENT.md` once added.
- `fail2ban`/`journalctl` remain the tool for security-incident forensics; nothing here replaces them.
- Revisit Option B if the free-tier error quota is outgrown, if there's a real want for historical CPU/memory graphs, or if self-hosting becomes a stated preference over SaaS telemetry.
- Still open, to decide at implementation time: Healthchecks.io vs UptimeRobot for uptime, and whether to add Grafana Cloud/Better Stack/Axiom now or wait.
