"""可信本机MCP示例：仅固定字典，无文件、网络检索、Shell或凭据访问。"""

import argparse

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

FACTS = {
    "langgraph": "LangGraph provides stateful graphs and checkpointed agent execution.",
    "mcp": "MCP is a protocol for connecting applications to external tools and data.",
    "skills": "Skills are workflow instructions; they do not grant tool permissions.",
}


def create_server(port=8765):
    """只监听回环；测试可以使用临时端口，默认仍为8765。"""
    server = FastMCP(
        "Mini DeerFlow read-only demo",
        host="127.0.0.1",
        port=port,
        log_level="WARNING",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(
        structured_output=False,
        annotations=ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
        ),
    )
    def lookup_fact(topic: str) -> str:
        """Look up a fixed local fact about langgraph, mcp, or skills. No internet or file access."""
        if topic not in FACTS:
            raise ValueError("Unknown demo topic")
        return FACTS[topic]

    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    create_server(args.port).run(transport="streamable-http")
