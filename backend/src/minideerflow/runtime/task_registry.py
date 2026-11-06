"""活动 Run 的有界任务句柄，SQL 才是任务历史权威。"""

import asyncio
from dataclasses import dataclass, field

from minideerflow.runtime.plan_repository import PlanError


async def _drain(tasks):
    """重复取消也先等待所有清理完成，再向调用方传播取消。"""
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
    semaphore: asyncio.Semaphore
    calls: int = 0
    closing: bool = False
    tasks: set[asyncio.Task] = field(default_factory=set)


class TaskRegistry:
    """每父 Run 最多三个执行、四次尝试；不创建离线后台任务。"""

    def __init__(self, concurrency: int = 3, max_calls: int = 4):
        self.concurrency = concurrency
        self.max_calls = max_calls
        self._runs: dict[str, _RunTasks] = {}
        self._closing = False

    async def run(self, run_id: str, factory):
        """计数预留无 await，单事件循环内不会超额；句柄保留到回收。"""
        if self._closing:
            raise PlanError("SUBTASK_STOPPING")
        state = self._runs.setdefault(run_id, _RunTasks(asyncio.Semaphore(self.concurrency)))
        if state.closing:
            raise PlanError("SUBTASK_STOPPING")
        if state.calls >= self.max_calls:
            raise PlanError("SUBTASK_LIMIT")
        # 1. 拒绝第五次前不启动模型；失败/取消也消耗本轮委派次数。
        state.calls += 1
        work = asyncio.create_task(factory(state.semaphore), name="subagent-" + run_id)
        state.tasks.add(work)
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            # 2. 父取消必须等 child 的 SQL 清理结束，再继续父终态处理。
            if not work.done() and not work.cancelling():
                work.cancel()
            await _drain([work])
            raise
        finally:
            state.tasks.discard(work)

    async def close_run(self, run_id: str):
        """停止新增并回收全部 child；调用方保证父图已停止提交工具。"""
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
