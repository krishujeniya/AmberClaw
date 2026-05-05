#!/usr/bin/env bash
set -e

echo "======================================"
echo "    AmberClaw Bootstrap Setup"
echo "======================================"

# Install dependencies if Docker is requested
if [ "$1" == "--docker" ]; then
    echo "[*] Setting up Docker environment..."
    if ! command -v docker &> /dev/null; then
        echo "Docker is not installed. Please install Docker first."
        exit 1
    fi
    docker-compose up -d
    echo "Docker environment started."
    exit 0
fi

# Check for uv or pip
if command -v uv &> /dev/null; then
    echo "[*] Using uv for installation..."
    uv tool install amberclaw
else
    echo "[*] Using pip for installation..."
    pip install amberclaw
fi

echo "[*] Running initial onboarding setup..."
amberclaw onboard

echo "======================================"
echo "    Setup Complete! "
echo "    Run 'amberclaw agent' to start."
echo "======================================"
