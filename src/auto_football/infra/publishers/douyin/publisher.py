from __future__ import annotations

from auto_football.config import Settings
from auto_football.infra.publishers.base import PublishBundle
from auto_football.schemas import Platform, PublishResult


class DouyinPublisher:
    platform = Platform.DOUYIN

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def healthcheck(self) -> dict[str, object]:
        return {
            "platform": self.platform.value,
            "backend": "placeholder",
            "status": "not_implemented",
        }

    def create_draft(self, bundle: PublishBundle) -> PublishResult:
        del bundle
        return PublishResult(
            platform=self.platform,
            status="failed",
            error_message="Douyin publisher is not implemented yet.",
        )

    def publish(self, bundle: PublishBundle) -> PublishResult:
        return self.create_draft(bundle)
