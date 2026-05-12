from __future__ import annotations

from pathlib import Path

from auto_football.config import Settings
from auto_football.infra.images.ark_image_client import ArkImageClient


def test_ark_image_client_is_disabled_without_key(tmp_path) -> None:
    client = ArkImageClient(
        Settings(
            AI_IMAGE_ENABLED=True,
            ARK_API_KEY="",
            IMAGE_OUTPUT_DIR=str(tmp_path),
        )
    )

    assert client.enabled is False


def test_ark_image_client_posts_prompt_and_downloads_image(tmp_path, monkeypatch) -> None:
    calls: dict[str, dict[str, object]] = {}

    class FakeImageItem:
        def __init__(self, url: str) -> None:
            self.url = url

    class FakeImagesResponse:
        def __init__(self, url: str) -> None:
            self.data = [FakeImageItem(url)]

    class FakeArk:
        def __init__(self, *, base_url=None, api_key=None, **kwargs) -> None:
            calls["sdk_init"] = {"base_url": base_url, "api_key": api_key, "kwargs": kwargs}

            class Images:
                @staticmethod
                def generate(*, model, prompt, size=None, response_format=None, watermark=None):
                    calls["sdk_generate"] = {
                        "model": model,
                        "prompt": prompt,
                        "size": size,
                        "response_format": response_format,
                        "watermark": watermark,
                    }
                    return FakeImagesResponse("https://img.example/generated.png")

            self.images = Images()

    class FakeResponse:
        def __init__(self, payload, content: bytes = b"") -> None:
            self._payload = payload
            self.content = content

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return FakeResponse({"data": [{"url": "https://img.example/generated.png"}]})

    def fake_get(url, timeout=None):
        calls["get"] = {"url": url, "timeout": timeout}
        return FakeResponse({}, content=b"png-bytes")

    monkeypatch.setattr("auto_football.infra.images.ark_image_client.Ark", FakeArk)
    monkeypatch.setattr("auto_football.infra.images.ark_image_client.httpx.post", fake_post)
    monkeypatch.setattr("auto_football.infra.images.ark_image_client.httpx.get", fake_get)

    client = ArkImageClient(
        Settings(
            AI_IMAGE_ENABLED=True,
            ARK_API_KEY="ark-key",
            ARK_IMAGE_MODEL="doubao-seedream-4-5-251128",
            IMAGE_OUTPUT_DIR=str(tmp_path),
        )
    )

    output = client.generate_to_file(match_id=8001, slug="wechat-hero", prompt="sports action prompt")

    assert output is not None
    assert Path(output).exists()
    assert calls["sdk_init"]["base_url"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert calls["sdk_init"]["api_key"] == "ark-key"
    assert calls["sdk_generate"]["model"] == "doubao-seedream-4-5-251128"
    assert calls["sdk_generate"]["prompt"] == "sports action prompt"
    assert calls["sdk_generate"]["size"] == "1920x1920"
    assert calls["sdk_generate"]["response_format"] == "url"
    assert calls["sdk_generate"]["watermark"] is False
    assert calls["get"]["url"] == "https://img.example/generated.png"
