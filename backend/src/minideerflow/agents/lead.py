from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool


def build_lead_agent(model: BaseChatModel, tools: list[BaseTool]):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=(
            "Answer ordinary questions directly. For precise arithmetic, call calculate. "
            "Never claim a tool was called unless it actually was. Explain tool errors honestly."
        ),
    )
