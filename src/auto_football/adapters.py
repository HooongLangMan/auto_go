from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher
from auto_football.schemas import GeneratedContent, MatchInfo, Platform, PublishResult
from auto_football.infra.publishers.base import PublishBundle

try:
    from wechat_oa_api_mcp.core.access_token import get_access_token as get_wechat_access_token
    from wechat_oa_api_mcp.core.draft import create_wechat_draft_tool
    from wechat_oa_api_mcp.core.publish import publish_wechat_draft_tool
    from wechat_oa_api_mcp.core.draft import upload_media as upload_wechat_media
except Exception:  # pragma: no cover - optional dependency resilience
    get_wechat_access_token = None
    create_wechat_draft_tool = None
    publish_wechat_draft_tool = None
    upload_wechat_media = None


class PublisherRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.xhs_publisher = XiaohongshuPublisher(settings)
        self.wechat_publisher = WechatPublisher(settings)
        from auto_football.infra.publishers.registry import PublisherRegistry as InfraPublisherRegistry

        self._registry = InfraPublisherRegistry(
            settings,
            wechat_publisher=self.wechat_publisher,
            xhs_publisher=self.xhs_publisher,
        )

    def publish(self, match_id: int, content: GeneratedContent, match: MatchInfo | None = None) -> PublishResult:
        if self.settings.run_dry or not self.settings.publish_enabled:
            return PublishResult(
                platform=content.platform,
                status="dry_run",
                publish_id=f"dry-{content.platform.value}-{match_id}",
            )

        if content.platform is Platform.XIAOHONGSHU:
            if not self.settings.xhs_publish_enabled:
                return PublishResult(platform=content.platform, status="skipped", error_message="XHS publish disabled.")
            if match is not None:
                return self._registry.get(Platform.XIAOHONGSHU).create_draft(PublishBundle(match=match, content=content))
            return self.xhs_publisher.publish(match_id, content)

        if content.platform is Platform.WECHAT:
            if not self.settings.wechat_publish_enabled:
                return PublishResult(platform=content.platform, status="skipped", error_message="Wechat publish disabled.")
            if match is None:
                return PublishResult(platform=content.platform, status="failed", error_message="Match payload required for Wechat publishing.")
            return self._registry.get(Platform.WECHAT).create_draft(PublishBundle(match=match, content=content))

        return PublishResult(platform=content.platform, status="failed", error_message="Unsupported platform.")

    def describe_platform_config(self, platform: Platform) -> dict[str, str | list[str]]:
        if platform is Platform.WECHAT:
            return {
                "command": self.settings.wechat_mcp_command,
                "args": self.settings.wechat_mcp_args,
                "workdir": self.settings.wechat_mcp_workdir,
            }
        return self.xhs_publisher.status()


class XiaohongshuPublisher:
    platform = Platform.XIAOHONGSHU

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._publisher = XiaohongshuPlaywrightPublisher(settings)

    @property
    def backend(self) -> str:
        return self._publisher.backend

    @property
    def not_implemented_message(self) -> str:
        return "Xiaohongshu publishing is backed by BitBrowser + Playwright."

    def publish(self, match_id: int, content: GeneratedContent) -> PublishResult:
        del match_id
        return PublishResult(
            platform=content.platform,
            status="failed",
            error_message="Playwright Xiaohongshu publishing requires a full match payload.",
        )

    def create_draft(self, bundle: PublishBundle) -> PublishResult:
        return self._publisher.create_draft(bundle)

    def status(self) -> dict:
        return self._publisher.status()

    def healthcheck(self) -> dict[str, object]:
        return self._publisher.healthcheck()

    def login(self, timeout_seconds: int = 180, force: bool = False) -> int:
        return self._publisher.login(timeout_seconds=timeout_seconds, force=force)

    def ensure_browser(self) -> int:
        return self._publisher.ensure_browser()


class WechatPublisher:
    platform = Platform.WECHAT

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def publish(self, match_id: int | PublishBundle, content: GeneratedContent | None = None, match: MatchInfo | None = None) -> PublishResult:
        if isinstance(match_id, PublishBundle):
            return self.create_draft(match_id)

        if content is None or match is None:
            raise ValueError("GeneratedContent and MatchInfo are required for Wechat publishing.")

        return self._publish_legacy(match_id, content, match)

    def create_draft(self, bundle: PublishBundle) -> PublishResult:
        return self._publish_bundle(bundle)

    def healthcheck(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "backend": "wechat_oa_api_mcp",
            "has_dependency": bool(get_wechat_access_token and create_wechat_draft_tool and publish_wechat_draft_tool),
            "has_app_id": bool(self.settings.wechat_app_id),
            "has_app_secret": bool(self.settings.wechat_app_secret),
        }

    def _publish_legacy(self, match_id: int, content: GeneratedContent, match: MatchInfo) -> PublishResult:
        del match_id
        if (
            get_wechat_access_token is None
            or create_wechat_draft_tool is None
            or publish_wechat_draft_tool is None
            or upload_wechat_media is None
        ):
            return PublishResult(
                platform=content.platform,
                status="failed",
                error_message="Optional package 'wechat_oa_api_mcp' is not installed.",
            )

        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            return PublishResult(platform=content.platform, status="failed", error_message="Wechat AppID/AppSecret not configured.")

        token_result = get_wechat_access_token({"appid": self.settings.wechat_app_id, "appsecret": self.settings.wechat_app_secret})
        if not token_result.get("success"):
            return PublishResult(platform=content.platform, status="failed", error_message=token_result.get("error_msg") or "Failed to get Wechat access token.")

        cover_image_url = match.competition_logo_url or match.home_logo_url or match.away_logo_url
        if not cover_image_url:
            return PublishResult(platform=content.platform, status="failed", error_message="No public cover image URL available for Wechat draft.")

        inline_image_urls = self._upload_inline_images(token_result["access_token"], content.images)
        bundle = PublishBundle(
            match=match,
            content=content,
            cover_image=cover_image_url,
            inline_images=inline_image_urls,
        )
        return self._create_wechat_draft(token_result["access_token"], bundle)

    def _publish_bundle(self, bundle: PublishBundle) -> PublishResult:
        content = bundle.content
        if (
            get_wechat_access_token is None
            or create_wechat_draft_tool is None
            or publish_wechat_draft_tool is None
            or upload_wechat_media is None
        ):
            return PublishResult(
                platform=content.platform,
                status="failed",
                error_message="Optional package 'wechat_oa_api_mcp' is not installed.",
            )

        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            return PublishResult(platform=content.platform, status="failed", error_message="Wechat AppID/AppSecret not configured.")

        token_result = get_wechat_access_token({"appid": self.settings.wechat_app_id, "appsecret": self.settings.wechat_app_secret})
        if not token_result.get("success"):
            return PublishResult(platform=content.platform, status="failed", error_message=token_result.get("error_msg") or "Failed to get Wechat access token.")

        cover_image_url = bundle.cover_image or bundle.match.competition_logo_url or bundle.match.home_logo_url or bundle.match.away_logo_url
        if not cover_image_url:
            return PublishResult(platform=content.platform, status="failed", error_message="No public cover image URL available for Wechat draft.")

        inline_image_urls = bundle.inline_images or self._upload_inline_images(token_result["access_token"], content.images)
        prepared_bundle = bundle.model_copy(update={"cover_image": cover_image_url, "inline_images": inline_image_urls})
        return self._create_wechat_draft(token_result["access_token"], prepared_bundle)

    def _create_wechat_draft(self, access_token: str, bundle: PublishBundle) -> PublishResult:
        content = bundle.content
        draft_result = create_wechat_draft_tool(
            {
                "access_token": access_token,
                "image_url": bundle.cover_image,
                "title": self._normalize_title(content.title),
                "content": self._to_html(content.content, inline_image_urls=bundle.inline_images),
                "author": self.settings.wechat_author,
            }
        )
        if not draft_result.get("success"):
            return PublishResult(platform=content.platform, status="failed", error_message=draft_result.get("error_msg") or "Wechat draft creation failed.")

        draft_id = draft_result.get("draft_media_id")
        if not self.settings.wechat_auto_publish:
            return PublishResult(platform=content.platform, status="draft_created", publish_id=str(draft_id))

        publish_result = publish_wechat_draft_tool(
            {
                "access_token": access_token,
                "draft_media_id": draft_id,
            }
        )
        if not publish_result.get("success"):
            return PublishResult(platform=content.platform, status="failed", error_message=publish_result.get("error_msg") or "Wechat publish failed.")
        return PublishResult(platform=content.platform, status="published", publish_id=str(publish_result.get("publish_id") or draft_id))

    @staticmethod
    def _normalize_title(title: str) -> str:
        return " ".join(title.replace("\r", " ").replace("\n", " ").split())[:64]

    @staticmethod
    def _to_html(content: str, *, inline_image_urls: list[str] | None = None) -> str:
        parts = [part.strip() for part in content.replace("\r\n", "\n").split("\n\n") if part.strip()]
        if not parts:
            return ""

        images = [url for url in (inline_image_urls or []) if url]
        html_parts: list[str] = []
        image_insert_positions = WechatPublisher._image_insert_positions(len(parts), len(images))
        for index, part in enumerate(parts):
            html_parts.append(f"<p>{part.replace(chr(10), '<br>')}</p>")
            if index in image_insert_positions:
                image_url = images[image_insert_positions[index]]
                html_parts.append(WechatPublisher._inline_image_html(image_url))
        return "".join(html_parts)

    def _upload_inline_images(self, access_token: str, image_paths: list[str]) -> list[str]:
        uploaded_urls: list[str] = []
        for image_path in image_paths[:2]:
            if not image_path:
                continue
            try:
                uploaded_urls.append(upload_local_wechat_image(access_token, image_path))
            except Exception:
                continue
        return uploaded_urls

    @staticmethod
    def _image_insert_positions(paragraph_count: int, image_count: int) -> dict[int, int]:
        if paragraph_count <= 0 or image_count <= 0:
            return {}
        positions: dict[int, int] = {0: 0}
        if image_count >= 2 and paragraph_count >= 3:
            positions[paragraph_count - 2] = 1
        return positions

    @staticmethod
    def _inline_image_html(image_url: str) -> str:
        return (
            '<p><img '
            f'src="{image_url}" '
            'style="max-width:100%;height:auto;" '
            'data-ratio="0" data-s="300,640" /></p>'
        )


def upload_local_wechat_image(access_token: str, image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Wechat inline image not found: {image_path}")

    mime_type, _ = mimetypes.guess_type(path.name)
    content_type = (mime_type or "image/png").lower()
    with path.open("rb") as file_handle:
        files = {"media": (path.name, file_handle, content_type)}
        response = httpx.post(
            "https://api.weixin.qq.com/cgi-bin/media/uploadimg",
            params={"access_token": access_token},
            files=files,
            timeout=30,
        )
    response.raise_for_status()
    result = response.json()
    image_url = result.get("url")
    if not image_url:
        errcode = result.get("errcode")
        errmsg = result.get("errmsg") or result
        raise RuntimeError(f"Wechat inline image upload failed: {errcode} {errmsg}")
    return str(image_url)
