"""Mini DeerFlow 的单次请求命令行入口。"""

import argparse
import asyncio
import sys

from minideerflow.agents.service import AgentExecutionError, run_agent_once
from minideerflow.core.model import ModelNotConfigured


def main() -> int:
    """提供一次性终端入口，直接复用 Web 调用的 Agent 服务。"""
    # 1. 解析本次消息；CLI 不维护独立的会话状态。
    parser = argparse.ArgumentParser(description="Run one Mini DeerFlow Agent request")
    parser.add_argument("message")
    args = parser.parse_args()
    # 2. 交给同一 AgentService 执行，错误转换为可读提示与非零退出码。
    try:
        response = asyncio.run(run_agent_once(args.message))
    except ModelNotConfigured:
        print("MODEL_NOT_CONFIGURED: Set MODEL_NAME and MODEL_API_KEY", file=sys.stderr)
        return 1
    except AgentExecutionError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 1
    except ValueError:
        print("INVALID_MESSAGE: message must contain 1 to 2000 characters", file=sys.stderr)
        return 1
    # 3. 输出最终答复及真实工具轨迹，不展示密钥和 Provider 内部信息。
    print(response.answer)
    for call in response.tool_calls:
        print(f"{call.name} {call.args} => {call.result} (ok={call.ok})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
