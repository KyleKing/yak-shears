# Deployment Guide

This guide covers deploying Yak Shears to a Hetzner VPS using cloud-init automation.

## Prerequisites

- Hetzner Cloud account with API access
- SSH key pair (generate with `ssh-keygen -t ed25519 -C "your-email@example.com"`)
- Domain DNS configured (A record pointing to VPS IP)
- Local tools: `ssh`, `git`

## Quick Deployment

1. **Create VPS via Hetzner Cloud Console or API**
   - OS: Ubuntu 22.04 or later
   - Server type: CX22 or larger (4GB+ RAM recommended)
   - Location: Your preference
   - SSH key: Add your public key
   - Cloud-init: Paste contents of `cloud-config.yaml` (replace `<public_ssh_key>` placeholder)

2. **Wait for provisioning** (~5-10 minutes)
   - Server will automatically install dependencies, configure services, and reboot
   - Monitor progress: Hetzner Console → Server → Graphs (watch CPU activity)

3. **Verify deployment**
   ```sh
   # SSH access (after reboot)
   ssh -p 2222 yakshears@<vps-ip>

   # Check service status
   systemctl status yak-shears caddy syncthing@yakshears gitops-update.timer

   # View logs if needed
   journalctl -u yak-shears -n 50
   ```

4. **Create initial user**
   ```sh
   ssh -p 2222 yakshears@<vps-ip>
   uv run yak-shears-users create your-email@example.com
   ```

5. **Access application**
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
- **HTTPS**: Caddy auto-provisions Let's Encrypt certificates
- **Passwordless sudo**: Enabled for automation; consider restricting for production
- **Hetzner Cloud Firewall**: Recommended as additional layer (separate from UFW)

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

### Domain not resolving
```sh
# Verify DNS propagation
dig yak-shears.kyleking.me +short

# Check Caddy config
sudo caddy validate --config /etc/caddy/Caddyfile

# Review Caddy logs for certificate issues
journalctl -u caddy -n 100
```

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
- User database: `/home/yakshears/.yak-shears-users.json`
- Yak notes: `/home/yakshears/Sync/yak-shears/` (synced via Syncthing)
- Caddy certificates: `/var/lib/caddy/.local/share/caddy/` (auto-renewable)

**Restore process:**
1. Deploy fresh VPS with same `cloud-config.yaml`
2. Restore `.yak-shears-users.json`
3. Configure Syncthing to sync yak files

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
