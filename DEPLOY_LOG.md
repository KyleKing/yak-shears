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

## Step 1: dedicated SSH key `[ ]`

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

## Step 2: hcloud auth `[ ]`

The CLI is already installed (`brew install hcloud`). Token setup is manual:

1. Hetzner Cloud Console (https://console.hetzner.cloud) > pick or create a project > Security > API Tokens > Generate API Token (Read & Write)
2. `hcloud context create yak-shears` and paste the token when prompted (stored in `~/.config/hcloud/cli.toml`)
3. Register the public key with the project:

```sh
hcloud ssh-key create --name yak-shears --public-key-from-file ~/.ssh/id_ed25519_yak_shears.pub
```

## Step 3: fill in the user-data `[ ]`

`cloud-config.yaml` has a `<public_ssh_key>` placeholder. Fill it into a local copy (gitignored, since it embeds the key):

```sh
sed "s|<public_ssh_key>|$(cat ~/.ssh/id_ed25519_yak_shears.pub)|" cloud-config.yaml > cloud-config.local.yaml
```

Sanity-check the result: `grep ssh-ed25519 cloud-config.local.yaml`

## Step 4: create the server `[ ]`

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

## Step 5: DNS immediately after `[ ]`

Add the A record right away so Let's Encrypt can verify once Caddy starts (propagation takes 1-30 min):

- `yak-shears.kyleking.me` A `<vps-ip>`, DNS-only (gray cloud if Cloudflare)
- Verify: `dig yak-shears.kyleking.me +short` returns the IP

## Step 6: wait for cloud-init, then verify `[ ]`

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

## Step 7: first user `[ ]`

```sh
ssh yak-shears
cd ~/yak-shears
uv run yak-shears-users create <email>
```

## Step 8: Syncthing pairing `[ ]`

```sh
ssh -L 9998:localhost:8384 yak-shears
```

Open http://localhost:9998, add the laptop's device ID, share `~/Sync/yak-shears` bidirectionally. Notes appear on the VPS once the initial sync completes. Important: `yak_shears_search.db` must NOT be in the synced folder (the pre-flight `--search-db-dir` fix handles this, but confirm no stray `yak_shears_search.db` syncs over from the laptop; add it to Syncthing ignore patterns if one exists locally).

## Step 9: smoke test `[ ]`

- [ ] Login at https://yak-shears.kyleking.me with the Step 7 user
- [ ] Open a note, edit, save, reload, confirm persistence
- [ ] Paste an image into a categorized note; confirm upload and thumbnail
- [ ] Upload a short video; confirm transcode plays (proves ffmpeg)
- [ ] Search returns results
- [ ] No CSP violations in the browser console (security headers only exist in auth mode and have not been exercised in production before)
- [ ] Push a trivial commit to `yak-shears-py`, confirm GitOps picks it up within ~5 min: `ssh yak-shears journalctl -u gitops-update -n 20`

## Issues hit

(append as they happen)

## Known deferred items

- ufw rules reportedly reset on VPS boot in a past experiment; verify with `ssh yak-shears sudo ufw status` after a reboot and persist if needed
- No snapshot/backup automation yet; `hcloud server create-image --type snapshot yak-shears` is the manual version (see DEPLOYMENT.md Backup)
- Passwordless sudo is broad; consider narrowing to the gitops restart command once stable
