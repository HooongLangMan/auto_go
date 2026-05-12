# Auto Draft Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight selector service and CLI entrypoints that automatically choose one existing ready-to-publish draft and send it to the target platform draft flow without rerunning the content pipeline.

**Architecture:** Reuse the existing DB preview aggregation and publisher bundle flow. Add a shared `AutoDraftSelectorService` with common filtering plus platform-specific scoring, then expose it through CLI commands, implementing Xiaohongshu first and WeChat second under the same selector skeleton.

**Tech Stack:** Python 3.12+, Typer, SQLAlchemy-backed DB service, pytest, monkeypatch

---

## File Structure

- Create: `D:/auto_go/src/auto_football/domain/services/auto_draft_selector_service.py`
  - Shared candidate filtering and platform-specific scoring.
- Modify: `D:/auto_go/src/auto_football/cli.py`
  - Add `xhs-auto-draft` and `wechat-auto-draft` commands.
- Modify: `D:/auto_go/tests/test_cli_entrypoint.py`
  - Cover new CLI command behavior.
- Create: `D:/auto_go/tests/test_auto_draft_selector_service.py`
  - Cover common filtering and platform-specific scoring.

### Task 1: Add Service-Level Selection Tests

**Files:**
- Create: `D:/auto_go/tests/test_auto_draft_selector_service.py`

- [ ] **Step 1: Write the failing test for Xiaohongshu selection**

```python
from auto_football.domain.services.auto_draft_selector_service import AutoDraftSelectorService


def test_selector_prefers_ready_xhs_content_with_images_and_better_length() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 1,
            "home_team": "A",
            "away_team": "B",
            "contents": [
                {
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "short",
                    "title": "short title",
                    "images": ["a.png"],
                }
            ],
        },
        {
            "match_id": 2,
            "home_team": "C",
            "away_team": "D",
            "contents": [
                {
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "x" * 320,
                    "title": "better title",
                    "images": ["b.png"],
                }
            ],
        },
    ]

    picked = service.select_from_preview_payloads(payloads, platform="xiaohongshu")

    assert picked["match_id"] == 2
```

- [ ] **Step 2: Write the failing test for WeChat filtering**

```python
def test_selector_rejects_short_wechat_content() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 10,
            "home_team": "Home",
            "away_team": "Away",
            "contents": [
                {
                    "platform": "wechat",
                    "status": "ready_to_publish",
                    "content": "x" * 350,
                    "title": "too short",
                    "images": [],
                }
            ],
        }
    ]

    picked = service.select_from_preview_payloads(payloads, platform="wechat")

    assert picked is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_auto_draft_selector_service.py -v`

Expected: FAIL because `AutoDraftSelectorService` does not exist yet

- [ ] **Step 4: Write minimal implementation**

```python
from __future__ import annotations


class AutoDraftSelectorService:
    def select_from_preview_payloads(self, payloads, *, platform: str):
        candidates = []
        for payload in payloads:
            for content in payload.get("contents", []):
                if content.get("platform") != platform:
                    continue
                if content.get("status") != "ready_to_publish":
                    continue
                if not content.get("title") or not content.get("content"):
                    continue
                if platform == "xiaohongshu" and not content.get("images"):
                    continue
                if platform == "wechat" and len(content.get("content") or "") < 800:
                    continue
                score = self._score(platform, content)
                candidates.append((score, payload, content))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, payload, content = candidates[0]
        return {"match_id": payload["match_id"], "payload": payload, "content": content}

    def _score(self, platform: str, content: dict) -> int:
        length = len(content.get("content") or "")
        image_bonus = 100 if content.get("images") else 0
        if platform == "xiaohongshu":
            return image_bonus + min(length, 500)
        return min(length, 2000)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_auto_draft_selector_service.py -v`

Expected: PASS

### Task 2: Add Bundle Resolution Tests

**Files:**
- Modify: `D:/auto_go/tests/test_auto_draft_selector_service.py`

- [ ] **Step 1: Write the failing bundle-selection test**

```python
def test_selector_returns_reasonable_content_payload_reference() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 11,
            "home_team": "Home",
            "away_team": "Away",
            "contents": [
                {
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "x" * 300,
                    "title": "selected title",
                    "images": ["cover.png"],
                }
            ],
        }
    ]

    picked = service.select_from_preview_payloads(payloads, platform="xiaohongshu")

    assert picked["content"]["title"] == "selected title"
    assert picked["payload"]["home_team"] == "Home"
```

- [ ] **Step 2: Run test to verify it fails if result shape is incomplete**

Run: `pytest tests/test_auto_draft_selector_service.py::test_selector_returns_reasonable_content_payload_reference -v`

Expected: FAIL if the returned structure is not yet complete

- [ ] **Step 3: Adjust implementation minimally**

Return both:

- the chosen preview payload
- the chosen content block
- the chosen match id

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auto_draft_selector_service.py::test_selector_returns_reasonable_content_payload_reference -v`

Expected: PASS

### Task 3: Add CLI Tests for Auto Draft Commands

**Files:**
- Modify: `D:/auto_go/tests/test_cli_entrypoint.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
def test_xhs_auto_draft_command_selects_and_saves(monkeypatch) -> None:
    from typer.testing import CliRunner
    from auto_football.cli import app

    runner = CliRunner()
    captured = {}

    class FakeDB:
        def __init__(self, settings):
            pass

        def get_preview_payloads(self, **kwargs):
            return [{
                "match_id": 5,
                "home_team": "Home",
                "away_team": "Away",
                "contents": [{
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "x" * 300,
                    "title": "good",
                    "images": ["cover.png"],
                }],
            }]

        def get_match_bundle(self, match_id):
            return {
                "match": "fake-match",
                "contents": {"xiaohongshu": "fake-content"},
            }

        def log_publish(self, match_id, result):
            captured["logged"] = (match_id, result.status)

    class FakePublisher:
        def __init__(self, settings):
            pass

        def create_draft(self, bundle):
            class Result:
                status = "draft_saved"
                def model_dump(self):
                    return {"status": "draft_saved"}
            return Result()

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.XiaohongshuPlaywrightPublisher", FakePublisher)

    result = runner.invoke(app, ["xhs-auto-draft"])

    assert result.exit_code == 0
    assert "match_id=5" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_entrypoint.py -k "auto_draft" -v`

Expected: FAIL because command does not exist yet

- [ ] **Step 3: Write minimal CLI implementation**

```python
@app.command("xhs-auto-draft")
def xhs_auto_draft() -> None:
    settings = get_settings()
    db = Database(settings)
    selector = AutoDraftSelectorService()
    picked = selector.select_from_preview_payloads(
        db.get_preview_payloads(limit_matches=12),
        platform="xiaohongshu",
    )
    if picked is None:
        typer.echo("No eligible xiaohongshu draft candidate found.")
        raise typer.Exit(code=1)
    bundle = db.get_match_bundle(picked["match_id"])
    content = bundle["contents"].get("xiaohongshu")
    publisher = XiaohongshuPlaywrightPublisher(settings)
    result = publisher.create_draft(PublishBundle(match=bundle["match"], content=content))
    db.log_publish(picked["match_id"], result)
    typer.echo(f"Selected match_id={picked['match_id']}")
    typer.echo(json_dumps(result.model_dump()))
```

Add the analogous `wechat-auto-draft` command, but route through `WechatPublisher`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_entrypoint.py -k "auto_draft" -v`

Expected: PASS

### Task 4: Add a WeChat-Specific Selector Test

**Files:**
- Modify: `D:/auto_go/tests/test_auto_draft_selector_service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_selector_prefers_longer_wechat_content_when_both_are_ready() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 21,
            "contents": [{"platform": "wechat", "status": "ready_to_publish", "title": "a", "content": "x" * 850, "images": []}],
        },
        {
            "match_id": 22,
            "contents": [{"platform": "wechat", "status": "ready_to_publish", "title": "b", "content": "x" * 980, "images": []}],
        },
    ]

    picked = service.select_from_preview_payloads(payloads, platform="wechat")

    assert picked["match_id"] == 22
```

- [ ] **Step 2: Run test to verify it fails if score ordering is wrong**

Run: `pytest tests/test_auto_draft_selector_service.py::test_selector_prefers_longer_wechat_content_when_both_are_ready -v`

Expected: FAIL if WeChat scoring is still incomplete

- [ ] **Step 3: Adjust scoring minimally**

Prefer longer WeChat content after the minimum threshold is satisfied.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auto_draft_selector_service.py::test_selector_prefers_longer_wechat_content_when_both_are_ready -v`

Expected: PASS

### Task 5: Run Non-Destructive Verification

**Files:**
- Test: `D:/auto_go/tests/test_auto_draft_selector_service.py`
- Test: `D:/auto_go/tests/test_cli_entrypoint.py`

- [ ] **Step 1: Run selector and CLI tests**

Run:

```powershell
pytest `
  tests/test_auto_draft_selector_service.py `
  tests/test_cli_entrypoint.py -k "auto_draft" `
  -v
```

Expected: PASS

- [ ] **Step 2: Record readiness notes**

Document:

- that the selector service consumes existing DB payloads only,
- that no real platform draft action was executed during this verification,
- that Xiaohongshu is the first intended live target,
- that no git commit was created because the workspace is not a git repository.

## Self-Review

- Spec coverage:
  - Shared skeleton + platform-specific scoring is covered by Tasks 1, 2, and 4.
  - Xiaohongshu-first CLI support is covered by Task 3.
  - Non-destructive verification is covered by Task 5.
- Placeholder scan:
  - No `TODO`, `TBD`, or vague implementation placeholders remain.
- Type consistency:
  - The selector result shape remains consistent across tests and CLI integration.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-auto-draft-selector.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
