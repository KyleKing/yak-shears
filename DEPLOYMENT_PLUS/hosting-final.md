# Hosting

Selected VPS for similarity to local usage and Hetzner because of cost and IaC support (<https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/server>). See notes on deployment saved in 1Password for Hetzner (and more info on SSH Keys if needed: <https://community.hetzner.com/tutorials/howto-ssh-key>)

*Hetzner Web Console requires Rescue>Reset to get a root password when created with SSH: <https://docs.hetzner.com/cloud/servers/getting-started/vnc-console>*

## Install SyncThing

Following: <https://idroot.us/install-syncthing-ubuntu-24-04>

```sh
sudo apt update -y && sudo apt upgrade -y && sudo apt autoremove

sudo apt install gnupg2 curl apt-transport-https -y

# Follow instructions from: https://apt.syncthing.net
sudo mkdir -p /etc/apt/keyrings
sudo curl -L -o /etc/apt/keyrings/syncthing-archive-keyring.gpg https://syncthing.net/release-key.gpg
# Add the "stable" channel to your APT sources:
echo "deb [signed-by=/etc/apt/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list
sudo apt update
sudo apt install syncthing
syncthing --version

# Warning: consider making a non-root user for the application in a future iteration
sudo systemctl enable syncthing@root.service
sudo systemctl start syncthing@root.service
sudo systemctl status syncthing@root.service

# Keep SSH, turn on web, and allow ports for Syncthing
sudo ufw allow ssh && sudo ufw allow http && sudo ufw allow https &&
	sudo ufw allow 22000/tcp && sudo ufw allow 22000/udp && sudo ufw allow 21027/udp && sudo ufw enable && sudo ufw status
```

```sh
# Port-Forward the UI to Sync (run on Laptop)
ssh -L 9998:localhost:8384 ubuntu-4gb-hel1-1
# Copy Laptop Device ID, accept from laptop, then edit the connection to check all three options (introducer, share, etc.), and confirm one more time from laptop
# <https://docs.syncthing.net/intro/getting-started.html#configuring>
```

## Install Caddy

Following: <https://caddyserver.com/docs/install#debian-ubuntu-raspbian>

```sh
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Following: <https://caddyserver.com/docs/quick-starts/https> and Gemini

```sh
sudo ufw allow OpenSSH && sudo ufw allow http && sudo ufw allow https && sudo ufw enable && sudo ufw status
# Check that the domain is configured
curl "https://cloudflare-dns.com/dns-query?name=yak-shears.kyleking.me&type=A" \
	-H "accept: application/dns-json"

tee "Caddyfile" >/dev/null <<'EOF'
{
    email dev.act.kyle@gmail.com  # Recommended for Let's Encrypt notifications
}

yak-shears.kyleking.me {
    # 8384 for Syncthing fails because of host check errors as designed
    reverse_proxy localhost:8084 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
    header {
        # (HSTS): Forces browsers to always use HTTPS.
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        # Prevents browsers from MIME-sniffing
        X-Content-Type-Options "nosniff"
        # Helps prevent clickjacking attacks.
        X-Frame-Options "DENY
        # Controls how much referrer information is sent with requests.
        Referrer-Policy "same-origin
        # Content-Security-Policy "default-src 'self';" # Customize as needed
    }
}
EOF

# # Example reviewing logs:
# sudo journalctl -u caddy --no-pager
```

## TODO

1. The ufw rules appear to reset on VPS boot. I may need to edit the defaults?
1. And keep Caddy running: <https://caddyserver.com/docs/running>
1. Create script that copies all the manually managed files into a single location for version control (e.g. traefik config, sshd_config, maybe output of ufw, apt versions, Linux version, systemctl, etc.)
1. Create a basic HTMX app with authentication
1. Add list all files (show `<header> (<dir>/<filename>)` in future version)
1. Then per file, shows the raw text and then allows edits with HTMX submit (in future, default view is a preview where switching to edit would warn other users -- maybe locally is also git to track changes? How to use different users when editing the files from the go server?)
1. Further in the future, have GitOps where a cron-scheduled service checks for git changes, pulls, and then updates the service (how to handle downtime - maybe have flag in UI that current users can delay while working on changes?)
   - 10-min golang+systemctl deploy: https://jonathanmh.com/p/deploying-go-apps-systemd-10-minutes-without-docker/
   - Other options: https://www.ecosia.org/search?q=running%20golang+on+vps&addon=firefox&addonversion=5.2.0&method=topbar
   - https://reintech.io/blog/writing-web-based-code-editor-go
   - https://www.magicbell.com/blog/setting-up-htmx-and-templ-for-go
   - https://gist.github.com/peterhellberg/60dcccab932f8446bacd2ceb57ba603d
   - https://www.youtube.com/watch?v=x7v6SNIgJpE (Primeagen Golang+HTMX)
   - Structure: https://www.youtube.com/watch?v=lVyIQV-op5I
