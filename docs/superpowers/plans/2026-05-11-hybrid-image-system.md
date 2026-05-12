# Hybrid Image System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a balanced-cost hybrid image pipeline that routes WeChat and Xiaohongshu content through visual briefs, optional Ark image generation, and existing local fallback rendering.

**Architecture:** Keep the existing pipeline stages and `GeneratedContent.images` contract intact. Add a visual-brief routing layer plus an Ark image client, then teach the image-generation stage to choose between remote AI base imagery and the existing local renderer. Persist all new image strategy data inside `editorial_metadata` to avoid schema churn in v1.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy, Typer, Pillow, httpx, Ark image API, pytest

---

## File Structure

- Modify: `D:/auto_go/src/auto_football/config.py`
  - Add Ark image provider settings and image budget settings.
- Modify: `D:/auto_go/src/auto_football/schemas.py`
  - Add lightweight visual brief schemas and keep them serializable through `editorial_metadata`.
- Create: `D:/auto_go/src/auto_football/domain/services/visual_brief_service.py`
  - Build deterministic visual briefs from `GeneratedContent` + `MatchInfo`.
- Create: `D:/auto_go/src/auto_football/infra/images/__init__.py`
  - Package marker for image provider clients.
- Create: `D:/auto_go/src/auto_football/infra/images/ark_image_client.py`
  - Encapsulate Ark image API calls and local image download.
- Modify: `D:/auto_go/src/auto_football/domain/services/image_generation_service.py`
  - Route through visual briefs, budget checks, Ark generation, and fallback local rendering.
- Modify: `D:/auto_go/src/auto_football/pipeline.py`
  - Wire the new visual brief service and Ark image client into the pipeline.
- Modify: `D:/auto_go/src/auto_football/images.py`
  - Add a simple helper for deriving fallback local assets when AI generation is skipped or fails.
- Test: `D:/auto_go/tests/test_content_engine_schemas.py`
  - Validate new visual brief schema serialization.
- Create: `D:/auto_go/tests/test_visual_brief_service.py`
  - Cover routing and fallback-chain construction.
- Create: `D:/auto_go/tests/test_ark_image_client.py`
  - Cover request payloads, disabled behavior, and local download behavior with monkeypatching.
- Create: `D:/auto_go/tests/test_image_generation_service.py`
  - Cover balanced-cost routing, AI budget limits, fallback behavior, and editorial metadata persistence.
- Modify: `D:/auto_go/tests/test_stage0_smoke_baseline.py`
  - Ensure the full pipeline still persists previewable image assets in the fallback path.

### Task 1: Add Configuration Coverage for Ark and Image Budgets

**Files:**
- Modify: `D:/auto_go/src/auto_football/config.py`
- Test: `D:/auto_go/tests/test_wechat_config.py`

- [ ] **Step 1: Write the failing configuration test**

```python
from auto_football.config import Settings


def test_settings_expose_ark_image_configuration() -> None:
    settings = Settings(
        AI_IMAGE_ENABLED=True,
        ARK_API_KEY="ark-key",
        ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3",
        ARK_IMAGE_MODEL="doubao-seedream-3-0-t2i-250415",
        AI_IMAGE_DAILY_LIMIT=6,
        AI_IMAGE_PER_MATCH_LIMIT=1,
        WECHAT_INLINE_AI_IMAGE_LIMIT=1,
    )

    assert settings.ai_image_enabled is True
    assert settings.ark_api_key == "ark-key"
    assert settings.ark_base_url.endswith("/api/v3")
    assert settings.ark_image_model == "doubao-seedream-3-0-t2i-250415"
    assert settings.ai_image_daily_limit == 6
    assert settings.ai_image_per_match_limit == 1
    assert settings.wechat_inline_ai_image_limit == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wechat_config.py::test_settings_expose_ark_image_configuration -v`

Expected: FAIL with missing `Settings` attributes such as `ai_image_enabled`

- [ ] **Step 3: Write the minimal configuration implementation**

```python
class Settings(BaseSettings):
    # ...
    ai_image_enabled: bool = Field(default=False, alias="AI_IMAGE_ENABLED")
    ark_base_url: str = Field(default="https://ark.cn-beijing.volces.com/api/v3", alias="ARK_BASE_URL")
    ark_api_key: str = Field(default="", alias="ARK_API_KEY")
    ark_image_model: str = Field(default="doubao-seedream-3-0-t2i-250415", alias="ARK_IMAGE_MODEL")
    ai_image_daily_limit: int = Field(default=6, alias="AI_IMAGE_DAILY_LIMIT")
    ai_image_per_match_limit: int = Field(default=1, alias="AI_IMAGE_PER_MATCH_LIMIT")
    wechat_inline_ai_image_limit: int = Field(default=1, alias="WECHAT_INLINE_AI_IMAGE_LIMIT")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_wechat_config.py::test_settings_expose_ark_image_configuration -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not currently a git repository, skip commit creation and record that limitation in the execution notes.

### Task 2: Introduce Visual Brief Schemas

**Files:**
- Modify: `D:/auto_go/src/auto_football/schemas.py`
- Modify: `D:/auto_go/tests/test_content_engine_schemas.py`

- [ ] **Step 1: Write the failing schema test**

```python
from auto_football.schemas import (
    ContentMode,
    Platform,
    VisualBrief,
    VisualBriefSlot,
    VisualImageType,
)


def test_visual_brief_round_trips_through_json() -> None:
    brief = VisualBrief(
        platform=Platform.WECHAT,
        slot=VisualBriefSlot.WECHAT_HERO,
        image_type=VisualImageType.AI_ACTION_PHOTO,
        scene_angle="home pressure",
        emotion="tense",
        subject_focus="duel",
        headline_text="",
        supporting_text="",
        data_dependency="low",
        fallback_chain=["ai_action_photo", "fallback_card"],
    )

    restored = VisualBrief.model_validate(brief.model_dump(mode="json"))

    assert restored.slot is VisualBriefSlot.WECHAT_HERO
    assert restored.image_type is VisualImageType.AI_ACTION_PHOTO
    assert restored.fallback_chain == ["ai_action_photo", "fallback_card"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_engine_schemas.py::test_visual_brief_round_trips_through_json -v`

Expected: FAIL with import error for `VisualBrief`

- [ ] **Step 3: Write the minimal schema implementation**

```python
class VisualImageType(StrEnum):
    REAL_PHOTO = "real_photo"
    AI_ACTION_PHOTO = "ai_action_photo"
    HYBRID_COVER = "hybrid_cover"
    FALLBACK_CARD = "fallback_card"


class VisualBriefSlot(StrEnum):
    WECHAT_HERO = "wechat_hero"
    WECHAT_INLINE = "wechat_inline"
    XHS_COVER = "xhs_cover"


class VisualBrief(BaseModel):
    platform: Platform
    slot: VisualBriefSlot
    image_type: VisualImageType
    scene_angle: str
    emotion: str
    subject_focus: str
    headline_text: str = ""
    supporting_text: str = ""
    data_dependency: str = "low"
    fallback_chain: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_engine_schemas.py::test_visual_brief_round_trips_through_json -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not currently a git repository, skip commit creation and record that limitation in the execution notes.

### Task 3: Build the Visual Brief Routing Service

**Files:**
- Create: `D:/auto_go/src/auto_football/domain/services/visual_brief_service.py`
- Create: `D:/auto_go/tests/test_visual_brief_service.py`

- [ ] **Step 1: Write the failing routing tests**

```python
from datetime import datetime, timezone

from auto_football.domain.services.visual_brief_service import VisualBriefService
from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform, VisualBriefSlot, VisualImageType


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=8001,
        league="Premier League",
        match_time=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Chelsea",
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        merged_context={"coverage": {"ready": False, "total_signals": 2}},
    )


def test_visual_brief_service_routes_wechat_pre_match_to_editorial_scene() -> None:
    service = VisualBriefService()
    content = GeneratedContent(
        match_id=8001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        title="利物浦不败，这场别想太复杂",
        content="主场压迫感会先上来。",
    )

    briefs = service.build(content, _match())

    assert briefs[0].slot is VisualBriefSlot.WECHAT_HERO
    assert briefs[0].image_type is VisualImageType.AI_ACTION_PHOTO
    assert briefs[0].scene_angle == "home pressure"
    assert briefs[0].data_dependency == "low"


def test_visual_brief_service_routes_xhs_cover_to_hybrid_claim() -> None:
    service = VisualBriefService()
    content = GeneratedContent(
        match_id=8001,
        platform=Platform.XIAOHONGSHU,
        mode=ContentMode.PRE_MATCH,
        title="利物浦不败",
        content="结论前置，主场压迫感更强。",
    )

    briefs = service.build(content, _match())

    assert briefs[0].slot is VisualBriefSlot.XHS_COVER
    assert briefs[0].image_type is VisualImageType.HYBRID_COVER
    assert briefs[0].headline_text == "利物浦不败"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_visual_brief_service.py -v`

Expected: FAIL with missing module or missing `build` implementation

- [ ] **Step 3: Write the minimal routing implementation**

```python
from __future__ import annotations

from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform, VisualBrief, VisualBriefSlot, VisualImageType


class VisualBriefService:
    def build(self, content: GeneratedContent, match: MatchInfo) -> list[VisualBrief]:
        scene_angle = self._scene_angle(content, match)
        if content.platform is Platform.WECHAT:
            return [
                VisualBrief(
                    platform=content.platform,
                    slot=VisualBriefSlot.WECHAT_HERO,
                    image_type=VisualImageType.AI_ACTION_PHOTO,
                    scene_angle=scene_angle,
                    emotion="tense",
                    subject_focus="match action",
                    data_dependency="low",
                    fallback_chain=["ai_action_photo", "fallback_card"],
                )
            ]
        return [
            VisualBrief(
                platform=content.platform,
                slot=VisualBriefSlot.XHS_COVER,
                image_type=VisualImageType.HYBRID_COVER,
                scene_angle=scene_angle,
                emotion="charged",
                subject_focus="narrative scene",
                headline_text=content.title,
                data_dependency="low",
                fallback_chain=["hybrid_cover", "fallback_card"],
            )
        ]

    @staticmethod
    def _scene_angle(content: GeneratedContent, match: MatchInfo) -> str:
        text = f"{content.title}\n{content.content}".lower()
        if "不败" in content.title or "压迫" in text:
            return "home pressure"
        if content.mode is ContentMode.RESULT_FLASH:
            return "result emotion"
        return "match tension"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_visual_brief_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not currently a git repository, skip commit creation and record that limitation in the execution notes.

### Task 4: Add the Ark Image Client

**Files:**
- Create: `D:/auto_go/src/auto_football/infra/images/__init__.py`
- Create: `D:/auto_go/src/auto_football/infra/images/ark_image_client.py`
- Create: `D:/auto_go/tests/test_ark_image_client.py`

- [ ] **Step 1: Write the failing Ark client tests**

```python
from pathlib import Path

from auto_football.config import Settings
from auto_football.infra.images.ark_image_client import ArkImageClient


def test_ark_image_client_is_disabled_without_key(tmp_path) -> None:
    client = ArkImageClient(Settings(AI_IMAGE_ENABLED=True, IMAGE_OUTPUT_DIR=str(tmp_path)))
    assert client.enabled is False


def test_ark_image_client_posts_prompt_and_downloads_image(tmp_path, monkeypatch) -> None:
    calls = {}

    class FakeResponse:
        def __init__(self, payload, content=b""):
            self._payload = payload
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return FakeResponse({"data": [{"url": "https://img.example/generated.png"}]})

    def fake_get(url, timeout=None):
        calls["get"] = {"url": url, "timeout": timeout}
        return FakeResponse({}, content=b"png-bytes")

    monkeypatch.setattr("auto_football.infra.images.ark_image_client.httpx.post", fake_post)
    monkeypatch.setattr("auto_football.infra.images.ark_image_client.httpx.get", fake_get)

    client = ArkImageClient(
        Settings(
            AI_IMAGE_ENABLED=True,
            ARK_API_KEY="ark-key",
            ARK_IMAGE_MODEL="doubao-seedream-3-0-t2i-250415",
            IMAGE_OUTPUT_DIR=str(tmp_path),
        )
    )

    output = client.generate_to_file(match_id=8001, slug="wechat-hero", prompt="sports action prompt")

    assert Path(output).exists()
    assert calls["post"]["json"]["model"] == "doubao-seedream-3-0-t2i-250415"
    assert calls["post"]["json"]["prompt"] == "sports action prompt"
    assert calls["get"]["url"] == "https://img.example/generated.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ark_image_client.py -v`

Expected: FAIL with missing module `auto_football.infra.images.ark_image_client`

- [ ] **Step 3: Write the minimal Ark client implementation**

```python
from __future__ import annotations

from pathlib import Path

import httpx

from auto_football.config import Settings


class ArkImageClient:
    def __init__(self, settings: Settings) -> None:
        self.enabled = bool(settings.ai_image_enabled and settings.ark_api_key and settings.ark_image_model)
        self.base_url = settings.ark_base_url.rstrip("/")
        self.api_key = settings.ark_api_key
        self.model = settings.ark_image_model
        self.output_dir = Path(settings.image_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_to_file(self, *, match_id: int, slug: str, prompt: str) -> str | None:
        if not self.enabled:
            return None
        response = httpx.post(
            f"{self.base_url}/images/generations",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "prompt": prompt},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        image_url = payload["data"][0]["url"]
        image = httpx.get(image_url, timeout=60)
        image.raise_for_status()
        path = self.output_dir / f"{match_id}_{slug}.png"
        path.write_bytes(image.content)
        return str(path.resolve())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ark_image_client.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not currently a git repository, skip commit creation and record that limitation in the execution notes.

### Task 5: Upgrade the Image Generation Service with Balanced Routing

**Files:**
- Modify: `D:/auto_go/src/auto_football/domain/services/image_generation_service.py`
- Create: `D:/auto_go/tests/test_image_generation_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
from datetime import datetime, timezone

from auto_football.domain.services.image_generation_service import ImageGenerationService
from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform, VisualBrief, VisualBriefSlot, VisualImageType


class FakeDB:
    def __init__(self) -> None:
        self.updated = []
        self.cloned = []

    def update_content_assets(self, content):
        self.updated.append(content)

    def clone_content_assets_to_slice(self, content):
        self.cloned.append(content)


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=8101,
        league="Premier League",
        match_time=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Chelsea",
    )


def test_image_generation_service_uses_ai_cover_then_persists_metadata() -> None:
    db = FakeDB()
    generated = []

    class FakeArk:
        def generate_to_file(self, *, match_id, slug, prompt):
            generated.append((match_id, slug, prompt))
            return f"D:/fake/{match_id}_{slug}.png"

    class FakeVisualBriefs:
        def build(self, content, match):
            return [
                VisualBrief(
                    platform=content.platform,
                    slot=VisualBriefSlot.XHS_COVER,
                    image_type=VisualImageType.HYBRID_COVER,
                    scene_angle="home pressure",
                    emotion="charged",
                    subject_focus="narrative scene",
                    headline_text=content.title,
                    fallback_chain=["hybrid_cover", "fallback_card"],
                )
            ]

    class FakeFallback:
        def build_assets(self, match, verdict):
            return [f"D:/fallback/{match.match_id}_cover.png", f"D:/fallback/{match.match_id}_prediction.png"]

    service = ImageGenerationService(
        db=db,
        image_generator=FakeFallback(),
        verdict_fn=lambda match: "Liverpool不败",
        image_prompts_for_mode_fn=lambda match, mode, verdict: [f"{match.home_team} {verdict}"],
        visual_brief_service=FakeVisualBriefs(),
        ai_image_client=FakeArk(),
        settings=type("Settings", (), {"ai_image_daily_limit": 6, "ai_image_per_match_limit": 1, "wechat_inline_ai_image_limit": 1})(),
    )

    content = GeneratedContent(match_id=8101, platform=Platform.XIAOHONGSHU, mode=ContentMode.PRE_MATCH, title="利物浦不败", content="正文")
    result = service.generate([content], {8101: _match()})

    assert result[0].images == ["D:/fake/8101_xhs-cover.png"]
    assert result[0].editorial_metadata["visual_strategy"] == "ai_primary"
    assert result[0].editorial_metadata["image_budget_used"] == 1
    assert generated == [(8101, "xhs-cover", "Liverpool Liverpool不败")]


def test_image_generation_service_falls_back_when_budget_is_exhausted() -> None:
    db = FakeDB()

    class FakeArk:
        def generate_to_file(self, *, match_id, slug, prompt):
            raise AssertionError("AI should not be called when budget is exhausted")

    class FakeVisualBriefs:
        def build(self, content, match):
            return [
                VisualBrief(
                    platform=content.platform,
                    slot=VisualBriefSlot.WECHAT_HERO,
                    image_type=VisualImageType.AI_ACTION_PHOTO,
                    scene_angle="home pressure",
                    emotion="tense",
                    subject_focus="action",
                    fallback_chain=["ai_action_photo", "fallback_card"],
                )
            ]

    class FakeFallback:
        def build_assets(self, match, verdict):
            return [f"D:/fallback/{match.match_id}_cover.png", f"D:/fallback/{match.match_id}_prediction.png"]

    service = ImageGenerationService(
        db=db,
        image_generator=FakeFallback(),
        verdict_fn=lambda match: "Liverpool不败",
        image_prompts_for_mode_fn=lambda match, mode, verdict: [f"{match.home_team} {verdict}"],
        visual_brief_service=FakeVisualBriefs(),
        ai_image_client=FakeArk(),
        settings=type("Settings", (), {"ai_image_daily_limit": 0, "ai_image_per_match_limit": 0, "wechat_inline_ai_image_limit": 1})(),
    )

    content = GeneratedContent(match_id=8101, platform=Platform.WECHAT, mode=ContentMode.PRE_MATCH, title="利物浦不败", content="正文")
    result = service.generate([content], {8101: _match()})

    assert result[0].images == ["D:/fallback/8101_cover.png", "D:/fallback/8101_prediction.png"]
    assert result[0].editorial_metadata["visual_strategy"] == "fallback_local"
    assert result[0].editorial_metadata["image_budget_used"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_generation_service.py -v`

Expected: FAIL with unexpected `ImageGenerationService` signature or missing metadata behavior

- [ ] **Step 3: Write the minimal service implementation**

```python
class ImageGenerationService:
    def __init__(
        self,
        db,
        image_generator,
        verdict_fn,
        image_prompts_for_mode_fn,
        *,
        visual_brief_service,
        ai_image_client,
        settings,
    ) -> None:
        self.db = db
        self.image_generator = image_generator
        self.verdict_fn = verdict_fn
        self.image_prompts_for_mode_fn = image_prompts_for_mode_fn
        self.visual_brief_service = visual_brief_service
        self.ai_image_client = ai_image_client
        self.settings = settings

    def generate(self, contents, match_data):
        run_budget_used = 0
        per_match_budget: dict[int, int] = {}
        for content in contents:
            match = match_data[content.match_id]
            verdict = self.verdict_fn(match)
            prompts = self.image_prompts_for_mode_fn(match, content.mode, verdict)
            briefs = self.visual_brief_service.build(content, match)
            image_paths = None
            budget_used = 0

            can_use_ai = (
                run_budget_used < self.settings.ai_image_daily_limit
                and per_match_budget.get(content.match_id, 0) < self.settings.ai_image_per_match_limit
                and bool(briefs)
            )
            if can_use_ai:
                slug = "xhs-cover" if content.platform.value == "xiaohongshu" else "wechat-hero"
                image_path = self.ai_image_client.generate_to_file(match_id=content.match_id, slug=slug, prompt=prompts[0])
                if image_path:
                    image_paths = [image_path]
                    run_budget_used += 1
                    per_match_budget[content.match_id] = per_match_budget.get(content.match_id, 0) + 1
                    budget_used = 1

            if image_paths is None:
                image_paths = self.image_generator.build_assets(match, verdict)
                strategy = "fallback_local"
            else:
                strategy = "ai_primary"

            content.images = image_paths
            content.image_prompts = prompts
            content.editorial_metadata = {
                **(content.editorial_metadata or {}),
                "visual_strategy": strategy,
                "visual_briefs": [item.model_dump(mode="json") for item in briefs],
                "image_budget_used": budget_used,
            }
            self.db.update_content_assets(content)
            self.db.clone_content_assets_to_slice(content)
        return contents
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_image_generation_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not currently a git repository, skip commit creation and record that limitation in the execution notes.

### Task 6: Wire the New Services into the Pipeline

**Files:**
- Modify: `D:/auto_go/src/auto_football/pipeline.py`
- Modify: `D:/auto_go/tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Write the failing smoke test update**

```python
def test_stage0_pipeline_smoke_baseline_marks_fallback_visual_strategy(tmp_path) -> None:
    # reuse the smoke-test fixture setup
    # ...
    state = pipeline.run(run_date=date(2026, 5, 4))

    assert state["contents"][0].editorial_metadata["visual_strategy"] == "fallback_local"
    assert state["contents"][0].editorial_metadata["image_budget_used"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stage0_smoke_baseline.py::test_stage0_pipeline_smoke_baseline_marks_fallback_visual_strategy -v`

Expected: FAIL because the pipeline does not inject the new services or metadata

- [ ] **Step 3: Write the minimal pipeline wiring**

```python
from auto_football.domain.services.visual_brief_service import VisualBriefService
from auto_football.infra.images.ark_image_client import ArkImageClient


class AutoFootballPipeline:
    def __init__(self, settings: Settings) -> None:
        # ...
        self.visual_brief_service = VisualBriefService()
        self.ai_image_client = ArkImageClient(settings)
        self.image_service = ImageGenerationService(
            self.db,
            self.image_generator,
            self._verdict,
            self._image_prompts_for_mode,
            visual_brief_service=self.visual_brief_service,
            ai_image_client=self.ai_image_client,
            settings=settings,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stage0_smoke_baseline.py::test_stage0_pipeline_smoke_baseline_marks_fallback_visual_strategy -v`

Expected: PASS

- [ ] **Step 5: Commit**

Because this workspace is not currently a git repository, skip commit creation and record that limitation in the execution notes.

### Task 7: Run the Targeted Verification Suite

**Files:**
- Test: `D:/auto_go/tests/test_wechat_config.py`
- Test: `D:/auto_go/tests/test_content_engine_schemas.py`
- Test: `D:/auto_go/tests/test_visual_brief_service.py`
- Test: `D:/auto_go/tests/test_ark_image_client.py`
- Test: `D:/auto_go/tests/test_image_generation_service.py`
- Test: `D:/auto_go/tests/test_stage0_smoke_baseline.py`

- [ ] **Step 1: Run the focused verification suite**

Run:

```powershell
pytest `
  tests/test_wechat_config.py::test_settings_expose_ark_image_configuration `
  tests/test_content_engine_schemas.py::test_visual_brief_round_trips_through_json `
  tests/test_visual_brief_service.py `
  tests/test_ark_image_client.py `
  tests/test_image_generation_service.py `
  tests/test_stage0_smoke_baseline.py::test_stage0_pipeline_smoke_baseline_marks_fallback_visual_strategy `
  -v
```

Expected: all selected tests PASS

- [ ] **Step 2: Run one broader regression file for image persistence**

Run: `pytest tests/test_stage0_smoke_baseline.py -v`

Expected: PASS for the smoke baseline file, including image persistence assertions

- [ ] **Step 3: Record execution notes**

Document:

- which tests passed,
- whether Ark generation was only mocked in tests,
- that no git commit was created because the workspace is not a git repository,
- whether a local real API smoke run still needs manual user approval and credentials validation.

## Self-Review

- Spec coverage:
  - Visual brief routing is covered by Task 3.
  - Ark provider integration is covered by Task 4.
  - Balanced-cost budget behavior is covered by Task 5.
  - Pipeline wiring and fallback persistence are covered by Task 6.
  - Verification is covered by Task 7.
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” placeholders remain.
- Type consistency:
  - `VisualBrief`, `VisualBriefSlot`, and `VisualImageType` are introduced in Task 2 and used consistently in later tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-hybrid-image-system.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
