from __future__ import annotations

from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.schemas import GeneratedContent, MatchInfo, Platform, PublishResult


def _bundle():
    from auto_football.infra.publishers.base import PublishBundle

    match = MatchInfo(
        match_id=42,
        league="Premier League",
        match_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
    )
    content = GeneratedContent(
        match_id=42,
        platform=Platform.WECHAT,
        title="测试标题",
        content="测试正文",
    )
    return PublishBundle(match=match, content=content)


def test_publish_bundle_keeps_cover_and_inline_images() -> None:
    from auto_football.infra.publishers.base import PublishBundle

    bundle = PublishBundle(
        match=_bundle().match,
        content=_bundle().content,
        cover_image="https://img.example/cover.png",
        inline_images=["https://img.example/1.png", "https://img.example/2.png"],
        metadata={"mode": "draft"},
    )

    assert bundle.cover_image == "https://img.example/cover.png"
    assert bundle.inline_images == ["https://img.example/1.png", "https://img.example/2.png"]
    assert bundle.metadata["mode"] == "draft"


def test_publisher_registry_exposes_wechat_xhs_and_douyin_publishers() -> None:
    from auto_football.infra.publishers.registry import PublisherRegistry

    registry = PublisherRegistry(Settings())

    assert registry.get(Platform.WECHAT).platform is Platform.WECHAT
    assert registry.get(Platform.XIAOHONGSHU).platform is Platform.XIAOHONGSHU
    assert registry.get(Platform.DOUYIN).platform is Platform.DOUYIN


def test_douyin_placeholder_returns_not_implemented() -> None:
    from auto_football.infra.publishers.douyin.publisher import DouyinPublisher

    publisher = DouyinPublisher(Settings())
    result = publisher.create_draft(_bundle())

    assert result.platform is Platform.DOUYIN
    assert result.status == "failed"
    assert result.error_message is not None
    assert "not implemented" in result.error_message.lower()
