from __future__ import annotations

import sys
import types

from auto_football.config import Settings
from auto_football.schemas import GeneratedContent, Platform


def _install_wechat_test_doubles() -> None:
    packages = [
        "wechat_oa_api_mcp",
        "wechat_oa_api_mcp.core",
    ]
    for name in packages:
        sys.modules.setdefault(name, types.ModuleType(name))

    access_token = types.ModuleType("wechat_oa_api_mcp.core.access_token")
    access_token.get_access_token = lambda payload: {"success": False}
    draft = types.ModuleType("wechat_oa_api_mcp.core.draft")
    draft.create_wechat_draft_tool = lambda payload: {"success": False}
    publish = types.ModuleType("wechat_oa_api_mcp.core.publish")
    publish.publish_wechat_draft_tool = lambda payload: {"success": False}

    sys.modules.setdefault("wechat_oa_api_mcp.core.access_token", access_token)
    sys.modules.setdefault("wechat_oa_api_mcp.core.draft", draft)
    sys.modules.setdefault("wechat_oa_api_mcp.core.publish", publish)


_install_wechat_test_doubles()

from auto_football.adapters import PublisherRegistry, XiaohongshuPublisher


def test_xhs_publisher_does_not_use_removed_mcp_backend() -> None:
    settings = Settings(RUN_DRY=False, PUBLISH_ENABLED=True, XHS_PUBLISH_ENABLED=True)
    publisher = XiaohongshuPublisher(settings)

    result = publisher.publish(
        9001,
        GeneratedContent(
            match_id=9001,
            platform=Platform.XIAOHONGSHU,
            title="标题",
            content="正文",
            images=["missing.png"],
        ),
    )

    assert result.status == "failed"
    assert result.error_message is not None
    assert "Playwright" in result.error_message
    assert "xhs" + "-" + "mcp" not in result.error_message


def test_xhs_platform_config_reports_bitbrowser_playwright_backend() -> None:
    settings = Settings(BITBROWSER_PROFILE_ID="", XHS_DRAFT_ONLY=True)
    registry = PublisherRegistry(settings)

    config = registry.describe_platform_config(Platform.XIAOHONGSHU)

    assert config["backend"] == "bitbrowser+playwright"
    assert config["draft_only"] is True
    assert config["has_profile_id"] is False


def test_xhs_legacy_adapter_delegates_status_to_playwright_backend(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePlaywrightPublisher:
        def __init__(self, settings) -> None:
            captured["settings"] = settings

        def healthcheck(self) -> dict[str, object]:
            return self.status()

        def status(self) -> dict[str, object]:
            return {
                "platform": "xiaohongshu",
                "backend": "bitbrowser+playwright",
                "has_profile_id": True,
                "draft_only": False,
            }

    monkeypatch.setattr("auto_football.adapters.XiaohongshuPlaywrightPublisher", FakePlaywrightPublisher)

    publisher = XiaohongshuPublisher(Settings(BITBROWSER_PROFILE_ID="profile-1", XHS_DRAFT_ONLY=False))
    payload = publisher.status()

    assert payload["backend"] == "bitbrowser+playwright"
    assert payload["has_profile_id"] is True
    assert payload["draft_only"] is False


def test_xhs_status_reports_configured_backend(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher

    class FakeSessionManager:
        backend_name = "patchright"

        def __init__(self, settings) -> None:
            self.settings = settings

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.publisher.BitBrowserSessionManager",
        FakeSessionManager,
    )

    publisher = XiaohongshuPlaywrightPublisher(Settings(XHS_AUTOMATION_BACKEND="patchright"))
    payload = publisher.status()

    assert payload["backend_configured"] == "patchright"
    assert payload["backend_active"] == "patchright"
