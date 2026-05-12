from __future__ import annotations


class AutoDraftSelectorService:
    def select_from_preview_payloads(self, payloads, *, platform: str):
        candidates = []
        for payload in payloads:
            for content in payload.get("contents", []):
                if content.get("platform") != platform:
                    continue
                if content.get("status") != "ready_to_publish":
                    continue
                if not content.get("title") or not content.get("content"):
                    continue
                if platform == "xiaohongshu" and not content.get("images"):
                    continue
                if platform == "wechat" and len(content.get("content") or "") < 800:
                    continue
                score = self._score(platform, content)
                candidates.append((score, payload, content))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, payload, content = candidates[0]
        return {"match_id": payload["match_id"], "payload": payload, "content": content}

    def _score(self, platform: str, content: dict) -> int:
        length = len(content.get("content") or "")
        image_bonus = 100 if content.get("images") else 0
        if platform == "xiaohongshu":
            return image_bonus + min(length, 500)
        return min(length, 2000)
