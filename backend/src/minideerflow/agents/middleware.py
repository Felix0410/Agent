"""使用官方hook记录最终模型响应；父子共享预算且不改消息对象。"""

import asyncio

from langchain.agents.middleware import AgentMiddleware

from minideerflow.runtime.budget import estimate_messages


class UsageBudgetMiddleware(AgentMiddleware):
    """统计实际模型调用，不监听token delta，避免重复入账。"""

    def __init__(self, source="parent", hard_limit=18000):
        self.source = source
        self.hard_limit = hard_limit

    async def awrap_model_call(self, request, handler):
        context = request.runtime.context
        tracker = getattr(context, "budget_tracker", None)
        if tracker is None:
            return await handler(request)
        messages = list(request.messages)
        if request.system_message:
            messages.insert(0, request.system_message)
        if estimate_messages(messages) > self.hard_limit:
            from minideerflow.runtime.budget import BudgetError

            raise BudgetError("CONTEXT_BUDGET_EXCEEDED")
        reserved = await tracker.reserve("model", estimate_messages(messages), self.source)
        usage = None
        status = "error"
        try:
            await tracker.check()
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
            await tracker.check()
            result = await handler(request)
            status = "ok"
            return result
        finally:
            await tracker.finish(reserved, status)


class ContextCompactionMiddleware(AgentMiddleware):
    """复用官方abefore_model+RemoveMessage的最小安全分区实现。"""

    def __init__(self, manager, model_factory):
        self.manager = manager
        self.model_factory = model_factory

    async def abefore_model(self, state, runtime):
        from langchain_core.messages import RemoveMessage
        from langgraph.graph.message import REMOVE_ALL_MESSAGES

        context = runtime.context
        if getattr(context, "budget_tracker", None) is None:
            return None
        await context.budget_tracker.check()
        result = await self.manager.prepare(state["messages"], context, self.model_factory)
        if result is None:
            return None
        messages, summary, before = result
        tracker = context.budget_tracker
        tracker.compactions += 1
        await tracker.flush()
        if tracker.event_sink:
            await tracker.event_sink(
                "context_compacted",
                {
                    "run_id": context.run_id,
                    "old_message_count": len(state["messages"]),
                    "new_message_count": len(messages),
                    "estimated_before": before,
                    "estimated_after": estimate_messages(messages),
                },
            )
        return {
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages],
            "context_summary": summary,
        }
