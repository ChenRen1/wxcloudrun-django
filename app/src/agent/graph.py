"""LangGraph 图定义。"""

from __future__ import annotations

import json

from langgraph.graph import END, START, StateGraph

from app.src.agent.model import call_chat_model
from app.src.agent.policy import detect_intent, load_response_strategy
from app.src.agent.repository import retrieve_knowledge
from app.src.agent.state import AgentState


def _make_prompt(state: AgentState) -> str:
    strategy = load_response_strategy()
    knowledge = [
        {
            "title": item.title,
            "source": item.source,
            "content": item.content,
            "score": item.score,
        }
        for item in state.get("citations", [])
    ]
    return (
        "请严格依据下列知识库内容回复用户，不要编造链接或未提供的学校数据。\n\n"
        f"当前识别意图：{state.get('intent', 'fallback')}\n\n"
        f"回复策略：\n{json.dumps(strategy, ensure_ascii=False, indent=2)}\n\n"
        f"知识库命中结果：\n{json.dumps(knowledge, ensure_ascii=False, indent=2)}\n\n"
        f"用户问题：\n{state['user_message']}"
    )


def detect_intent_node(state: AgentState) -> AgentState:
    return {"intent": detect_intent(state["user_message"])}


async def retrieve_node(state: AgentState) -> AgentState:
    citations = await retrieve_knowledge(
        state["user_message"],
        state.get("intent", "fallback"),
        limit=4,
    )
    return {"citations": citations}


def build_prompt_node(state: AgentState) -> AgentState:
    return {"prompt": _make_prompt(state)}


async def answer_node(state: AgentState) -> AgentState:
    answer = await call_chat_model(state["prompt"])
    return {"answer": answer or "模型暂时不可用。"}


def build_agent_graph():
    """构建并编译 LangGraph 图。"""

    graph = StateGraph(AgentState)
    graph.add_node("detect_intent", detect_intent_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "detect_intent")
    graph.add_edge("detect_intent", "retrieve")
    graph.add_edge("retrieve", "build_prompt")
    graph.add_edge("build_prompt", "answer")
    graph.add_edge("answer", END)

    return graph.compile()
