# WeChat Longform Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate WeChat generation into a single longform path that produces reader-safe 800-1200 character pre-match articles, longer recap copy, and never leaks raw source fragments into the final body.

**Architecture:** Remove the duplicate WeChat method definitions in `pipeline.py` and replace them with one final set of WeChat helpers. The surviving path should combine angle-driven candidate generation, paragraph gating, reader-safe knowledge rendering, and longform expansion so the final chosen candidate is suitable for公众号 publication.

**Tech Stack:** Python 3.12+, existing LangGraph pipeline, Pydantic data models, pytest.

---

### Task 1: Add Regression Tests For WeChat Longform Requirements

**Files:**
- Modify: `tests/test_wechat_fallback_diversity.py`
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_wechat_angle_fallback_reaches_longform_target(tmp_path) -> None:
    assert 800 <= len(candidate.content) <= 1200
```

```python
def test_wechat_stage0_content_is_reader_safe_and_longform(tmp_path) -> None:
    assert len(content["content"]) >= 800
    assert "[clubelo]" not in content["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py -q`
Expected: FAIL because current WeChat bodies are too short and still rely on mixed legacy/current helper paths.

- [ ] **Step 3: Implement the minimal production changes**

```python
# Add a longform-expansion helper and route WeChat fallbacks through it.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py
git commit -m "test: add wechat longform publication regressions"
```

### Task 2: Consolidate Duplicate WeChat Helpers

**Files:**
- Modify: `src/auto_football/pipeline.py`

- [ ] **Step 1: Write the failing structural test**

```python
def test_pipeline_keeps_single_wechat_helper_definition() -> None:
    assert source.count("def _fallback_wechat_variant") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wechat_fallback_diversity.py -q`
Expected: FAIL because the file currently contains duplicate WeChat helper definitions.

- [ ] **Step 3: Write minimal implementation**

```python
# Remove duplicate helper bodies and keep one final implementation for:
# - _fallback_wechat_variant
# - _fallback_wechat_result
# - _fallback_wechat_hot_recap
# - _apply_section_rules_to_generated_content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/pipeline.py tests/test_wechat_fallback_diversity.py
git commit -m "refactor: consolidate duplicate wechat helpers"
```

### Task 3: Expand WeChat Bodies To Publication Length

**Files:**
- Modify: `src/auto_football/pipeline.py`
- Modify: `src/auto_football/clients.py`

- [ ] **Step 1: Write the failing behavior test**

```python
def test_wechat_candidate_pool_prefers_longform_publishable_copy(tmp_path) -> None:
    assert all(len(item.content) >= 800 for item in wechat_candidates[:1])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: FAIL because the chosen WeChat candidates are still only a few hundred characters.

- [ ] **Step 3: Write minimal implementation**

```python
def _expand_wechat_longform(...):
    ...
```

```python
def _reader_safe_knowledge_summary(...):
    ...
```

```python
if plan.platform is Platform.WECHAT:
    content = self._expand_wechat_longform(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/pipeline.py src/auto_football/clients.py tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py
git commit -m "feat: expand wechat candidates to longform publication length"
```

### Task 4: Verify End-To-End Reader-Facing Output

**Files:**
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Add end-to-end assertions**

```python
assert len(wechat_contents[0]["content"]) >= 800
assert "待补充" not in wechat_contents[0]["content"]
assert "[openfootball]" not in wechat_contents[0]["content"]
```

- [ ] **Step 2: Run focused verification suite**

Run: `pytest tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py tests/test_content_pipeline_phase1.py -q`
Expected: PASS

- [ ] **Step 3: Run broader regression suite**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_style_diversification.py tests/test_wechat_fallback_diversity.py tests/test_content_validation_service.py tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_stage0_smoke_baseline.py
git commit -m "test: verify wechat publication output end to end"
```
