"""智能体图状态定义。"""

from __future__ import annotations

from typing import TypedDict

from app.src.agent.schemas import SearchResult


class AgentState(TypedDict, total=False):
    """LangGraph 运行时共享状态。"""

    user_message: str
    intent: str
    citations: list[SearchResult]
    prompt: str
    answer: str
