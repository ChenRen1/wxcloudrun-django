"""智能体模型调用层。"""

from __future__ import annotations

import httpx

from app.src.agent.config import api_key, base_url, model_name, role_prompt


async def call_chat_model(user_prompt: str) -> str | None:
    """调用 OpenAI 兼容接口。"""

    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return None

    choices = data.get("choices", [])
    if not choices:
        return None

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None

    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                text = item.get("text")
                if text:
                    texts.append(text)
        joined = "\n".join(texts).strip()
        return joined or None

    return None
