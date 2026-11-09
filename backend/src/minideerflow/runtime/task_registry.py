"""活动 Run 的有界任务句柄，SQL 才是任务历史权威。"""

import asyncio
from dataclasses import dataclass, field

from minideerflow.runtime.plan_repository import PlanError


async def _drain(tasks):
    """等待所有子任务完成"""
    group = asyncio.gather(*tasks, return_exceptions=True)
    interrupted = False
    while not group.done():
        try:
            await asyncio.shield(group)
        except asyncio.CancelledError:
            # 超时取消期间又收到服务关闭，不能让第二次取消打断 child 落库。
            interrupted = True
    if interrupted:
        raise asyncio.CancelledError


@dataclass
class _RunTasks:
    """子任务状态"""

    semaphore: asyncio.Semaphore  # 并发信号量
    calls: int = 0  # 已调用次数
    closing: bool = False
    tasks: set[asyncio.Task] = field(default_factory=set)


class TaskRegistry:
    """子任务注册器"""

    def __init__(self, concurrency: int = 3, max_calls: int = 4):
        self.concurrency = concurrency  # 最大并发数
        self.max_calls = max_calls  # 最大调用次数
        self._runs: dict[str, _RunTasks] = {}
        self._closing = False

    async def run(self, run_id: str, factory):
        """执行子任务"""
        if self._closing:
            raise PlanError("SUBTASK_STOPPING")
        # 1. 检查当前run下的子任务状态
        state = self._runs.setdefault(run_id, _RunTasks(asyncio.Semaphore(self.concurrency)))
        if state.closing:
            raise PlanError("SUBTASK_STOPPING")
        if state.calls >= self.max_calls:
            raise PlanError("SUBTASK_LIMIT")
        state.calls += 1
        # 2. 执行子任务
        work = asyncio.create_task(factory(state.semaphore), name="subagent-" + run_id)
        state.tasks.add(work)
        try:
            return await asyncio.shield(work)
        # 3. 处理任务取消时的异常
        except asyncio.CancelledError:
            if not work.done() and not work.cancelling():
                work.cancel()
            await _drain([work])
            raise
        finally:
            state.tasks.discard(work)

    async def close_run(self, run_id: str):
        """关闭当前run下的所有子任务"""
        state = self._runs.get(run_id)
        if state is None:
            return
        state.closing = True
        for task in tuple(state.tasks):
            if not task.done() and not task.cancelling():
                task.cancel()
        try:
            await _drain(tuple(state.tasks))
        finally:
            self._runs.pop(run_id, None)

    async def shutdown(self):
        """先停止准入，再回收所有 Run 的任务句柄。"""
        self._closing = True
        await asyncio.gather(*(self.close_run(r) for r in tuple(self._runs)))
