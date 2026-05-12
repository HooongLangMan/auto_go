from __future__ import annotations

import requests
import time

from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.selectors import PUBLISH_PAGE_URL


class PatchrightCDPBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def open_publish_page(self, *, force: bool = False):
        try:
            from patchright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Patchright is not installed in the active Python environment: {exc}") from exc

        # Patchright currently shows stale-frame failures when attaching to a reused
        # BitBrowser session. Force a fresh session unless the caller explicitly
        # chooses otherwise.
        effective_force = True if force is False else force
        open_url = f"{self.settings.bitbrowser_base_url.rstrip('/')}/browser/open"
        payload = None
        for attempt in range(3):
            response = requests.post(
                open_url,
                json={"id": self.settings.bitbrowser_profile_id, "force": effective_force},
                timeout=self.settings.xhs_action_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("success") and payload.get("data"):
                break
            if "打开中" in str(payload.get("msg") or "") and attempt < 2:
                time.sleep(2)
                continue
            raise RuntimeError(f"BitBrowser open failed: {payload}")

        ws_endpoint = payload["data"].get("ws")
        if not ws_endpoint:
            raise RuntimeError(f"BitBrowser did not return websocket endpoint: {payload}")

        patchright = sync_playwright().start()
        browser = patchright.chromium.connect_over_cdp(ws_endpoint)
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
