#!/bin/sh
set -e

REPO_URL="https://github.com/krishujeniya/AmberClaw.git"
TARGET_DIR="${AMBERCLAW_DIR:-AmberClaw}"

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

printf "==> Installing AmberClaw...\n"

if ! command_exists git; then
  echo "Error: git is required to clone AmberClaw." >&2
  exit 1
fi

if [ -d "$TARGET_DIR" ]; then
  printf "==> Directory '%s' already exists. Updating repository...\n" "$TARGET_DIR"
  cd "$TARGET_DIR"
  git pull --ff-only || true
else
  printf "==> Cloning into '%s'...\n" "$TARGET_DIR"
  git clone "$REPO_URL" "$TARGET_DIR"
  cd "$TARGET_DIR"
fi

if [ ! -f amberclaw/backend/.env ]; then
  if [ -f amberclaw/backend/.env.example ]; then
    cp amberclaw/backend/.env.example amberclaw/backend/.env
    printf "==> Created amberclaw/backend/.env from amberclaw/backend/.env.example\n"
  fi
fi

if command_exists uv; then
  printf "==> Syncing dependencies with uv...\n"
  uv --directory amberclaw/backend sync
  printf "\nAmberClaw is installed!\n"
  printf "To run doctor:    cd %s && uv --directory amberclaw/backend run amberclaw doctor\n" "$TARGET_DIR"
  printf "To start agent:   cd %s && uv --directory amberclaw/backend run amberclaw agent\n" "$TARGET_DIR"
elif command_exists python3; then
  printf "==> uv not found; checking python3 virtual environment...\n"
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python3 -m pip install --upgrade pip
  python3 -m pip install -e ./amberclaw/backend
  printf "\nAmberClaw is installed in virtualenv!\n"
  printf "Run: cd %s && . .venv/bin/activate && amberclaw doctor\n" "$TARGET_DIR"
else
  echo "Error: Python 3.11+ or uv is required to run AmberClaw." >&2
  exit 1
fi
