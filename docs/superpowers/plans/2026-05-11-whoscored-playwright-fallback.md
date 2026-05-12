# WhoScored Playwright Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a targeted Playwright fallback for WhoScored so missing cached schedule/preview data does not block availability enrichment for a specific match.

**Architecture:** Keep the existing `soccerdata` / cache-first `WhoScoredClient` path, but when the target match cannot be found in cached schedule data, invoke a small Playwright-backed fetcher that loads the relevant preview page and extracts missing-player / availability information into the existing snapshot schema.

**Tech Stack:** Python 3.12+, pytest, existing `WhoScoredClient`, Playwright (new Python dependency or local runtime integration), lxml / HTML parsing.

---

### Task 1: Add Regression Tests For Fallback Activation

**Files:**
- Modify: `tests/test_whoscored_schedule_pool.py`
- Modify: `tests/test_whoscored_preview_cache.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_whoscored_match_snapshot_uses_playwright_fallback_when_schedule_misses() -> None:
    ...
    assert calls["playwright"] == 1
    assert snapshot["home_missing"] == [...]
```

```python
def test_whoscored_playwright_html_parser_extracts_missing_players() -> None:
    ...
    assert parsed["summary"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py -q`
Expected: FAIL because no Playwright fallback exists yet.

- [ ] **Step 3: Implement the minimal production changes**

```python
# Add WhoScored fallback fetch + parse helpers in clients.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py
git commit -m "test: add whoscored playwright fallback coverage"
```

### Task 2: Implement Targeted Playwright Preview Fetch

**Files:**
- Modify: `src/auto_football/clients.py`

- [ ] **Step 1: Write the failing behavior test**

```python
def test_whoscored_build_match_documents_returns_fallback_snapshot_when_preview_page_found() -> None:
    assert docs[0].payload["home_missing"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py -q`
Expected: FAIL because fallback path is absent.

- [ ] **Step 3: Write minimal implementation**

```python
def _fetch_preview_html_playwright(...):
    ...
```

```python
def _build_match_snapshot_via_playwright(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/clients.py tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py
git commit -m "feat: add targeted whoscored playwright fallback"
```

### Task 3: Verify Real Sample Behavior

**Files:**
- No source-file changes required unless verification reveals a bug

- [ ] **Step 1: Run focused client verification**

Run: a one-off Python script invoking `WhoScoredClient.get_match_snapshot("Premier League", "Liverpool", "Chelsea", run_date=date(2026, 5, 8))`
Expected: non-`None` snapshot or a concrete logged failure reason from the Playwright fallback path

- [ ] **Step 2: Run relevant regression suite**

Run: `pytest tests/test_fbref_reader_integration_contract.py tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py tests/test_whoscored_integration_path.py -q`
Expected: PASS

- [ ] **Step 3: Commit if verification required code changes**

```bash
git add src/auto_football/clients.py tests/test_fbref_reader_integration_contract.py tests/test_whoscored_schedule_pool.py tests/test_whoscored_preview_cache.py tests/test_whoscored_integration_path.py
git commit -m "fix: stabilize whoscored fallback verification path"
```
