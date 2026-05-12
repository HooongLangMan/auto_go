from __future__ import annotations

from auto_football.config import Settings
from auto_football.infra.publishers.base import Publisher
from auto_football.infra.publishers.douyin.publisher import DouyinPublisher
from auto_football.schemas import Platform


class PublisherRegistry:
    def __init__(self, settings: Settings, *, wechat_publisher: Publisher | None = None, xhs_publisher: Publisher | None = None, douyin_publisher: Publisher | None = None) -> None:
        if wechat_publisher is None or xhs_publisher is None:
            from auto_football.adapters import WechatPublisher, XiaohongshuPublisher

            wechat_publisher = wechat_publisher or WechatPublisher(settings)
            xhs_publisher = xhs_publisher or XiaohongshuPublisher(settings)

        self._publishers: dict[Platform, Publisher] = {
            Platform.WECHAT: wechat_publisher,
            Platform.XIAOHONGSHU: xhs_publisher,
            Platform.DOUYIN: douyin_publisher or DouyinPublisher(settings),
        }

    def get(self, platform: Platform) -> Publisher:
        return self._publishers[platform]
