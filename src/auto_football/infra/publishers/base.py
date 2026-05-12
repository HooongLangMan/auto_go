from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from auto_football.schemas import GeneratedContent, MatchInfo, Platform, PublishResult


class PublishBundle(BaseModel):
    match: MatchInfo
    content: GeneratedContent
    cover_image: str | None = None
    inline_images: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class Publisher(Protocol):
    platform: Platform

    def healthcheck(self) -> dict[str, object]:
        ...

    def create_draft(self, bundle: PublishBundle) -> PublishResult:
        ...

    def publish(self, bundle: PublishBundle) -> PublishResult:
        ...
