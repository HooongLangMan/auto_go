from __future__ import annotations

from auto_football.config import Settings
from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend
from auto_football.infra.publishers.xiaohongshu.backends.playwright_backend import PlaywrightCDPBackend


class BitBrowserSessionManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        backend_name = (settings.xhs_automation_backend or "playwright").strip().lower()
        if backend_name not in {"playwright", "patchright"}:
            backend_name = "playwright"
        self.backend_name = backend_name
        self.backend = PatchrightCDPBackend(settings) if backend_name == "patchright" else PlaywrightCDPBackend(settings)

    def open_publish_page(self, *, force: bool = False):
        return self.backend.open_publish_page(force=force)
