"""智能体内部策略配置读取。"""

from __future__ import annotations

import json
from pathlib import Path


def _load_json(filename: str) -> dict:
    """读取 `app/configs` 目录下的 JSON 配置文件。"""

    path = Path(__file__).resolve().parents[2] / "configs" / filename
    return json.loads(path.read_text(encoding="utf-8"))


def load_business_data() -> dict:
    """读取业务数据配置。"""

    return _load_json("business_data.json")


def load_response_strategy() -> dict:
    """读取回复策略配置。"""

    return _load_json("response_strategy.json")


def detect_intent(text: str) -> str:
    """根据配置中的关键词做轻量意图识别。"""

    strategy = load_response_strategy()
    normalized = text.strip()

    for keyword in strategy["keywords"]["summary"]:
        if keyword in normalized:
            return "summary"
    for keyword in strategy["keywords"]["experience"]:
        if keyword in normalized:
            return "experience"
    for keyword in strategy["keywords"]["analysis"]:
        if keyword in normalized:
            return "analysis"
    return "fallback"
