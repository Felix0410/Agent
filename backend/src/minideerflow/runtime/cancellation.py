"""只管理单Run任务句柄；用户取消不能杀死worker或其它Run。"""

import asyncio


class RunCancellationRegistry:
    """SQL是取消请求权威，句柄只是进程内通知渠道。"""

    def __init__(self, repository):
        self.repository = repository
        self.active = {}

    async def register(self, run_id, task, tracker):
        """先登记再复核SQL，覆盖取消请求先于句柄到达的窗口。"""
        self.active[run_id] = (task, tracker)

        async def requested():
            return (await self.repository.get_run(run_id)).cancel_requested_at is not None

        tracker.cancel_check = requested
        if await requested():
            tracker.cancelled.set()
            raise asyncio.CancelledError

    def signal(self, run_id):
        """数据库已提交后才发信号，重复请求不会重复打断清理。"""
        entry = self.active.get(run_id)
        if entry:
            task, tracker = entry
            tracker.cancelled.set()
            if not task.done() and not task.cancelling():
                task.cancel()

    def unregister(self, run_id):
        self.active.pop(run_id, None)
