# Deployment Guide

This guide covers deploying Yak Shears to a Hetzner VPS using cloud-init automation.

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
   - OS: Ubuntu 22.04 or later
   - Server type: CX22 or larger (4GB+ RAM recommended)
   - Location: Your preference
   - SSH key: Add your public key
   - Cloud-init: Paste contents of `cloud-config.yaml` (replace `<public_ssh_key>` placeholder)
   - **Note the VPS IP address** assigned after creation

### Option B: hcloud CLI

```sh
# Install hcloud CLI
brew install hcloud  # macOS
# or download from https://github.com/hetznercloud/cli/releases

# Authenticate (create API token in Hetzner Cloud Console)
hcloud context create yak-shears

# Create server with cloud-config
hcloud server create \
  --name yak-shears \
  --type cx22 \
  --image ubuntu-22.04 \
  --location nbg1 \
  --ssh-key YOUR_KEY_NAME \
  --user-data-from-file cloud-config.yaml

# Get server IP
hcloud server ip yak-shears
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
   uv run yak-shears-users create your-email@example.com
   ```

6. **Access application**
   - HTTPS: `https://yak-shears.kyleking.me` (update domain in `cloud-config.yaml`)
   - Login with created user credentials

## Configuration Checklist

Before deploying, update `cloud-config.yaml`:

- [ ] Replace `<public_ssh_key>` with your actual SSH public key
- [ ] Update Caddy email: `dev.act.kyle+caddy@gmail.com` → your email
- [ ] Update domain: `yak-shears.kyleking.me` → your domain
- [ ] Update git clone URL if using private fork
- [ ] Review firewall rules (UFW ports: 2222, 80, 443, 22000, 21027)
- [ ] Consider setting `sudo: ['ALL=(ALL) ALL']` instead of NOPASSWD for production

## Syncthing Setup

Syncthing provides file synchronization for yak notes (`~/Sync/yak-shears`).

```sh
# Port-forward Syncthing UI (run from laptop)
ssh -p 2222 -L 9998:localhost:8384 yakshears@<vps-ip>

# Open http://localhost:9998 in browser
# - Copy Device ID from your laptop's Syncthing
# - Paste in VPS Syncthing → Actions → Show ID → Add Remote Device
# - Share ~/Sync/yak-shears folder bidirectionally
```

See: https://docs.syncthing.net/intro/getting-started.html#configuring

## GitOps Auto-Updates

The server polls `origin/main` every 5 minutes and automatically:
- Pulls new commits
- Runs `mise install && uv sync`
- Restarts `yak-shears` service

```sh
# Monitor GitOps activity
journalctl -u gitops-update -f

# Manually trigger update
sudo systemctl start gitops-update.service
```

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

# Update mise tools
mise upgrade

# Update Python dependencies
cd /home/yakshears/yak-shears
uv lock --upgrade
uv sync

# Restart services after manual updates
sudo systemctl restart yak-shears
```

## Additional Resources

- Hetzner Cloud API: https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs
- Cloud-init docs: https://cloudinit.readthedocs.io/en/latest/
- Caddy docs: https://caddyserver.com/docs/
- Syncthing docs: https://docs.syncthing.net/
