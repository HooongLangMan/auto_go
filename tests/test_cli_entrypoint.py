from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner


def test_cli_help_works_without_optional_wechat_package() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(src), env.get("PYTHONPATH", "")]).strip(os.pathsep)

    result = subprocess.run(
        [sys.executable, "-m", "auto_football.cli", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "doctor" in result.stdout


def test_xhs_auto_draft_command_selects_and_saves(monkeypatch) -> None:
    from auto_football.cli import app
    from auto_football.schemas import GeneratedContent, MatchInfo, Platform

    runner = CliRunner()
    captured: dict[str, object] = {}

    class FakeDB:
        def __init__(self, settings):
            pass

        def get_preview_payloads(self, **kwargs):
            return [
                {
                    "match_id": 5,
                    "home_team": "Home",
                    "away_team": "Away",
                    "contents": [
                        {
                            "platform": "xiaohongshu",
                            "status": "ready_to_publish",
                            "content": "x" * 300,
                            "title": "good",
                            "images": ["cover.png"],
                        }
                    ],
                }
            ]

        def get_match_bundle(self, match_id):
            return {
                "match": MatchInfo(
                    match_id=5,
                    league="Test League",
                    match_time=datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc),
                    home_team="Home",
                    away_team="Away",
                ),
                "contents": {
                    "xiaohongshu": GeneratedContent(
                        match_id=5,
                        platform=Platform.XIAOHONGSHU,
                        title="good",
                        content="x" * 300,
                        images=["cover.png"],
                    )
                },
            }

        def log_publish(self, match_id, result):
            captured["logged"] = (match_id, result.status)

    class FakeSelector:
        def select_from_preview_payloads(self, payloads, *, platform):
            return {"match_id": 5, "payload": payloads[0], "content": payloads[0]["contents"][0]}

    class FakePublisher:
        def __init__(self, settings):
            pass

        def create_draft(self, bundle):
            captured["bundle"] = bundle

            class Result:
                status = "draft_saved"

                @staticmethod
                def model_dump():
                    return {"status": "draft_saved"}

            return Result()

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.AutoDraftSelectorService", lambda: FakeSelector())
    monkeypatch.setattr("auto_football.cli.XiaohongshuPlaywrightPublisher", FakePublisher)

    result = runner.invoke(app, ["xhs-auto-draft"])

    assert result.exit_code == 0
    assert "match_id=5" in result.stdout
    assert captured["logged"] == (5, "draft_saved")


def test_wechat_auto_draft_command_selects_and_saves(monkeypatch) -> None:
    from auto_football.cli import app
    from auto_football.schemas import GeneratedContent, MatchInfo, Platform

    runner = CliRunner()
    captured: dict[str, object] = {}

    class FakeDB:
        def __init__(self, settings):
            pass

        def get_preview_payloads(self, **kwargs):
            return [
                {
                    "match_id": 8,
                    "home_team": "Home",
                    "away_team": "Away",
                    "contents": [
                        {
                            "platform": "wechat",
                            "status": "ready_to_publish",
                            "content": "x" * 900,
                            "title": "good wechat",
                            "images": [],
                        }
                    ],
                }
            ]

        def get_match_bundle(self, match_id):
            return {
                "match": MatchInfo(
                    match_id=8,
                    league="Test League",
                    match_time=datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc),
                    home_team="Home",
                    away_team="Away",
                ),
                "contents": {
                    "wechat": GeneratedContent(
                        match_id=8,
                        platform=Platform.WECHAT,
                        title="good wechat",
                        content="x" * 900,
                        images=[],
                    )
                },
            }

        def log_publish(self, match_id, result):
            captured["logged"] = (match_id, result.status)

    class FakeSelector:
        def select_from_preview_payloads(self, payloads, *, platform):
            return {"match_id": 8, "payload": payloads[0], "content": payloads[0]["contents"][0]}

    class FakePublisher:
        def __init__(self, settings):
            pass

        def create_draft(self, bundle):
            captured["bundle"] = bundle

            class Result:
                status = "draft_created"

                @staticmethod
                def model_dump():
                    return {"status": "draft_created"}

            return Result()

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.AutoDraftSelectorService", lambda: FakeSelector())
    monkeypatch.setattr("auto_football.cli.WechatPublisher", FakePublisher)

    result = runner.invoke(app, ["wechat-auto-draft"])

    assert result.exit_code == 0
    assert "match_id=8" in result.stdout
    assert captured["logged"] == (8, "draft_created")
