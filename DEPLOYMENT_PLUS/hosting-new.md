## ADD CLOUDFLARE A / CNAME RECORDS for ACME!
## Convert to Caddy? (https://www.programonaut.com/how-to-set-up-a-reverse-proxy-with-free-ssl-using-caddy)

# Hosting

Selected VPS for similarity to local usage and Hetzner because of cost and IaC support (<https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/server>). See notes on deployment saved in 1Password for Hetzner (and more info on SSH Keys if needed: <https://community.hetzner.com/tutorials/howto-ssh-key>)

Note: could use NixOS: <https://wrycode.com/reproducible-syncthing-deployments>

## Manual Setup

*Note: for ipv6, copy and replace '/64' with '1': <https://docs.hetzner.com/cloud/servers/getting-started/connecting-to-the-server>*

*Hetzner Web Console requires Rescue>Reset to get a root password when created with SSH: <https://docs.hetzner.com/cloud/servers/getting-started/vnc-console>*

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
sudo ufw allow ssh && sudo ufw allow http && sudo ufw allow https && \
    sudo ufw allow 22000/tcp && sudo ufw allow 22000/udp && sudo ufw allow 21027/udp && sudo ufw enable && sudo ufw status
```

```sh
# Port-Forward the UI to Sync (run on Laptop)
ssh -L 9998:localhost:8384 ubuntu-4gb-hel1-1
# Copy Laptop Device ID, accept from laptop, then edit the connection to check all three options (introducer, share, etc.), and confirm one more time from laptop
# <https://docs.syncthing.net/intro/getting-started.html#configuring>
```

## Configure Web Services

Follows: <https://github.com/ThomasSoum/traefik-binary-installation>

```sh
# Get desired version from: https://github.com/traefik/traefik/releases
mkdir ~/traefik-tmp
cd ~/traefik-tmp
curl -L https://github.com/traefik/traefik/releases/download/v3.3.4/traefik_v3.3.4_linux_armv6.tar.gz > traefik_linux_armv6.tar.gz
tar xzvf traefik_linux_armv6.tar.gz
# Move the binary
sudo cp ~/traefik-tmp/traefik /usr/local/bin/.
sudo chown root:root /usr/local/bin/traefik
sudo chmod 755 /usr/local/bin/traefik
cd ~ && rm -rf ~/traefik-tmp

# Give the Traefik binary the ability to bind to privileged ports (80, 443) as non-root.
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/traefik

# Setup Traefik user, group and permissions
sudo groupadd traefik
sudo useradd \
    -g traefik --no-user-group \
    -d /etc/traefik --no-create-home \
    -s /usr/sbin/nologin \
    -r traefik

# Create folder for the traefik static and dynamic config files and set permissions.
sudo mkdir /etc/traefik
sudo mkdir /etc/traefik/dynamic
sudo chown -R root:root /etc/traefik
sudo chown -R traefik:traefik /etc/traefik/dynamic
# Create Log
sudo touch /var/log/traefik.log
sudo chown traefik:traefik /var/log/traefik.log
# Create the .env file for the DNS Challenge credentials.
sudo touch /etc/traefik/.env
# Create the file where the certificates will be stored and set permissions.
sudo mkdir /etc/traefik/acme/
sudo touch /etc/traefik/acme/acme.json
sudo chmod 600 /etc/traefik/acme/acme.json
sudo chown traefik:traefik /etc/traefik/acme/acme.json

# Create a systemd service for Traefik
sudo tee "/lib/systemd/system/traefik.service" > /dev/null <<'EOF'
# /lib/systemd/system/traefik.service
[Unit]
Description=Traefik reverse proxy service
After=network-online.target
Wants=network-online.target systemd-networkd-wait-online.service

[Service]
Restart=on-failure

User=traefik
Group=traefik

ProtectHome=true
ProtectSystem=full
ReadWriteDirectories=/etc/traefik/acme
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true

TimeoutStopSec=300
EnvironmentFile=/etc/traefik/.env
ExecStart=/usr/local/bin/traefik --configFile=/etc/traefik/traefik.toml

[Install]
WantedBy=multi-user.target
EOF
sudo chown root:root /lib/systemd/system/traefik.service
sudo chmod 644 /lib/systemd/system/traefik.service
sudo systemctl daemon-reload

sudo tee "/etc/traefik/traefik.toml" > /dev/null <<'EOF'
# Traefik static configuration file (/etc/traefik/traefik.toml)
# See https://doc.traefik.io/traefik/getting-started/configuration-overview/#the-static-configuration
# and https://doc.traefik.io/traefik/reference/static-configuration/cli
[global]
checkNewVersion = true

[api]
dashboard = true
insecure = true

[log]
filePath = "/var/log/traefik.log"
format = "json"
level = "WARN"

[providers.file]
directory = "/etc/traefik/dynamic"
watch = true

[entryPoints.web]
address = ":80"

[entryPoints.web.http.redirections.entryPoint]
to = "websecure"
scheme = "https"

[entryPoints.websecure]
address = ":443"

[entryPoints.websecure.http.tls]
certResolver = "letsencrypt"

  [[entryPoints.websecure.http.tls.domains]]
  main = "yak-shears.kyleking.me"

[certificatesResolvers.letsencrypt.acme]
email = #Your email address
storage = "/etc/traefik/acme/acme.json"

  [certificatesResolvers.letsencrypt.acme.dnsChallenge]
  provider = "cloudflare"
  resolvers = [ "1.1.1.1:53", "1.0.0.1:53" ]
EOF
# Set email address
sudo vim /etc/traefik/traefik.toml

# Then set environment (example for Cloudflare from: <https://go-acme.github.io/lego/dns/cloudflare>)
# CLOUDFLARE_EMAIL=something@example.com
# CLOUDFLARE_API_KEY=some_api_key
sudo vim /etc/traefik/.env

# Configure dynamic provider for Go service on localhost
sudo tee "/etc/traefik/dynamic/dynamic.toml" > /dev/null <<'EOF'
[http.routers.app]
entryPoints = ["websecure"]
rule = "Host(`yak-shears.kyleking.me`)"
service = "app-service"

[[http.services.app-service.loadBalancer.servers]]
url = "http://127.0.0.1:8384"
EOF

# Now start!
sudo systemctl enable traefik.service
sudo systemctl start traefik.service
sudo systemctl status traefik.service
```

```sh
# Debugging:
sudo journalctl --boot -u traefik.service
sudo cat /var/log/traefik.log
sudo systemctl restart traefik.service
curl localhost:443

# From laptop:
ssh -L 8081:localhost:8080 ubuntu-4gb-hel1-1
# Open Traefik dashboard at localhost:8081
```

**Update: traefik was removed in favor of implementing Caddy**

```sh
sudo systemctl disable traefik.service
```

## FileBrowser

<https://github.com/filebrowser/filebrowser>

```sh
curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash
filebrowser config init --port 8084
/usr/local/bin/filebrowser -r /root/Sync
# While the above is running (TODO: because the systemctl configuration isn't working)
ssh -L 8084:localhost:8084 ubuntu-4gb-hel1-1

# Create a systemd service for FileBrowser
sudo tee "/lib/systemd/system/filebrowser.service" > /dev/null <<'EOF'
# Adapted from: /lib/systemd/system/traefik.service
# /lib/systemd/system/filebrowser.service
[Unit]
Description=Run Filebrowser at startup
# After=network-online.target
# Wants=network-online.target systemd-networkd-wait-online.service

[Service]
Restart=on-failure

# TODO: run as non-root
User=root

# ProtectHome=true
# ProtectSystem=full
# ReadWriteDirectories=/etc/traefik/acme
# CapabilityBoundingSet=CAP_NET_BIND_SERVICE
# AmbientCapabilities=CAP_NET_BIND_SERVICE
# NoNewPrivileges=true

# TimeoutStopSec=300
# EnvironmentFile=/etc/traefik/.env
ExecStart=/usr/local/bin/filebrowser -r /root/Sync
Type=simple

[Install]
WantedBy=multi-user.target
EOF
sudo chown root:root /lib/systemd/system/filebrowser.service
sudo chmod 644 /lib/systemd/system/filebrowser.service
sudo systemctl daemon-reload
```

## Caddy

Install: <https://caddyserver.com/docs/install#debian-ubuntu-raspbian>

```sh
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

HTTPS: <https://caddyserver.com/docs/quick-starts/https> and Gemini

```sh
sudo ufw allow OpenSSH && sudo ufw allow http && sudo ufw allow https && sudo ufw enable && sudo ufw status
# Check that the domain is configured
curl "https://cloudflare-dns.com/dns-query?name=yak-shears.kyleking.me&type=A" \
  -H "accept: application/dns-json"

tee "Caddyfile" > /dev/null <<'EOF'
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
        X-Frame-Options "DENY"
        # Controls how much referrer information is sent with requests.
        Referrer-Policy "same-origin"
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
2. Create script that copies all the manually managed files into a single location for version control (e.g. traefik config, sshd_config, maybe output of ufw, apt versions, Linux version, systemctl, etc.)
2. Create a basic HTMX app with authentication
2. Add list all files (show `<header> (<dir>/<filename>)` in future version)
2. Then per file, shows the raw text and then allows edits with HTMX submit (in future, default view is a preview where switching to edit would warn other users -- maybe locally is also git to track changes? How to use different users when editing the files from the go server?)
2. Further in the future, have GitOps where a cron-scheduled service checks for git changes, pulls, and then updates the service (how to handle downtime - maybe have flag in UI that current users can delay while working on changes?)

- 10-min golang+systemctl deploy: https://jonathanmh.com/p/deploying-go-apps-systemd-10-minutes-without-docker/
- Other options: https://www.ecosia.org/search?q=running%20golang+on+vps&addon=firefox&addonversion=5.2.0&method=topbar
- https://reintech.io/blog/writing-web-based-code-editor-go
- https://www.magicbell.com/blog/setting-up-htmx-and-templ-for-go
- https://gist.github.com/peterhellberg/60dcccab932f8446bacd2ceb57ba603d
- https://www.youtube.com/watch?v=x7v6SNIgJpE (Primeagen Golang+HTMX)
- Structure: https://www.youtube.com/watch?v=lVyIQV-op5I
