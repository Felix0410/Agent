"""官方ToolNode外层守卫：不另写执行循环，不重试handler。"""

import asyncio
import json

from jsonschema import ValidationError as JSONSchemaError
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from pydantic import ValidationError

from minideerflow.agents.context import AgentRunContext
from minideerflow.runtime.budget import BudgetError
from minideerflow.tools.registry import ToolPolicy, ToolPolicyError, ToolRegistry
from minideerflow.workspace.service import WorkspaceService


class ToolGuardMiddleware(AgentMiddleware):
    """工具执行安全中间件"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def awrap_tool_call(self, request, handler):
        """工具执行安全中间件"""
        tracker = getattr(request.runtime.context, "budget_tracker", None)
        if tracker is None:
            return await self._guard(request, handler)
        reservation = await tracker.reserve("tool")
        status = "error"
        try:
            result = await self._guard(request, handler)
            status = "ok" if getattr(result, "status", None) != "error" else "error"
            return result
        finally:
            await tracker.finish(reservation, status)

    async def _guard(self, request, handler):
        """权限/参数校验→单次有界执行→脱敏错误；取消必须传播。"""
        call = request.tool_call
        call_id = call.get("id", "")
        definition = None
        execution_started = False
        execution_confirmed = False
        try:
            # 1. 可信身份和当前Policy必须一致，不能由模型多传一个参数越权。
            name = call.get("name")
            args = call.get("args")
            if (
                not isinstance(call_id, str)
                or not call_id
                or not isinstance(name, str)
                or not isinstance(args, dict)
            ):
                raise ToolPolicyError("TOOL_INVALID_ARGS")
            context = request.runtime.context
            if (
                not isinstance(context, AgentRunContext)
                or not isinstance(context.tool_policy, ToolPolicy)
                or not isinstance(context.workspace_service, WorkspaceService)
            ):
                raise ToolPolicyError("TOOL_NOT_ALLOWED")
            policy = context.tool_policy
            if policy.run_id != context.run_id or policy.thread_id != context.thread_id:
                raise ToolPolicyError("TOOL_NOT_ALLOWED")
            definition = self.registry.get(name)
            if (
                name not in policy.allowed_names
                or definition.permission not in policy.allowed_permissions
            ):
                raise ToolPolicyError("TOOL_NOT_ALLOWED")
            await context.workspace_service.repository.check_run(context.thread_id, context.run_id)
            if (
                definition.source == "mcp"
                and len(json.dumps(args, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                > 2048
            ):
                raise ToolPolicyError("TOOL_INVALID_ARGS")
            schema = definition.tool.tool_call_schema
            public_schema = schema if isinstance(schema, dict) else schema.model_json_schema()
            # 部分既有Pydantic工具默认忽略extra；守卫必须显式拒绝模型伪造字段。
            if args.keys() - public_schema.get("properties", {}).keys():
                raise ToolPolicyError("TOOL_INVALID_ARGS")
            if isinstance(schema, dict):
                # MCP原始JSONSchema由标准验证器检查，不改写参数契约。
                from jsonschema import validate

                validate(args, schema)
            else:
                schema.model_validate(args, strict=True)
            # 2. 官方handler负责注入runtime；只执行一次，Command原对象直接返回。
            tracker = getattr(context, "budget_tracker", None)
            if tracker:
                await tracker.check()
            execution_started = True
            result = await asyncio.wait_for(handler(request), timeout=definition.timeout_seconds)
            execution_confirmed = True
            if definition.source == "mcp":
                # MCP仅允许纯文本，原始错误/结构化artifact已由SDK拦截器清理。
                if not isinstance(result, ToolMessage):
                    raise ToolPolicyError("MCP_TOOL_ERROR")
                content = result.content
                text = (
                    content
                    if isinstance(content, str)
                    else "\n".join(
                        c.get("text", "")
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                )
                result = result.model_copy(update={"content": text, "artifact": None})
            return result
        except BudgetError:
            raise
        except asyncio.CancelledError:
            tracker = getattr(request.runtime.context, "budget_tracker", None)
            if (
                tracker
                and execution_started
                and not execution_confirmed
                and definition
                and definition.permission == "write"
            ):
                tracker.outcome_unknown = True
            raise
        except TimeoutError:
            tracker = getattr(request.runtime.context, "budget_tracker", None)
            if (
                tracker
                and execution_started
                and not execution_confirmed
                and definition
                and definition.permission == "write"
            ):
                tracker.outcome_unknown = True
            code = "TOOL_TIMEOUT"
            if definition is not None and definition.source == "mcp":
                self.registry.mark_origin_offline(definition.origin)
        except (ValidationError, JSONSchemaError, TypeError, ValueError):
            code = "TOOL_INVALID_ARGS"
        except ToolPolicyError as exc:
            code = exc.code
        except Exception:  # noqa: BLE001 - Provider/文件路径/认证异常不能输出给模型
            tracker = getattr(request.runtime.context, "budget_tracker", None)
            if (
                tracker
                and execution_started
                and not execution_confirmed
                and definition
                and definition.permission == "write"
            ):
                tracker.outcome_unknown = True
            code = "TOOL_EXECUTION_FAILED"
            if definition is not None and definition.source == "mcp":
                code = "MCP_UNAVAILABLE"
                self.registry.mark_origin_offline(definition.origin)
        # 3. 不把超时写操作当失败可重试；结果未知，由用户/后续工具复核。
        return ToolMessage(
            content=f"ERROR[{code}]: Tool call failed; do not retry writes automatically",
            tool_call_id=call_id if isinstance(call_id, str) else "",
            status="error",
        )
