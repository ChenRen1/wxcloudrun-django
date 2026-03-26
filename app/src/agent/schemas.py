"""智能体内部使用的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """统一的知识片段结构。"""

    id: int
    title: str
    source: str | None
    content: str
    score: float = 1.0


@dataclass
class MessageResponse:
    """最小消息结构。"""

    id: int
    conversation_id: str
    role: str
    content: str
    citations: list[SearchResult] = field(default_factory=list)
