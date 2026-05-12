from __future__ import annotations


PUBLISH_PAGE_URL = "https://creator.xiaohongshu.com/publish/publish"

LOGIN_MARKERS = [
    "//div[contains(text(), '发布图文')]",
    "//div[contains(text(), '上传图文')]",
    "//button[contains(., '发布')]",
    "//*[contains(text(), '创作服务平台')]",
]

UPLOAD_INPUT_XPATH = "//input[@type='file' and @multiple and contains(@accept, '.jpg')]"
ANY_FILE_INPUT_XPATH = "//input[@type='file']"
IMAGE_MODE_TRIGGER_XPATH = "//*[contains(text(), '上传图文')]"
IMAGE_MODE_TRIGGER_CANDIDATES = [
    "//*[@data-hp-bound='1' and contains(@class, 'creator-tab') and .//span[contains(text(), '上传图文')]]",
    "//*[contains(text(), '上传图文')]",
    "//*[contains(text(), '图文')]",
    "//*[@data-testid='creator-tab-image']",
    "//*[@role='tab' and contains(., '图文')]",
]
TITLE_INPUT_XPATH = "//input[contains(@placeholder, '填写标题')]"
CONTENT_INPUT_XPATH = "//*[@contenteditable='true']"
TAG_INPUT_XPATH = "//input[@placeholder='添加话题']"
DRAFT_BUTTON_XPATH = "//button[contains(., '暂存离开') or contains(., '存草稿')]"
PUBLISH_BUTTON_XPATH = "//button[contains(., '发布')]"
