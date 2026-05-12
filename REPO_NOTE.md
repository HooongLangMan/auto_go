# Repository Note

This GitHub repository contains the project source skeleton, core Python modules, docs, scripts, and example configuration.

It intentionally does **not** include the full local working environment or large generated artifacts.

## Not Included In GitHub

The following categories are intentionally excluded from the published repository:

- `.env` and any real API keys or local secrets
- local databases such as `*.db`, `*.sqlite`, `*.sqlite3`
- generated runtime artifacts under `generated/`
- temporary images under `temp_images/`
- local test/runtime helper caches such as `.superpowers/`, `.pytest_cache/`, `__pycache__/`
- the local Pixelle clone and its generated outputs under `temp_browser/`
- local browser binaries and other large environment-specific files
- temporary exploratory scripts such as `temp_*.py`

## What This Repository Is Meant To Preserve

This repository is mainly for:

- source code under `src/`
- project docs under `docs/`
- basic run scripts under `scripts/`
- dependency declarations such as `pyproject.toml` and `package*.json`
- example configuration in `.env.example`

## Local Runtime Requirements

If you want to reproduce the local workflow, you still need to prepare the runtime pieces manually on your machine, for example:

- Python environment(s)
- PostgreSQL / SQLite as needed
- Redis if used
- browser runtime for Playwright-related flows
- FFmpeg for video composition
- Pixelle local service if you want to run the Douyin video generation flow
- valid API keys for upstream services

## Douyin Video Flow Note

The repository includes the project-side Douyin video generation integration code, but the full local Pixelle runtime environment and its output artifacts are not committed here.

If you want to restore that path locally, you need to:

1. prepare Pixelle separately as a local sidecar service
2. configure the required LLM/TTS/runtime dependencies
3. run the project-side CLI commands against that local Pixelle service
