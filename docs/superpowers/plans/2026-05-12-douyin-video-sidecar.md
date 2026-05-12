# Douyin Video Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a test-first Douyin video generation path that turns existing match facts into Pixelle video tasks and stores render results without implementing Douyin publishing.

**Architecture:** Keep Pixelle as a local sidecar service and add a narrow Douyin video module inside the project. The project decides whether to generate a `pre_match` or `result_flash` video, builds a compact provider payload, submits it through a provider client, then syncs the task result back into project-owned persistence.

**Tech Stack:** Python 3.12, Typer CLI, Pydantic, SQLAlchemy, pytest, local Pixelle HTTP sidecar

---

## File Structure

### Create

- `src/auto_football/douyin_video.py`
  - Douyin video planner, payload builder, provider client protocol, fake client, orchestrating service
- `tests/test_douyin_video_service.py`
  - Planner, payload builder, service orchestration, fake provider behavior
- `tests/test_douyin_video_cli.py`
  - CLI submit/sync/run command behavior with fakes
- `tests/test_douyin_video_db.py`
  - DB persistence for task submission, status sync, failure states, and result capture

### Modify

- `src/auto_football/schemas.py`
  - Add Douyin video request/result/status models and enums
- `src/auto_football/config.py`
  - Add Pixelle configuration fields
- `src/auto_football/cli.py`
  - Add test-first Douyin video commands
- `src/auto_football/db.py`
  - Expose Douyin video task persistence methods
- `src/auto_football/infra/db/models.py`
  - Add table/model for Douyin video tasks
- `src/auto_football/infra/db/migrations.py`
  - Add schema bootstrap for the new Douyin video task table when needed
- `src/auto_football/infra/db/repositories.py`
  - Add repository functions for saving/submitting/updating Douyin video task rows

## Task 1: Define Douyin video models and config

**Files:**
- Modify: `src/auto_football/schemas.py`
- Modify: `src/auto_football/config.py`
- Test: `tests/test_douyin_video_service.py`

- [ ] **Step 1: Write the failing schema/config test**

Add this test to `tests/test_douyin_video_service.py`:

```python
from __future__ import annotations

from auto_football.config import Settings
from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskStatus


def test_douyin_video_settings_and_enums_exist() -> None:
    settings = Settings()

    assert settings.pixelle_enabled is False
    assert settings.pixelle_base_url == "http://127.0.0.1:8000"
    assert settings.pixelle_submit_path == "/api/video/generate/async"
    assert settings.pixelle_task_path_template == "/api/tasks/{task_id}"

    assert DouyinVideoMode.PRE_MATCH == "pre_match"
    assert DouyinVideoMode.RESULT_FLASH == "result_flash"
    assert DouyinVideoTaskStatus.QUEUED == "queued"
    assert DouyinVideoTaskStatus.SUCCEEDED == "succeeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py::test_douyin_video_settings_and_enums_exist -v
```

Expected:

- FAIL with import or attribute errors for missing settings/enums

- [ ] **Step 3: Add minimal enums and settings**

Update `src/auto_football/schemas.py` with these new enums and models near the existing platform/content models:

```python
class DouyinVideoMode(StrEnum):
    PRE_MATCH = "pre_match"
    RESULT_FLASH = "result_flash"


class DouyinVideoTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SUBMIT_FAILED = "submit_failed"
    RENDER_FAILED = "render_failed"
    TIMEOUT = "timeout"
    SKIPPED_INSUFFICIENT_DATA = "skipped_insufficient_data"


class DouyinVideoJobRequest(BaseModel):
    match_id: int
    video_mode: DouyinVideoMode
    title: str
    caption_cards: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    assets: dict[str, Any] = Field(default_factory=dict)
    duration_target_sec: int = 20


class DouyinVideoTaskRecord(BaseModel):
    match_id: int
    video_mode: DouyinVideoMode
    provider: str = "pixelle"
    provider_task_id: str | None = None
    status: DouyinVideoTaskStatus
    video_url: str | None = None
    error_message: str | None = None
    payload_snapshot: dict[str, Any] = Field(default_factory=dict)
```

Update `src/auto_football/config.py` with these fields inside `Settings`:

```python
    pixelle_enabled: bool = Field(default=False, alias="PIXELLE_ENABLED")
    pixelle_base_url: str = Field(default="http://127.0.0.1:8000", alias="PIXELLE_BASE_URL")
    pixelle_submit_path: str = Field(default="/api/video/generate/async", alias="PIXELLE_SUBMIT_PATH")
    pixelle_task_path_template: str = Field(default="/api/tasks/{task_id}", alias="PIXELLE_TASK_PATH_TEMPLATE")
    pixelle_timeout_seconds: int = Field(default=60, alias="PIXELLE_TIMEOUT_SECONDS")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py::test_douyin_video_settings_and_enums_exist -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/schemas.py src/auto_football/config.py tests/test_douyin_video_service.py
git commit -m "feat: add douyin video schemas and pixelle config"
```

## Task 2: Add the Douyin video planner and payload builder

**Files:**
- Create: `src/auto_football/douyin_video.py`
- Test: `tests/test_douyin_video_service.py`

- [ ] **Step 1: Write failing planner and payload tests**

Append these tests to `tests/test_douyin_video_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from auto_football.douyin_video import DouyinVideoPayloadBuilder, DouyinVideoPlanner
from auto_football.schemas import DouyinVideoMode, MatchInfo


def _match(**overrides):
    base = MatchInfo(
        match_id=101,
        league="Premier League",
        match_time=datetime(2026, 5, 12, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
    )
    return base.model_copy(update=overrides)


def test_planner_accepts_pre_match_with_minimum_fields() -> None:
    planner = DouyinVideoPlanner()

    result = planner.plan(_match(), DouyinVideoMode.PRE_MATCH)

    assert result.generate is True
    assert result.skip_reason is None


def test_planner_skips_result_flash_without_score() -> None:
    planner = DouyinVideoPlanner()

    result = planner.plan(_match(home_score=None, away_score=None), DouyinVideoMode.RESULT_FLASH)

    assert result.generate is False
    assert result.skip_reason == "missing_required_fields"


def test_payload_builder_creates_short_caption_cards_for_pre_match() -> None:
    builder = DouyinVideoPayloadBuilder()

    payload = builder.build(
        _match(standings_summary="Liverpool second, Arsenal fourth."),
        DouyinVideoMode.PRE_MATCH,
    )

    assert payload.video_mode == DouyinVideoMode.PRE_MATCH
    assert payload.match_id == 101
    assert payload.duration_target_sec == 20
    assert payload.caption_cards
    assert len(payload.caption_cards) <= 6
    assert payload.assets == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -k "planner or payload_builder" -v
```

Expected:

- FAIL because `DouyinVideoPlanner` and `DouyinVideoPayloadBuilder` do not exist

- [ ] **Step 3: Implement the planner and payload builder**

Create `src/auto_football/douyin_video.py` with this initial content:

```python
from __future__ import annotations

from dataclasses import dataclass

from auto_football.schemas import DouyinVideoJobRequest, DouyinVideoMode, MatchInfo


@dataclass
class DouyinVideoPlanDecision:
    generate: bool
    skip_reason: str | None = None


class DouyinVideoPlanner:
    def plan(self, match: MatchInfo, mode: DouyinVideoMode) -> DouyinVideoPlanDecision:
        if mode is DouyinVideoMode.PRE_MATCH:
            required_ok = bool(match.home_team and match.away_team and match.match_time and match.league)
            return DouyinVideoPlanDecision(generate=required_ok, skip_reason=None if required_ok else "missing_required_fields")

        required_ok = (
            bool(match.home_team and match.away_team)
            and match.home_score is not None
            and match.away_score is not None
        )
        return DouyinVideoPlanDecision(generate=required_ok, skip_reason=None if required_ok else "missing_required_fields")


class DouyinVideoPayloadBuilder:
    def build(self, match: MatchInfo, mode: DouyinVideoMode) -> DouyinVideoJobRequest:
        cards: list[str] = []
        if mode is DouyinVideoMode.PRE_MATCH:
            cards.append(f"{match.home_team} vs {match.away_team}")
            cards.append(f"{match.league} {match.match_time.strftime('%m-%d %H:%M')}")
            if match.standings_summary:
                cards.append(match.standings_summary)
            if match.form_summary:
                cards.append(match.form_summary)
        else:
            cards.append(f"{match.home_team} {match.home_score}-{match.away_score} {match.away_team}")
            cards.append(match.fixture_status_text or "赛果已出")
            if match.standings_summary:
                cards.append(match.standings_summary)
            if match.form_summary:
                cards.append(match.form_summary)

        cards = [item.strip() for item in cards if item and item.strip()][:6]
        title = cards[0] if cards else f"{match.home_team} vs {match.away_team}"
        return DouyinVideoJobRequest(
            match_id=match.match_id,
            video_mode=mode,
            title=title,
            caption_cards=cards,
            facts={
                "league": match.league,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "match_time": match.match_time.isoformat(),
                "home_score": match.home_score,
                "away_score": match.away_score,
            },
            assets={},
            duration_target_sec=20,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -k "planner or payload_builder" -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/douyin_video.py tests/test_douyin_video_service.py
git commit -m "feat: add douyin video planner and payload builder"
```

## Task 3: Add provider protocol, fake provider, and orchestration service

**Files:**
- Modify: `src/auto_football/douyin_video.py`
- Test: `tests/test_douyin_video_service.py`

- [ ] **Step 1: Write failing service orchestration tests**

Append these tests to `tests/test_douyin_video_service.py`:

```python
from __future__ import annotations

from auto_football.douyin_video import (
    DouyinVideoPayloadBuilder,
    DouyinVideoPlanner,
    DouyinVideoService,
    FakePixelleClient,
)
from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskStatus


class InMemoryTaskStore:
    def __init__(self):
        self.saved = {}

    def save_submitted_task(self, record):
        self.saved[record.provider_task_id] = record
        return record

    def get_task_by_provider_task_id(self, provider_task_id):
        return self.saved.get(provider_task_id)

    def update_task(self, provider_task_id, *, status, video_url=None, error_message=None):
        record = self.saved[provider_task_id]
        record.status = status
        record.video_url = video_url
        record.error_message = error_message
        return record


def test_service_submit_creates_queued_task_record() -> None:
    store = InMemoryTaskStore()
    service = DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=FakePixelleClient(),
        task_store=store,
    )

    record = service.submit(_match(), DouyinVideoMode.PRE_MATCH)

    assert record.status == DouyinVideoTaskStatus.QUEUED
    assert record.provider_task_id is not None
    assert record.payload_snapshot["match_id"] == 101


def test_service_sync_updates_finished_video_url() -> None:
    store = InMemoryTaskStore()
    provider = FakePixelleClient()
    service = DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=provider,
        task_store=store,
    )

    submitted = service.submit(_match(home_score=2, away_score=1), DouyinVideoMode.RESULT_FLASH)
    provider.complete(submitted.provider_task_id, video_url="https://video.example/out.mp4")

    synced = service.sync(submitted.provider_task_id)

    assert synced.status == DouyinVideoTaskStatus.SUCCEEDED
    assert synced.video_url == "https://video.example/out.mp4"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -k "service_submit or service_sync" -v
```

Expected:

- FAIL because the service and fake provider do not exist

- [ ] **Step 3: Implement provider protocol, fake provider, and service**

Append this code to `src/auto_football/douyin_video.py`:

```python
from dataclasses import dataclass
from typing import Protocol

from auto_football.schemas import (
    DouyinVideoTaskRecord,
    DouyinVideoTaskStatus,
)


@dataclass
class ProviderSubmitResult:
    provider_task_id: str
    status: DouyinVideoTaskStatus


@dataclass
class ProviderPollResult:
    status: DouyinVideoTaskStatus
    video_url: str | None = None
    error_message: str | None = None


class VideoProvider(Protocol):
    def submit(self, payload: DouyinVideoJobRequest) -> ProviderSubmitResult:
        ...

    def poll(self, provider_task_id: str) -> ProviderPollResult:
        ...


class FakePixelleClient:
    def __init__(self) -> None:
        self._tasks: dict[str, ProviderPollResult] = {}
        self._counter = 0

    def submit(self, payload: DouyinVideoJobRequest) -> ProviderSubmitResult:
        self._counter += 1
        task_id = f"fake-{self._counter}"
        self._tasks[task_id] = ProviderPollResult(status=DouyinVideoTaskStatus.RUNNING)
        return ProviderSubmitResult(provider_task_id=task_id, status=DouyinVideoTaskStatus.QUEUED)

    def poll(self, provider_task_id: str) -> ProviderPollResult:
        return self._tasks[provider_task_id]

    def complete(self, provider_task_id: str, *, video_url: str) -> None:
        self._tasks[provider_task_id] = ProviderPollResult(
            status=DouyinVideoTaskStatus.SUCCEEDED,
            video_url=video_url,
        )


class DouyinVideoService:
    def __init__(self, *, planner, payload_builder, provider: VideoProvider, task_store) -> None:
        self.planner = planner
        self.payload_builder = payload_builder
        self.provider = provider
        self.task_store = task_store

    def submit(self, match: MatchInfo, mode: DouyinVideoMode) -> DouyinVideoTaskRecord:
        decision = self.planner.plan(match, mode)
        if not decision.generate:
            record = DouyinVideoTaskRecord(
                match_id=match.match_id,
                video_mode=mode,
                status=DouyinVideoTaskStatus.SKIPPED_INSUFFICIENT_DATA,
                error_message=decision.skip_reason,
            )
            return self.task_store.save_submitted_task(record)

        payload = self.payload_builder.build(match, mode)
        submitted = self.provider.submit(payload)
        record = DouyinVideoTaskRecord(
            match_id=match.match_id,
            video_mode=mode,
            provider_task_id=submitted.provider_task_id,
            status=submitted.status,
            payload_snapshot=payload.model_dump(mode="json"),
        )
        return self.task_store.save_submitted_task(record)

    def sync(self, provider_task_id: str) -> DouyinVideoTaskRecord:
        polled = self.provider.poll(provider_task_id)
        return self.task_store.update_task(
            provider_task_id,
            status=polled.status,
            video_url=polled.video_url,
            error_message=polled.error_message,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -k "service_submit or service_sync" -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/douyin_video.py tests/test_douyin_video_service.py
git commit -m "feat: add douyin video service orchestration"
```

## Task 4: Add task persistence in the database layer

**Files:**
- Modify: `src/auto_football/infra/db/models.py`
- Modify: `src/auto_football/infra/db/migrations.py`
- Modify: `src/auto_football/infra/db/repositories.py`
- Modify: `src/auto_football/db.py`
- Test: `tests/test_douyin_video_db.py`

- [ ] **Step 1: Write the failing DB persistence test**

Create `tests/test_douyin_video_db.py` with:

```python
from __future__ import annotations

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskRecord, DouyinVideoTaskStatus


def test_database_saves_and_updates_douyin_video_tasks(tmp_path) -> None:
    db_path = tmp_path / "douyin_video.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    saved = db.save_douyin_video_task(
        DouyinVideoTaskRecord(
            match_id=501,
            video_mode=DouyinVideoMode.PRE_MATCH,
            provider_task_id="task-1",
            status=DouyinVideoTaskStatus.QUEUED,
            payload_snapshot={"match_id": 501},
        )
    )

    assert saved.provider_task_id == "task-1"
    assert db.get_douyin_video_task("task-1").status == DouyinVideoTaskStatus.QUEUED

    updated = db.update_douyin_video_task(
        "task-1",
        status=DouyinVideoTaskStatus.SUCCEEDED,
        video_url="https://video.example/final.mp4",
        error_message=None,
    )

    assert updated.status == DouyinVideoTaskStatus.SUCCEEDED
    assert updated.video_url == "https://video.example/final.mp4"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_db.py -v
```

Expected:

- FAIL because the model and database methods do not exist

- [ ] **Step 3: Add the DB model, migration bootstrap, repository functions, and Database methods**

Add this model to `src/auto_football/infra/db/models.py`:

```python
class DouyinVideoTaskRecordModel(Base):
    __tablename__ = "douyin_video_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer)
    video_mode: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32), default="pixelle")
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(64))
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
```

Add this helper to `src/auto_football/infra/db/migrations.py`:

```python
def ensure_douyin_video_task_columns(engine) -> None:
    inspector = inspect(engine)
    if "douyin_video_tasks" not in inspector.get_table_names():
        return
```

Add these repository helpers to `src/auto_football/infra/db/repositories.py`:

```python
from auto_football.schemas import DouyinVideoTaskRecord, DouyinVideoTaskStatus
from .models import DouyinVideoTaskRecordModel


def save_douyin_video_task(session, payload: DouyinVideoTaskRecord) -> DouyinVideoTaskRecord:
    record = DouyinVideoTaskRecordModel(
        match_id=payload.match_id,
        video_mode=payload.video_mode.value,
        provider=payload.provider,
        provider_task_id=payload.provider_task_id,
        status=payload.status.value,
        video_url=payload.video_url,
        error_message=payload.error_message,
        payload_snapshot=payload.payload_snapshot,
    )
    session.add(record)
    session.commit()
    return payload


def get_douyin_video_task(session, provider_task_id: str) -> DouyinVideoTaskRecord | None:
    row = session.execute(
        select(DouyinVideoTaskRecordModel).where(DouyinVideoTaskRecordModel.provider_task_id == provider_task_id)
    ).scalar_one_or_none()
    if row is None:
        return None
    return DouyinVideoTaskRecord(
        match_id=row.match_id,
        video_mode=row.video_mode,
        provider=row.provider,
        provider_task_id=row.provider_task_id,
        status=row.status,
        video_url=row.video_url,
        error_message=row.error_message,
        payload_snapshot=row.payload_snapshot or {},
    )


def update_douyin_video_task(session, provider_task_id: str, *, status: DouyinVideoTaskStatus, video_url: str | None, error_message: str | None) -> DouyinVideoTaskRecord:
    row = session.execute(
        select(DouyinVideoTaskRecordModel).where(DouyinVideoTaskRecordModel.provider_task_id == provider_task_id)
    ).scalar_one()
    row.status = status.value
    row.video_url = video_url
    row.error_message = error_message
    row.updated_at = datetime.utcnow()
    session.commit()
    return DouyinVideoTaskRecord(
        match_id=row.match_id,
        video_mode=row.video_mode,
        provider=row.provider,
        provider_task_id=row.provider_task_id,
        status=row.status,
        video_url=row.video_url,
        error_message=row.error_message,
        payload_snapshot=row.payload_snapshot or {},
    )
```

Add these methods to `src/auto_football/db.py`:

```python
    def save_douyin_video_task(self, payload):
        with self.session() as session:
            return repositories.save_douyin_video_task(session, payload)

    def get_douyin_video_task(self, provider_task_id: str):
        with self.session() as session:
            return repositories.get_douyin_video_task(session, provider_task_id)

    def update_douyin_video_task(self, provider_task_id: str, *, status, video_url=None, error_message=None):
        with self.session() as session:
            return repositories.update_douyin_video_task(
                session,
                provider_task_id,
                status=status,
                video_url=video_url,
                error_message=error_message,
            )
```

Also update `Database.init_db()` to call `ensure_douyin_video_task_columns(self.engine)`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_db.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/infra/db/models.py src/auto_football/infra/db/migrations.py src/auto_football/infra/db/repositories.py src/auto_football/db.py tests/test_douyin_video_db.py
git commit -m "feat: persist douyin video tasks"
```

## Task 5: Wire the service to the real database-backed store

**Files:**
- Modify: `src/auto_football/douyin_video.py`
- Test: `tests/test_douyin_video_service.py`

- [ ] **Step 1: Write the failing database-backed service test**

Append this test to `tests/test_douyin_video_service.py`:

```python
from __future__ import annotations

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.douyin_video import (
    DatabaseDouyinVideoTaskStore,
    DouyinVideoPayloadBuilder,
    DouyinVideoPlanner,
    DouyinVideoService,
    FakePixelleClient,
)
from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskStatus


def test_database_task_store_round_trips_service_records(tmp_path) -> None:
    db_path = tmp_path / "service_store.db"
    db = Database(Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    db.init_db()
    store = DatabaseDouyinVideoTaskStore(db)
    provider = FakePixelleClient()
    service = DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=provider,
        task_store=store,
    )

    submitted = service.submit(_match(), DouyinVideoMode.PRE_MATCH)
    provider.complete(submitted.provider_task_id, video_url="https://video.example/ok.mp4")
    synced = service.sync(submitted.provider_task_id)

    assert synced.status == DouyinVideoTaskStatus.SUCCEEDED
    assert db.get_douyin_video_task(submitted.provider_task_id).video_url == "https://video.example/ok.mp4"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py::test_database_task_store_round_trips_service_records -v
```

Expected:

- FAIL because `DatabaseDouyinVideoTaskStore` does not exist

- [ ] **Step 3: Implement the DB-backed task store**

Add this class to `src/auto_football/douyin_video.py`:

```python
class DatabaseDouyinVideoTaskStore:
    def __init__(self, db) -> None:
        self.db = db

    def save_submitted_task(self, record: DouyinVideoTaskRecord) -> DouyinVideoTaskRecord:
        return self.db.save_douyin_video_task(record)

    def get_task_by_provider_task_id(self, provider_task_id: str) -> DouyinVideoTaskRecord | None:
        return self.db.get_douyin_video_task(provider_task_id)

    def update_task(self, provider_task_id: str, *, status, video_url=None, error_message=None) -> DouyinVideoTaskRecord:
        return self.db.update_douyin_video_task(
            provider_task_id,
            status=status,
            video_url=video_url,
            error_message=error_message,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py::test_database_task_store_round_trips_service_records -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/douyin_video.py tests/test_douyin_video_service.py
git commit -m "feat: add database-backed douyin video task store"
```

## Task 6: Add CLI commands for submit, sync, and run

**Files:**
- Modify: `src/auto_football/cli.py`
- Test: `tests/test_douyin_video_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/test_douyin_video_cli.py` with:

```python
from __future__ import annotations

from datetime import datetime, timezone

from typer.testing import CliRunner

from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform


def test_douyin_video_submit_command_submits_task(monkeypatch) -> None:
    from auto_football.cli import app

    runner = CliRunner()

    class FakeDB:
        def __init__(self, settings):
            pass

        def get_match_bundle(self, match_id):
            return {
                "match": MatchInfo(
                    match_id=match_id,
                    league="Premier League",
                    match_time=datetime(2026, 5, 12, 20, 0, tzinfo=timezone.utc),
                    home_team="Liverpool",
                    away_team="Arsenal",
                ),
                "contents": {
                    "wechat": GeneratedContent(
                        match_id=match_id,
                        platform=Platform.WECHAT,
                        mode=ContentMode.PRE_MATCH,
                        title="seed",
                        content="seed content",
                    )
                },
            }

    class FakeService:
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, match, mode):
            from auto_football.schemas import DouyinVideoTaskRecord, DouyinVideoTaskStatus
            return DouyinVideoTaskRecord(
                match_id=match.match_id,
                video_mode=mode,
                provider_task_id="task-123",
                status=DouyinVideoTaskStatus.QUEUED,
            )

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.build_douyin_video_service", lambda settings, db: FakeService())

    result = runner.invoke(app, ["douyin-video-submit", "--match-id", "42", "--mode", "pre_match"])

    assert result.exit_code == 0
    assert "task-123" in result.stdout


def test_douyin_video_sync_command_prints_video_url(monkeypatch) -> None:
    from auto_football.cli import app

    runner = CliRunner()

    class FakeDB:
        def __init__(self, settings):
            pass

    class FakeService:
        def __init__(self, *args, **kwargs):
            pass

        def sync(self, task_id):
            from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskRecord, DouyinVideoTaskStatus
            return DouyinVideoTaskRecord(
                match_id=42,
                video_mode=DouyinVideoMode.PRE_MATCH,
                provider_task_id=task_id,
                status=DouyinVideoTaskStatus.SUCCEEDED,
                video_url="https://video.example/final.mp4",
            )

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.build_douyin_video_service", lambda settings, db: FakeService())

    result = runner.invoke(app, ["douyin-video-sync", "--task-id", "task-123"])

    assert result.exit_code == 0
    assert "final.mp4" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_cli.py -v
```

Expected:

- FAIL because the commands and builder entrypoint do not exist

- [ ] **Step 3: Add CLI service builder and commands**

Add this helper near the top of `src/auto_football/cli.py` imports:

```python
from auto_football.douyin_video import (
    DatabaseDouyinVideoTaskStore,
    DouyinVideoPayloadBuilder,
    DouyinVideoPlanner,
    DouyinVideoService,
    PixelleHttpClient,
)
from auto_football.schemas import DouyinVideoMode
```

Add this helper function in `src/auto_football/cli.py`:

```python
def build_douyin_video_service(settings, db):
    return DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=PixelleHttpClient(settings),
        task_store=DatabaseDouyinVideoTaskStore(db),
    )
```

Add these commands:

```python
@app.command("douyin-video-submit")
def douyin_video_submit(
    match_id: int = typer.Option(..., "--match-id"),
    mode: str = typer.Option(..., "--mode"),
) -> None:
    settings = get_settings()
    db = Database(settings)
    bundle = db.get_match_bundle(match_id)
    if bundle is None:
        typer.echo(f"Match {match_id} not found.")
        raise typer.Exit(code=1)
    service = build_douyin_video_service(settings, db)
    record = service.submit(bundle["match"], DouyinVideoMode(mode))
    typer.echo(json_dumps(record.model_dump()))


@app.command("douyin-video-sync")
def douyin_video_sync(task_id: str = typer.Option(..., "--task-id")) -> None:
    settings = get_settings()
    db = Database(settings)
    service = build_douyin_video_service(settings, db)
    record = service.sync(task_id)
    typer.echo(json_dumps(record.model_dump()))
```

Also add:

```python
@app.command("douyin-video-run")
def douyin_video_run(
    match_id: int = typer.Option(..., "--match-id"),
    mode: str = typer.Option(..., "--mode"),
) -> None:
    settings = get_settings()
    db = Database(settings)
    bundle = db.get_match_bundle(match_id)
    if bundle is None:
        typer.echo(f"Match {match_id} not found.")
        raise typer.Exit(code=1)
    service = build_douyin_video_service(settings, db)
    submitted = service.submit(bundle["match"], DouyinVideoMode(mode))
    if submitted.provider_task_id is None:
        typer.echo(json_dumps(submitted.model_dump()))
        raise typer.Exit(code=0)
    record = service.sync(submitted.provider_task_id)
    typer.echo(json_dumps(record.model_dump()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_cli.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/cli.py tests/test_douyin_video_cli.py
git commit -m "feat: add douyin video test commands"
```

## Task 7: Add the real Pixelle HTTP client

**Files:**
- Modify: `src/auto_football/douyin_video.py`
- Test: `tests/test_douyin_video_service.py`

- [ ] **Step 1: Write the failing HTTP client tests**

Append these tests to `tests/test_douyin_video_service.py`:

```python
from __future__ import annotations

import httpx

from auto_football.config import Settings
from auto_football.douyin_video import PixelleHttpClient
from auto_football.schemas import DouyinVideoJobRequest, DouyinVideoMode, DouyinVideoTaskStatus


def test_pixelle_http_client_submit_maps_task_id(monkeypatch) -> None:
    settings = Settings()
    client = PixelleHttpClient(settings)

    def fake_post(self, url, json, timeout):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"task_id": "pixelle-123"}

        return Response()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    result = client.submit(
        DouyinVideoJobRequest(
            match_id=1,
            video_mode=DouyinVideoMode.PRE_MATCH,
            title="Title",
            caption_cards=["A", "B"],
            facts={},
            assets={},
            duration_target_sec=20,
        )
    )

    assert result.provider_task_id == "pixelle-123"
    assert result.status == DouyinVideoTaskStatus.QUEUED
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -k "pixelle_http_client" -v
```

Expected:

- FAIL because `PixelleHttpClient` does not exist

- [ ] **Step 3: Implement the HTTP client**

Append this code to `src/auto_football/douyin_video.py`:

```python
import httpx


class PixelleHttpClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    def submit(self, payload: DouyinVideoJobRequest) -> ProviderSubmitResult:
        with httpx.Client() as client:
            response = client.post(
                self.settings.pixelle_base_url.rstrip("/") + self.settings.pixelle_submit_path,
                json=payload.model_dump(mode="json"),
                timeout=self.settings.pixelle_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        task_id = str(body.get("task_id") or body.get("id") or "")
        if not task_id:
            raise ValueError("Pixelle submit response missing task_id")
        return ProviderSubmitResult(provider_task_id=task_id, status=DouyinVideoTaskStatus.QUEUED)

    def poll(self, provider_task_id: str) -> ProviderPollResult:
        task_path = self.settings.pixelle_task_path_template.format(task_id=provider_task_id)
        with httpx.Client() as client:
            response = client.get(
                self.settings.pixelle_base_url.rstrip("/") + task_path,
                timeout=self.settings.pixelle_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()

        status_text = str(body.get("status") or "").lower()
        if status_text in {"queued", "pending"}:
            return ProviderPollResult(status=DouyinVideoTaskStatus.QUEUED)
        if status_text in {"running", "processing"}:
            return ProviderPollResult(status=DouyinVideoTaskStatus.RUNNING)
        if status_text in {"succeeded", "success", "completed"}:
            return ProviderPollResult(
                status=DouyinVideoTaskStatus.SUCCEEDED,
                video_url=body.get("video_url") or body.get("url"),
            )
        return ProviderPollResult(
            status=DouyinVideoTaskStatus.RENDER_FAILED,
            error_message=str(body.get("error_message") or body.get("error") or "render_failed"),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -k "pixelle_http_client" -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_football/douyin_video.py tests/test_douyin_video_service.py
git commit -m "feat: add pixelle http client"
```

## Task 8: Run focused verification for the new chain

**Files:**
- Modify: none
- Test: `tests/test_douyin_video_service.py`
- Test: `tests/test_douyin_video_db.py`
- Test: `tests/test_douyin_video_cli.py`

- [ ] **Step 1: Run the service tests**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py -v
```

Expected:

- PASS

- [ ] **Step 2: Run the DB tests**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_db.py -v
```

Expected:

- PASS

- [ ] **Step 3: Run the CLI tests**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_cli.py -v
```

Expected:

- PASS

- [ ] **Step 4: Run a combined focused suite**

Run:

```powershell
& 'D:\code_app\annconda_use\envs\auto_football\python.exe' -m pytest tests/test_douyin_video_service.py tests/test_douyin_video_db.py tests/test_douyin_video_cli.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_douyin_video_service.py tests/test_douyin_video_db.py tests/test_douyin_video_cli.py
git commit -m "test: verify douyin video sidecar flow"
```

## Self-Review

Spec coverage check:

- Local sidecar strategy: covered by Pixelle HTTP client and config task
- `pre_match` and `result_flash`: covered by planner and payload builder task
- Shared facts, separate Douyin payload: covered by payload builder task
- Task persistence: covered by DB task
- CLI test flow: covered by CLI task
- Testing-first, no Douyin publishing: covered by focused verification task

Placeholder scan:

- No `TBD`, `TODO`, or "implement later" placeholders remain in tasks
- Every code-editing task includes concrete code and exact commands

Type consistency check:

- `DouyinVideoMode`, `DouyinVideoTaskStatus`, and `DouyinVideoTaskRecord` are introduced before later tasks use them
- `submit`, `poll`, `save_douyin_video_task`, and `update_douyin_video_task` signatures are reused consistently
