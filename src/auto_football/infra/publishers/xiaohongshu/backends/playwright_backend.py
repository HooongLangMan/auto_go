from __future__ import annotations

import requests

from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.selectors import PUBLISH_PAGE_URL


class PlaywrightCDPBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def open_publish_page(self, *, force: bool = False):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Playwright is not installed in the active Python environment: {exc}") from exc

        open_url = f"{self.settings.bitbrowser_base_url.rstrip('/')}/browser/open"
        response = requests.post(
            open_url,
            json={"id": self.settings.bitbrowser_profile_id, "force": force},
            timeout=self.settings.xhs_action_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success") or not payload.get("data"):
            raise RuntimeError(f"BitBrowser open failed: {payload}")

        ws_endpoint = payload["data"].get("ws")
        if not ws_endpoint:
            raise RuntimeError(f"BitBrowser did not return websocket endpoint: {payload}")

        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(ws_endpoint)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = self._find_existing_publish_page(context.pages)
        if page is None:
            page = context.new_page()
            page.goto(self.publish_url, wait_until="load")
            page.wait_for_timeout(1500)
        else:
            page.wait_for_load_state(state="load", timeout=self.settings.xhs_action_timeout_seconds * 1000)
        return page

    @property
    def publish_url(self) -> str:
        return self.settings.xhs_publish_url or PUBLISH_PAGE_URL

    def _find_existing_publish_page(self, pages):
        target = self.publish_url.split("?")[0]
        for page in pages:
            try:
                page_url = page.url or ""
            except Exception:
                continue
            if page_url.startswith(target):
                return page
        return None
