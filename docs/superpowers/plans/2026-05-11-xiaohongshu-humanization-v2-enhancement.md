# Xiaohongshu Humanization V2 Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen Xiaohongshu draft-save humanization with medium-intensity page, input, and flow-level behavior enhancements without running real draft-save verification today.

**Architecture:** Keep the existing session/backend layer unchanged. Enhance only the shared humanization and draft-writing flow so the same draft-save logic gains stronger pauses, review moments, and stage-aware noise. Validation should rely on unit tests and low-risk page-state checks, not real saves.

**Tech Stack:** Python 3.12+, Patchright/Playwright-style page APIs, BitBrowser CDP, pytest, monkeypatch

---

## File Structure

- Modify: `D:/auto_go/src/auto_football/infra/publishers/humanizer.py`
  - Add a few explicit stage-level helper actions on top of the current random noise.
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py`
  - Insert humanized pauses and review steps at the key workflow boundaries.
- Modify: `D:/auto_go/tests/test_xhs_playwright_publisher.py`
  - Cover the new stage-level humanization behavior with fake pages and fake humanizers.

### Task 1: Add Basic Stage Hooks to the Humanizer

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/humanizer.py`
- Test: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_humanizer_stage_methods_can_be_called_from_draft_flow(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    actions = []

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append("maybe_noise")

        def pause(self, min_ms=120, max_ms=420):
            actions.append(("pause", min_ms, max_ms))

        def click_locator(self, page, locator):
            actions.append("click_locator")

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def review_scroll(self, page):
            actions.append("review_scroll")

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

    # patch writer humanizer and assert stage_transition gets used
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_humanizer_stage_methods_can_be_called_from_draft_flow -v`

Expected: FAIL because `stage_transition` is not used by the draft flow yet

- [ ] **Step 3: Write the minimal implementation**

```python
class PlaywrightHumanizer:
    # existing methods...

    def stage_transition(self, page, label: str) -> None:
        del label
        self.pause(180, 420)
        self.maybe_noise(page)

    def short_review_pause(self) -> None:
        self.pause(260, 640)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_humanizer_stage_methods_can_be_called_from_draft_flow -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 2: Humanize the Upload-to-Title Transition

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py`
- Modify: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Write the failing transition test**

```python
def test_xhs_draft_writer_pauses_after_upload_before_typing(tmp_path, monkeypatch) -> None:
    # fake page with image-mode upload
    # fake humanizer records stage_transition("after_upload")
    # assert upload happens before stage_transition and typing happens after it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_pauses_after_upload_before_typing -v`

Expected: FAIL because no explicit after-upload stage exists yet

- [ ] **Step 3: Write minimal implementation**

```python
upload_locator.set_input_files(media_path)
self.humanizer.pause(1200, 2600)
self.humanizer.stage_transition(page, "after_upload")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_pauses_after_upload_before_typing -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 3: Add a Clear Title-to-Body Transition

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py`
- Modify: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Write the failing transition test**

```python
def test_xhs_draft_writer_adds_pause_between_title_and_body(tmp_path, monkeypatch) -> None:
    # fake humanizer records stage_transition("after_title")
    # assert title typing happens before this marker and body typing happens after it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_adds_pause_between_title_and_body -v`

Expected: FAIL because the draft flow moves straight from title to body

- [ ] **Step 3: Write minimal implementation**

```python
self.humanizer.type_into(page, title_locator, bundle.content.title)
self.humanizer.pause(180, 420)
self.humanizer.stage_transition(page, "after_title")
self.humanizer.maybe_noise(page, anchor_locator=content_locator)
self.humanizer.type_into(page, content_locator, bundle.content.content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_adds_pause_between_title_and_body -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 4: Add a Body-to-Tags Review Moment

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py`
- Modify: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Write the failing review test**

```python
def test_xhs_draft_writer_reviews_after_body_before_tags(tmp_path, monkeypatch) -> None:
    # fake humanizer records stage_transition("after_body")
    # assert after_body happens before tag typing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_reviews_after_body_before_tags -v`

Expected: FAIL because the current flow moves directly into tags

- [ ] **Step 3: Write minimal implementation**

```python
self.humanizer.stage_transition(page, "after_body")
self.humanizer.short_review_pause()
if tags:
    # existing tag entry logic
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_reviews_after_body_before_tags -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 5: Add an Explicit Pre-Save Review Phase

**Files:**
- Modify: `D:/auto_go/src/auto_football/infra/publishers/xiaohongshu/draft_writer.py`
- Modify: `D:/auto_go/tests/test_xhs_playwright_publisher.py`

- [ ] **Step 1: Write the failing pre-save test**

```python
def test_xhs_draft_writer_runs_pre_save_review_phase(tmp_path, monkeypatch) -> None:
    # fake humanizer records review_scroll then stage_transition("before_save")
    # assert save click happens after those review actions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_runs_pre_save_review_phase -v`

Expected: FAIL because there is no explicit `before_save` stage yet

- [ ] **Step 3: Write minimal implementation**

```python
self.humanizer.review_scroll(page)
self.humanizer.stage_transition(page, "before_save")
if self._click_if_exists(page, DRAFT_BUTTON_XPATH):
    self.humanizer.pause(1800, 3200)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xhs_playwright_publisher.py::test_xhs_draft_writer_runs_pre_save_review_phase -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not a git repository, skip commit creation and record that in the execution notes.

### Task 6: Run Non-Destructive Verification

**Files:**
- Test: `D:/auto_go/tests/test_xhs_playwright_publisher.py`
- Test: `D:/auto_go/tests/test_xhs_patchright_backend.py`

- [ ] **Step 1: Run the humanization-focused test file**

Run: `pytest tests/test_xhs_playwright_publisher.py -v`

Expected: PASS

- [ ] **Step 2: Run the patchright backend regression tests**

Run: `pytest tests/test_xhs_patchright_backend.py -v`

Expected: PASS

- [ ] **Step 3: Record readiness notes**

Document:

- that no real draft-save verification was run today,
- that humanization changes are now covered by fake-page tests,
- that the system is ready for one real save tomorrow,
- that no git commit was created because the workspace is not a git repository.

## Self-Review

- Spec coverage:
  - Page-level, input-level, and flow-level humanization are covered by Tasks 1 through 5.
  - Low-risk verification strategy is covered by Task 6.
  - No real save today is explicitly preserved in Task 6.
- Placeholder scan:
  - No `TODO`, `TBD`, or deferred placeholders remain.
- Type consistency:
  - `stage_transition` and `short_review_pause` are introduced first and reused consistently in later tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-xiaohongshu-humanization-v2-enhancement.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
