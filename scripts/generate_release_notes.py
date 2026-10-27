#!/usr/bin/env python3
# ruff: noqa: T201, S603, S607, PLR2004
"""Automated release notes generator using Conventional Commits."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def get_git_commits(limit: int = 50) -> list[str]:
    """Retrieve recent git commit messages."""
    try:
        res = subprocess.run(
            ["git", "log", f"-n{limit}", "--oneline", "--no-merges"],
            check=True,
            capture_output=True,
            text=True,
        )
        return [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
    except Exception:
        return []


def categorize_commits(commits: list[str]) -> dict[str, list[str]]:
    """Group commit messages by conventional commit prefix."""
    categories: dict[str, list[str]] = {
        "🚀 Features": [],
        "🛡️ Security & Zero-Trust": [],
        "🐞 Bug Fixes": [],
        "⚡ Performance & Reliability": [],
        "📚 Documentation & Guides": [],
        "🔧 Maintenance & Chores": [],
    }

    for item in commits:
        parts = item.split(" ", 1)
        if len(parts) < 2:
            continue
        sha, msg = parts[0], parts[1]
        formatted = f"- {msg} (`{sha}`)"

        lower = msg.lower()
        if lower.startswith("feat"):
            categories["🚀 Features"].append(formatted)
        elif lower.startswith("sec") or "security" in lower or "cve" in lower:
            categories["🛡️ Security & Zero-Trust"].append(formatted)
        elif lower.startswith("fix"):
            categories["🐞 Bug Fixes"].append(formatted)
        elif lower.startswith("perf") or "latency" in lower:
            categories["⚡ Performance & Reliability"].append(formatted)
        elif lower.startswith("docs"):
            categories["📚 Documentation & Guides"].append(formatted)
        else:
            categories["🔧 Maintenance & Chores"].append(formatted)

    return categories


def build_release_notes(version: str, categories: dict[str, list[str]]) -> str:
    """Format categories into markdown release notes."""
    lines = [
        f"# Release Notes — AmberClaw AI OS v{version}",
        "",
        "Enterprise-grade personal AI assistant framework and autonomous agent OS.",
        "",
    ]

    for title, items in categories.items():
        if items:
            lines.append(f"### {title}")
            lines.extend(items)
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate release notes from git commits."
    )
    parser.add_argument("--version", default="2026.0.1", help="Target release version")
    parser.add_argument("--out", help="Output file path (default: stdout)")
    args = parser.parse_args()

    commits = get_git_commits()
    categories = categorize_commits(commits)
    notes = build_release_notes(args.version, categories)

    if args.out:
        Path(args.out).write_text(notes, encoding="utf-8")
        print(f"Wrote release notes to {args.out}")
    else:
        print(notes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
