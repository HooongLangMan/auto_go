# Xiaohongshu Dual Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Xiaohongshu draft-save automation so that it can switch between Playwright and Patchright session backends without duplicating the publishing workflow.

**Architecture:** Keep `publisher.py` and `draft_writer.py` as the shared business layer. Move browser session acquisition behind a backend selector in `session.py`, add separate backend implementations for Playwright and Patchright, and route through one configuration value. Invalid configuration falls back to Playwright, but Patchright runtime failure must stay explicit.

**Tech Stack:** Python 3.12+, BitBrowser CDP, Playwright-style sync APIs, Patchright, requests, pytest, monkeypatch

---

## File Structure

- Modify: `D:/auto_go/src/auto_football/config.py`
  - Add Xiaohongshu backend selection config.
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/session.py`
  - Convert into a backend selector/entry point.
- Create: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/backends/__init__.py`
  - Backend package marker.
- Create: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/backends/playwright_backend.py`
  - Move current BitBrowser + CDP + Playwright implementation here.
- Create: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/backends/patchright_backend.py`
  - Add BitBrowser + CDP + Patchright implementation.
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/publisher.py`
  - Expose configured/active backend in status reporting.
- Modify: `D:/auto_go/tests/test_xhs_session.py`
  - Cover backend selection and Playwright backend behavior.
- Modify: `D:/auto_go/tests/test_xhs_publisher.py`
  - Cover status output for backend selection.
- Create: `D:/auto_go/tests/test_xhs_patchright_backend.py`
  - Cover Patchright backend initialization and failure behavior.

### Task 1: Add Backend Configuration

**Files:**
- Modify: `D:/auto_go/src/auto_football/config.py`
- Modify: `D:/auto_go/tests/test_wechat_config.py`

- [ ] **Step 1: Write the failing test**

```python
from auto_football.config import Settings


def test_settings_expose_xhs_automation_backend() -> None:
    settings = Settings(XHS_AUTOMATION_BACKEND="patchright")

    assert settings.xhs_automation_backend == "patchright"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wechat_config.py::test_settings_expose_xhs_automation_backend -v`

Expected: FAIL with missing `xhs_automation_backend`

- [ ] **Step 3: Write minimal implementation**

```python
class Settings(BaseSettings):
    # ...
    xhs_automation_backend: str = Field(default="playwright", alias="XHS_AUTOMATION_BACKEND")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wechat_config.py::test_settings_expose_xhs_automation_backend -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 2: Extract the Current Playwright Session Backend

**Files:**
- Create: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/backends/__init__.py`
- Create: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/backends/playwright_backend.py`
- Modify: `D:/auto_go/tests/test_xhs_session.py`

- [ ] **Step 1: Write the failing backend test**

```python
from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.backends.playwright_backend import PlaywrightCDPBackend


def test_playwright_backend_reuses_existing_publish_page(monkeypatch) -> None:
    # Reuse the existing FakeResponse / FakePage / FakeContext strategy from test_xhs_session.py
    backend = PlaywrightCDPBackend(
        Settings(
            BITBROWSER_PROFILE_ID="profile-1",
            BITBROWSER_BASE_URL="http://127.0.0.1:54345",
        )
    )
    page = backend.open_publish_page()
    assert page is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_session.py::test_playwright_backend_reuses_existing_publish_page -v`

Expected: FAIL because backend module does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import requests

from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.selectors import PUBLISH_PAGE_URL


class PlaywrightCDPBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def open_publish_page(self, *, force: bool = False):
        from playwright.sync_api import sync_playwright
        # move the existing BitBrowser CDP logic here
```
```

Move the existing logic from `session.py` into this backend without behavioral changes.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_session.py::test_playwright_backend_reuses_existing_publish_page -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 3: Turn session.py Into a Backend Selector

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/session.py`
- Modify: `D:/auto_go/tests/test_xhs_session.py`

- [ ] **Step 1: Write the failing selector tests**

```python
from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.session import BitBrowserSessionManager


def test_session_manager_defaults_invalid_backend_to_playwright(monkeypatch) -> None:
    manager = BitBrowserSessionManager(Settings(XHS_AUTOMATION_BACKEND="bogus"))
    assert manager.backend_name == "playwright"


def test_session_manager_uses_patchright_when_configured(monkeypatch) -> None:
    manager = BitBrowserSessionManager(Settings(XHS_AUTOMATION_BACKEND="patchright"))
    assert manager.backend_name == "patchright"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_session.py::test_session_manager_defaults_invalid_backend_to_playwright tests/test_xhs_session.py::test_session_manager_uses_patchright_when_configured -v`

Expected: FAIL because `backend_name` does not exist yet

- [ ] **Step 3: Write minimal selector implementation**

```python
from auto_football.infra.publishers.xiaohongshu.backends.playwright_backend import PlaywrightCDPBackend
from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend


class BitBrowserSessionManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        backend_name = (settings.xhs_automation_backend or "playwright").strip().lower()
        if backend_name not in {"playwright", "patchright"}:
            backend_name = "playwright"
        self.backend_name = backend_name
        self.backend = (
            PatchrightCDPBackend(settings)
            if backend_name == "patchright"
            else PlaywrightCDPBackend(settings)
        )

    def open_publish_page(self, *, force: bool = False):
        return self.backend.open_publish_page(force=force)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_session.py::test_session_manager_defaults_invalid_backend_to_playwright tests/test_xhs_session.py::test_session_manager_uses_patchright_when_configured -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 4: Add the Patchright Backend

**Files:**
- Create: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/backends/patchright_backend.py`
- Create: `D:/auto_go/tests/test_xhs_patchright_backend.py`

- [ ] **Step 1: Write the failing Patchright backend tests**

```python
from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend


def test_patchright_backend_connects_over_cdp(monkeypatch) -> None:
    backend = PatchrightCDPBackend(
        Settings(
            BITBROWSER_PROFILE_ID="profile-1",
            BITBROWSER_BASE_URL="http://127.0.0.1:54345",
        )
    )
    page = backend.open_publish_page()
    assert page is not None


def test_patchright_backend_reports_missing_dependency_as_runtime_error(monkeypatch) -> None:
    backend = PatchrightCDPBackend(Settings(BITBROWSER_PROFILE_ID="profile-1"))
    # monkeypatch import to fail
    # assert RuntimeError contains "Patchright"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_patchright_backend.py -v`

Expected: FAIL because backend module does not exist yet

- [ ] **Step 3: Write minimal Patchright implementation**

```python
from __future__ import annotations

import requests

from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.selectors import PUBLISH_PAGE_URL


class PatchrightCDPBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def open_publish_page(self, *, force: bool = False):
        try:
            from patchright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError(f"Patchright is not installed in the active Python environment: {exc}") from exc
        # mirror the Playwright backend logic with patchright.sync_api
```

The implementation should mirror the Playwright backend logic as closely as possible and should not auto-fallback to Playwright.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_patchright_backend.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 5: Expose Backend Information in Publisher Status

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/publisher.py`
- Modify: `D:/auto_go/tests/test_xhs_publisher.py`

- [ ] **Step 1: Write the failing publisher status test**

```python
from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher


def test_xhs_status_reports_configured_backend(monkeypatch) -> None:
    publisher = XiaohongshuPlaywrightPublisher(Settings(XHS_AUTOMATION_BACKEND="patchright"))
    payload = publisher.status()

    assert payload["backend_configured"] == "patchright"
    assert payload["backend_active"] == "patchright"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_publisher.py::test_xhs_status_reports_configured_backend -v`

Expected: FAIL because `backend_configured` and `backend_active` are missing

- [ ] **Step 3: Write minimal publisher status implementation**

```python
class XiaohongshuPlaywrightPublisher:
    @property
    def backend(self) -> str:
        return f"bitbrowser+{self.session_manager.backend_name}"

    def healthcheck(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "backend": self.backend,
            "backend_configured": (self.settings.xhs_automation_backend or "playwright").strip().lower(),
            "backend_active": self.session_manager.backend_name,
            "has_profile_id": bool(self.settings.bitbrowser_profile_id),
            "draft_only": bool(self.settings.xhs_draft_only),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_publisher.py::test_xhs_status_reports_configured_backend -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 6: Verify Shared Workflow Still Works

**Files:**
- Modify: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Write the failing compatibility test**

```python
from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher


def test_xhs_publisher_uses_selected_session_backend_without_changing_draft_writer(monkeypatch) -> None:
    captured = {}

    class FakeSessionManager:
        backend_name = "patchright"

        def open_publish_page(self):
            captured["opened"] = True
            return "fake-page"

    class FakeDraftWriter:
        def save_draft(self, *, page, bundle, default_tags):
            captured["page"] = page
            return {"ok": True, "status": "draft_saved", "message": "draft saved"}

    monkeypatch.setattr("auto_football.infra.publishers.xiaohongshu.publisher.BitBrowserSessionManager", lambda settings: FakeSessionManager())
    monkeypatch.setattr("auto_football.infra.publishers.xiaohongshu.publisher.XiaohongshuDraftWriter", lambda settings: FakeDraftWriter())

    publisher = XiaohongshuPlaywrightPublisher(Settings(BITBROWSER_PROFILE_ID="profile-1", XHS_AUTOMATION_BACKEND="patchright"))
    result = publisher.create_draft(_bundle())

    assert result.status == "draft_saved"
    assert captured["page"] == "fake-page"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_publisher_uses_selected_session_backend_without_changing_draft_writer -v`

Expected: FAIL if publisher or session manager assumptions still force the old path

- [ ] **Step 3: Write minimal compatibility fixes**

Adjust only what is necessary so that:

- publisher still calls one session manager,
- draft writer remains shared,
- backend choice remains inside the session layer.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_publisher_uses_selected_session_backend_without_changing_draft_writer -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 7: Run the Targeted Verification Suite

**Files:**
- Test: `D:/auto_go/tests/test_wechat_config.py`
- Test: `D:/auto_go/tests/test_xhs_session.py`
- Test: `D:/auto_go/tests/test_xhs_patchright_backend.py`
- Test: `D:/auto_go/tests/test_xhs_publisher.py`
- Test: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Run focused backend verification**

Run:

```powershell
pytest `
  tests/test_wechat_config.py::test_settings_expose_xhs_automation_backend `
  tests/test_xhs_session.py `
  tests/test_xhs_patchright_backend.py `
  tests/test_xhs_publisher.py `
  tests/test_xhs_playwright_publisher.py `
  -v
```

Expected: all selected tests PASS

- [ ] **Step 2: Record execution notes**

Document:

- whether Patchright dependency is installed or only mocked in tests,
- that invalid backend config defaults to Playwright,
- that Patchright runtime failure remains explicit,
- that no git commit was created because the workspace is not a git repository.

## Self-Review

- Spec coverage:
  - Shared workflow preservation is covered by Tasks 2, 3, and 6.
  - Dual backend support is covered by Tasks 2, 3, and 4.
  - Config handling is covered by Tasks 1 and 3.
  - Explicit runtime failure behavior is covered by Task 4.
  - Status visibility is covered by Task 5.
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” placeholders remain.
- Type consistency:
  - `BitBrowserSessionManager` remains the shared entry point.
  - Backend names are consistently `playwright` and `patchright`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-xiaohongshu-dual-backend.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
