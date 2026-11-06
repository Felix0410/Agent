"""父 Tool 内同步等待子代理；权限来自可信 Run Context。"""

import asyncio
from dataclasses import replace

from minideerflow.agents.context import AgentRunContext, ChildContext
from minideerflow.agents.subagents.config import SPECS
from minideerflow.agents.subagents.executor import execute_child
from minideerflow.agents.subagents.models import TaskResult, TaskStatus
from minideerflow.runtime.plan_repository import PlanError
from minideerflow.runtime.plan_service import safe_emit
from minideerflow.runtime.task_registry import TaskRegistry
from minideerflow.tools.calculator import calculate
from minideerflow.tools.file_tools import list_files, read_text


class TaskDispatcher:
    """每 Run 的限额与生命周期由同一个 TaskRegistry 管理。"""

    def __init__(self, repository, model_factory, registry=None, *, timeout=35, recursion_limit=14):
        self.repository = repository
        self.model_factory = model_factory
        self.registry = registry or TaskRegistry()
        self.timeout = timeout
        self.recursion_limit = recursion_limit

    async def dispatch(
        self, context, agent_type: str, description: str, todo_id: str | None = None
    ) -> TaskResult:
        """角色与父权限取交集，子 Context 不包含 dispatcher。"""
        if not isinstance(context, AgentRunContext) or context.task_dispatcher is not self:
            raise PlanError("SUBTASK_CONTEXT_INVALID")
        if agent_type not in SPECS:
            raise PlanError("SUBTASK_ROLE_INVALID")
        # 1. 先验证真实身份和输入，再保留有界执行名额。
        if not 1 <= len(description.strip()) <= 1000:
            raise PlanError("SUBTASK_INVALID")
        await context.workspace_service.repository.check_run(context.thread_id, context.run_id)
        return await self.registry.run(
            context.run_id,
            lambda semaphore: self._execute(context, agent_type, description, todo_id, semaphore),
        )

    async def _execute(self, context, agent_type, description, todo_id, semaphore):
        """SQL 阶段用 shield 确认提交结果，取消时不遗留 PENDING/RUNNING。"""
        registration = asyncio.create_task(
            self.repository.create_subtask(
                context.run_id, context.thread_id, agent_type, description, todo_id
            )
        )
        record = None
        phase = None
        try:
            record = await asyncio.shield(registration)
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
            # 2. 第四个已登记任务在这里排队；等待被取消不能伪造已启动。
            async with semaphore:
                phase = asyncio.create_task(
                    self.repository.transition_subtask(
                        record.id, context.run_id, context.thread_id, TaskStatus.RUNNING
                    )
                )
                await asyncio.shield(phase)
                await safe_emit(
                    context,
                    "subtask_started",
                    {"task_id": record.id, "agent_type": agent_type, "status": "RUNNING"},
                )
                spec = replace(
                    SPECS[agent_type], timeout=self.timeout, max_steps=self.recursion_limit
                )
                tools = [
                    t
                    for t in (calculate, list_files, read_text)
                    if t.name in spec.allowed_tools and t.name in context.allowed_tools
                ]
                child = ChildContext(context.thread_id, context.run_id, context.workspace_service)
                result = await execute_child(
                    spec, description, child, self.model_factory, tools, record.id
                )
                # 3. 已提交终态遇取消仍保留；等待最终提交后才回收句柄。
                phase = asyncio.create_task(self._finish(context, result))
                await asyncio.shield(phase)
                return result
        except BaseException:
            # shield 只防止半途取消；必须显式等待，不能让 SQL 写入逃逸生命周期。
            try:
                record = record or await registration
                if phase is not None:
                    await phase
                records = await self.repository.list_subtasks(context.run_id)
                current = next(t for t in records if t.id == record.id)
                if current.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    status = (
                        TaskStatus.FAILED
                        if current.status == TaskStatus.PENDING
                        else TaskStatus.CANCELLED
                        if asyncio.current_task().cancelling()
                        else TaskStatus.FAILED
                    )
                    result = TaskResult(
                        task_id=record.id,
                        status=status,
                        error_code="SUBTASK_CANCELLED"
                        if asyncio.current_task().cancelling()
                        else "SUBTASK_EXECUTION_FAILED",
                    )
                    cleanup = asyncio.create_task(self._finish(context, result))
                    await asyncio.shield(cleanup)
            except Exception:  # noqa: BLE001 - 库故障留给启动孤儿核查，不打印敏感异常
                import logging

                logging.getLogger("minideerflow").error("Subtask cleanup unavailable")
            raise

    async def _finish(self, context, result):
        """持久化真实终态并发出对应父 Run 事件。"""
        await self.repository.transition_subtask(
            result.task_id, context.run_id, context.thread_id, result.status, result
        )
        payload = {"task_id": result.task_id, "status": result.status.value}
        if result.status == TaskStatus.COMPLETED:
            payload.update(
                summary=result.summary,
                source_file_ids=result.source_file_ids,
                truncated=result.truncated,
            )
            kind = "subtask_completed"
        else:
            payload["error_code"] = result.error_code
            kind = "subtask_failed"
        await safe_emit(context, kind, payload)
