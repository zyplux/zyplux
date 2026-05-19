# sys-conf-py

Declarative Ubuntu/Kubuntu Wayland laptop config: apt repos + packages, eGPU
auto-PRIME at boot, and Brave + VS Code Insiders GPU-acceleration flags. PEP
723 single-file scripts; re-runnable; same script for first-run bootstrap and
ongoing upkeep.

## One-time setup

```bash
./src/install_from_urls.py            # user-scoped CLIs (bun, uv, claude, rustup, cargo-binstall)
./src/install_cargo_packages.py       # user-scoped cargo packages (just, just-lsp, rumdl, cargo-update)
sudo ./src/configure_with_apt.py      # repos, keys, pin priorities, full-upgrade, packages
sudo ./src/configure_gpu.py           # egpu-prime.service (boot-time prime-select)
sudo ./src/configure_apps.py          # Brave/Code Insiders launcher + flag overrides
sudo reboot
```

Or `just up` to chain all five.

After reboot, the egpu-prime service runs before SDDM and picks
`prime-select nvidia` when the eGPU is on PCI, else `prime-select on-demand`.
No manual commands.

## Config

| File | Purpose |
|---|---|
| `src/apt_config.toml` | repos, packages, pin priorities |
| `src/apps_config.toml` | Shared `[env]`; one section per app (`desktop` path + flags via `features`/`switches`/`local_state_flags`/`argv` as appropriate) |
| `src/url_config.toml` | user-scoped CLI installers (vendor `curl \| bash` scripts) |
| `src/cargo_config.toml` | user-scoped cargo packages installed via `cargo-binstall` |
| `src/files/` | static assets installed verbatim (apt hooks, prefs, egpu-prime sources) |
| `src/harness.py` | shared subprocess / log-tee / sudo plumbing imported by every playbook script |
| `logs/` | timestamped per-run log (chowned to invoking user) |

Edit a TOML, re-run the matching script (`configure_with_apt.py` for `apt_config.toml`,
`configure_apps.py` for `apps_config.toml`, `install_from_urls.py` for `url_config.toml`,
`install_cargo_packages.py` for `cargo_config.toml`; `configure_gpu.py` takes no config). All
scripts only rewrite files whose contents would actually change, so idle
re-runs are cheap.

## Verify after first boot

```bash
prime-select query                                 # -> nvidia (docked) or on-demand
journalctl -u egpu-prime.service -b -n 30          # boot-time switch decision
LIBVA_DRIVER_NAME=nvidia vainfo                    # VA-API profiles via NVDEC
```

In Brave, open `brave://gpu` -> *Graphics Feature Status* should show all
**Hardware accelerated**, and *Video Acceleration Information* should list
H.264/VP9/AV1 decode profiles.

## Further reading

- `docs/performance/README.md` — egpu-prime mechanics, PRIME modes, rescue path
- `docs/performance/brave-dumps/brave-config.md` — Brave config layers, flag rationale, rollout order

## Rollback

```bash
# eGPU service
sudo systemctl disable --now egpu-prime.service
sudo rm /etc/systemd/system/egpu-prime.service /usr/local/sbin/egpu-prime-switch

# Brave / Code Insiders flag overrides (back to system defaults)
rm ~/.local/share/applications/brave-browser.desktop
rm ~/.local/share/applications/code-insiders.desktop
# argv.json: open and manually remove the keys you don't want; the file is JSON
```
