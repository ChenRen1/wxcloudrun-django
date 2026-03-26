"""LangGraph 终端对话测试脚本。

这是当前最推荐的本地调试入口之一，因为它：
- 不依赖 FastAPI
- 不依赖数据库服务
- 直接调用 `app/src` 下的新 LangGraph 智能体

适合快速验证：
1. 意图识别是否正常
2. 引用片段是否正常返回
3. 模型输出是否符合 `role_prompt`
4. 整条图链路是否可以从输入跑到输出
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 确保直接运行脚本时也能导入项目根目录下的 `app/src` 模块。
# 否则使用 `python scripts/chat_langgraph.py` 时，Python 可能只把 `scripts/`
# 当成起点，找不到项目根目录下的包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from app.src.agent.runner import run_agent


async def main() -> None:
    """运行一个简单的命令行对话循环。"""

    print("LangGraph 对话测试已启动")
    print("输入问题后回车发送，输入 /exit 退出。")
    print("示例：25考情汇总、我想看考研经验、华中科技大学考情分析")
    print()

    while True:
        # 这里用同步 `input()` 读用户输入，再把处理交给异步图执行。
        user_input = input("你: ").strip()
        if not user_input:
            continue

        if user_input == "/exit":
            print("已退出。")
            return

        # `run_agent()` 返回的是完整状态，不只是最终答案。
        # 这里顺手把 `intent` 和 `citations` 打印出来，方便调试图的中间结果。
        result = await run_agent(user_input)
        answer = result.get("answer", "")
        intent = result.get("intent", "")
        citations = result.get("citations", [])

        print(f"意图: {intent}")
        print(f"客服: {answer}")
        if citations:
            print("引用:")
            for item in citations[:3]:
                print(f"- {item.title} ({item.source})")
        print()


if __name__ == "__main__":
    asyncio.run(main())
