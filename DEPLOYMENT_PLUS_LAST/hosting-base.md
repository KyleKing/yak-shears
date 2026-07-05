# Base Hosting Setup: Syncthing & Caddy

This document contains the shared installation and configuration steps for Syncthing and Caddy that are used across multiple hosting scenarios (new setup, final deployment, etc.).

**See also:**
- **hosting-new.md** — Full, detailed guide for new VPS setup (canonical reference)
- **hosting-final.md** — Quick-start guide with links to full instructions
- **hosting-gemini.md** — Gemini-specific hosting notes

---

## Install Syncthing

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

**Configure Syncthing (from local laptop):**

```sh
# Port-Forward the UI to Sync (run on Laptop)
ssh -L 9998:localhost:8384 ubuntu-4gb-hel1-1
# Copy Laptop Device ID, accept from laptop, then edit the connection to check all three options (introducer, share, etc.), and confirm one more time from laptop
# <https://docs.syncthing.net/intro/getting-started.html#configuring>
```

---

## Install Caddy

Following: <https://caddyserver.com/docs/install#debian-ubuntu-raspbian>

```sh
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

---

## Configure Caddy

Following: <https://caddyserver.com/docs/quick-starts/https>

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
        X-Frame-Options "DENY
        # Controls how much referrer information is sent with requests.
        Referrer-Policy "same-origin
        # Content-Security-Policy "default-src 'self';" # Customize as needed
    }
}
EOF

# Example reviewing logs:
# sudo journalctl -u caddy --no-pager
```

---

## See Also

- Caddy documentation: <https://caddyserver.com/docs/running>
- Syncthing documentation: <https://docs.syncthing.net/>
