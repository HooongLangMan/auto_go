from __future__ import annotations

import sys
import types

from auto_football.config import Settings


def test_session_manager_reuses_existing_publish_page(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.session import BitBrowserSessionManager

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"success": True, "data": {"ws": "ws://127.0.0.1/fake"}}

    class FakePage:
        def __init__(self, url: str) -> None:
            self.url = url
            self.waited = False

        def wait_for_load_state(self, state="load", timeout=None):
            self.waited = True

    existing_page = FakePage("https://creator.xiaohongshu.com/publish/publish?from=menu&target=image")

    class FakeContext:
        def __init__(self) -> None:
            self.pages = [existing_page]
            self.new_page_called = False

        def new_page(self):
            self.new_page_called = True
            raise AssertionError("should not create a new page when publish page already exists")

    fake_context = FakeContext()

    class FakeBrowser:
        def __init__(self) -> None:
            self.contexts = [fake_context]

    class FakePlaywrightRuntime:
        class Chromium:
            @staticmethod
            def connect_over_cdp(ws_endpoint: str):
                assert ws_endpoint == "ws://127.0.0.1/fake"
                return FakeBrowser()

        chromium = Chromium()

    class FakePlaywrightCM:
        def start(self):
            return FakePlaywrightRuntime()

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.backends.playwright_backend.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    fake_sync_api = types.ModuleType("playwright.sync_api")
    fake_sync_api.sync_playwright = lambda: FakePlaywrightCM()
    sys.modules["playwright.sync_api"] = fake_sync_api

    manager = BitBrowserSessionManager(
        Settings(
            BITBROWSER_PROFILE_ID="ccb11b7c74294e1d9d00efcac642b237",
            BITBROWSER_BASE_URL="http://127.0.0.1:54345",
            XHS_AUTOMATION_BACKEND="playwright",
        )
    )

    page = manager.open_publish_page()

    assert page is existing_page
    assert existing_page.waited is True


def test_session_manager_defaults_invalid_backend_to_playwright() -> None:
    from auto_football.infra.publishers.xiaohongshu.session import BitBrowserSessionManager

    manager = BitBrowserSessionManager(Settings(XHS_AUTOMATION_BACKEND="bogus"))

    assert manager.backend_name == "playwright"


def test_session_manager_uses_patchright_when_configured() -> None:
    from auto_football.infra.publishers.xiaohongshu.session import BitBrowserSessionManager

    manager = BitBrowserSessionManager(Settings(XHS_AUTOMATION_BACKEND="patchright"))

    assert manager.backend_name == "patchright"
