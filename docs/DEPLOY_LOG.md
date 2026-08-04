# Deploy Log: Hetzner (2026-07)

Running record of the first real deployment. [DEPLOYMENT.md](./DEPLOYMENT.md) is the generic guide; this file is what I actually did, in order, plus every issue hit along the way. Steps marked `[ ]` haven't been run yet.

## Pre-flight fixes (2026-07-04, committed but not yet pushed)

Blockers found by auditing `cloud-config.yaml` against the current branch. None of these would have surfaced until the VPS was already broken:

- Added `ffmpeg` to the package list (media upload shells out to it for video transcode and poster frames)
- GitOps script polled `origin/main`, but the default branch is `yak-shears-py`, so auto-update would never have fired once
- The systemd unit bound `:8080` (the `serve` default) while Caddy proxied `localhost:8084`; the unit now passes `--port 8084`
- The search DB defaulted into `$YAK_SHEARS_DIR`, which Syncthing syncs and would corrupt; the unit now passes `--search-db-dir /home/yakshears/.local/state/yak-shears` (with an `ExecStartPre` mkdir, since the app doesn't create the directory)
- Added `Environment=IN_TLS_CONTEXT=TRUE` so the session cookie is marked `Secure` behind Caddy
- Ubuntu 22.10+ socket-activates sshd, and `ssh.socket` owns the listen port, so `Port 2222` in sshd_config could be silently ignored; the runcmd now disables `ssh.socket` and runs `ssh.service` traditionally
- Removed mise from the VPS entirely. `.config/mise.toml` pins npm tools (biome, dprint, terser) that need node, so `mise install` would fail on the server and abort every GitOps update. uv provisions its own managed CPython during `uv sync`, so the server only needs uv
- `gitops-update.sh` runs as `yakshears` but called bare `systemctl restart`; now uses `sudo` (the user has NOPASSWD sudo)
- Vendored `htmx.min.js` and `codejar.min.js` into git. They were built locally by `mise run download-assets` (which needs node/tsc/terser) and never committed, so a fresh clone would have served a broken UI
- `UserStore._save` now chmods `.yak-shears-users.json` to 0600. Also verified the file was never committed (it is gitignored; `git log --all` on it is empty), so the history-purge item in PLAN.md was stale

## Step 1: dedicated SSH key `[x]`

One key per purpose; this one only unlocks the VPS.

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_yak_shears -C "yak-shears-hetzner"
```

Then add a host block to `~/.ssh/config` (fill in the IP after Step 4):

```
Host yak-shears
    HostName <vps-ip>
    Port 2222
    User yakshears
    IdentityFile ~/.ssh/id_ed25519_yak_shears
    IdentitiesOnly yes
```

After this, `ssh yak-shears` just works.

## Step 2: hcloud auth `[x]`

The CLI is already installed (`brew install hcloud`). Token setup is manual:

1. Hetzner Cloud Console (https://console.hetzner.cloud) > pick or create a project > Security > API Tokens > Generate API Token (Read & Write)
2. `hcloud context create yak-shears` and paste the token when prompted (stored in `~/.config/hcloud/cli.toml`)
3. Register the public key with the project:

```sh
hcloud ssh-key create --name yak-shears --public-key-from-file ~/.ssh/id_ed25519_yak_shears.pub
```

## Step 3: fill in the user-data `[x]`

`cloud-config.yaml` has a `<public_ssh_key>` placeholder. Fill it into a local copy (gitignored, since it embeds the key):

```sh
sed "s|<public_ssh_key>|$(cat ~/.ssh/id_ed25519_yak_shears.pub)|" cloud-config.yaml > cloud-config.local.yaml
```

Sanity-check the result: `grep ssh-ed25519 cloud-config.local.yaml`

## Step 4: create the server `[x]` (CPX11, not CPX21 -- cheaper tier chosen at deploy time)

CPX21 (3 vCPU / 4GB, ~$8.49/mo) in Ashburn. The CX line is EU-only, and 4GB gives headroom for ffmpeg transcodes next to DuckDB. CPX11 (2GB, ~$4.99/mo) would probably also work if the price matters more.

```sh
hcloud server create \
  --name yak-shears \
  --type cpx21 \
  --image ubuntu-24.04 \
  --location ash \
  --ssh-key yak-shears \
  --user-data-from-file cloud-config.local.yaml

hcloud server ip yak-shears
```

## Step 5: DNS immediately after `[x]` (A record already existed from a prior attempt; just repointed it)

Add the A record right away so Let's Encrypt can verify once Caddy starts (propagation takes 1-30 min):

- `yak-shears.kyleking.me` A `<vps-ip>`, DNS-only (gray cloud if Cloudflare)
- Verify: `dig yak-shears.kyleking.me +short` returns the IP

## Step 6: wait for cloud-init, then verify `[x]` (cloud-init partially failed -- see Issues hit)

Provisioning takes 5-10 minutes and ends with a reboot. Watch progress without SSH:

```sh
hcloud server request-console yak-shears   # or watch CPU in the console Graphs tab
```

Once it settles (SSH is on port 2222 after the reboot; port 22 will refuse):

```sh
ssh yak-shears cloud-init status                    # want: done
ssh yak-shears systemctl is-active yak-shears caddy syncthing@yakshears gitops-update.timer
ssh yak-shears journalctl -u yak-shears -n 30
curl -I https://yak-shears.kyleking.me              # expect 303/200, valid cert
```

If anything is off, `/var/log/cloud-init-output.log` on the VPS has the full provisioning transcript.

## Step 7: first user `[x]`

```sh
ssh yak-shears
cd ~/yak-shears
uv run yak-shears-users create <email>
```

## Step 8: Syncthing pairing `[x]`

```sh
ssh -L 9998:localhost:8384 yak-shears
```

Open http://localhost:9998, add the laptop's device ID, share `~/Sync/yak-shears` bidirectionally. Notes appear on the VPS once the initial sync completes. Important: `yak_shears_search.db` must NOT be in the synced folder (the pre-flight `--search-db-dir` fix handles this, but confirm no stray `yak_shears_search.db` syncs over from the laptop; add it to Syncthing ignore patterns if one exists locally).

## Step 9: smoke test `[x]` (partial -- see Issues hit)

- [x] Login at https://yak-shears.kyleking.me with the Step 7 user (failed on first attempt, fixed -- see Issues hit)
- [x] Open a note, edit, save, reload, confirm persistence
- [x] Paste an image into a categorized note; confirm upload and thumbnail
- [ ] Upload a short video; confirm transcode plays (proves ffmpeg) -- not yet exercised
- [ ] Search returns results -- not yet exercised
- [ ] No CSP violations in the browser console -- not yet checked
- [ ] Push a trivial commit to `yak-shears-py`, confirm GitOps picks it up within ~5 min -- gitops fetch/pull logic verified working (correct branch, no-op detected correctly) but not exercised end-to-end with a real commit

## Issues hit

- **`runcmd` aborted mid-provision on the Caddy install.** `write_files` drops `/etc/caddy/Caddyfile` onto disk before `runcmd` runs, so when `apt install caddy` hit that pre-existing conffile, dpkg's interactive prompt had no TTY to answer and `runpaths` failed, aborting everything after it (repo clone, service enable/start, ssh hardening restart). Recovered by hand over SSH: `dpkg --configure -a --force-confdef --force-confold` (kept our Caddyfile), then ran the rest of the interrupted `runcmd` steps manually (clone, `uv sync`, enable/start all services, gitops timer, disable `ssh.socket`/enable `ssh.service`). Fixed `cloud-config.yaml` for next time: `apt install` for caddy now runs with `DEBIAN_FRONTEND=noninteractive` plus `--force-confdef --force-confold`.
- **Login failed with "Invalid email or password" right after creating the first user.** Root cause: `_default_store = UserStore.load_sync()` in `storage.py` is a module-level singleton loaded once at process import. The `yak-shears-users create` CLI is a separate process from the running `yak-shears` systemd service -- the CLI wrote the new user to `.yak-shears-users.json` on disk, but the already-running service kept its stale in-memory (empty) store and never re-read the file. Fixed by restarting the `yak-shears` service after user creation. Worth remembering for any future user management: **restart the service after `yak-shears-users create`/`delete`**, or the change won't take effect until next restart/gitops cycle.
- **Syncthing `-L` tunnel failed with "administratively prohibited."** The SSH hardening drop-in sets `AllowTcpForwarding no`, which blocks `ssh -L` entirely (that step in Step 8 assumed it would just work). Fixed by changing to `AllowTcpForwarding local` (permits `-L`, still blocks `-R` remote forwarding) both live on the VPS and in `cloud-config.yaml`.
- **Syncthing device pairing showed "no route to host" on the IPv6 address at first.** The VPS has a working IPv6 address and advertises `quic://[...]:22000` alongside the IPv4 address; the laptop's network apparently doesn't have a route to it. Self-resolved within ~1-2 minutes once Syncthing fell back to the IPv4/relay addresses -- IPv4 TCP+UDP to port 22000 tested reachable throughout. Not a VPS misconfig, no fix needed, just a heads up that the first connection attempt may show a scary error before falling back.
- **Domain and DNS were not actually "fresh."** `yak-shears.kyleking.me` already resolved via Cloudflare (proxied, valid cert) from a prior attempt, pointing at nothing live. Just needed the A record repointed at the new IP rather than created from scratch; TLS kept working throughout via Cloudflare's proxy without needing to wait on a fresh Let's Encrypt issuance.
- **Sync folder didn't match the runbook's assumption.** The laptop already syncs a single `default` folder rooted at `~/Sync` (with `yak-shears` as one subfolder among several) across multiple existing devices, not a dedicated `yak-shears`-only folder as DEPLOYMENT.md's Syncthing section implies. Decided to share the existing `default` folder with the VPS rather than carve out a new folder, to stay consistent with how the other paired devices already work. One older device in that folder's device list (`ubuntu-4gb-hel1-1`, a prior Hetzner box) is decommissioned/stale -- left untouched, not part of this deployment.

## Known deferred items

- Video upload/transcode (ffmpeg), search, and CSP console checks from the smoke test are not yet exercised -- do these before treating the app as fully verified
- GitOps auto-update has only been verified as a no-op (correct branch, correctly detects no diff); hasn't yet picked up a real commit end-to-end
- No snapshot/backup automation yet; `hcloud server create-image --type snapshot yak-shears` is the manual version (see DEPLOYMENT.md Backup)
- Passwordless sudo is broad; consider narrowing to the gitops restart command once stable
- Consider whether `yak-shears-users create`/`delete` should trigger (or document requiring) a service restart, given the module-level singleton store
