"""智能体对外入口。"""

from __future__ import annotations

from app.src.agent.graph import build_agent_graph


agent_graph = build_agent_graph()


async def run_agent(user_message: str) -> dict:
    """执行一次图调用，并返回完整状态。"""

    return await agent_graph.ainvoke({"user_message": user_message})
