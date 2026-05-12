from __future__ import annotations

from pathlib import Path

from auto_football.config import Settings
from auto_football.infra.publishers.humanizer import PlaywrightHumanizer

from .selectors import ANY_FILE_INPUT_XPATH, CONTENT_INPUT_XPATH, DRAFT_BUTTON_XPATH, IMAGE_MODE_TRIGGER_CANDIDATES, LOGIN_MARKERS, TAG_INPUT_XPATH, TITLE_INPUT_XPATH, UPLOAD_INPUT_XPATH


class XiaohongshuDraftWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.humanizer = PlaywrightHumanizer(settings.xhs_behavior_profile)

    def save_draft(self, *, page, bundle, default_tags: list[str]):
        media_path = self._primary_media_path(bundle)
        if not media_path:
            return {"ok": False, "status": "missing_media", "message": "没有可用的图文封面路径"}
        if not Path(media_path).exists():
            return {"ok": False, "status": "missing_media", "message": f"图片文件不存在: {media_path}"}
        if not self._is_logged_in(page):
            return {"ok": False, "status": "login_required", "message": "小红书登录失效，请手动登录"}

        if not self._ensure_image_mode(page):
            return {"ok": False, "status": "image_mode_unavailable", "message": "未能切换到图文上传模式"}

        self.humanizer.maybe_noise(page)
        upload_locator = self._image_upload_locator(page)
        if upload_locator is None:
            return {"ok": False, "status": "missing_media_input", "message": "未找到图文上传控件"}
        upload_locator.set_input_files(media_path)
        self.humanizer.pause(1200, 2600)
        self.humanizer.stage_transition(page, "after_upload")

        content_locator = page.locator(f"xpath={CONTENT_INPUT_XPATH}")
        title_locator = page.locator(f"xpath={TITLE_INPUT_XPATH}")
        self.humanizer.maybe_noise(page, anchor_locator=title_locator)
        self.humanizer.type_into(page, title_locator, bundle.content.title)
        self.humanizer.pause(180, 420)
        self.humanizer.stage_transition(page, "after_title")
        self.humanizer.maybe_noise(page, anchor_locator=content_locator)
        self.humanizer.type_into(page, content_locator, bundle.content.content)
        self.humanizer.stage_transition(page, "after_body")
        self.humanizer.short_review_pause()

        tags = self._merged_tags(bundle.content.tags, default_tags)
        if tags:
            tag_locator = page.locator(f"xpath={TAG_INPUT_XPATH}")
            if tag_locator.count() > 0:
                for tag in tags:
                    self.humanizer.maybe_noise(page, anchor_locator=tag_locator)
                    self.humanizer.type_into(page, tag_locator, tag)
                    page.keyboard.press("Enter")
                    self.humanizer.pause(220, 520)

        self.humanizer.review_scroll(page)
        self.humanizer.stage_transition(page, "before_save")
        if self._click_if_exists(page, DRAFT_BUTTON_XPATH):
            self.humanizer.pause(1800, 3200)
            return {"ok": True, "status": "draft_saved", "message": "已存入小红书草稿"}
        return {"ok": False, "status": "failed", "message": "未找到存草稿按钮"}

    def _is_logged_in(self, page) -> bool:
        for xpath in LOGIN_MARKERS:
            if page.locator(f"xpath={xpath}").count() > 0:
                return True
        return False

    def _ensure_image_mode(self, page) -> bool:
        locator = self._image_upload_locator(page)
        if locator is not None:
            return True

        for xpath in IMAGE_MODE_TRIGGER_CANDIDATES:
            trigger = page.locator(f"xpath={xpath}")
            if trigger.count() <= 0:
                continue
            try:
                self.humanizer.click_locator(page, trigger.nth(0))
            except Exception:
                continue
            page.wait_for_timeout(1200)
            if self._image_upload_locator(page) is not None:
                return True
        return False

    @staticmethod
    def _image_upload_locator(page):
        preferred = page.locator(f"xpath={UPLOAD_INPUT_XPATH}")
        if preferred.count() > 0:
            return preferred

        all_inputs = page.locator(f"xpath={ANY_FILE_INPUT_XPATH}")
        count = all_inputs.count()
        for index in range(count):
            locator = all_inputs.nth(index)
            try:
                meta = locator.evaluate(
                    "el => ({accept: (el.accept || '').toLowerCase(), multiple: !!el.multiple})"
                )
            except Exception:
                continue
            accept = str(meta.get("accept") or "")
            is_image_accept = any(token in accept for token in (".jpg", ".jpeg", ".png", ".webp", "image/"))
            if is_image_accept:
                return locator
        return None

    @staticmethod
    def _click_if_exists(page, xpath: str) -> bool:
        locator = page.locator(f"xpath={xpath}")
        if locator.count() <= 0:
            return False
        PlaywrightHumanizer().click_locator(page, locator)
        return True

    @staticmethod
    def _primary_media_path(bundle) -> str | None:
        content = bundle.content
        if content.primary_media_path:
            return content.primary_media_path
        if content.images:
            return content.images[0]
        if content.remote_images:
            return content.remote_images[0]
        return None

    @staticmethod
    def _merged_tags(content_tags: list[str], default_tags: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for tag in [*(content_tags or []), *(default_tags or [])]:
            value = str(tag).strip().lstrip("#＃").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
        return merged[:8]
