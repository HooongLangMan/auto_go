from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from auto_football.config import Settings
from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform


def _install_wechat_test_doubles() -> None:
    packages = [
        "wechat_oa_api_mcp",
        "wechat_oa_api_mcp.core",
    ]
    for name in packages:
        sys.modules.setdefault(name, types.ModuleType(name))

    access_token = types.ModuleType("wechat_oa_api_mcp.core.access_token")
    access_token.get_access_token = lambda payload: {"success": True, "access_token": "token-123"}
    draft = types.ModuleType("wechat_oa_api_mcp.core.draft")
    draft.create_wechat_draft_tool = lambda payload: {"success": True, "draft_media_id": "draft-123"}
    draft.upload_media = lambda access_token, file_info: "media-123"
    publish = types.ModuleType("wechat_oa_api_mcp.core.publish")
    publish.publish_wechat_draft_tool = lambda payload: {"success": True, "publish_id": "publish-123"}

    sys.modules["wechat_oa_api_mcp.core.access_token"] = access_token
    sys.modules["wechat_oa_api_mcp.core.draft"] = draft
    sys.modules["wechat_oa_api_mcp.core.publish"] = publish


_install_wechat_test_doubles()

import auto_football.adapters as adapters
from auto_football.adapters import WechatPublisher
from auto_football.adapters import upload_local_wechat_image


def test_wechat_body_html_inserts_inline_images_between_paragraphs() -> None:
    html = WechatPublisher._to_html(
        "第一段\n\n第二段\n\n第三段",
        inline_image_urls=["https://img.example/one.png", "https://img.example/two.png"],
    )

    assert "<p>第一段</p>" in html
    assert '<img src="https://img.example/one.png"' in html
    assert '<img src="https://img.example/two.png"' in html
    assert html.index("第一段") < html.index("https://img.example/one.png") < html.index("第二段")
    assert html.index("第二段") < html.index("https://img.example/two.png") < html.index("第三段")


def test_wechat_publish_uploads_inline_images_and_passes_html_to_draft(tmp_path, monkeypatch) -> None:
    cover_path = tmp_path / "cover.png"
    prediction_path = tmp_path / "prediction.png"
    cover_path.write_bytes(b"cover-bytes")
    prediction_path.write_bytes(b"prediction-bytes")

    uploaded: list[tuple[str, str]] = []
    captured_payload: dict[str, str] = {}

    def fake_upload_local_image(access_token: str, image_path: str) -> str:
        uploaded.append((access_token, image_path))
        return f"https://cdn.example/{Path(image_path).name}"

    def fake_create_wechat_draft_tool(payload: dict[str, str]) -> dict[str, str]:
        captured_payload.update(payload)
        return {"success": True, "draft_media_id": "draft-456"}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"url": "https://cdn.example/uploaded-inline.png"}

    def fake_post(url: str, *, params=None, files=None, timeout=None):
        del url, params, files, timeout
        return FakeResponse()

    monkeypatch.setattr(adapters, "get_wechat_access_token", lambda payload: {"success": True, "access_token": "token-123"})
    monkeypatch.setattr(adapters, "publish_wechat_draft_tool", lambda payload: {"success": True, "publish_id": "publish-123"})
    monkeypatch.setattr(adapters, "upload_wechat_media", object())

    monkeypatch.setattr(adapters, "upload_local_wechat_image", fake_upload_local_image)
    monkeypatch.setattr(adapters, "create_wechat_draft_tool", fake_create_wechat_draft_tool)
    monkeypatch.setattr(adapters.httpx, "post", fake_post)

    publisher = WechatPublisher(
        Settings(
            WECHAT_APP_ID="wx-test",
            WECHAT_APP_SECRET="secret-test",
        )
    )

    result = publisher.publish(
        9005,
        GeneratedContent(
            match_id=9005,
            platform=Platform.WECHAT,
            mode=ContentMode.PRE_MATCH,
            title="测试标题",
            content="第一段\n\n第二段\n\n第三段",
            images=[str(cover_path), str(prediction_path)],
        ),
        MatchInfo(
            match_id=9005,
            league="Premier League",
            match_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            home_team="Home",
            away_team="Away",
            competition_logo_url="https://example.com/cover.png",
        ),
    )

    assert result.status == "draft_created"
    assert uploaded == [
        ("token-123", str(cover_path)),
        ("token-123", str(prediction_path)),
    ]
    assert captured_payload["image_url"] == "https://example.com/cover.png"
    assert '<img src="https://cdn.example/cover.png"' in captured_payload["content"]
    assert '<img src="https://cdn.example/prediction.png"' in captured_payload["content"]


def test_upload_local_wechat_image_uses_uploadimg_returned_url(tmp_path, monkeypatch) -> None:
    image_path = tmp_path / "inline.png"
    image_path.write_bytes(b"inline-bytes")
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"url": "https://mmbiz.qpic.cn/real-inline-url"}

    def fake_post(url: str, *, params=None, files=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["files_keys"] = sorted((files or {}).keys())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(adapters.httpx, "post", fake_post)

    result = upload_local_wechat_image("token-123", str(image_path))

    assert result == "https://mmbiz.qpic.cn/real-inline-url"
    assert captured["url"] == "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
    assert captured["params"] == {"access_token": "token-123"}
    assert captured["files_keys"] == ["media"]
