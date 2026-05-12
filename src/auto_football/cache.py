from __future__ import annotations

import json
from datetime import date
from typing import Any

import redis

from auto_football.config import Settings


class CacheStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = self._build_client()

    def _build_client(self):
        try:
            client = redis.Redis.from_url(self.settings.redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def get_json(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        raw = self.client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        if not self.enabled:
            return
        self.client.set(key, json.dumps(payload, ensure_ascii=False, default=str), ex=ttl_seconds)

    @staticmethod
    def fixture_list_key(run_date: date, source: str) -> str:
        return f"auto_football:fixtures:{source}:{run_date.isoformat()}"

    @staticmethod
    def clubelo_key(run_date: date) -> str:
        return f"auto_football:clubelo:{run_date.isoformat()}"

    @staticmethod
    def source_docs_key(fixture_id: int) -> str:
        return f"auto_football:source_docs:{fixture_id}"

    @staticmethod
    def merged_context_key(fixture_id: int, run_date: date) -> str:
        return f"auto_football:merged_context:v2:{fixture_id}:{run_date.isoformat()}"
