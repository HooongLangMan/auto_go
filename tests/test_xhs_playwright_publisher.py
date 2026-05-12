from __future__ import annotations

from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.infra.publishers.base import PublishBundle
from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform


IMAGE_TAB_TEXT = "\u4e0a\u4f20\u56fe\u6587"
TITLE_TEXT = "\u6807\u9898"
BODY_TEXT = "\u6b63\u6587"
DRAFT_TEXT = "\u5b58\u8349\u7a3f"


def _bundle() -> PublishBundle:
    return PublishBundle(
        match=MatchInfo(
            match_id=9901,
            league="CSL",
            match_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            home_team="Shanghai Shenhua",
            away_team="Chengdu Rongcheng",
        ),
        content=GeneratedContent(
            match_id=9901,
            platform=Platform.XIAOHONGSHU,
            mode=ContentMode.PRE_MATCH,
            account_id="xhs-main",
            title="Test Xiaohongshu Title",
            content="Test Xiaohongshu Body",
            images=["D:/auto_go/generated/images/9901_cover.png"],
            tags=["football", "preview"],
        ),
    )


def test_xhs_playwright_publisher_reports_missing_profile_configuration() -> None:
    from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher

    publisher = XiaohongshuPlaywrightPublisher(Settings(BITBROWSER_PROFILE_ID=""))
    result = publisher.create_draft(_bundle())

    assert result.platform is Platform.XIAOHONGSHU
    assert result.status == "failed"
    assert result.error_message is not None
    assert "profile" in result.error_message.lower()


def test_xhs_playwright_publisher_uses_draft_writer(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher

    captured: dict[str, object] = {}

    class FakeSessionManager:
        backend_name = "playwright"

        def __init__(self, settings) -> None:
            captured["settings"] = settings

        def open_publish_page(self):
            captured["opened"] = True
            return "fake-page"

    class FakeDraftWriter:
        def save_draft(self, *, page, bundle, default_tags):
            captured["page"] = page
            captured["bundle"] = bundle
            captured["default_tags"] = default_tags
            return {"ok": True, "status": "draft_saved", "message": "draft saved"}

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.publisher.BitBrowserSessionManager",
        FakeSessionManager,
    )
    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.publisher.XiaohongshuDraftWriter",
        lambda settings: FakeDraftWriter(),
    )

    publisher = XiaohongshuPlaywrightPublisher(
        Settings(
            BITBROWSER_PROFILE_ID="profile-1",
            XHS_DEFAULT_TAGS="football,preview",
        )
    )
    result = publisher.create_draft(_bundle())

    assert result.platform is Platform.XIAOHONGSHU
    assert result.status == "draft_saved"
    assert captured["opened"] is True
    assert captured["page"] == "fake-page"
    assert captured["default_tags"] == ["football", "preview"]


def test_xhs_draft_writer_returns_login_required_when_login_markers_missing(tmp_path) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    class FakeLocator:
        def count(self):
            return 0

        def set_input_files(self, value):
            raise AssertionError("should not upload when not logged in")

    class FakePage:
        def locator(self, selector):
            return FakeLocator()

    bundle = _bundle()
    bundle.content.images = [str(image_path)]

    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=[])

    assert result["ok"] is False
    assert result["status"] == "login_required"


def test_xhs_draft_writer_uses_humanized_actions_when_logged_in(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    class FakeLocator:
        def __init__(self, count_value=1):
            self._count = count_value
            self.uploaded = None

        def count(self):
            return self._count

        def set_input_files(self, value):
            self.uploaded = value

        def click(self):
            return None

        def bounding_box(self):
            return None

    contenteditable = FakeLocator(1)
    title_input = FakeLocator(1)
    tag_input = FakeLocator(0)
    upload_input = FakeLocator(1)
    draft_button = FakeLocator(1)

    actions: list[tuple[str, object]] = []

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

        def type(self, text):
            actions.append(("keyboard_type", text))

    class FakePage:
        keyboard = FakeKeyboard()

        def locator(self, selector):
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return contenteditable
            if "\u6dfb\u52a0\u8bdd\u9898" in selector:
                return tag_input
            if "@multiple" in selector or "@type='file'" in selector:
                return upload_input
            if "\u6682\u5b58\u79bb\u5f00" in selector or "\u5b58\u8349\u7a3f" in selector:
                return draft_button
            return FakeLocator(1)

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", True))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            actions.append(("click_locator", locator))

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]

    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=["football"])

    assert result["ok"] is True
    assert upload_input.uploaded == str(image_path)
    assert ("type_into", bundle.content.title) in actions
    assert ("type_into", bundle.content.content) in actions
    assert ("review_scroll", True) in actions
    assert any(item[0] == "maybe_noise" for item in actions)


def test_xhs_draft_writer_switches_to_image_mode_when_file_input_is_video_only(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, *, count_value=1, attrs=None, text="", click_hook=None):
            self._count = count_value
            self._attrs = attrs or {}
            self._text = text
            self._click_hook = click_hook
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def click(self):
            actions.append(("click", self._text))
            if self._click_hook:
                self._click_hook()

        def inner_text(self):
            return self._text

        def bounding_box(self):
            return {"x": 10, "y": 10, "width": 100, "height": 30}

    title_input = FakeLocator(text=TITLE_TEXT)
    contenteditable = FakeLocator(text=BODY_TEXT)
    draft_button = FakeLocator(text=DRAFT_TEXT)
    video_input = FakeLocator(attrs={"accept": ".mp4,.mov", "multiple": False}, text="video-input")
    image_input = FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True}, text="image-input")

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

    class FakeMouse:
        def move(self, *args, **kwargs):
            return None

        def down(self):
            return None

        def up(self):
            return None

        def wheel(self, *args, **kwargs):
            return None

    class FakePage:
        keyboard = FakeKeyboard()
        mouse = FakeMouse()

        def __init__(self):
            self.mode = "video"

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                return video_input if self.mode == "video" else image_input
            if IMAGE_TAB_TEXT in selector or "creator-tab" in selector or "\u56fe\u6587" in selector:
                page = self

                class ImageTabLocator(FakeLocator):
                    def click(self_nonlocal):
                        page.mode = "image"
                        actions.append(("switch_mode", "image"))

                return ImageTabLocator(text=IMAGE_TAB_TEXT)
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return contenteditable
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return draft_button
            return FakeLocator()

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", True))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            locator.click()

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]

    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=[])

    assert result["ok"] is True
    assert ("switch_mode", "image") in actions
    assert image_input.uploaded == str(image_path)


def test_xhs_draft_writer_prefers_bound_image_tab_over_hidden_clone(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, *, count_value=1, attrs=None, text="", click_hook=None):
            self._count = count_value
            self._attrs = attrs or {}
            self._text = text
            self._click_hook = click_hook
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def click(self):
            actions.append(("click", self._text))
            if self._click_hook:
                self._click_hook()

        def inner_text(self):
            return self._text

        def bounding_box(self):
            return {"x": 10, "y": 10, "width": 100, "height": 30}

    class FakeMouse:
        def move(self, *args, **kwargs):
            return None

        def down(self):
            return None

        def up(self):
            return None

        def wheel(self, *args, **kwargs):
            return None

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

    class FakePage:
        keyboard = FakeKeyboard()
        mouse = FakeMouse()

        def __init__(self):
            self.mode = "video"

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                if self.mode == "video":
                    return FakeLocator(attrs={"accept": ".mp4,.mov", "multiple": False}, text="video-input")
                return FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True}, text="image-input")
            if selector == f"xpath=//*[@data-hp-bound='1' and contains(@class, 'creator-tab') and .//span[contains(text(), '{IMAGE_TAB_TEXT}')]]":
                return FakeLocator(
                    text="bound-image-tab",
                    click_hook=lambda: setattr(self, "mode", "image"),
                )
            if IMAGE_TAB_TEXT in selector or "creator-tab" in selector or "\u56fe\u6587" in selector:
                return FakeLocator(text="hidden-image-tab")
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return FakeLocator(text=TITLE_TEXT)
            if "contenteditable" in selector:
                return FakeLocator(text=BODY_TEXT)
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return FakeLocator(text=DRAFT_TEXT)
            return FakeLocator()

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", True))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            locator.click()

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]

    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=[])

    assert result["ok"] is True
    assert ("click", "bound-image-tab") in actions
    assert ("click", "hidden-image-tab") not in actions


def test_humanizer_stage_methods_can_be_called_from_draft_flow(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, count_value=1, *, attrs=None, text=""):
            self._count = count_value
            self._attrs = attrs or {}
            self._text = text
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def click(self):
            actions.append(("click", self._text))

        def inner_text(self):
            return self._text

        def bounding_box(self):
            return None

    upload_input = FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True}, text="image-input")
    title_input = FakeLocator(text=TITLE_TEXT)
    contenteditable = FakeLocator(text=BODY_TEXT)
    draft_button = FakeLocator(text=DRAFT_TEXT)

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

        def type(self, text):
            actions.append(("keyboard_type", text))

    class FakePage:
        keyboard = FakeKeyboard()

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                return upload_input
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return contenteditable
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return draft_button
            return FakeLocator(1)

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", anchor_locator))

        def pause(self, min_ms=120, max_ms=420):
            actions.append(("pause", (min_ms, max_ms)))

        def click_locator(self, page, locator):
            actions.append(("click_locator", locator))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]

    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=["football"])

    assert result["ok"] is True
    assert ("stage_transition", "after_upload") in actions
    assert ("stage_transition", "after_title") in actions
    assert ("stage_transition", "after_body") in actions
    assert ("stage_transition", "before_save") in actions
    assert ("short_review_pause", True) in actions


def test_xhs_draft_writer_pauses_after_upload_before_typing(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")

    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, count_value=1, *, attrs=None):
            self._count = count_value
            self._attrs = attrs or {}
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def bounding_box(self):
            return None

    upload_input = FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True})
    title_input = FakeLocator()
    content_input = FakeLocator()
    draft_button = FakeLocator()

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

        def type(self, text):
            actions.append(("keyboard_type", text))

    class FakePage:
        keyboard = FakeKeyboard()

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                return upload_input
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return content_input
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return draft_button
            return FakeLocator()

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", anchor_locator))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            actions.append(("click_locator", locator))

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]
    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=[])

    assert result["ok"] is True
    upload_index = actions.index(("pause", (1200, 2600)))
    stage_index = actions.index(("stage_transition", "after_upload"))
    title_index = actions.index(("type_into", bundle.content.title))
    assert upload_index < stage_index < title_index


def test_xhs_draft_writer_adds_pause_between_title_and_body(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")
    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, count_value=1, *, attrs=None):
            self._count = count_value
            self._attrs = attrs or {}
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def bounding_box(self):
            return None

    upload_input = FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True})
    title_input = FakeLocator()
    content_input = FakeLocator()
    draft_button = FakeLocator()

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

        def type(self, text):
            actions.append(("keyboard_type", text))

    class FakePage:
        keyboard = FakeKeyboard()

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                return upload_input
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return content_input
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return draft_button
            return FakeLocator()

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", anchor_locator))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            actions.append(("click_locator", locator))

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]
    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=[])

    assert result["ok"] is True
    title_index = actions.index(("type_into", bundle.content.title))
    after_title_index = actions.index(("stage_transition", "after_title"))
    body_index = actions.index(("type_into", bundle.content.content))
    assert title_index < after_title_index < body_index


def test_xhs_draft_writer_reviews_after_body_before_tags(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")
    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, count_value=1, *, attrs=None):
            self._count = count_value
            self._attrs = attrs or {}
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def bounding_box(self):
            return None

    upload_input = FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True})
    title_input = FakeLocator()
    content_input = FakeLocator()
    tag_input = FakeLocator(1)
    draft_button = FakeLocator()

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

        def type(self, text):
            actions.append(("keyboard_type", text))

    class FakePage:
        keyboard = FakeKeyboard()

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                return upload_input
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return content_input
            if "\u6dfb\u52a0\u8bdd\u9898" in selector:
                return tag_input
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return draft_button
            return FakeLocator()

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", anchor_locator))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            actions.append(("click_locator", locator))

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]
    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=["football"])

    assert result["ok"] is True
    after_body_index = actions.index(("stage_transition", "after_body"))
    review_pause_index = actions.index(("short_review_pause", True))
    tag_type_index = actions.index(("type_into", "football"))
    assert after_body_index < review_pause_index < tag_type_index


def test_xhs_draft_writer_runs_pre_save_review_phase(tmp_path, monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.draft_writer import XiaohongshuDraftWriter

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"cover")
    actions: list[tuple[str, object]] = []

    class FakeLocator:
        def __init__(self, count_value=1, *, attrs=None):
            self._count = count_value
            self._attrs = attrs or {}
            self.uploaded = None

        def count(self):
            return self._count

        def nth(self, index):
            return self

        def evaluate(self, script):
            return self._attrs

        def set_input_files(self, value):
            self.uploaded = value

        def bounding_box(self):
            return None

        def click(self):
            actions.append(("draft_click", True))

    upload_input = FakeLocator(attrs={"accept": ".jpg,.jpeg,.png,.webp", "multiple": True})
    title_input = FakeLocator()
    content_input = FakeLocator()
    draft_button = FakeLocator()

    class FakeKeyboard:
        def press(self, key):
            actions.append(("press", key))

        def type(self, text):
            actions.append(("keyboard_type", text))

    class FakePage:
        keyboard = FakeKeyboard()

        def locator(self, selector):
            if selector == "xpath=//input[@type='file' and @multiple and contains(@accept, '.jpg')]":
                return FakeLocator(count_value=0)
            if selector == "xpath=//input[@type='file']":
                return upload_input
            if "placeholder" in selector and "\u6807\u9898" in selector:
                return title_input
            if "contenteditable" in selector:
                return content_input
            if "\u5b58\u8349\u7a3f" in selector or "\u6682\u5b58\u79bb\u5f00" in selector:
                return draft_button
            return FakeLocator()

        def wait_for_timeout(self, value):
            actions.append(("wait", value))

    class FakeHumanizer:
        def maybe_noise(self, page, *, anchor_locator=None):
            actions.append(("maybe_noise", anchor_locator))

        def type_into(self, page, locator, text):
            actions.append(("type_into", text))

        def click_locator(self, page, locator):
            locator.click()

        def pause(self, min_ms, max_ms):
            actions.append(("pause", (min_ms, max_ms)))

        def review_scroll(self, page):
            actions.append(("review_scroll", True))

        def stage_transition(self, page, label):
            actions.append(("stage_transition", label))

        def short_review_pause(self):
            actions.append(("short_review_pause", True))

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.draft_writer.PlaywrightHumanizer",
        lambda *args, **kwargs: FakeHumanizer(),
    )

    bundle = _bundle()
    bundle.content.images = [str(image_path)]
    writer = XiaohongshuDraftWriter(Settings())
    result = writer.save_draft(page=FakePage(), bundle=bundle, default_tags=[])

    assert result["ok"] is True
    review_index = actions.index(("review_scroll", True))
    before_save_index = actions.index(("stage_transition", "before_save"))
    draft_click_index = actions.index(("draft_click", True))
    assert review_index < before_save_index < draft_click_index


def test_xhs_publisher_uses_selected_session_backend_without_changing_draft_writer(monkeypatch) -> None:
    from auto_football.infra.publishers.xiaohongshu.publisher import XiaohongshuPlaywrightPublisher

    captured: dict[str, object] = {}

    class FakeSessionManager:
        backend_name = "patchright"

        def __init__(self, settings) -> None:
            self.settings = settings

        def open_publish_page(self):
            captured["opened"] = True
            return "fake-page"

    class FakeDraftWriter:
        def save_draft(self, *, page, bundle, default_tags):
            captured["page"] = page
            captured["bundle"] = bundle
            captured["default_tags"] = default_tags
            return {"ok": True, "status": "draft_saved", "message": "draft saved"}

    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.publisher.BitBrowserSessionManager",
        FakeSessionManager,
    )
    monkeypatch.setattr(
        "auto_football.infra.publishers.xiaohongshu.publisher.XiaohongshuDraftWriter",
        lambda settings: FakeDraftWriter(),
    )

    publisher = XiaohongshuPlaywrightPublisher(
        Settings(
            BITBROWSER_PROFILE_ID="profile-1",
            XHS_DEFAULT_TAGS="football,preview",
            XHS_AUTOMATION_BACKEND="patchright",
        )
    )
    result = publisher.create_draft(_bundle())

    assert result.status == "draft_saved"
    assert captured["opened"] is True
    assert captured["page"] == "fake-page"
