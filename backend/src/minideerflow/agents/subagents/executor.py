"""子任务执行器"""

import asyncio

from langchain.agents import create_agent
from openai import APIError, APITimeoutError

from minideerflow.agents.context import ChildContext
from minideerflow.agents.middleware import ChildToolBudgetMiddleware, UsageBudgetMiddleware
from minideerflow.agents.service import extract_final_answer, extract_run_tool_traces
from minideerflow.agents.subagents.models import TaskResult, TaskStatus
from minideerflow.runtime.budget import BudgetError
from minideerflow.tools.output_budget import ToolOutputBudgetMiddleware


async def execute_child(
    spec, description: str, child_context: ChildContext, model_factory, tools: list, task_id: str
) -> TaskResult:
    """执行子任务"""
    try:
        # 1. 创建子任务Agent
        agent = create_agent(
            model_factory(),
            tools,
            checkpointer=None,
            middleware=[
                UsageBudgetMiddleware("child"),
                ChildToolBudgetMiddleware(),
                ToolOutputBudgetMiddleware(),
            ],
            context_schema=ChildContext,
            system_prompt=spec.system_prompt,
        )
        # 2. 执行子任务agent，非流式输出
        async with asyncio.timeout(spec.timeout):
            state = await agent.ainvoke(
                {"messages": [{"role": "user", "content": description}]},
                config={"recursion_limit": spec.max_steps},
                context=child_context,
            )
        # 3. 提取子任务结果
        messages = state["messages"]
        traces = extract_run_tool_traces(messages)
        answer = extract_final_answer(messages)
        if any(not trace.ok for trace in traces):
            return TaskResult(
                task_id=task_id, status=TaskStatus.FAILED, error_code="SUBTASK_TOOL_ERROR"
            )
        sources = []
        # 4. 提取子任务来源文件ID
        for trace in traces:
            if trace.name == "read_text":
                file_id = trace.args["file_id"]
                await child_context.workspace_service.repository.get_file_for_thread(
                    child_context.thread_id, file_id
                )
                if file_id not in sources:
                    sources.append(file_id)
        # 5. 返回子任务结果
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            summary=answer[:1600],
            truncated=len(answer) > 1600,
            source_file_ids=sources,
        )
    except BudgetError:
        raise
    except asyncio.CancelledError:
        raise
    except (TimeoutError, APITimeoutError):
        return TaskResult(
            task_id=task_id, status=TaskStatus.TIMED_OUT, error_code="SUBTASK_TIMEOUT"
        )
    except APIError:
        return TaskResult(
            task_id=task_id, status=TaskStatus.FAILED, error_code="SUBTASK_MODEL_ERROR"
        )
    except Exception:  # noqa: BLE001 - 不能泄露 Provider 或 Workspace 底层异常
        return TaskResult(
            task_id=task_id, status=TaskStatus.FAILED, error_code="SUBTASK_EXECUTION_FAILED"
        )
