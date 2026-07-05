# 0005: Hosting Stack — Hetzner VPS, Caddy, Syncthing, systemd GitOps

## Status

Accepted (2026-07); supersedes the Traefik/FileBrowser experiments in `archive/hosting-new.md`

## Context

The app is single-user and file-first: the note vault syncs between devices via Syncthing, and the web app is one more Syncthing peer that also serves HTTP. Earlier hosting iterations tried Traefik (heavier config, DNS-challenge env plumbing) and FileBrowser (redundant once the app itself edits files).

## Decision

- Hetzner CX22 VPS (cost, hcloud/Terraform support), provisioned by `cloud-config.yaml` cloud-init
- Caddy as reverse proxy with automatic Let's Encrypt (replaced Traefik)
- Syncthing syncs the note vault; the search/metadata DB must live outside the synced folder
- The app runs as a systemd unit under a non-root user via `uv run serve`
- Deployment is GitOps-style: a systemd timer polls the git remote and restarts the service on new commits (no Docker, no CI deploy pipeline)

## Rationale

Caddy's config is a fraction of Traefik's for one vhost and handles ACME with zero extra credentials. cloud-init keeps the whole server reproducible from one file in the repo. Polling GitOps is crude but sufficient for a single-user app where a few minutes of deploy latency is fine.

## Consequences

- Everything the server needs must be in `cloud-config.yaml` (packages: ffmpeg, ripgrep when the search backend lands; correct branch name; correct proxy port)
- `IN_TLS_CONTEXT=TRUE` must be set in the unit so session cookies are `Secure` behind the proxy
- No rollback mechanism beyond `git revert` and waiting for the timer
- Known open items: ufw rules may reset on boot; VPS config drift should be snapshotted into version control (PLAN.md Phase 1)
