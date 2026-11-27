# Copilot & Agent Instructions for AmberClaw

- Maintain `main` as the sole permanent branch.
- Author commits as `Krish Ujeniya <100012208+krishujeniya@users.noreply.github.com>`.
- Execute all Python tasks exclusively via `uv` (`uv --directory amberclaw/backend ...`).
- Never commit secrets, `.env` files, or agent workspace metadata (`GEMINI.md`, `CLAUDE.md`, `.cursor/`, etc.).
- Keep Dockerfiles and compose files inside `deploy/docker/` for local parity; deploy static frontend to Cloudflare Pages via `.github/workflows/deploy.yml`.
