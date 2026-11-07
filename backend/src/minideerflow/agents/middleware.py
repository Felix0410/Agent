"""使用官方hook记录最终模型响应；父子共享预算且不改消息对象。"""

import asyncio

from langchain.agents.middleware import AgentMiddleware

from minideerflow.runtime.budget import estimate_messages, estimate_tools


class UsageBudgetMiddleware(AgentMiddleware):
    """统计实际模型调用，不监听token delta，避免重复入账。"""

    def __init__(self, source="parent", hard_limit=18000):
        self.source = source
        self.hard_limit = hard_limit

    async def awrap_model_call(self, request, handler):
        """预算预扣后执行一次，最终回执入账且取消继续向上传播。"""
        # 1. 估算必须覆盖真实消息、System与公开工具Schema。
        context = request.runtime.context
        tracker = getattr(context, "budget_tracker", None)
        if tracker is None:
            return await handler(request)
        messages = list(request.messages)
        if request.system_message:
            messages.insert(0, request.system_message)
        estimate = estimate_messages(messages) + estimate_tools(request.tools)
        if estimate > min(self.hard_limit, tracker.context_hard_limit):
            from minideerflow.runtime.budget import BudgetError

            raise BudgetError("CONTEXT_BUDGET_EXCEEDED")
        # 2. 预留成功才进入官方handler，不监听chunk重复计数。
        reserved = await tracker.reserve("model", estimate, self.source)
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
            # 3. 包含失败/取消的最终结果也只有一个invocation入账。
            await tracker.finish(reserved, status, usage)


class ChildToolBudgetMiddleware(AgentMiddleware):
    """child与旧轻量工具路径共用计数，不改变原有工具集合。"""

    def __init__(self, source="child"):
        self.source = source

    async def awrap_tool_call(self, request, handler):
        tracker = getattr(request.runtime.context, "budget_tracker", None)
        if tracker is None:
            return await handler(request)
        reserved = await tracker.reserve("tool", source=self.source)
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
        """完整分区成功后才返回官方State消息替换，不修改Todo。"""
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
            await tracker.emit(
                "context_compacted",
                {
                    "run_id": context.run_id,
                    "old_message_count": len(state["messages"]),
                    "new_message_count": len(messages),
                    "estimated_before": before,
                    "estimated_after": estimate_messages(messages) + self.manager.tool_estimate,
                },
            )
        return {
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages],
            "context_summary": summary,
        }
