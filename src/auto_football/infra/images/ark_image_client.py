from __future__ import annotations

from pathlib import Path

import httpx

from auto_football.config import Settings

try:
    from volcenginesdkarkruntime import Ark
except Exception:  # pragma: no cover - optional dependency
    Ark = None


class ArkImageClient:
    def __init__(self, settings: Settings) -> None:
        self.enabled = bool(settings.ai_image_enabled and settings.ark_api_key and settings.ark_image_model)
        self.base_url = settings.ark_base_url.rstrip("/")
        self.api_key = settings.ark_api_key
        self.model = settings.ark_image_model
        self.output_dir = Path(settings.image_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sdk_client = (
            Ark(base_url=self.base_url, api_key=self.api_key) if self.enabled and Ark is not None else None
        )

    def generate_to_file(self, *, match_id: int, slug: str, prompt: str) -> str | None:
        if not self.enabled:
            return None
        try:
            image_url = None
            if self._sdk_client is not None:
                response = self._sdk_client.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size="1920x1920",
                    response_format="url",
                    watermark=False,
                )
                data = getattr(response, "data", None) or []
                if data:
                    image_url = getattr(data[0], "url", None)
            if not image_url:
                response = httpx.post(
                    f"{self.base_url}/images/generations",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "size": "1920x1920",
                        "response_format": "url",
                        "watermark": False,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                payload = response.json()
                image_url = payload["data"][0]["url"]
            image = httpx.get(image_url, timeout=60)
            image.raise_for_status()
            path = self.output_dir / f"{match_id}_{slug}.png"
            path.write_bytes(image.content)
            return str(path.resolve())
        except Exception:
            return None
