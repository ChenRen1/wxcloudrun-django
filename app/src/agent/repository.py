"""智能体内部最小知识检索实现。"""

from __future__ import annotations

import re

from app.src.agent.policy import load_business_data
from app.src.agent.schemas import SearchResult


def _extract_year(text: str) -> int | None:
    match = re.search(r"20(1[9]|2[0-5])", text)
    if not match:
        return None
    return int(match.group(0))


def _make_citation(idx: int, title: str, source: str, content: str) -> SearchResult:
    return SearchResult(
        id=idx,
        title=title,
        source=source,
        content=content,
        score=1.0,
    )


async def retrieve_knowledge(user_message: str, intent: str, limit: int = 4) -> list[SearchResult]:
    """根据当前配置返回最相关的知识片段。"""

    business_data = load_business_data()

    if intent == "summary":
        summary = business_data["albums"]["summary"]
        return [_make_citation(1, summary["title"], summary["source"], summary["url"])]

    if intent == "experience":
        return [
            _make_citation(idx, item["title"], item["source"], item["url"])
            for idx, item in enumerate(business_data["albums"]["experience"], start=1)
        ][:limit]

    if intent == "analysis":
        school_articles = business_data.get("school_articles", [])
        matched_schools = [item["school"] for item in school_articles if item["school"] in user_message]
        if not matched_schools:
            return []

        school = matched_schools[0]
        year = _extract_year(user_message)
        school_items = [item for item in school_articles if item["school"] == school]
        if year is not None:
            school_items = [item for item in school_items if int(item["year"]) == year]
        else:
            school_items = sorted(school_items, key=lambda item: int(item["year"]), reverse=True)

        return [
            _make_citation(idx, item["title"], item["source"], item["url"])
            for idx, item in enumerate(school_items, start=1)
        ][:limit]

    return []
