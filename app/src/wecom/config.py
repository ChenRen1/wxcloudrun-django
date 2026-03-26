"""企业微信模块配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


QYAPI_BASE_URL = "https://qyapi.weixin.qq.com"
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


@dataclass(slots=True)
class WeComKFSettings:
    """企业微信客服运行配置。"""

    corp_id: str
    corp_secret: str
    callback_token: str | None = None
    encoding_aes_key: str | None = None
    receive_id: str | None = None
    base_url: str = QYAPI_BASE_URL
    auto_reply_enabled: bool = False


def load_wecom_settings() -> WeComKFSettings:
    """读取企业微信配置。"""

    _load_local_env()
    return WeComKFSettings(
        corp_id=os.getenv("WECOM_CORP_ID", ""),
        corp_secret=os.getenv("WECOM_KF_SECRET", ""),
        callback_token=os.getenv("WECOM_CALLBACK_TOKEN"),
        encoding_aes_key=os.getenv("WECOM_CALLBACK_AES_KEY"),
        receive_id=os.getenv("WECOM_CALLBACK_RECEIVE_ID") or os.getenv("WECOM_CORP_ID"),
        base_url=os.getenv("WECOM_API_BASE_URL", QYAPI_BASE_URL),
        auto_reply_enabled=os.getenv("WECOM_AUTO_REPLY_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
    )


def _load_local_env() -> None:
    """从项目根目录 `.env` 补充读取企业微信配置。"""

    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.startswith("WECOM_"):
            continue
        os.environ[key] = value.strip().strip("'").strip('"')
