"""父 Tool 内同步等待子代理；权限来自可信 Run Context。"""

import asyncio

from minideerflow.agents.context import AgentRunContext, ChildContext
from minideerflow.agents.subagents.config import SPECS
from minideerflow.agents.subagents.executor import execute_child
from minideerflow.agents.subagents.models import TaskResult, TaskStatus
from minideerflow.runtime.plan_repository import PlanError
from minideerflow.runtime.plan_service import safe_emit
from minideerflow.tools.calculator import calculate
from minideerflow.tools.file_tools import list_files, read_text


class TaskDispatcher:
    """B 阶段同 Run 串行委派，C 再加入有限并发注册表。"""

    def __init__(self, repository, model_factory):
        self.repository = repository
        self.model_factory = model_factory
        self._serial = asyncio.Lock()

    async def dispatch(
        self, context, agent_type: str, description: str, todo_id: str | None = None
    ) -> TaskResult:
        """角色与父权限取交集，子 Context 不包含 dispatcher。"""
        if not isinstance(context, AgentRunContext) or context.task_dispatcher is not self:
            raise PlanError("SUBTASK_CONTEXT_INVALID")
        if agent_type not in SPECS:
            raise PlanError("SUBTASK_ROLE_INVALID")
        async with self._serial:
            # 1. 同一事务验证 Run/Thread/Todo 后才分配真实任务。
            record = await self.repository.create_subtask(
                context.run_id, context.thread_id, agent_type, description, todo_id
            )
            await safe_emit(
                context,
                "subtask_created",
                {
                    "task_id": record.id,
                    "agent_type": agent_type,
                    "description": description,
                    "todo_id": todo_id,
                    "status": "PENDING",
                },
            )
            await self.repository.transition_subtask(
                record.id, context.run_id, context.thread_id, TaskStatus.RUNNING
            )
            await safe_emit(
                context,
                "subtask_started",
                {"task_id": record.id, "agent_type": agent_type, "status": "RUNNING"},
            )
            # 2. 只有三个只读工具候选，双方交集无法增加 task/write 权限。
            spec = SPECS[agent_type]
            tools = [
                t
                for t in (calculate, list_files, read_text)
                if t.name in spec.allowed_tools and t.name in context.allowed_tools
            ]
            child = ChildContext(context.thread_id, context.run_id, context.workspace_service)
            try:
                result = await execute_child(
                    spec, description, child, self.model_factory, tools, record.id
                )
            except asyncio.CancelledError:
                result = TaskResult(
                    task_id=record.id, status=TaskStatus.CANCELLED, error_code="SUBTASK_CANCELLED"
                )
                await self._finish(context, result)
                raise
            # 3. 终态先提交，再事件/工具回执；父措辞不会修改状态。
            await self._finish(context, result)
            return result

    async def _finish(self, context, result):
        """持久化真实终态并发出对应父 Run 事件。"""
        await self.repository.transition_subtask(
            result.task_id, context.run_id, context.thread_id, result.status, result
        )
        payload = {"task_id": result.task_id, "status": result.status.value}
        if result.status == TaskStatus.COMPLETED:
            payload.update(summary=result.summary, source_file_ids=result.source_file_ids)
            kind = "subtask_completed"
        else:
            payload["error_code"] = result.error_code
            kind = "subtask_failed"
        await safe_emit(context, kind, payload)
