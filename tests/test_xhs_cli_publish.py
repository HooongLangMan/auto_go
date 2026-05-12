from __future__ import annotations

from datetime import datetime, timezone

import auto_football.cli as cli
import pytest
from auto_football.schemas import ContentMode, ContentStatus, GeneratedContent, MatchInfo, Platform, PublishResult


def test_xhs_publish_match_uses_playwright_publisher(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, settings) -> None:
            self.settings = settings

        def get_match_bundle(self, match_id: int):
            return {
                "match": MatchInfo(
                    match_id=match_id,
                    league="CSL",
                    match_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
                    home_team="Shanghai Shenhua",
                    away_team="Chengdu Rongcheng",
                ),
                "contents": {
                    "xiaohongshu": GeneratedContent(
                        match_id=match_id,
                        platform=Platform.XIAOHONGSHU,
                        mode=ContentMode.PRE_MATCH,
                        account_id="xhs-main",
                        status=ContentStatus.READY_TO_PUBLISH,
                        title="测试小红书标题",
                        content="测试小红书正文",
                        images=["D:/auto_go/generated/images/test.png"],
                    )
                },
            }

        def log_publish(self, match_id: int, result: PublishResult) -> None:
            captured["logged_match_id"] = match_id
            captured["logged_status"] = result.status

    class FakePublisher:
        def __init__(self, settings) -> None:
            self.settings = settings

        def create_draft(self, bundle):
            captured["bundle"] = bundle
            return PublishResult(platform=Platform.XIAOHONGSHU, status="draft_saved", publish_id="xhs-draft-1")

    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setattr(cli, "XiaohongshuPlaywrightPublisher", FakePublisher)

    cli.xhs_publish_match(match_id=9902)

    output = capsys.readouterr().out
    assert captured["bundle"].content.platform is Platform.XIAOHONGSHU
    assert captured["logged_match_id"] == 9902
    assert captured["logged_status"] == "draft_saved"
    assert "draft_saved" in output


def test_xhs_status_uses_playwright_publisher(monkeypatch, capsys) -> None:
    class FakePublisher:
        def __init__(self, settings) -> None:
            self.settings = settings

        def status(self):
            return {"backend": "bitbrowser+playwright", "has_profile_id": True}

    monkeypatch.setattr(cli, "XiaohongshuPlaywrightPublisher", FakePublisher)

    cli.xhs_status()

    output = capsys.readouterr().out
    assert "bitbrowser+playwright" in output


def test_xhs_login_uses_playwright_publisher(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePublisher:
        def __init__(self, settings) -> None:
            self.settings = settings

        def login(self, timeout_seconds: int = 180, force: bool = False) -> int:
            captured["timeout"] = timeout_seconds
            captured["force"] = force
            return 0

    monkeypatch.setattr(cli, "XiaohongshuPlaywrightPublisher", FakePublisher)

    with pytest.raises(cli.typer.Exit) as exc_info:
        cli.xhs_login(timeout=45, force=True)

    assert exc_info.value.exit_code == 0
    assert captured == {"timeout": 45, "force": True}


def test_xhs_browser_uses_playwright_publisher(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePublisher:
        def __init__(self, settings) -> None:
            self.settings = settings

        def ensure_browser(self) -> int:
            captured["called"] = True
            return 0

    monkeypatch.setattr(cli, "XiaohongshuPlaywrightPublisher", FakePublisher)

    with pytest.raises(cli.typer.Exit) as exc_info:
        cli.xhs_browser()

    assert exc_info.value.exit_code == 0
    assert captured["called"] is True
