# WeChat Ranking Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable ranking and league-context paragraphs to WeChat longform articles whenever structured ranking data is present, without surfacing placeholder text when rankings are missing.

**Architecture:** Keep ranking sourcing in the existing structured enrichment path, then make WeChat longform expansion explicitly include a ranking/context paragraph only when `home_rank`, `away_rank`, or `standings_summary` are trustworthy. Do not let missing rankings produce fallback placeholder text.

**Tech Stack:** Python 3.12+, existing `StructuredDataService`, `AutoFootballPipeline`, pytest.

---

### Task 1: Add Regression Tests For Ranking Context In WeChat Copy

**Files:**
- Modify: `tests/test_wechat_fallback_diversity.py`
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_wechat_longform_includes_ranking_context_when_available(tmp_path) -> None:
    assert "联赛位置" in candidate.content or "第2" in candidate.content
```

```python
def test_wechat_longform_skips_ranking_paragraph_when_missing(tmp_path) -> None:
    assert "暂无稳定联赛排名数据" not in candidate.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py -q`
Expected: FAIL because the current longform expansion repeats generic macro paragraphs instead of using available ranking context.

- [ ] **Step 3: Implement the minimal production changes**

```python
# Add a ranking-context helper and thread it into _expand_wechat_longform()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py
git commit -m "test: add wechat ranking context coverage"
```

### Task 2: Implement Ranking Paragraph Injection

**Files:**
- Modify: `src/auto_football/pipeline.py`

- [ ] **Step 1: Write the failing integration test**

```python
def test_wechat_candidate_pool_uses_ranking_context_for_ranked_match(tmp_path) -> None:
    assert "第2" in top_candidate.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: FAIL because current expansion does not prioritize ranking context.

- [ ] **Step 3: Write minimal implementation**

```python
def _reader_safe_ranking_summary(match: MatchInfo) -> str:
    ...
```

```python
fillers.insert(... ranking_summary ...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/pipeline.py tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py
git commit -m "feat: inject ranking context into wechat longform"
```

### Task 3: Verify End-To-End Output

**Files:**
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Add end-to-end assertions**

```python
assert "第" in wechat_contents[0]["content"]
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
git commit -m "test: verify ranking context in end-to-end wechat output"
```
