"""主 Agent 装配入口；当前阶段只包含最小模型与工具配置。"""

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver


def build_lead_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    context_schema: type | None = None,
    state_schema: type | None = None,
    prompt_suffix: str = "",
):
    """使用 LangChain 原生 Agent 组装模型、工具与系统提示词。"""
    # Agent 循环由 create_agent 执行，不在项目中另写固定流程图或 while 循环。
    return create_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        context_schema=context_schema,
        state_schema=state_schema,
        system_prompt=(
            "Answer ordinary questions directly. For precise arithmetic, call calculate. "
            "Never claim a tool was called unless it actually was. Explain tool errors honestly."
        )
        + prompt_suffix,
    )
