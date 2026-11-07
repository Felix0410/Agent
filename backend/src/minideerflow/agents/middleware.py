"""使用官方hook记录最终模型响应；父子共享预算且不改消息对象。"""

import asyncio

from langchain.agents.middleware import AgentMiddleware

from minideerflow.runtime.budget import estimate_messages


class UsageBudgetMiddleware(AgentMiddleware):
    """统计实际模型调用，不监听token delta，避免重复入账。"""

    def __init__(self, source="parent"):
        self.source = source

    async def awrap_model_call(self, request, handler):
        context = request.runtime.context
        tracker = getattr(context, "budget_tracker", None)
        if tracker is None:
            return await handler(request)
        messages = list(request.messages)
        if request.system_message:
            messages.insert(0, request.system_message)
        reserved = await tracker.reserve("model", estimate_messages(messages), self.source)
        usage = None
        status = "error"
        try:
            response = await handler(request)
            usage = response.result[-1].usage_metadata if response.result else None
            status = "ok"
            return response
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        finally:
            await tracker.finish(reserved, status, usage)


class ChildToolBudgetMiddleware(AgentMiddleware):
    """child仍沿用只读工具集合，仅增加共享计数。"""

    async def awrap_tool_call(self, request, handler):
        tracker = getattr(request.runtime.context, "budget_tracker", None)
        if tracker is None:
            return await handler(request)
        reserved = await tracker.reserve("tool", source="child")
        status = "error"
        try:
            result = await handler(request)
            status = "ok"
            return result
        finally:
            await tracker.finish(reserved, status)
