"""官方MCP Adapter的受控连接/审批，不复制MCP会话实现。"""

import asyncio
import hashlib
import json

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.types import CallToolResult, TextContent

from minideerflow.core.mcp_settings import load_mcp_settings
from minideerflow.tools.registry import ToolDefinition, ToolPolicyError

MCP_INPUT_LIMIT = 2048
MCP_OUTPUT_LIMIT = 8192


def tool_digest(tool) -> str:
    """计算工具的稳定JSON摘要"""
    payload = {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.args_schema,
        "annotations": tool.metadata or {},
    }
    data = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def local_http_factory(url):
    """创建本地HTTP客户端工厂，确保请求和响应目标为指定URL"""

    async def check_request(request):
        if request.url != httpx.URL(url):
            raise ToolPolicyError("MCP_UNAVAILABLE")

    async def check_response(response):
        if response.is_redirect:
            raise ToolPolicyError("MCP_UNAVAILABLE")

    def factory(headers=None, timeout=None, auth=None):
        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout or 5,
            follow_redirects=False,
            trust_env=False,
            event_hooks={"request": [check_request], "response": [check_response]},
        )

    return factory


async def text_only_interceptor(request, handler):
    """接收官方原始回执，只允许有界文本；错误不透传服务端细节。"""
    result = await handler(request)

    def fail(code):
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=f"ERROR[{code}]: MCP result rejected")],
        )

    if result.isError:
        return fail("MCP_TOOL_ERROR")
    if result.structuredContent is not None or any(
        not isinstance(c, TextContent) for c in result.content
    ):
        return fail("MCP_TOOL_ERROR")
    text = "\n".join(c.text for c in result.content)
    if len(text.encode("utf-8")) > MCP_OUTPUT_LIMIT:
        return fail("MCP_OUTPUT_TOO_LARGE")
    return CallToolResult(content=[TextContent(type="text", text=text)])


async def discover(server):
    """发现MCP Server上的所有工具"""
    connection = {
        "transport": "streamable_http",
        "url": server.url,
        "timeout": 5,
        "sse_read_timeout": 10,
        "httpx_client_factory": local_http_factory(server.url),
    }
    client = MultiServerMCPClient(
        {server.id: connection}, tool_interceptors=[text_only_interceptor], handle_tool_errors=True
    )
    async with asyncio.timeout(8):
        return await client.get_tools(server_name=server.id)


def validate_local_schema(value):
    """参数Schema也不能通过远端ref触发隐式联网。"""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("$ref", "$dynamicRef") and (
                not isinstance(item, str) or not item.startswith("#/")
            ):
                raise ToolPolicyError("MCP_NOT_APPROVED")
            validate_local_schema(item)
    elif isinstance(value, list):
        for item in value:
            validate_local_schema(item)


async def register_mcp_tools(registry, path):
    """注册MCP Server上的所有工具"""
    try:
        settings = load_mcp_settings(path)
    except Exception:
        registry.mark_unavailable("mcp_configuration", "configuration", "MCP_INVALID_CONFIG")
        return
    for server in settings.servers:
        code = "MCP_UNAVAILABLE"
        try:
            # 1. 发现所有工具
            tools = await discover(server)
            indexed = {t.name: t for t in tools}
            if len(indexed) != len(tools):
                raise ToolPolicyError("MCP_NOT_APPROVED")
            definitions = []
            # 2. 验证工具是否被批准
            for approved in server.tools:
                original = indexed.get(approved.name)
                if original is None or tool_digest(original) != approved.schema_sha256:
                    raise ToolPolicyError("MCP_NOT_APPROVED")
                validate_local_schema(original.args_schema)
                meta = original.metadata or {}
                if meta.get("readOnlyHint") is not True or meta.get("destructiveHint") is not False:
                    raise ToolPolicyError("MCP_NOT_APPROVED")
                # 3. 注册工具
                alias = f"mcp_{server.id}_{approved.name}"
                if alias in registry.names:
                    raise ToolPolicyError("TOOL_DUPLICATE")
                tool = original.model_copy(update={"name": alias})
                definitions.append(
                    ToolDefinition(alias, tool, "mcp", "read", 10, server.id, tool.description)
                )
            for definition in definitions:
                registry.register(definition)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if isinstance(exc, ToolPolicyError):
                code = exc.code
            for approved in server.tools:
                registry.mark_unavailable(f"mcp_{server.id}_{approved.name}", server.id, code)


async def _print_demo_pin():
    """显式CLI只发现本仓库demo，不自动修改用户批准配置。"""
    from minideerflow.core.mcp_settings import MCPServer

    server = MCPServer(
        id="demo",
        transport="streamable_http",
        url="http://127.0.0.1:8765/mcp",
        tools=[{"name": "lookup_fact", "schema_sha256": "0" * 64}],
    )
    for tool in await discover(server):
        print(json.dumps({"name": tool.name, "schema_sha256": tool_digest(tool)}))


if __name__ == "__main__":
    asyncio.run(_print_demo_pin())
