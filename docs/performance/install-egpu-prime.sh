#!/bin/bash
# Installs the egpu-prime auto-switch service.
# Run with sudo from this directory.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root:  sudo $0" >&2
    exit 1
fi

install -m 0755 -o root -g root "$HERE/egpu-prime-switch" /usr/local/sbin/egpu-prime-switch
install -m 0644 -o root -g root "$HERE/egpu-prime.service" /etc/systemd/system/egpu-prime.service

systemctl daemon-reload
systemctl enable egpu-prime.service

echo
echo "Installed.  Test now without rebooting:"
echo "    sudo systemctl start egpu-prime.service"
echo "    journalctl -u egpu-prime.service -b -n 30"
echo
echo "To uninstall:"
echo "    sudo systemctl disable --now egpu-prime.service"
echo "    sudo rm /etc/systemd/system/egpu-prime.service /usr/local/sbin/egpu-prime-switch"
echo "    sudo systemctl daemon-reload"
