from __future__ import annotations

from auto_football.domain.services.auto_draft_selector_service import AutoDraftSelectorService


def test_selector_prefers_ready_xhs_content_with_images_and_better_length() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 1,
            "home_team": "A",
            "away_team": "B",
            "contents": [
                {
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "short",
                    "title": "short title",
                    "images": ["a.png"],
                }
            ],
        },
        {
            "match_id": 2,
            "home_team": "C",
            "away_team": "D",
            "contents": [
                {
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "x" * 320,
                    "title": "better title",
                    "images": ["b.png"],
                }
            ],
        },
    ]

    picked = service.select_from_preview_payloads(payloads, platform="xiaohongshu")

    assert picked["match_id"] == 2


def test_selector_rejects_short_wechat_content() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 10,
            "home_team": "Home",
            "away_team": "Away",
            "contents": [
                {
                    "platform": "wechat",
                    "status": "ready_to_publish",
                    "content": "x" * 350,
                    "title": "too short",
                    "images": [],
                }
            ],
        }
    ]

    picked = service.select_from_preview_payloads(payloads, platform="wechat")

    assert picked is None


def test_selector_returns_reasonable_content_payload_reference() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 11,
            "home_team": "Home",
            "away_team": "Away",
            "contents": [
                {
                    "platform": "xiaohongshu",
                    "status": "ready_to_publish",
                    "content": "x" * 300,
                    "title": "selected title",
                    "images": ["cover.png"],
                }
            ],
        }
    ]

    picked = service.select_from_preview_payloads(payloads, platform="xiaohongshu")

    assert picked["content"]["title"] == "selected title"
    assert picked["payload"]["home_team"] == "Home"


def test_selector_prefers_longer_wechat_content_when_both_are_ready() -> None:
    service = AutoDraftSelectorService()
    payloads = [
        {
            "match_id": 21,
            "contents": [{"platform": "wechat", "status": "ready_to_publish", "title": "a", "content": "x" * 850, "images": []}],
        },
        {
            "match_id": 22,
            "contents": [{"platform": "wechat", "status": "ready_to_publish", "title": "b", "content": "x" * 980, "images": []}],
        },
    ]

    picked = service.select_from_preview_payloads(payloads, platform="wechat")

    assert picked["match_id"] == 22
