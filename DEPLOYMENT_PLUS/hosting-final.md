# Hosting — Quick-Start Guide

**This is a quick-start overview. For detailed instructions, see the full guides below.**

---

## Documentation Map

- **hosting-new.md** — **Canonical full reference guide** with all setup details (Syncthing, Caddy, FileBrowser, Traefik history)
- **hosting-base.md** — Shared installation and configuration for Syncthing and Caddy (referenced by other guides)
- **hosting-final.md** — This quick-start (you are here)
- **hosting-gemini.md** — Gemini-specific hosting notes

---

## Quick Setup Checklist

### Prerequisites

Selected VPS for similarity to local usage and Hetzner because of cost and IaC support:
- <https://registry.terraform.io/providers/hetznercloud/hcloud/latest/docs/resources/server>
- See notes on deployment saved in 1Password for Hetzner
- More SSH Key info: <https://community.hetzner.com/tutorials/howto-ssh-key>

### Steps

1. **Install Syncthing**
   Follow the complete instructions in **hosting-base.md** — Install Syncthing section

2. **Install and Configure Caddy**
   Follow the complete instructions in **hosting-base.md** — Install Caddy and Configure Caddy sections

3. **Set up FileBrowser** (optional, for file management UI)
   See **hosting-new.md** — FileBrowser section for details

4. **Additional Configuration Details**
   Refer to **hosting-new.md** for:
   - IPv6 setup notes
   - Hetzner Web Console access via Rescue/Reset
   - UFW firewall rules and persistence issues
   - FileBrowser systemd service configuration

---

## Common Tasks

| Task | Location |
|------|----------|
| Syncthing setup | hosting-base.md → Install Syncthing |
| Caddy installation & config | hosting-base.md → Install Caddy |
| FileBrowser setup | hosting-new.md → FileBrowser |
| UFW firewall issues | hosting-new.md → TODO section |
| Full reference | hosting-new.md |

---

## Notes

- The ufw rules may reset on VPS boot; see hosting-new.md TODO section for workarounds
- For Caddy running as a service: <https://caddyserver.com/docs/running>
- Consider using NixOS for reproducible deployments: <https://wrycode.com/reproducible-syncthing-deployments>

---

## Related Docs

- hosting-gemini.md — Gemini-specific configuration
- hosting-base.md — Shared setup instructions
- hosting-new.md — Full reference guide
