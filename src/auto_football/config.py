from __future__ import annotations

import json
from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from auto_football.schemas import ContentTarget


DEFAULT_LOCAL_CHROME = "D:/auto_go/tools/chrome-147/chrome-win64/chrome.exe"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_timezone: str = Field(default="Asia/Shanghai", alias="APP_TIMEZONE")
    selection_count: int = Field(default=3, alias="SELECTION_COUNT")
    run_dry: bool = Field(default=True, alias="RUN_DRY")
    publish_enabled: bool = Field(default=False, alias="PUBLISH_ENABLED")
    wechat_publish_enabled: bool = Field(default=False, alias="WECHAT_PUBLISH_ENABLED")
    xhs_publish_enabled: bool = Field(default=False, alias="XHS_PUBLISH_ENABLED")
    wechat_auto_publish: bool = Field(default=False, alias="WECHAT_AUTO_PUBLISH")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="auto_football", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    database_url_override: str = Field(default="", alias="DATABASE_URL")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    fixture_cache_ttl_seconds: int = Field(default=86400, alias="FIXTURE_CACHE_TTL_SECONDS")
    context_cache_ttl_seconds: int = Field(default=259200, alias="CONTEXT_CACHE_TTL_SECONDS")
    source_doc_cache_ttl_seconds: int = Field(default=604800, alias="SOURCE_DOC_CACHE_TTL_SECONDS")

    api_football_base_url: str = Field(default="https://v3.football.api-sports.io", alias="API_FOOTBALL_BASE_URL")
    api_football_key: str = Field(default="", alias="API_FOOTBALL_KEY")

    public_fixture_api_url: str = Field(default="https://688zb40.com/api/Football/all_match", alias="PUBLIC_FIXTURE_API_URL")

    thesportsdb_api_url: str = Field(default="https://www.thesportsdb.com/api/v1/json", alias="THESPORTSDB_API_URL")
    thesportsdb_api_key: str = Field(default="", alias="THESPORTSDB_API_KEY")
    clubelo_api_url: str = Field(default="http://api.clubelo.com", alias="CLUBELO_API_URL")
    clubelo_enabled: bool = Field(default=True, alias="CLUBELO_ENABLED")
    openfootball_enabled: bool = Field(default=True, alias="OPENFOOTBALL_ENABLED")
    statsbomb_enabled: bool = Field(default=False, alias="STATSBOMB_ENABLED")
    statsbomb_competition_scan_limit: int = Field(default=12, alias="STATSBOMB_COMPETITION_SCAN_LIMIT")
    fbref_enabled: bool = Field(default=False, alias="FBREF_ENABLED")
    fbref_browser_path: str = Field(default=DEFAULT_LOCAL_CHROME, alias="FBREF_BROWSER_PATH")
    fbref_headless: bool = Field(default=True, alias="FBREF_HEADLESS")
    whoscored_enabled: bool = Field(default=False, alias="WHOSCORED_ENABLED")
    whoscored_browser_path: str = Field(default=DEFAULT_LOCAL_CHROME, alias="WHOSCORED_BROWSER_PATH")
    whoscored_headless: bool = Field(default=True, alias="WHOSCORED_HEADLESS")
    football_data_api_url: str = Field(default="https://api.football-data.org/v4", alias="FOOTBALL_DATA_API_URL")
    football_data_api_key: str = Field(default="", alias="FOOTBALL_DATA_API_KEY")
    football_data_rate_limit_per_minute: int = Field(default=9, alias="FOOTBALL_DATA_RATE_LIMIT_PER_MINUTE")

    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_chat_path: str = Field(default="/chat/completions", alias="LLM_CHAT_PATH")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")

    wechat_mcp_command: str = Field(default="python", alias="WECHAT_MCP_COMMAND")
    wechat_mcp_args_json: str = Field(default='["-m","wechat_oa_api_mcp","--port","8123"]', alias="WECHAT_MCP_ARGS_JSON")
    wechat_mcp_workdir: str = Field(default="", alias="WECHAT_MCP_WORKDIR")
    wechat_oa_account: str = Field(default="", alias="WECHAT_OA_ACCOUNT")
    wechat_oa_password: str = Field(default="", alias="WECHAT_OA_PASSWORD")
    wechat_app_id: str = Field(default="", alias="WECHAT_APP_ID")
    wechat_app_secret: str = Field(default="", alias="WECHAT_APP_SECRET")
    wechat_author: str = Field(default="Auto Football", alias="WECHAT_AUTHOR")

    xhs_browser_path: str = Field(default="", alias="XHS_BROWSER_PATH")
    xhs_default_tags: str = Field(default="足球,比赛分析", alias="XHS_DEFAULT_TAGS")
    xhs_draft_only: bool = Field(default=True, alias="XHS_DRAFT_ONLY")
    xhs_automation_backend: str = Field(default="playwright", alias="XHS_AUTOMATION_BACKEND")
    xhs_behavior_profile: str = Field(default="", alias="XHS_BEHAVIOR_PROFILE")
    bitbrowser_profile_id: str = Field(default="", alias="BITBROWSER_PROFILE_ID")
    bitbrowser_base_url: str = Field(default="http://127.0.0.1:54345", alias="BITBROWSER_BASE_URL")
    xhs_publish_url: str = Field(default="https://creator.xiaohongshu.com/publish/publish", alias="XHS_PUBLISH_URL")
    xhs_action_timeout_seconds: int = Field(default=30, alias="XHS_ACTION_TIMEOUT_SECONDS")

    pixelle_enabled: bool = Field(default=False, alias="PIXELLE_ENABLED")
    pixelle_base_url: str = Field(default="http://127.0.0.1:8000", alias="PIXELLE_BASE_URL")
    pixelle_submit_path: str = Field(default="/api/video/generate/async", alias="PIXELLE_SUBMIT_PATH")
    pixelle_task_path_template: str = Field(default="/api/tasks/{task_id}", alias="PIXELLE_TASK_PATH_TEMPLATE")
    pixelle_timeout_seconds: int = Field(default=60, alias="PIXELLE_TIMEOUT_SECONDS")

    ai_image_enabled: bool = Field(default=False, alias="AI_IMAGE_ENABLED")
    ark_base_url: str = Field(default="https://ark.cn-beijing.volces.com/api/v3", alias="ARK_BASE_URL")
    ark_api_key: str = Field(default="", alias="ARK_API_KEY")
    ark_image_model: str = Field(default="doubao-seedream-4-5-251128", alias="ARK_IMAGE_MODEL")
    ai_image_daily_limit: int = Field(default=6, alias="AI_IMAGE_DAILY_LIMIT")
    ai_image_per_match_limit: int = Field(default=1, alias="AI_IMAGE_PER_MATCH_LIMIT")
    wechat_inline_ai_image_limit: int = Field(default=1, alias="WECHAT_INLINE_AI_IMAGE_LIMIT")

    image_output_dir: str = Field(default="generated/images", alias="IMAGE_OUTPUT_DIR")
    content_targets_json: str = Field(
        default=(
            '[{"account_id":"wechat-main","platform":"wechat","quota":2,"modes":["pre_match","result_flash","hot_recap"]},'
            '{"account_id":"xhs-main","platform":"xiaohongshu","quota":3,"modes":["pre_match","result_flash","hot_recap"]}]'
        ),
        alias="CONTENT_TARGETS_JSON",
    )

    @cached_property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def llm_chat_url(self) -> str:
        base = self.llm_base_url.rstrip("/")
        path = self.llm_chat_path if self.llm_chat_path.startswith("/") else f"/{self.llm_chat_path}"
        return f"{base}{path}" if base else ""

    @cached_property
    def wechat_mcp_args(self) -> list[str]:
        return self._parse_json_args(self.wechat_mcp_args_json)

    @cached_property
    def content_targets(self) -> list[ContentTarget]:
        raw_items = self._parse_json_value(self.content_targets_json)
        if not isinstance(raw_items, list):
            raise ValueError("CONTENT_TARGETS_JSON must be a JSON array.")
        return [ContentTarget.model_validate(item) for item in raw_items]

    @staticmethod
    def _parse_json_args(raw: str) -> list[str]:
        if not raw:
            return []
        value = Settings._parse_json_value(raw)
        if not isinstance(value, list):
            raise ValueError("MCP args must be a JSON array.")
        return [str(item) for item in value]

    @staticmethod
    def _parse_json_value(raw: str):
        if not raw:
            return None
        return json.loads(raw)


def get_settings() -> Settings:
    return Settings()
