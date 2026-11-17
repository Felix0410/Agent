"""使用官方hook记录最终模型响应；父子共享用量与取消信号且不改消息对象。"""

import asyncio

from langchain.agents.middleware import AgentMiddleware

from minideerflow.runtime.budget import budget_breakdown


class ModelUsageMiddleware(AgentMiddleware):
    """统计实际模型调用，不监听token delta，避免重复入账。"""

    def __init__(self, source="parent", hard_limit=None):
        self.source = source

    async def awrap_model_call(self, request, handler):
        """调用登记后执行一次，最终回执入账且取消继续向上传播。"""
        # 1. 估算必须覆盖真实消息、System与公开工具Schema。
        context = request.runtime.context
        tracker = getattr(context, "budget_tracker", None)
        if tracker is None:
            return await handler(request)
        # 字节大小仅作诊断；模型真实窗口与摘要由Provider/官方中间件处理。
        breakdown = budget_breakdown(
            request.messages,
            request.tools,
            request.system_message,
            soft=0,
            hard=0,
            cumulative=tracker.estimated,
        )
        await tracker.record_context(breakdown, "OBSERVATION_ONLY")
        reserved = await tracker.reserve("model", breakdown.total_bytes, self.source)
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


class ToolUsageMiddleware(AgentMiddleware):
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


# 旧内部导入名仅用于兼容，已弃用其预算语义，生产装配使用新名称。
UsageBudgetMiddleware = ModelUsageMiddleware
ChildToolBudgetMiddleware = ToolUsageMiddleware
