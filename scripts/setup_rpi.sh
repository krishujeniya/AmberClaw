#!/bin/bash
# AmberClaw AI OS - Raspberry Pi Setup Script
# This script automates the installation of AmberClaw as a system service on Raspberry Pi.

set -e

echo "🐾 Starting AmberClaw AI OS Setup for Raspberry Pi..."

# 1. Update and install base dependencies
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git build-essential

# 2. Install 'uv' for dependency management if not present
if ! command -v uv &> /dev/null; then
    echo "⚡ Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# 3. Create virtual environment and install dependencies
echo "🐍 Setting up Python environment..."
uv venv
source .venv/bin/activate
uv pip install -e .
uv pip install pyserial gpiozero

# 4. Create systemd service for AmberClaw Gateway
echo "⚙️ Creating systemd service..."
USER_NAME=$(whoami)
PROJECT_DIR=$(pwd)

CAT_SERVICE=$(cat <<EOF
[Unit]
Description=AmberClaw AI OS Gateway
After=network.target

[Service]
ExecStart=${PROJECT_DIR}/.venv/bin/python -m amberclaw.api.main
WorkingDirectory=${PROJECT_DIR}
User=${USER_NAME}
Restart=always
Environment=PYTHONPATH=${PROJECT_DIR}/src

[Install]
WantedBy=multi-user.target
EOF
)

echo "$CAT_SERVICE" | sudo tee /etc/systemd/system/amberclaw.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable amberclaw

echo "✅ Setup Complete!"
echo "🚀 Start AmberClaw with: sudo systemctl start amberclaw"
echo "📊 Check status with: sudo systemctl status amberclaw"
echo "🐾 Welcome to the AI OS era."
