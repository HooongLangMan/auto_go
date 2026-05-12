from __future__ import annotations

import sys
import types

from auto_football.config import Settings


def test_patchright_backend_connects_over_cdp(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend

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

        def new_page(self):
            raise AssertionError("should not create a new page when publish page already exists")

    fake_context = FakeContext()

    class FakeBrowser:
        def __init__(self) -> None:
            self.contexts = [fake_context]

    class FakePatchrightRuntime:
        class Chromium:
            @staticmethod
            def connect_over_cdp(ws_endpoint: str):
                assert ws_endpoint == "ws://127.0.0.1/fake"
                return FakeBrowser()

        chromium = Chromium()

    class FakePatchrightCM:
        def start(self):
            return FakePatchrightRuntime()

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.backends.patchright_backend.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    fake_sync_api = types.ModuleType("patchright.sync_api")
    fake_sync_api.sync_playwright = lambda: FakePatchrightCM()
    sys.modules["patchright.sync_api"] = fake_sync_api

    backend = PatchrightCDPBackend(
        Settings(
            BITBROWSER_PROFILE_ID="ccb11b7c74294e1d9d00efcac642b237",
            BITBROWSER_BASE_URL="http://127.0.0.1:54345",
        )
    )

    page = backend.open_publish_page()

    assert page is existing_page
    assert existing_page.waited is True


def test_patchright_backend_forces_fresh_bitbrowser_session(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"success": True, "data": {"ws": "ws://127.0.0.1/fake"}}

    class FakeBrowser:
        def __init__(self) -> None:
            self.contexts = []

        def new_context(self):
            class FakeContext:
                pages = []

                @staticmethod
                def new_page():
                    class FakePage:
                        url = ""

                        @staticmethod
                        def goto(url, wait_until="load"):
                            return None

                        @staticmethod
                        def wait_for_timeout(value):
                            return None

                    return FakePage()

            return FakeContext()

    class FakePatchrightRuntime:
        class Chromium:
            @staticmethod
            def connect_over_cdp(ws_endpoint: str):
                return FakeBrowser()

        chromium = Chromium()

    class FakePatchrightCM:
        def start(self):
            return FakePatchrightRuntime()

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.backends.patchright_backend.requests.post",
        fake_post,
    )

    fake_sync_api = types.ModuleType("patchright.sync_api")
    fake_sync_api.sync_playwright = lambda: FakePatchrightCM()
    sys.modules["patchright.sync_api"] = fake_sync_api

    backend = PatchrightCDPBackend(Settings(BITBROWSER_PROFILE_ID="profile-1"))
    backend.open_publish_page()

    assert captured["json"]["force"] is True


def test_patchright_backend_retries_when_bitbrowser_is_still_opening(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend

    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class FakePage:
        url = "https://creator.xiaohongshu.com/publish/publish"

        @staticmethod
        def wait_for_load_state(state="load", timeout=None):
            return None

    class FakeContext:
        pages = [FakePage()]

    class FakeBrowser:
        contexts = [FakeContext()]

    class FakePatchrightRuntime:
        class Chromium:
            @staticmethod
            def connect_over_cdp(ws_endpoint: str):
                return FakeBrowser()

        chromium = Chromium()

    class FakePatchrightCM:
        def start(self):
            return FakePatchrightRuntime()

    def fake_post(url, json=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse({"success": False, "msg": "浏览器正在打开中"})
        return FakeResponse({"success": True, "data": {"ws": "ws://127.0.0.1/fake"}})

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.backends.patchright_backend.requests.post",
        fake_post,
    )
    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.backends.patchright_backend.time.sleep",
        lambda value: None,
    )

    fake_sync_api = types.ModuleType("patchright.sync_api")
    fake_sync_api.sync_playwright = lambda: FakePatchrightCM()
    sys.modules["patchright.sync_api"] = fake_sync_api

    backend = PatchrightCDPBackend(Settings(BITBROWSER_PROFILE_ID="profile-1"))
    page = backend.open_publish_page()

    assert calls["count"] == 2
    assert page.url == "https://creator.xiaohongshu.com/publish/publish"


def test_patchright_backend_reports_missing_dependency_as_runtime_error(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.backends.patchright_backend import PatchrightCDPBackend

    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "patchright.sync_api":
            raise ModuleNotFoundError("No module named 'patchright'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    backend = PatchrightCDPBackend(Settings(BITBROWSER_PROFILE_ID="profile-1"))

    try:
        backend.open_publish_page()
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "Patchright" in str(exc)
