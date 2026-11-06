"""单进程有界后台执行：准入、队列、Graph 与业务终态各有明确边界。"""

import asyncio
import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from openai import APIError, APITimeoutError

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.service import AgentExecutionError, validate_message
from minideerflow.agents.state import P04AgentState
from minideerflow.agents.subagents.dispatcher import TaskDispatcher
from minideerflow.config import Settings
from minideerflow.core.model import ModelNotConfigured, build_chat_model
from minideerflow.runtime.events import EventBus
from minideerflow.runtime.models import RunAccepted, RunDto, RunStatus
from minideerflow.runtime.plan_service import PlanService
from minideerflow.runtime.repository import RuntimeRepository
from minideerflow.runtime.streaming import stream_agent
from minideerflow.runtime.task_registry import TaskRegistry
from minideerflow.tools.calculator import calculate
from minideerflow.tools.file_tools import list_files, read_text, write_text
from minideerflow.tools.task_tool import task
from minideerflow.tools.todo_tool import write_todos
from minideerflow.workspace.models import WorkspaceContext
from minideerflow.workspace.service import WorkspaceService

logger = logging.getLogger("minideerflow")


class RunServiceError(Exception):
    """只在请求准入阶段返回 HTTP 错误；后台失败写入 Run。"""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


class RunService:
    """最多两个 worker、八个排队任务，Task 强引用保持到 shutdown 回收。"""

    def __init__(
        self,
        repository: RuntimeRepository,
        checkpointer,
        settings: Settings,
        *,
        events: EventBus | None = None,
        model_factory: Callable[[Settings], BaseChatModel] | None = None,
        workspace: WorkspaceService | None = None,
        plans: PlanService | None = None,
        task_registry: TaskRegistry | None = None,
    ) -> None:
        self.task_registry = task_registry or TaskRegistry(
            settings.max_subagent_concurrency, settings.max_subagent_calls_per_run
        )
        self.plans = plans
        self.events = events
        self.workspace = workspace
        self.repository = repository
        self.checkpointer = checkpointer
        self.settings = settings
        self.model_factory = model_factory or build_chat_model
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.run_queue_size)
        self._admission = asyncio.Lock()
        self._workers: list[asyncio.Task] = []
        self.accepting = False

    def start(self) -> None:
        """只在应用生命周期启动 worker，不在这里构造或连接模型。"""
        if self._workers:
            return
        self.accepting = True
        self._workers = [
            asyncio.create_task(self._worker_loop(), name=f"run-worker-{index}")
            for index in range(self.settings.run_max_concurrency)
        ]

    async def start_run(self, thread_id: str, message: str) -> RunAccepted:
        """统一准入临界区内检查容量并创建/入队；失败绝不返回虚假的 202。"""
        validate_message(message)
        async with self._admission:
            # 1. 会话错误优先于容量错误，模型缺配置也不能残留 CREATED。
            if not self.accepting:
                raise RunServiceError("RUN_SERVICE_STOPPING", "Service is stopping", 503)
            await self.repository.check_thread_available(thread_id)
            try:
                self.model_factory(self.settings)
            except ModelNotConfigured:
                raise
            except Exception:  # noqa: BLE001 - 不向 HTTP 传递模型构造异常
                raise AgentExecutionError(
                    "MODEL_UPSTREAM_ERROR", "Model configuration failed"
                ) from None
            # 2. 只有此处是生产者；同一临界区内检查空间后写入并立即入队。
            if self.queue.full():
                raise RunServiceError("RUN_QUEUE_FULL", "Run queue is full", 429)
            run = await self.repository.create_run(thread_id, message)
            try:
                if self.events is not None:
                    await self.events.ensure_run(run.id, thread_id)
                self.queue.put_nowait(run.id)
            except BaseException:
                await self.repository.complete_run(
                    run.id, status=RunStatus.FAILED, error_code="RUN_INTERRUPTED"
                )
                raise
            return RunAccepted(run_id=run.id, thread_id=thread_id)

    async def _worker_loop(self) -> None:
        """独立回收每个任务的错误；单个模型失败不能杀死整个 worker。"""
        while True:
            run_id = await self.queue.get()
            try:
                run = await self.repository.get_run(run_id)
                await self._execute_run(run)
            except asyncio.CancelledError:
                # 取消也可能发生在读取 Run、尚未进入 _execute_run 的窗口。
                await self._fail_run(run_id, "RUN_INTERRUPTED", False)
                raise
            except Exception:  # noqa: BLE001 - worker 边界只记录脱敏日志
                logger.error("Run worker failed (run_id=%s)", run_id)
            finally:
                self.queue.task_done()

    async def _execute_run(self, run: RunDto) -> None:
        """成功先验收消息再提交；失败只保存稳定错误码与保守恢复标志。"""
        graph_started = False

        def mark_graph_started() -> None:
            nonlocal graph_started
            graph_started = True

        try:
            # 1. RUNNING 先提交，模型构造失败不代表已经修改 Graph。
            await self.repository.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
            await self._emit(run.id, "run_start", {"status": "RUNNING"})
            model = self.model_factory(self.settings)
            context = None
            if self.workspace is not None:
                # 身份来自已持久化的Run，不从Prompt/模型JSON/全局变量取得。
                context = WorkspaceContext(run.thread_id, run.id, self.workspace)
                tools = [calculate, list_files, read_text, write_text]
                p04 = self.plans is not None
                if p04:
                    dispatcher = TaskDispatcher(
                        self.plans.repository,
                        lambda: self.model_factory(self.settings),
                        self.task_registry,
                        timeout=self.settings.subagent_timeout_seconds,
                        recursion_limit=self.settings.subagent_recursion_limit,
                    )
                    context = AgentRunContext(
                        run.thread_id,
                        run.id,
                        self.workspace,
                        self.plans,
                        lambda kind, payload: self._emit(run.id, kind, payload),
                        dispatcher,
                    )
                    tools.extend([write_todos, task])
                agent = build_lead_agent(
                    model,
                    tools,
                    self.checkpointer,
                    context_schema=AgentRunContext if p04 else WorkspaceContext,
                    state_schema=P04AgentState if p04 else None,
                    prompt_suffix=(
                        " For complex tasks use write_todos and keep the complete plan updated. Use task to delegate focused goals to general/research (existing material only, no internet). Child agents cannot write files; use write_text yourself for a final artifact. Report failures honestly. Simple questions need no plan or delegation."
                        if p04
                        else ""
                    ),
                )
            else:
                # 旧单轮路径及无Workspace的局部Fake注入保持原工具范围。
                agent = build_lead_agent(model, [calculate], self.checkpointer)
            # 2. 整轮而非单次模型 HTTP 请求有时限；历史由 Checkpointer 自动传入。
            try:
                async with asyncio.timeout(
                    self.settings.run_timeout_seconds
                    if self.plans
                    else self.settings.model_timeout_seconds
                ):
                    response = await stream_agent(
                        agent,
                        run.thread_id,
                        run.input_message,
                        event_sink=lambda kind, payload: self._emit(run.id, kind, payload),
                        on_graph_start=mark_graph_started,
                        context=context,
                        recursion_limit=36 if self.plans else None,
                        initial_state_extra={"todos": []} if self.plans else None,
                    )
            finally:
                await self.task_registry.close_run(run.id)
            # 3. 只有有效的本轮最终消息才能写入 SUCCEEDED。
            await self._emit(run.id, "assistant_final", {"answer": response.answer})
            await self.repository.complete_run(
                run.id,
                status=RunStatus.SUCCEEDED,
                answer=response.answer,
                tool_calls=response.tool_calls,
            )
            await self._emit(run.id, "run_end", {"status": "SUCCEEDED"})
            if self.events is not None:
                await self.events.close_run(run.id)
        except asyncio.CancelledError:
            await self._fail_run(run.id, "RUN_INTERRUPTED", graph_started)
            raise
        except (TimeoutError, APITimeoutError):
            await self._fail_run(run.id, "MODEL_TIMEOUT", graph_started)
        except APIError:
            await self._fail_run(run.id, "MODEL_UPSTREAM_ERROR", graph_started)
        except Exception:  # noqa: BLE001 - 原始异常可能含 Provider 凭据
            await self._fail_run(run.id, "AGENT_EXECUTION_FAILED", graph_started)

    async def _fail_run(self, run_id: str, code: str, graph_started: bool) -> None:
        """不覆盖既有终态；数据库不可写时只记录安全日志，留待重启核查。"""
        try:
            run = await self.repository.get_run(run_id)
            if run.status not in (RunStatus.CREATED, RunStatus.RUNNING):
                return
            await self.repository.complete_run(
                run_id, status=RunStatus.FAILED, error_code=code, needs_recovery=graph_started
            )
            await self._emit(run_id, "error", {"code": code, "message": "Run execution failed"})
            await self._emit(run_id, "run_end", {"status": "FAILED"})
            if self.events is not None:
                await self.events.close_run(run_id)
        except Exception:  # noqa: BLE001 - 不能以伪造成功掩盖持久化失败
            logger.error("Run failure persistence failed (run_id=%s)", run_id)

    async def _emit(self, run_id: str, kind: str, payload: dict) -> None:
        """事件可用于观察，终态成功只能在 Repository 提交之后发出。"""
        if self.events is not None:
            await self.events.publish(run_id, kind, payload)

    async def shutdown(self, grace_seconds: float = 2) -> None:
        """先停止准入并有限等待，再取消/回收所有任务，最后清理排队记录。"""
        async with self._admission:
            self.accepting = False
        # 1. 给正常任务有限的完成时间，不能无限阻塞服务器退出。
        try:
            await asyncio.wait_for(self.queue.join(), timeout=grace_seconds)
        except TimeoutError:
            pass
        # 2. Graph 取消处理先落库，然后才能由 lifespan 关闭 Saver 与业务连接。
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        # 3. 尚未进入 Graph 的排队任务标记中断，但不污染正常 Thread 的恢复标志。
        while not self.queue.empty():
            run_id = self.queue.get_nowait()
            await self._fail_run(run_id, "RUN_INTERRUPTED", False)
            self.queue.task_done()
