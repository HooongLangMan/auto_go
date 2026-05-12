from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from auto_football.config import Settings


def test_settings_default_wechat_mcp_args_match_installed_package_name() -> None:
    settings = Settings()

    assert settings.wechat_mcp_args == ["-m", "wechat_oa_api_mcp", "--port", "8123"]


def test_doctor_reports_wechat_configuration_status(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(src), env.get("PYTHONPATH", "")]).strip(os.pathsep)

    result = subprocess.run(
        [sys.executable, "-m", "auto_football.cli", "doctor"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "- WECHAT_OA_API_MCP: MISSING" in result.stdout
    assert "- WECHAT_APP_ID: MISSING" in result.stdout
    assert "- WECHAT_APP_SECRET: MISSING" in result.stdout
    assert "- WECHAT_PUBLISH_ENABLED: False" in result.stdout


def test_settings_expose_ark_image_configuration() -> None:
    settings = Settings(
        AI_IMAGE_ENABLED=True,
        ARK_API_KEY="ark-key",
        ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3",
        ARK_IMAGE_MODEL="doubao-seedream-3-0-t2i-250415",
        AI_IMAGE_DAILY_LIMIT=6,
        AI_IMAGE_PER_MATCH_LIMIT=1,
        WECHAT_INLINE_AI_IMAGE_LIMIT=1,
    )

    assert settings.ai_image_enabled is True
    assert settings.ark_api_key == "ark-key"
    assert settings.ark_base_url.endswith("/api/v3")
    assert settings.ark_image_model == "doubao-seedream-3-0-t2i-250415"
    assert settings.ai_image_daily_limit == 6
    assert settings.ai_image_per_match_limit == 1
    assert settings.wechat_inline_ai_image_limit == 1


def test_settings_expose_xhs_automation_backend() -> None:
    settings = Settings(XHS_AUTOMATION_BACKEND="patchright")

    assert settings.xhs_automation_backend == "patchright"
