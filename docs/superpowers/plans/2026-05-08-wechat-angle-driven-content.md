# WeChat Angle-Driven Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild WeChat pre-match generation so candidates are driven by distinct editorial angles instead of converging on one safe template, while preserving all generated candidates through later pipeline stages.

**Architecture:** Keep the existing fact-pack and editorial-brief pipeline, but add a WeChat-specific angle planner that turns structured match signals into explicit candidate briefs. Feed those angle briefs into candidate prompting and fallback writing, then update validation/ranking so repeated openings and generic titles lose. Preserve candidate rows by separating “replace a content slice” from “update one existing candidate with images”.

**Tech Stack:** Python 3.12+, Pydantic models, SQLAlchemy repositories, pytest, existing LangGraph pipeline services.

---

### Task 1: Add Regression Tests For Angle Diversity

**Files:**
- Modify: `tests/test_content_pipeline_phase1.py`
- Modify: `tests/test_wechat_fallback_diversity.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_wechat_pre_match_candidate_pool_uses_distinct_editorial_angles(tmp_path) -> None:
    ...
    candidate_pool = pipeline._build_candidate_pool(plan, match)

    angle_ids = [item.editorial_metadata.get("wechat_angle_id") for item in candidate_pool]
    openings = [item.content.split("\n\n", 1)[0] for item in candidate_pool]

    assert len(candidate_pool) >= 3
    assert len(set(angle_ids)) == len(angle_ids)
    assert len(set(openings)) == len(openings)
```

```python
def test_wechat_fallback_uses_angle_specific_openings(tmp_path) -> None:
    ...
    assert "先给判断" not in market_angle.content.split("\n\n", 1)[0]
    assert "先给判断" not in pressure_angle.content.split("\n\n", 1)[0]
    assert market_angle.content != pressure_angle.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: FAIL because WeChat candidates still collapse to two generic style-driven variants with repeated openings.

- [ ] **Step 3: Implement the minimal production changes**

```python
# Add a WeChat angle-planning helper/service and thread angle metadata
# through candidate generation and fallback writing.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py
git commit -m "test: add wechat angle-driven regression coverage"
```

### Task 2: Implement WeChat Angle Planning And Candidate Rebuild

**Files:**
- Create: `src/auto_football/domain/services/wechat_angle_planner_service.py`
- Modify: `src/auto_football/pipeline.py`
- Modify: `src/auto_football/schemas.py`
- Modify: `src/auto_football/domain/services/content_validation_service.py`

- [ ] **Step 1: Write the failing test for model/service integration**

```python
def test_wechat_angle_planner_returns_distinct_angle_specs() -> None:
    specs = WechatAnglePlannerService().build(pack, brief)
    assert [spec.angle_id for spec in specs[:3]] == ["pressure", "market", "strength"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wechat_style_diversification.py -q`
Expected: FAIL because no angle planner/spec exists yet.

- [ ] **Step 3: Write minimal implementation**

```python
class WechatAngleSpec(BaseModel):
    angle_id: str
    title_instruction: str
    opening_instruction: str
    body_instruction: str


class WechatAnglePlannerService:
    def build(self, pack: FactPack, brief: EditorialBrief) -> list[WechatAngleSpec]:
        ...
```

```python
if plan.platform is Platform.WECHAT and plan.mode is ContentMode.PRE_MATCH:
    angle_specs = self.wechat_angle_planner_service.build(pack, brief)
    for angle in angle_specs:
        ...
        candidate.editorial_metadata["wechat_angle_id"] = angle.angle_id
```

```python
def _repetition_penalty(self, text: str, recent_openings: list[str]) -> float:
    opening = self._opening_line(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wechat_style_diversification.py tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/domain/services/wechat_angle_planner_service.py src/auto_football/pipeline.py src/auto_football/schemas.py src/auto_football/domain/services/content_validation_service.py tests/test_wechat_style_diversification.py tests/test_content_pipeline_phase1.py tests/test_wechat_fallback_diversity.py
git commit -m "feat: rebuild wechat candidates around editorial angles"
```

### Task 3: Preserve Candidate Pool Through Image Generation

**Files:**
- Modify: `src/auto_football/db.py`
- Modify: `src/auto_football/infra/db/repositories.py`
- Modify: `src/auto_football/domain/services/image_generation_service.py`
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Write the failing persistence test**

```python
def test_image_generation_updates_top_candidate_without_deleting_backups(tmp_path) -> None:
    ...
    records = pipeline.db.get_preview_payloads(match_id=7001, limit_matches=1)[0]["contents"]
    assert len([item for item in records if item["platform"] == "wechat"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage0_smoke_baseline.py -q`
Expected: FAIL because `save_content()` replaces the whole content slice during image generation and deletes backup candidates.

- [ ] **Step 3: Write minimal implementation**

```python
def update_content_assets(...):
    record = _find_existing_content_record(...)
    record.images = content.images
    record.image_prompts = ...
```

```python
class ImageGenerationService:
    def generate(self, contents, match_data):
        ...
        self.db.update_content_assets(content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/db.py src/auto_football/infra/db/repositories.py src/auto_football/domain/services/image_generation_service.py tests/test_stage0_smoke_baseline.py
git commit -m "fix: preserve content candidates during image generation"
```

### Task 4: Verify The End-To-End WeChat Behavior

**Files:**
- Modify: `tests/test_content_pipeline_phase1.py`
- Modify: `tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Add a focused end-to-end assertion**

```python
assert len({item["title"] for item in wechat_contents}) >= 2
assert len({item["editorial_style"] for item in wechat_contents}) >= 2 or len({item["editorial_metadata"]["wechat_angle_id"] for item in wechat_contents}) >= 2
```

- [ ] **Step 2: Run the focused verification suite**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_wechat_style_diversification.py tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 3: Run the broader content-engine regression suite**

Run: `pytest tests/test_content_pipeline_phase1.py tests/test_content_validation_service.py tests/test_wechat_style_diversification.py tests/test_wechat_fallback_diversity.py tests/test_stage0_smoke_baseline.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_content_pipeline_phase1.py tests/test_stage0_smoke_baseline.py
git commit -m "test: verify end-to-end wechat angle-driven behavior"
```
