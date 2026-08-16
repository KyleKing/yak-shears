# Deployment Guide

This guide covers deploying Yak Shears to a Hetzner VPS using cloud-init automation. It is the evergreen, reusable reference: it should always describe a procedure that works against the current `cloud-config.yaml` and current codebase. For the narrative of one specific deployment (what was actually run, in order, and every issue hit along the way) see [DEPLOY_LOG.md](./DEPLOY_LOG.md).

## Prerequisites

- Hetzner Cloud account with API access
- SSH key pair (generate with `ssh-keygen -t ed25519 -C "your-email@example.com"`)
- Domain name (for HTTPS via Let's Encrypt)
- DNS management access (Cloudflare, etc.)
- Local tools: `ssh`, `git`
- Server binaries: `ffmpeg` is required for media upload (video transcoding and poster frames); ensure it is in `cloud-config.yaml`'s package list

## DNS Configuration (Required for Let's Encrypt)

**IMPORTANT**: Configure DNS BEFORE deploying the VPS. Let's Encrypt needs to verify domain ownership via HTTP-01 challenge, which requires the domain to resolve to your server.

### Cloudflare Setup

1. **Create A Record**
   - Type: `A`
   - Name: `yak-shears` (or your subdomain)
   - IPv4 address: `<your-vps-ip>` (get this after creating VPS)
   - Proxy status: **DNS only** (gray cloud, not orange)
   - TTL: Auto

2. **SSL/TLS Settings** (Cloudflare Dashboard → SSL/TLS)
   - SSL/TLS encryption mode: **Full (strict)** or **Full**
   - Do NOT use "Flexible" mode (causes redirect loops)
   - Wait for SSL/TLS to show "Active Certificate"

3. **Why "DNS only" (gray cloud)?**
   - Let's Encrypt needs to reach your server directly on port 80
   - Cloudflare proxy (orange cloud) can interfere with ACME challenges
   - After SSL is provisioned, you can optionally enable proxy (orange cloud)

4. **Alternative: Use Cloudflare Proxy from the start**
   If you want to use Cloudflare proxy (orange cloud) immediately:
   - Change SSL/TLS mode to **Full** or **Full (strict)**
   - Caddy will still provision certificates, but via **TLS-ALPN-01** challenge instead
   - Ensure port 443 is not blocked

### Other DNS Providers

For non-Cloudflare providers:
- Add A record: `yak-shears.kyleking.me` → `<vps-ip>`
- TTL: 300-3600 seconds
- Wait for DNS propagation (check with `dig yak-shears.kyleking.me +short`)

### Verify DNS Before Deployment

```sh
# After creating VPS and configuring DNS, verify resolution
dig yak-shears.kyleking.me +short
# Should return your VPS IP address

# Also test from a different network/location
nslookup yak-shears.kyleking.me 8.8.8.8
```

## Quick Deployment

### Option A: Hetzner Cloud Console

1. **Create VPS via Hetzner Cloud Console**
   - OS: Ubuntu 24.04
   - Server type: CX22 or larger in the EU; CPX11/CPX21 in US locations (CX is EU-only)
   - Location: Your preference
   - SSH key: Add your public key
   - Cloud-init: Paste contents of `cloud-config.yaml` (replace `<public_ssh_key>` placeholder)
   - **Note the VPS IP address** assigned after creation

### Option B: hcloud CLI (recommended; this is what the reference deployment used)

```sh
# 0. Dedicated SSH key, one per purpose (don't reuse a personal/GitHub key for a VPS)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_yak_shears -C "yak-shears-hetzner"

# 1. Install hcloud CLI
brew install hcloud  # macOS
# or download from https://github.com/hetznercloud/cli/releases

# 2. Authenticate. Generate a Read & Write API token in the Hetzner Cloud Console
# (console.hetzner.cloud -> project -> Security -> API Tokens), then:
hcloud context create yak-shears   # paste the token when prompted; stored in ~/.config/hcloud/cli.toml

# 3. Register the key with the project
hcloud ssh-key create --name yak-shears --public-key-from-file ~/.ssh/id_ed25519_yak_shears.pub

# 4. Fill the <public_ssh_key> placeholder into a local, gitignored copy
sed "s|<public_ssh_key>|$(cat ~/.ssh/id_ed25519_yak_shears.pub)|" cloud-config.yaml > cloud-config.local.yaml
grep ssh-ed25519 cloud-config.local.yaml   # sanity check

# 5. Create the server with the filled-in cloud-config
hcloud server create \
  --name yak-shears \
  --type cpx11 \
  --image ubuntu-24.04 \
  --location ash \
  --ssh-key yak-shears \
  --user-data-from-file cloud-config.local.yaml

# Get server IP
hcloud server ip yak-shears
```

CPX11 (2 vCPU / 2GB, ~$4.99/mo) is the size actually used for the reference deployment and has held up fine for a single-user app. CPX21 (3 vCPU / 4GB, ~$8.49/mo) is the safer default if you want headroom for ffmpeg transcodes running alongside DuckDB, or expect more concurrent load. The CX line is EU-only; use CPX in US locations like `ash` (Ashburn).

Add a host block to `~/.ssh/config` once you have the IP so `ssh yak-shears` just works:

```
Host yak-shears
    HostName <vps-ip>
    Port 2222
    User yakshears
    IdentityFile ~/.ssh/id_ed25519_yak_shears
    IdentitiesOnly yes
```

2. **Configure DNS immediately** (see DNS Configuration section above)
   - Add A record in Cloudflare: `yak-shears.yourdomain.com` → `<vps-ip>`
   - Use "DNS only" (gray cloud) initially
   - Verify: `dig yak-shears.yourdomain.com +short` (should return VPS IP)
   - **Why now?** DNS propagation takes 1-30 minutes. Starting this early ensures Let's Encrypt can verify your domain when Caddy starts.

3. **Wait for provisioning** (~5-10 minutes)
   - Server will automatically install dependencies, configure services, and reboot
   - Monitor progress: Hetzner Console → Server → Graphs (watch CPU activity)

4. **Verify deployment**
   ```sh
   # SSH access (after reboot)
   ssh -p 2222 yakshears@<vps-ip>

   # Check service status
   systemctl status yak-shears caddy syncthing@yakshears gitops-update.timer

   # View logs if needed
   journalctl -u yak-shears -n 50
   journalctl -u caddy -n 50  # Check for SSL certificate provisioning
   ```

5. **Create initial user**
   ```sh
   ssh -p 2222 yakshears@<vps-ip>
   cd ~/yak-shears
   uv run yak-shears-users create your-email@example.com   # prompts for a password interactively
   ```
   Run the create/delete commands yourself over an interactive SSH session so the password never passes through any automation or chat transcript; `getpass` needs a real TTY and fails non-interactively (no `-t`, or stdin piped) with `EOFError`.

   The running `yak-shears` service picks up new/deleted users automatically (it reloads `.yak-shears-users.json` when the file's mtime changes, so no restart needed). If you're running an older deployment predating that fix, `sudo systemctl restart yak-shears` after any CLI user change.

6. **Access application**
   - HTTPS: `https://yak-shears.kyleking.me` (update domain in `cloud-config.yaml`)
   - Login with created user credentials

## Configuration Checklist

Before deploying, update `cloud-config.yaml`:

- [ ] Replace `<public_ssh_key>` with your actual SSH public key
- [ ] Replace `<ntfy_topic>` with a random ntfy.sh topic name (see Deploy notifications)
- [ ] Update Caddy email: `dev.act.kyle+caddy@gmail.com` → your email
- [ ] Update domain: `yak-shears.kyleking.me` → your domain
- [ ] Update git clone URL if using private fork
- [ ] Review firewall rules (UFW ports: 2222, 80, 443, 22000, 21027)
- [ ] Consider setting `sudo: ['ALL=(ALL) ALL']` instead of NOPASSWD for production

## Syncthing Setup

Syncthing provides file synchronization for yak notes. The VPS-side directory is `~/Sync/yak-shears` (created by cloud-init, chowned to `yakshears`); the search DB is deliberately kept out of it (see the Backup section).

```sh
# Port-forward Syncthing UI (run from laptop)
ssh -p 2222 -L 9998:localhost:8384 yakshears@<vps-ip>

# Open http://localhost:9998 in browser
# - Copy Device ID from your laptop's Syncthing
# - Paste in VPS Syncthing → Actions → Show ID → Add Remote Device
# - Share the folder bidirectionally (see "Which folder to share" below)
```

See: https://docs.syncthing.net/intro/getting-started.html#configuring

### Which folder to share

If this is your first Syncthing folder, share `~/Sync/yak-shears` directly, matching the VPS path above.

If you already sync other files between devices, you likely have one `default` folder rooted at `~/Sync` (with `yak-shears` as one subfolder among others), not a dedicated `yak-shears`-only folder. In that case it's simpler to add the VPS as another device on that existing folder (`~/Sync` <-> `/home/yakshears/Sync`) rather than carving out a new Syncthing folder just for this app, so the VPS behaves like any other paired device. The tradeoff: the VPS then receives everything in `~/Sync`, not just `yak-shears`, so check what else lives there before doing this.

### Troubleshooting: `ssh -L` fails with "administratively prohibited"

```
channel 3: open failed: administratively prohibited: open failed
```

The SSH hardening drop-in (`/etc/ssh/sshd_config.d/99-ssh-hardening.conf`, written by `cloud-config.yaml`) sets `AllowTcpForwarding local`, which permits `ssh -L` (local port forwarding, what the tunnel above needs) while still blocking `-R` remote forwarding. If you're hitting this error, the drop-in probably still has the old `AllowTcpForwarding no` — check with `ssh yak-shears "sudo cat /etc/ssh/sshd_config.d/99-ssh-hardening.conf"`, fix with:

```sh
ssh yak-shears "sudo sed -i 's/AllowTcpForwarding no/AllowTcpForwarding local/' /etc/ssh/sshd_config.d/99-ssh-hardening.conf && sudo sshd -t && sudo systemctl restart ssh.service"
```

### Troubleshooting: "no route to host" during device pairing

Syncthing advertises both IPv4 and IPv6 addresses for a device. If your network doesn't have a working route to the VPS's IPv6 address, the pairing UI may briefly show `no route to host` against the `quic://[ipv6]:22000` address before Syncthing falls back to IPv4 or a relay, which usually resolves itself within a minute or two. Not a server misconfiguration; only worth investigating further if the connection never establishes on any address after a few minutes (check `sudo ufw status` allows `22000/tcp`, `22000/udp`, `21027/udp`, and that `systemctl is-active syncthing@yakshears` is `active`).

## GitOps Auto-Updates

The server polls `origin/yak-shears-py` every 5 minutes. When the remote is ahead it checks GitHub's check runs for that commit and deploys only a green one, so a commit that broke CI (or is still building) leaves the box on the last commit that worked. A deploy pulls, runs `uv sync --no-dev --frozen`, regenerates the typed template wrappers, and restarts `yak-shears`.

It then polls `http://localhost:8084/auth/status` for 30 seconds. If the new commit never answers, the script resets to the previous commit, redeploys that, and records the bad SHA in `~/.local/state/yak-shears/failed-sha` so the next tick doesn't redeploy it. Delete that file to retry a commit after fixing whatever the server was missing.

Every outcome that isn't a clean deploy sends an ntfy notification (see below).

```sh
# Monitor GitOps activity
journalctl -u gitops-update -f

# Manually trigger update
sudo systemctl start gitops-update.service
```

### Deploy notifications

`/etc/yak-shears/deploy.env` holds `NTFY_TOPIC`. Any ntfy.sh topic is readable and writable by anyone who knows its name, so generate a random one rather than picking something guessable, and keep the filled-in value out of git the same way the SSH key is kept out:

```sh
# On the server, pick a topic and install it
TOPIC="yak-shears-$(openssl rand -hex 12)"
printf 'NTFY_TOPIC=%s\n' "$TOPIC" | sudo tee /etc/yak-shears/deploy.env >/dev/null
sudo chown root:yakshears /etc/yak-shears/deploy.env
sudo chmod 640 /etc/yak-shears/deploy.env
echo "Subscribe to https://ntfy.sh/$TOPIC in the ntfy app"
```

With `NTFY_TOPIC` unset the deploy still runs and just skips the notification.

## Monitoring & Logs

```sh
# Service status
systemctl status yak-shears caddy syncthing@yakshears fail2ban

# Application logs
journalctl -u yak-shears -f

# Web server logs
journalctl -u caddy -f

# SSH attack attempts
journalctl -u fail2ban -f

# System resource usage
htop
```

## Security Notes

- **SSH**: Hardened (port 2222, no passwords, no root, fail2ban enabled)
- **Firewall**: UFW active with minimal ports open
- **HTTPS**: Caddy auto-provisions Let's Encrypt certificates (see below)
- **Passwordless sudo**: Enabled for automation; consider restricting for production
- **Hetzner Cloud Firewall**: Recommended as additional layer (separate from UFW)

### Passwordless Sudo Risks

The default configuration grants passwordless sudo for convenience:

```yaml
sudo: ALL=(ALL) NOPASSWD:ALL
```

**Risks:**
- If the GitOps script is compromised, attacker gains root
- If the repository is compromised, attacker can execute arbitrary code
- If SSH key is stolen, attacker has unrestricted access

**Mitigations:**

1. **Restrict sudo commands** (edit `cloud-config.yaml`):
   ```yaml
   sudo: /usr/bin/systemctl restart yak-shears, /usr/local/bin/gitops-update.sh
   ```

2. **Require passwords** (edit `cloud-config.yaml`):
   ```yaml
   sudo: ALL=(ALL) ALL  # Remove NOPASSWD
   ```

3. **Use deploy keys**: Create GitHub deploy key with read-only access instead of full SSH key

### How Let's Encrypt Works with Caddy

Caddy automatically handles HTTPS certificate provisioning with **zero configuration**:

1. **On First Start**: When Caddy starts and sees `yak-shears.kyleking.me` in the Caddyfile:
   - It automatically requests a certificate from Let's Encrypt
   - Uses HTTP-01 challenge (serves a file on port 80 to prove domain ownership)
   - Let's Encrypt verifies the domain resolves to your server
   - Certificate is issued and stored in `/var/lib/caddy/.local/share/caddy/`

2. **Automatic Renewal**: Caddy renews certificates automatically before expiration (every 60 days for 90-day certs)

3. **What Can Go Wrong**:
   - DNS not pointing to server → Let's Encrypt can't verify ownership
   - Port 80 or 443 blocked → Challenge fails
   - Domain in Caddyfile doesn't match actual domain → No certificate issued

4. **Verify HTTPS is Working**:
   ```sh
   # Check Caddy logs for certificate provisioning
   journalctl -u caddy -n 100 | grep -i "certificate"

   # Test HTTPS endpoint
   curl -I https://yak-shears.kyleking.me

   # Check certificate details
   echo | openssl s_client -connect yak-shears.kyleking.me:443 -servername yak-shears.kyleking.me 2>/dev/null | openssl x509 -noout -text | grep -A2 "Issuer"
   # Should show: Issuer: C = US, O = Let's Encrypt
   ```

5. **First-Time Setup Timeline**:
   - DNS propagation: 1-30 minutes (depends on TTL and provider)
   - Caddy starts: Immediately after cloud-init completes
   - Certificate request: Within 30 seconds of Caddy start
   - Certificate issuance: 10-60 seconds if DNS is correct
   - **Total**: Expect HTTPS to work within 2-5 minutes after VPS reboot (assuming DNS was configured first)

## Troubleshooting

### Services not starting
```sh
# Check cloud-init completion
cloud-init status

# View cloud-init logs
cat /var/log/cloud-init-output.log
tail -100 /var/log/cloud-init.log

# Restart services manually
sudo systemctl restart yak-shears caddy
```

### GitOps not pulling updates
```sh
# Check timer is active
systemctl status gitops-update.timer

# Run update script manually to see errors
sudo -u yakshears /usr/local/bin/gitops-update.sh
```

### `cloud-init status` shows `error`, and only some services came up

```
errors:
    - ('scripts_user', RuntimeError('Runparts: 1 failures (runcmd) in 1 attempted commands'))
```

`runcmd` runs each command in sequence and stops at the first failure, so everything after the failure point (repo clone, `uv sync`, enabling/starting services, the gitops timer, the SSH hardening restart) silently never runs. Find where it stopped:

```sh
sudo tail -150 /var/log/cloud-init-output.log
```

The one hit on the reference deployment: `apt install caddy` prompted interactively over dpkg because `write_files` had already dropped `/etc/caddy/Caddyfile` on disk (write_files runs before runcmd), and dpkg saw a conffile conflict with no TTY to answer it. `cloud-config.yaml` now installs Caddy with `DEBIAN_FRONTEND=noninteractive` and `--force-confdef --force-confold` to avoid this, but if you hit it anyway (e.g. on an older cloud-config, or a different package with the same shape of problem):

```sh
# Finish the stuck package non-interactively, keeping cloud-init's version of any conffile
sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a --force-confdef --force-confold

# Then run whatever runcmd steps never got to execute, e.g.:
sudo mkdir -p /home/yakshears/Sync/yak-shears
sudo chown -R yakshears:yakshears /home/yakshears/Sync
sudo -u yakshears git clone https://github.com/KyleKing/yak-shears.git /home/yakshears/yak-shears
sudo -u yakshears sh -c 'cd /home/yakshears/yak-shears && /home/yakshears/.local/bin/uv sync --no-dev --frozen && .venv/bin/types-for-jinja wrapper'
sudo systemctl enable --now syncthing@yakshears.service caddy yak-shears
sudo systemctl daemon-reload
sudo systemctl enable --now gitops-update.timer
sudo systemctl disable --now ssh.socket
sudo systemctl enable ssh.service
sudo systemctl restart ssh.service   # safe: reads the new sshd_config.d drop-in, existing session survives
```

### SSL Certificate / HTTPS Issues

**Symptoms**: "Connection not secure", certificate errors, or site not loading on HTTPS

```sh
# 1. Verify DNS is pointing to your server
dig yak-shears.kyleking.me +short
# Should return your VPS IP

# 2. Check if Caddy is running
systemctl status caddy

# 3. Validate Caddyfile syntax
sudo caddy validate --config /etc/caddy/Caddyfile

# 4. Check Caddy logs for certificate errors
journalctl -u caddy -n 200 | grep -i "certificate\|acme\|error"

# Common error messages and solutions:
# - "no such host" → DNS not configured correctly
# - "connection refused" → Port 80/443 blocked by firewall
# - "authorization failed" → Let's Encrypt can't reach your server
# - "rate limit" → Too many certificate requests (wait 1 hour)

# 5. Test if port 80 is accessible from internet
curl -v http://yak-shears.kyleking.me/.well-known/acme-challenge/test
# Should get 404 from Caddy (proves port 80 works)

# 6. If using Cloudflare with orange cloud (proxy enabled):
# - Ensure SSL/TLS mode is "Full" or "Full (strict)", NOT "Flexible"
# - Check if Caddy got a certificate: sudo ls -la /var/lib/caddy/.local/share/caddy/certificates/
# - Caddy may use TLS-ALPN-01 challenge instead of HTTP-01

# 7. Force certificate renewal (if needed)
sudo systemctl stop caddy
sudo rm -rf /var/lib/caddy/.local/share/caddy/certificates/acme-v02.api.letsencrypt.org-directory/
sudo systemctl start caddy
# Watch logs: journalctl -u caddy -f
```

**Cloudflare-Specific Issues**:
- Gray cloud (DNS only): Use this initially for easiest setup
- Orange cloud (Proxied): Requires "Full" or "Full (strict)" SSL mode
- If you see "too many redirects": Check SSL/TLS mode is not "Flexible"

### SSH connection refused
- VPS may still be rebooting (wait 2-3 minutes after creation)
- Verify port 2222 is open in Hetzner Cloud Firewall
- Check SSH service: `ssh -p 22 root@<vps-ip>` (emergency access via console)

### Private repository access
```sh
# Generate deploy key on VPS
sudo -u yakshears ssh-keygen -t ed25519 -C "yakshears@vps" -f /home/yakshears/.ssh/id_ed25519
sudo -u yakshears cat /home/yakshears/.ssh/id_ed25519.pub

# Add to GitHub: Settings → Deploy keys → Add deploy key (read-only)
```

## Backup

**What to backup:**
- User database: `/home/yakshears/yak-shears/yak_shears/.yak-shears-users.json` (lives inside the package directory)
- Yak notes: `/home/yakshears/Sync/yak-shears/` (synced via Syncthing)
- Caddy certificates: `/var/lib/caddy/.local/share/caddy/` (auto-renewable)

**Restore process:**
1. Deploy fresh VPS with same `cloud-config.yaml`
2. Restore `.yak-shears-users.json`
3. Configure Syncthing to sync yak files

### Hetzner Snapshots

```sh
# Install hcloud CLI
brew install hcloud  # macOS
# or: apt install hcloud-cli  # Linux

# Authenticate (use API token from Hetzner Cloud Console)
hcloud context create yak-shears

# Manual snapshot
hcloud server create-image \
  --description "yak-shears-$(date +%Y%m%d-%H%M)" \
  --type snapshot \
  <server-name>

# List snapshots
hcloud image list --type snapshot
```

### Health Check Script

Create `/usr/local/bin/health-check.sh`:

```sh
#!/bin/bash
# Simple health check for yak-shears

# Check if service is running
if ! systemctl is-active --quiet yak-shears; then
    echo "ERROR: yak-shears service not running"
    exit 1
fi

# Check if port 8084 is listening
if ! ss -tlnp | grep -q ':8084'; then
    echo "ERROR: Port 8084 not listening"
    exit 1
fi

# Check recent GitOps errors
if journalctl -u gitops-update -n 10 --no-pager | grep -q "ERROR"; then
    echo "WARNING: Recent GitOps errors detected"
    exit 1
fi

echo "OK: Yak Shears healthy"
```

Add to cron for regular checks:
```sh
chmod +x /usr/local/bin/health-check.sh
echo "*/15 * * * * /usr/local/bin/health-check.sh" | crontab -
```

## Maintenance

```sh
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies. Lock from a dev machine and commit uv.lock;
# the server installs runtime deps only and refuses a stale lockfile.
# The typed template wrappers are gitignored generated code that the app
# imports, so they have to be rebuilt after every pull.
cd /home/yakshears/yak-shears
uv sync --no-dev --frozen
.venv/bin/types-for-jinja wrapper

# Restart services after manual updates
sudo systemctl restart yak-shears
```

## Additional Resources

- Hetzner Cloud API: https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs
- Cloud-init docs: https://cloudinit.readthedocs.io/en/latest/
- Caddy docs: https://caddyserver.com/docs/
- Syncthing docs: https://docs.syncthing.net/
