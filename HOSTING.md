# Hosting

Selected VPS for similarity to local usage and Hetzner because of cost and IaC support (<https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/server>). See notes on deployment saved in 1Password for Hetzner (and more info on SSH Keys if needed: <https://community.hetzner.com/tutorials/howto-ssh-key>)

*Hetzner Web Console requires Rescue>Reset to get a root password when created with SSH: <https://docs.hetzner.com/cloud/servers/getting-started/vnc-console>*

## Automated Setup

The setup is fully automated using cloud-config. When creating the VPS, provide the cloud-config file (replace `<public_ssh_key>` with your actual public key).

The cloud-config will:
- Create user `holu` with sudo access and SSH key authentication
- Harden SSH (port 2222, no root login, key-only auth)
- Install and configure fail2ban for SSH
- Install mise for Python management, uv, git, Syncthing, Caddy
- Clone the yak-shears repo and install dependencies
- Setup systemd services for yak-shears, Syncthing, Caddy
- Configure Caddy as reverse proxy to yak-shears on port 8084
- Setup GitOps for automatic updates (polls every 5 minutes)
- Configure UFW firewall

After the VPS boots, the server should be running at `https://yak-shears.kyleking.me`.

## SSH Access

```sh
ssh -p 2222 holu@<vps-ip>
```

## Syncthing Setup

Syncthing is installed and running as user `holu`. To configure:

```sh
# Port-forward the UI (run on your laptop)
ssh -p 2222 -L 9998:localhost:8384 holu@<vps-ip>
# Then open http://localhost:9998 in browser
# Copy your laptop's Device ID, accept from VPS, enable all options
# See: https://docs.syncthing.net/intro/getting-started.html#configuring
```

The yak directory is at `/home/holu/Sync/yak-shears`.

## Manual Steps (if needed)

- Create initial user: `uv run yak-shears-users create test@example.com` (password: secure123)
- If repo is private, add SSH key for git: `su - holu -c "ssh-keygen -t ed25519 -C 'holu@vps'"` and add to GitHub

## GitOps Updates

The server automatically checks for git updates every 5 minutes. If changes are detected on the `main` branch, it pulls and restarts the service.

To check status:
```sh
systemctl status gitops-update.timer
journalctl -u gitops-update
```

## Monitoring

- Yak-shears service: `systemctl status yak-shears`
- Caddy logs: `journalctl -u caddy`
- Syncthing: `systemctl status syncthing@holu`

## Backup

All config is in the repo. User data is in `/home/holu/.yak-shears-users.json` and `/home/holu/Sync/yak-shears`.

## Future Improvements

- Blue-green deployment to avoid downtime during updates
- Health checks and rollback on failure
- Monitoring and alerting
