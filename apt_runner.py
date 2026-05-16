#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["toon-format>=0.9.0b1"]
# ///
"""
apt_runner.py — idempotent apt repo + key + pinning setup and package
install for a fresh Ubuntu/Kubuntu install.

All repos and packages are declared in apt.toml alongside this script:
  packages       packages to apt install at the end
  [ubuntu_pin]   Ubuntu archive uprank policy ({release} interpolated)
  [[repo]]       one block per third-party apt repo

Both repos use the modern layout:
  - GPG key in a non-globally-trusted location (NOT /etc/apt/trusted.gpg.d/)
  - .sources file with `Signed-By:` so each key is only honored for its repo

Cross-repo safety: apt-preferences uprank Ubuntu's main/updates/security
archives above the default priority of 500. Any third-party repo that
ships a package with the same name as one from Ubuntu loses to Ubuntu.
Third-party-only packages still install fine since no Ubuntu version
exists to compete with them. To let a specific third-party package
override Ubuntu, add a per-package pin at priority > 900 elsewhere in
/etc/apt/preferences.d/.

Hardening: /etc/apt/trusted.gpg.d/ is marked immutable (chattr +i) so
install scripts that follow the old `cp foo.gpg /etc/apt/trusted.gpg.d/`
pattern fail even as root. A DPkg::Pre/Post-Invoke hook auto-toggles
the immutable bit around any dpkg run so apt upgrades AND do-release-
upgrade work transparently (this was a real prior failure mode — a
release upgrade aborted mid-way because ubuntu-keyring tried to install
new files into the locked dir).

Safe to re-run. Designed for a fresh install with nothing but the base
system (no curl, no gnupg, no lsb-release) — only uv is required, to
satisfy the shebang.
"""

import os
import platform
import pwd
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from toon_format import encode

# apt requires files in preferences.d/ to have either no extension or `.pref`.
UBUNTU_PREF = Path("/etc/apt/preferences.d/ubuntu-archives.pref")
TRUSTED_GPGD = Path("/etc/apt/trusted.gpg.d")
TRUSTED_GPGD_HOOK = Path("/etc/apt/apt.conf.d/99-trusted-gpgd-autounlock")

SCRIPT = Path(__file__).resolve()
APT_TOML = SCRIPT.parent / "apt.toml"
FILES_DIR = SCRIPT.parent / "files"


def run(*cmd: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def write_file(path: Path, content: str, note: str = "") -> None:
    print(f">> Writing {path}" + (f" ({note})" if note else ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o644)


def policy_row(pkg: str) -> dict:
    """Parse `apt-cache policy <pkg>` into a flat row for the TOON summary."""
    out = subprocess.run(["apt-cache", "policy", pkg], capture_output=True, text=True).stdout
    lines = out.splitlines()
    installed = next((l.split(":", 1)[1].strip() for l in lines if l.strip().startswith("Installed:")), "(none)")
    candidate = next((l.split(":", 1)[1].strip() for l in lines if l.strip().startswith("Candidate:")), "(none)")
    # Skip /var/lib/dpkg/status — apt's "installed on disk" bookkeeping, not a real repo.
    # priority stays int so TOON emits it unquoted; 0 means "no match found".
    priority, source, matching, in_table = 0, "", False, False
    for line in lines:
        if line.strip() == "Version table:":
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("        "):  # source line (8+ space indent)
            if matching and not source:
                bits = line.split()
                if len(bits) >= 2 and bits[1] != "/var/lib/dpkg/status":
                    source = urlparse(bits[1]).hostname or bits[1]
        else:  # version line: " *** VERSION PRIO" or "     VERSION PRIO"
            tokens = line.replace("***", "").split()
            matching = len(tokens) >= 2 and tokens[0] == candidate
            if matching:
                priority = int(tokens[1])
    return {"package": pkg, "installed": installed, "candidate": candidate,
            "priority": priority, "source": source}


# Load config pre-sudo so TOML errors surface before the sudo re-exec.
with APT_TOML.open("rb") as f:
    config = tomllib.load(f)
repos = config.get("repo", [])
packages = config.get("packages", [])

if os.geteuid() != 0:
    print(">> Re-running under sudo")
    os.execvp("sudo", ["sudo", sys.executable, __file__, *sys.argv[1:]])

# Hand logs back to the invoking user so they're not stuck as root-owned.
# tee runs as root (post-sudo) but appends to an existing file, so the
# pre-set ownership sticks.
log_dir = SCRIPT.parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"{SCRIPT.stem}-{datetime.now():%Y%m%d-%H%M%S}.log"
log_file.touch()
if sudo_user := os.environ.get("SUDO_USER"):
    pw = pwd.getpwnam(sudo_user)
    for p in (log_dir, *log_dir.iterdir()):
        os.chown(p, pw.pw_uid, pw.pw_gid)
tee = subprocess.Popen(["tee", "-a", str(log_file)], stdin=subprocess.PIPE)
os.dup2(tee.stdin.fileno(), 1)
os.dup2(tee.stdin.fileno(), 2)
tee.stdin.close()
print(f">> Logging this run to {log_file}")
print(f">> Loaded config from {APT_TOML} ({len(repos)} repo(s), {len(packages)} package(s))")

osr = platform.freedesktop_os_release()
release = osr.get("VERSION_CODENAME") or osr.get("UBUNTU_CODENAME")
if not release:
    sys.exit("ERROR: could not determine release codename")
print(f">> Detected release codename: {release}")

# Install the hook BEFORE any apt operation: the very next apt-get auto-unlocks
# /etc/apt/trusted.gpg.d/ around dpkg, so no manual unlock is needed even when
# re-running against a system where the dir is already immutable.
hook_tmpl = (FILES_DIR / TRUSTED_GPGD_HOOK.name).read_text()
write_file(TRUSTED_GPGD_HOOK, hook_tmpl, "auto-unlock dir around dpkg runs")

pin = config["ubuntu_pin"]
pin_blocks = "\n\n".join(
    f"Package: *\nPin: release o=Ubuntu, a={s.format(release=release)}\nPin-Priority: {pin['priority']}"
    for s in pin["suites"]
)
pref_tmpl = (FILES_DIR / UBUNTU_PREF.name).read_text()
write_file(UBUNTU_PREF, pref_tmpl.format(priority=pin["priority"], pin_blocks=pin_blocks),
           "uprank Ubuntu archives above third-party default")

# A fresh system may lack curl/gnupg/ca-certificates.
os.environ["DEBIAN_FRONTEND"] = "noninteractive"
print(">> Refreshing base apt cache and installing prerequisites")
run("apt-get", "update")
run("apt-get", "install", "-y", "--no-install-recommends", "curl", "gnupg", "ca-certificates")

for repo in repos:
    name = repo["name"]
    keyring = Path(repo.get("keyring", f"/usr/share/keyrings/{name}.gpg"))
    source = Path(repo.get("source_path", f"/etc/apt/sources.list.d/{name}.sources"))
    print(f">> Installing {name} GPG key to {keyring}")
    keyring.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(repo["key_url"]) as r:
        data = r.read()
    # ASCII-armored keys start with the RFC 4880 §6.2 header; binary OpenPGP
    # packets start with a high-bit-set tag byte and never match.
    if data.lstrip().startswith(b"-----BEGIN PGP"):
        run("gpg", "--dearmor", "--yes", "-o", str(keyring), input=data)
    else:
        keyring.write_bytes(data)
    keyring.chmod(0o644)
    lines = [
        "Types: deb",
        f"URIs: {repo['uris']}",
        f"Suites: {repo.get('suites', 'stable').format(release=release)}",
        f"Components: {repo.get('components', 'main')}",
    ]
    # Omitting Architectures: lets apt use the host's dpkg arch (plus any
    # added via `dpkg --add-architecture`); only pin for repos that ship a
    # strict subset of arches the host supports.
    if archs := repo.get("architectures"):
        lines.append(f"Architectures: {archs}")
    lines.append(f"Signed-By: {keyring}")
    write_file(source, "\n".join(lines) + "\n")

print(">> Refreshing apt cache with new repos")
run("apt-get", "update")

# bash is included as a control: it should show priority 900 (the Ubuntu pin).
print()
print(">> Verification — installed/candidate versions and effective pin priorities:")
print(encode([policy_row(p) for p in [*packages, "bash"]]))
print()
print(f"--- {TRUSTED_GPGD} (expect 'i' attribute set) ---")
run("lsattr", "-d", str(TRUSTED_GPGD))

if packages:
    print(f"\n>> Installing packages: {' '.join(packages)}")
    run("apt-get", "install", "-y", *packages)

print(f"""
>> Done. Configured {len(repos)} repo(s) and {len(packages)} package(s).
   Edit apt.toml to manage repos and the package list, then re-run.

>> Note: {TRUSTED_GPGD} is now immutable. Apt/dpkg operations unlock
   it automatically via {TRUSTED_GPGD_HOOK}, so distro upgrades work.
   To make a manual change there: sudo chattr -i {TRUSTED_GPGD}""")
