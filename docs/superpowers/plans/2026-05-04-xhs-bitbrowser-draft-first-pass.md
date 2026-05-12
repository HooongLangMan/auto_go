# Xiaohongshu BitBrowser Draft First Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-pass Xiaohongshu draft-only publishing flow that connects to an existing BitBrowser profile and saves a single match's图文内容 into the Xiaohongshu creator draft box.

**Architecture:** Reuse the existing `xhs-publish-match --match-id` CLI entry, but route it through the new `infra.publishers.xiaohongshu` package. Keep BitBrowser profile/session concerns in `session.py`, page selectors in `selectors.py`, and page interactions in `draft_writer.py`, so later Douyin and future XHS changes stay isolated from the pipeline and CLI.

**Tech Stack:** Python 3.13, Pydantic Settings, Playwright-compatible browser control via BitBrowser local API, pytest

---

### Task 1: Discover BitBrowser Session Contract

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/session.py`
- Test: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] Probe the local BitBrowser API on `http://127.0.0.1:54345` to identify the endpoint for opening or attaching to profile `ccb11b7c74294e1d9d00efcac642b237`.
- [ ] Record the minimum response fields needed to launch or attach Playwright.
- [ ] Implement a concrete `BitBrowserSessionManager.open_publish_page()` that either:
  - opens the configured profile via the local API and returns a page handle, or
  - attaches to an already-open profile page and navigates it to the Xiaohongshu publish URL.

### Task 2: Implement Login Check And Draft Writer

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/selectors.py`
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py`
- Test: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] Add explicit login-state selectors.
- [ ] Implement `save_draft(page=..., bundle=..., default_tags=...)` with this order:
  - validate local media path exists
  - validate login state
  - upload the first image
  - fill title
  - fill body
  - add tags
  - click `存草稿`
  - return a structured dict like `{"ok": True, "status": "draft_saved", "message": "..."}`.

### Task 3: Harden Publisher Integration

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/publisher.py`
- Modify: `D:/auto_go/src/auto_football/cli.py`
- Test: `D:/auto_go/tests/test_xhs_cli_publish.py`

- [ ] Keep `create_draft(bundle)` draft-only.
- [ ] Preserve the existing CLI contract:
  - `python -m auto_football.cli xhs-publish-match --match-id <id>`
- [ ] Ensure failures return readable statuses:
  - missing profile id
  - page not logged in
  - missing media
  - draft button not found
  - BitBrowser API error

### Task 4: Verify Against The Current Codebase Baseline

**Files:**
- Test: `D:/auto_go/tests/test_xhs_playwright_publisher.py`
- Test: `D:/auto_go/tests/test_xhs_cli_publish.py`
- Test: `D:/auto_go/tests/test_xhs_publisher.py`

- [ ] Run targeted publisher tests.
- [ ] Run full `pytest -q`.
- [ ] If the BitBrowser session contract works locally, do one manual end-to-end dry validation against a real match id and stop at draft save.
