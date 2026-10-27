#!/usr/bin/env bash
set -euo pipefail

# AmberClaw Systemd Service Installation Script

if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (e.g. sudo ./install-systemd.sh)" 1>&2
   exit 1
fi

echo "Installing AmberClaw Systemd Services..."

# Create system user if not present
if ! id "amberclaw" &>/dev/null; then
    useradd -r -s /bin/false -d /opt/amberclaw amberclaw
    echo "Created service user: amberclaw"
fi

mkdir -p /opt/amberclaw/data /opt/amberclaw/logs
chown -R amberclaw:amberclaw /opt/amberclaw

cp deploy/systemd/amberclaw-gateway.service /etc/systemd/system/
cp deploy/systemd/amberclaw-agent.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable amberclaw-gateway.service
systemctl enable amberclaw-agent.service

echo "AmberClaw systemd services installed and enabled successfully."
echo "Use 'systemctl start amberclaw-gateway' to start the service."
