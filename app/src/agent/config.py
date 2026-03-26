"""智能体相关配置。"""

from pathlib import Path


api_key = "sk-9adf1d91a297432d8775a9d91d90da09"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model_name = "qwen-plus"

role_prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "role_prompt.md"
role_prompt = role_prompt_path.read_text(encoding="utf-8").strip()
