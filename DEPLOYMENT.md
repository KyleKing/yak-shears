# Hetzner Deployment Guide

Automated deployment for mdformat-plugin-template using Hetzner Cloud and cloud-init.

## Prerequisites

- Hetzner Cloud account
- SSH key pair (`ssh-keygen -t ed25519` if needed)
- GitHub repository access

## Quick Start

### 1. Prepare Cloud-Config

Edit `cloud-config.yaml` and replace ALL CAPS variables:

```yaml
YOUR_USERNAME         # e.g., deploy
YOUR_SSH_PUBLIC_KEY_HERE  # Full key from ~/.ssh/id_rsa.pub
YOUR_GITHUB_USERNAME  # GitHub username
```

**Security Review Checklist:**
- [ ] SSH public key is correct and corresponds to your private key
- [ ] Repository URL is correct
- [ ] Reviewed passwordless sudo implications (see Security section)
- [ ] Considered restricting sudo to specific commands
- [ ] Verified timezone setting

### 2. Create Hetzner Server

**Via Hetzner Cloud Console:**

1. Create new server
2. Choose **Ubuntu 22.04 LTS** or newer
3. Select server size (**CX11** minimum)
4. Under "Cloud config", paste **entire contents** of `cloud-config.yaml`
5. Add your SSH key
6. Create server

**Via CLI (`hcloud`):**

```bash
# Install hcloud CLI
brew install hcloud  # macOS
# or: apt install hcloud  # Linux
# or: download from https://github.com/hetznercloud/cli/releases

# Authenticate
hcloud context create mdformat-project
# Follow prompts to enter API token from Hetzner Cloud Console

# Create server with cloud-config
hcloud server create \
  --name mdformat-server \
  --type cx11 \
  --image ubuntu-22.04 \
  --location nbg1 \
  --ssh-key YOUR_KEY_NAME \
  --user-data-from-file cloud-config.yaml

# Get server IP
hcloud server ip mdformat-server
```

### 3. Verify Deployment

**Wait 3-5 minutes** for cloud-init to complete, then:

```bash
# SSH into server
ssh YOUR_USERNAME@SERVER_IP

# Check cloud-init completion
cloud-init status --wait

# Verify services are running
systemctl status auto-deploy.timer
systemctl status syncthing@YOUR_USERNAME

# View auto-deploy logs
tail -f ~/.local/var/log/auto-deploy.log

# Check service logs
journalctl -u auto-deploy.service -f
```

## What Gets Configured

### Automatic Setup

- **SSH Hardening**: Password auth disabled, pubkey only, root login disabled
- **mise**: Installed for Python version management
- **Git Repository**: Cloned to `/opt/mdformat-plugin-template`, branch `main`
- **Auto-deploy**: Pulls latest from `main` every 5 minutes
- **Syncthing**: File sync service on port 8384 (web UI) and 22000 (sync)
- **Security**: Automatic package updates enabled

### Services (All Auto-Start on Reboot)

| Service | Description |
|---------|-------------|
| `auto-deploy.timer` | Auto-update from GitHub |
| `syncthing@USER` | File synchronization |

## Security Considerations

### ⚠️  Passwordless Sudo

The default configuration grants **passwordless sudo** for convenience:

```yaml
sudo: ALL=(ALL) NOPASSWD:ALL
```

**Risks:**
- If the deployment script is compromised, attacker gains root
- If the repository is compromised, attacker can execute arbitrary code
- If SSH key is stolen, attacker has unrestricted access

**Mitigations:**

1. **Restrict sudo commands** (edit `cloud-config.yaml`):
   ```yaml
   sudo: /usr/bin/systemctl restart auto-deploy.timer, /usr/local/bin/auto-deploy.sh
   ```

2. **Require passwords** (edit `cloud-config.yaml`):
   ```yaml
   sudo: ALL=(ALL) ALL  # Remove NOPASSWD
   ```
   Then manually enter password when needed

3. **SSH key constraints** (in `~/.ssh/authorized_keys`):
   ```
   command="/usr/local/bin/auto-deploy.sh",no-port-forwarding,no-X11-forwarding ssh-ed25519 AAAA...
   ```

4. **Use deploy keys**: Create GitHub deploy key with read-only access

### Remote Script Execution

Cloud-config downloads and executes mise installation script:

```bash
curl https://mise.run | sh
```

**For production:**
- Verify checksums before execution
- Pin specific versions
- Self-host installation scripts
- Review source code: [mise installer](https://github.com/jdx/mise/blob/main/install.sh)

### Firewall Configuration

Add UFW rules to restrict access:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 22000/tcp  # Syncthing transfer
sudo ufw allow 21027/udp  # Syncthing discovery
sudo ufw enable
```

**Better**: Use Hetzner Cloud Firewall (applied at network level):

```bash
hcloud firewall create --name mdformat-fw
hcloud firewall add-rule mdformat-fw --direction in --protocol tcp --port 22 --source-ips 0.0.0.0/0 --source-ips ::/0
hcloud firewall add-rule mdformat-fw --direction in --protocol tcp --port 22000 --source-ips 0.0.0.0/0
hcloud firewall apply-to-resource mdformat-fw --type server --server mdformat-server
```

## Manual Operations

### Trigger Deployment

```bash
# Force immediate update
sudo systemctl start auto-deploy.service

# Watch logs
journalctl -u auto-deploy.service -f
```

### Check Logs

```bash
# Auto-deploy logs (note: new location for user-writable path)
tail -f ~/.local/var/log/auto-deploy.log

# Service logs
journalctl -u auto-deploy.service -f
journalctl -u syncthing@YOUR_USERNAME -f
```

### Update Dependencies

```bash
cd /opt/mdformat-plugin-template

# Update mise tools
mise upgrade
mise prune  # Remove unused versions
```

### Syncthing Configuration

Access web UI via SSH tunnel:

```bash
# On local machine
ssh -L 8384:localhost:8384 YOUR_USERNAME@SERVER_IP

# Visit http://localhost:8384 in browser
```

**Configure:**
1. Set GUI authentication password
2. Add folders to sync (e.g., `/opt/mdformat-plugin-template`)
3. Add devices (get device ID from other Syncthing instances)
4. Configure folder sharing between devices

## Troubleshooting

### Cloud-init Failed

```bash
# Check status
cloud-init status --long

# View full logs
sudo cat /var/log/cloud-init-output.log
sudo journalctl -u cloud-init

# Common issues:
# - Typo in cloud-config YAML (indentation, missing fields)
# - Network timeout during package installation
# - Git clone failure (invalid credentials, repo doesn't exist)
```

### Auto-deploy Not Running

```bash
# Check timer status
systemctl status auto-deploy.timer
systemctl list-timers --all

# Check last run
journalctl -u auto-deploy.service -n 50

# Manually trigger
sudo systemctl start auto-deploy.service

# Reset timer
sudo systemctl restart auto-deploy.timer
```

### mise Not Found

```bash
# Check installation
which mise

# Reinstall mise
curl https://mise.run | sh
echo 'eval "$(/home/YOUR_USERNAME/.local/bin/mise activate bash)"' >> ~/.bashrc
source ~/.bashrc

# Verify PATH
echo $PATH  # Should include ~/.local/bin
```

### Git Authentication Issues

```bash
# For private repos, add deploy key
ssh-keygen -t ed25519 -C "deploy@mdformat" -f ~/.ssh/mdformat_deploy
# Add ~/.ssh/mdformat_deploy.pub to GitHub repo Settings > Deploy keys

# Configure git to use deploy key
cat >> ~/.ssh/config <<EOF
Host github.com
    IdentityFile ~/.ssh/mdformat_deploy
    IdentitiesOnly yes
EOF
```

## Customization

### Change Update Interval

Edit `/etc/systemd/system/auto-deploy.timer`:

```ini
[Timer]
OnUnitActiveSec=15min  # Change from 5min to 15min
```

Reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart auto-deploy.timer
```

### Add Environment Variables

Edit `/etc/systemd/system/auto-deploy.service`:

```ini
[Service]
Environment="DATABASE_URL=sqlite:///data/db.sqlite"
Environment="SECRET_KEY=your-secret-key"
```

Reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart auto-deploy.service
```

### Modify Deploy Script

Edit `/usr/local/bin/auto-deploy.sh` to add custom commands:

```bash
# After git pull, add:
log "Running tests..."
/home/$APP_USER/.local/bin/mise run test

log "Building docs..."
/home/$APP_USER/.local/bin/mise run docs
```

## Monitoring

### Log Aggregation

```bash
# Install lnav for better log viewing
sudo apt install lnav

# View all logs
sudo lnav /var/log/syslog ~/.local/var/log/auto-deploy.log
```

### Health Checks

Create simple health check script:

```bash
#!/bin/bash
# /usr/local/bin/health-check.sh

LOG_FILE="$HOME/.local/var/log/auto-deploy.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "WARNING: Log file missing"
    exit 1
fi

# Check if last deploy was successful
if tail -20 "$LOG_FILE" | grep -q "ERROR"; then
    echo "ERROR: Recent deploy failures detected"
    exit 1
fi

echo "OK: Deployment healthy"
```

Add to cron:

```bash
crontab -e
# Add: */15 * * * * /usr/local/bin/health-check.sh
```

## Backup Strategy

### Hetzner Snapshots

```bash
# Manual snapshot
hcloud server create-image \
  --description "mdformat-$(date +%Y%m%d-%H%M)" \
  --type snapshot \
  mdformat-server

# Automated snapshots (daily at 3 AM)
cat > /usr/local/bin/snapshot.sh <<'EOF'
#!/bin/bash
hcloud server create-image \
  --description "auto-mdformat-$(date +%Y%m%d)" \
  --type snapshot \
  mdformat-server

# Keep only last 7 snapshots
hcloud image list -o noheader -o columns=id,description | \
  grep "auto-mdformat" | \
  sort -r | \
  tail -n +8 | \
  awk '{print $1}' | \
  xargs -I{} hcloud image delete {}
EOF

chmod +x /usr/local/bin/snapshot.sh
echo "0 3 * * * /usr/local/bin/snapshot.sh" | crontab -
```

### Syncthing for Real-time Sync

Syncthing provides continuous synchronization. Configure multiple nodes for redundancy.

### Application Data Backup

```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/home/YOUR_USERNAME/backups"
mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/mdformat-$(date +%Y%m%d).tar.gz" \
  /opt/mdformat-plugin-template \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='.git'

# Keep only last 30 days
find "$BACKUP_DIR" -name "mdformat-*.tar.gz" -mtime +30 -delete
```

## References

- [Cloud-init Documentation](https://cloudinit.readthedocs.io/)
- [Hetzner Cloud Docs](https://docs.hetzner.com/cloud/)
- [Systemd Service Management](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Syncthing Documentation](https://docs.syncthing.net/)
- [mise Documentation](https://mise.jdx.dev/)
