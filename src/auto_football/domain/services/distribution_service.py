from __future__ import annotations

from auto_football.schemas import ContentStatus


class DistributionService:
    def __init__(self, settings, publisher, db) -> None:
        self.settings = settings
        self.publisher = publisher
        self.db = db

    def distribute(self, contents, match_data):
        publish_status: dict[int, dict[str, object]] = {}
        for content in contents:
            publish_status.setdefault(content.match_id, {})
            key = f"{content.platform.value}:{content.mode.value}:{content.account_id}"
            if self.settings.run_dry or not self.settings.publish_enabled:
                publish_status[content.match_id][key] = {
                    "platform": content.platform.value,
                    "status": ContentStatus.READY_TO_PUBLISH.value,
                    "account_id": content.account_id,
                }
                continue
            result = self.publisher.publish(content.match_id, content, match_data[content.match_id])
            self.db.log_publish(content.match_id, result)
            publish_status[content.match_id][key] = result.model_dump()
        return publish_status
