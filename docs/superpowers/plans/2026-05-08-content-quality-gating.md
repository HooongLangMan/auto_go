# Content Quality Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent placeholder text, raw source fragments, and broken comparison sentences from reaching stored content or previews.

**Architecture:** Add a post-generation content-quality gate for WeChat text that removes or rewrites bad paragraphs before final persistence. The gate should work on paragraph semantics, not on one-off string replacements: skip whole sections when required signals are missing, reject raw ingestion artifacts, and only keep comparison sentences when both sides are complete.

**Tech Stack:** Python 3.12+, existing pipeline helpers, pytest, SQLAlchemy-backed preview path.

---

### Task 1: Add Regression Tests For Dirty Paragraph Suppression

**Files:**
- Modify: `tests/test_content_validation_service.py`
- Modify: `tests/test_wechat_fallback_diversity.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_opening_line_handles_chinese_and_english_sentence_boundaries() -> None:
    assert ContentValidationService.opening_line("主队更稳。客队波动更大。") == "主队更稳"
```

```python
def test_wechat_hot_recap_skips_placeholder_form_comparison(tmp_path) -> None:
    content = pipeline._fallback_wechat_hot_recap(match_without_form)
    assert "待补充 vs 待补充" not in content.content
```

```python
def test_wechat_result_copy_drops_raw_source_fragments(tmp_path) -> None:
    cleaned = pipeline._apply_section_rules_to_generated_content(plan, match, raw_text)
    assert "[clubelo]" not in cleaned
    assert "ranked None" not in cleaned
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_content_validation_service.py tests/test_wechat_fallback_diversity.py -q`
Expected: FAIL because placeholders and raw fragments are still allowed through.

- [ ] **Step 3: Implement the minimal production changes**

```python
# Add paragraph classification helpers and skip/clean rules in pipeline.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_content_validation_service.py tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_content_validation_service.py tests/test_wechat_fallback_diversity.py
git commit -m "test: add content quality gating regressions"
```

### Task 2: Implement Paragraph Gating For WeChat Copy

**Files:**
- Modify: `src/auto_football/pipeline.py`

- [ ] **Step 1: Write the failing integration test**

```python
def test_wechat_result_copy_keeps_only_reader_safe_paragraphs(tmp_path) -> None:
    ...
    assert "None" not in cleaned
    assert "待补充" not in cleaned
    assert "vs 待补充" not in cleaned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wechat_fallback_diversity.py -q`
Expected: FAIL because paragraph cleanup is still shallow.

- [ ] **Step 3: Write minimal implementation**

```python
def _apply_section_rules_to_generated_content(...):
    paragraphs = ...
    filtered = [p for p in paragraphs if not _is_bad_placeholder_paragraph(...)]
```

```python
def _is_bad_placeholder_paragraph(paragraph: str, match: MatchInfo) -> bool:
    ...
```

```python
def _humanize_knowledge_briefs(briefs: list[str]) -> list[str]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/pipeline.py tests/test_wechat_fallback_diversity.py
git commit -m "feat: gate placeholder and raw-source paragraphs in wechat copy"
```

### Task 3: Verify End-To-End Reader-Facing Output

**Files:**
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Add end-to-end assertions**

```python
for item in wechat_contents:
    assert "待补充" not in item["content"]
    assert "[clubelo]" not in item["content"]
    assert "ranked None" not in item["content"]
```

- [ ] **Step 2: Run focused verification suite**

Run: `pytest tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py tests/test_content_validation_service.py -q`
Expected: PASS

- [ ] **Step 3: Run broader content regression suite**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_style_diversification.py tests/test_wechat_fallback_diversity.py tests/test_content_validation_service.py tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_stage0_smoke_baseline.py
git commit -m "test: verify wechat content quality gating end to end"
```
