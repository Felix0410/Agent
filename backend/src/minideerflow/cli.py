import argparse
import asyncio
import sys

from minideerflow.agents.service import AgentExecutionError, run_agent_once
from minideerflow.core.model import ModelNotConfigured


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Mini DeerFlow Agent request")
    parser.add_argument("message")
    args = parser.parse_args()
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
    print(response.answer)
    for call in response.tool_calls:
        print(f"{call.name} {call.args} => {call.result} (ok={call.ok})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
