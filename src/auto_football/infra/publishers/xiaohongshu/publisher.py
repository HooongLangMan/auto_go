from __future__ import annotations

import json
import time

from auto_football.config import Settings
from auto_football.infra.publishers.base import PublishBundle
from auto_football.schemas import Platform, PublishResult

from .draft_writer import XiaohongshuDraftWriter
from .session import BitBrowserSessionManager


class XiaohongshuPlaywrightPublisher:
    platform = Platform.XIAOHONGSHU

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session_manager = BitBrowserSessionManager(settings)
        self.draft_writer = XiaohongshuDraftWriter(settings)

    @property
    def backend(self) -> str:
        return f"bitbrowser+{self.session_manager.backend_name}"

    def healthcheck(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "backend": self.backend,
            "backend_configured": (self.settings.xhs_automation_backend or "playwright").strip().lower(),
            "backend_active": self.session_manager.backend_name,
            "has_profile_id": bool(self.settings.bitbrowser_profile_id),
            "draft_only": bool(self.settings.xhs_draft_only),
        }

    def status(self) -> dict[str, object]:
        payload = self.healthcheck()
        payload["status"] = "ready" if payload["has_profile_id"] else "missing_profile_id"
        payload["publish_url"] = self.settings.xhs_publish_url
        return payload

    def create_draft(self, bundle: PublishBundle) -> PublishResult:
        if not self.settings.bitbrowser_profile_id:
            return PublishResult(
                platform=self.platform,
                status="failed",
                error_message="BitBrowser profile id is not configured.",
            )
        try:
            page = self.session_manager.open_publish_page()
            result = self.draft_writer.save_draft(
                page=page,
                bundle=bundle,
                default_tags=self._default_tags(),
            )
        except Exception as exc:
            return PublishResult(platform=self.platform, status="failed", error_message=str(exc))

        return PublishResult(
            platform=self.platform,
            status=str(result.get("status") or "failed"),
            publish_id=result.get("draft_id"),
            error_message=result.get("message") if not result.get("ok") else None,
        )

    def publish(self, bundle: PublishBundle) -> PublishResult:
        return self.create_draft(bundle)

    def login(self, timeout_seconds: int = 180, force: bool = False) -> int:
        try:
            page = self.session_manager.open_publish_page(force=force)
        except Exception as exc:
            print(json.dumps(self._error_payload(str(exc)), ensure_ascii=False, indent=2))
            return 1

        if self._wait_for_login(page, timeout_seconds=timeout_seconds):
            return 0

        print(
            json.dumps(
                self._error_payload(f"Login was not detected within {timeout_seconds} seconds."),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    def ensure_browser(self) -> int:
        try:
            self.session_manager.open_publish_page()
        except Exception as exc:
            print(json.dumps(self._error_payload(str(exc)), ensure_ascii=False, indent=2))
            return 1
        return 0

    def _default_tags(self) -> list[str]:
        raw = self.settings.xhs_default_tags or ""
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _wait_for_login(self, page, *, timeout_seconds: int) -> bool:
        if self.draft_writer.is_logged_in(page):
            return True

        deadline = time.monotonic() + max(timeout_seconds, 0)
        while time.monotonic() < deadline:
            page.wait_for_timeout(1000)
            if self.draft_writer.is_logged_in(page):
                return True
        return False

    def _error_payload(self, message: str) -> dict[str, object]:
        payload = self.status()
        payload["status"] = "failed"
        payload["message"] = message
        return payload
