"""LangGraph 版服务入口。"""

from __future__ import annotations

from app.src.agent.runner import run_agent
from app.src.agent.schemas import MessageResponse, SearchResult


async def answer_customer(conversation_id: str, user_message: str) -> tuple[str, list[SearchResult]]:
    """调用 LangGraph 智能体并返回答案与引用。"""

    _ = conversation_id
    result = await run_agent(user_message)
    return result.get("answer", ""), result.get("citations", [])


def attach_citations(message: MessageResponse, citations: list[SearchResult]) -> MessageResponse:
    """把引用信息挂到消息对象上。"""

    message.citations = citations
    return message
