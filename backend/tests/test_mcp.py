"""真实本机SDK进程与官方Adapter；无外网、用户文件或模型额度。"""

import asyncio
import json
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.core.mcp_settings import MCPServer
from minideerflow.runtime.plan_repository import PlanRepository
from minideerflow.runtime.plan_service import PlanService
from minideerflow.tools.executor import ToolGuardMiddleware
from minideerflow.tools.mcp_adapter import (
    discover,
    local_http_factory,
    register_mcp_tools,
    tool_digest,
)
from minideerflow.tools.registry import (
    ToolPolicy,
    ToolPolicyError,
    ToolRegistry,
    register_builtin_tools,
)

BACKEND = Path(__file__).resolve().parents[1]


@contextmanager
def mcp_server(script=None, port=None):
    """只管理本测试自己的子进程；临时端口不干扰用户8765服务。"""
    if port is None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
    command = (
        [sys.executable, "examples/mcp_readonly_server.py", "--port", str(port)]
        if script is None
        else [sys.executable, "-c", script, str(port)]
    )
    process = subprocess.Popen(
        command, cwd=BACKEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Test MCP process exited")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.02)
        else:
            raise RuntimeError("Test MCP startup timeout")
        yield process, port
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


async def approved_config(tmp_path, port):
    server = MCPServer(
        id="demo",
        transport="streamable_http",
        url=f"http://127.0.0.1:{port}/mcp",
        tools=[{"name": "lookup_fact", "schema_sha256": "0" * 64}],
    )
    tools = await discover(server)
    data = server.model_dump()
    data["tools"][0]["schema_sha256"] = tool_digest(tools[0])
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"servers": [data]}))
    return path, tools


async def invoke(ws, repo, registry, expression="langgraph"):
    thread = await repo.create_thread()
    run = await active_run(repo, thread)
    policy = ToolPolicy(
        run.id, thread.id, registry.names, frozenset({"read", "write", "orchestrate"})
    )
    ctx = AgentRunContext(
        thread.id, run.id, ws, PlanService(PlanRepository(repo.database)), tool_policy=policy
    )
    args = expression if isinstance(expression, dict) else {"topic": expression}
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"id": "mcp-call", "name": "mcp_demo_lookup_fact", "args": args}],
            ),
            AIMessage(content="done"),
        ]
    )
    graph = build_lead_agent(
        model,
        registry.list_allowed(policy),
        context_schema=AgentRunContext,
        middleware=[ToolGuardMiddleware(registry)],
    )
    state = await graph.ainvoke({"messages": [{"role": "user", "content": "fact"}]}, context=ctx)
    from minideerflow.agents.service import extract_run_tool_traces

    return extract_run_tool_traces(state["messages"])[0]


def test_real_sdk_pin_alias_error_and_offline(tmp_path):
    with mcp_server() as (process, port):

        async def scenario():
            path, tools = await approved_config(tmp_path, port)
            assert (
                tool_digest(tools[0])
                == "bb4d0dd3eb360c06d10f7c9b59a01324cd9435f32722da5d12fc5f0e5167e2c3"
            )
            registry = ToolRegistry()
            register_builtin_tools(registry)
            await register_mcp_tools(registry, path)
            registry.freeze()
            assert "mcp_demo_lookup_fact" in registry.names
            async with workspace(tmp_path) as (ws, repo, _):
                trace = await invoke(ws, repo, registry)
                assert trace.ok and "LangGraph" in trace.result
                error = await invoke(ws, repo, registry, "unknown")
                assert not error.ok and "MCP_TOOL_ERROR" in error.result
                assert not (
                    await invoke(ws, repo, registry, {"topic": "langgraph", "thread_id": "forged"})
                ).ok
                assert not (await invoke(ws, repo, registry, {"topic": "x" * 2049})).ok
                process.terminate()
                process.wait(timeout=5)
                offline = await invoke(ws, repo, registry)
                assert not offline.ok and "MCP_UNAVAILABLE" in offline.result
                assert (
                    "calculate" in registry.names and "mcp_demo_lookup_fact" not in registry.names
                )
                assert (
                    next(t for t in registry.list_catalog() if t["source"] == "mcp")["availability"]
                    == "MCP_UNAVAILABLE"
                )
                with pytest.raises(ToolPolicyError):
                    registry.get("mcp_demo_lookup_fact")

        asyncio.run(scenario())


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8765/mcp",
        "http://127.1:8765/mcp",
        "http://2130706433:8765/mcp",
        "http://127.0.0.1:8765/mcp?x=1",
        "http://user@127.0.0.1:8765/mcp",
        "http://127.0.0.1:8765/mcp#x",
        "http://[::1]:8765/mcp",
        "http://127.0.0.1:0/mcp",
        "http://127.0.0.1:65536/mcp",
        "https://127.0.0.1:8765/mcp",
        "http://127.0.0.1:8765/mcp/",
    ],
)
def test_url_fail_closed(url):
    with pytest.raises(ValidationError):
        MCPServer(
            id="demo",
            transport="streamable_http",
            url=url,
            tools=[{"name": "lookup_fact", "schema_sha256": "0" * 64}],
        )


@pytest.mark.parametrize(
    "mode", ["pin", "name", "transport", "duplicate", "too_many", "missing_pin", "credentials"]
)
def test_configuration_and_discovery_rejects(tmp_path, mode):
    with mcp_server() as (_, port):

        async def scenario():
            path, _ = await approved_config(tmp_path, port)
            data = json.loads(path.read_text())
            server = data["servers"][0]
            if mode == "pin":
                server["tools"][0]["schema_sha256"] = "0" * 64
            if mode == "name":
                server["tools"][0]["name"] = "unapproved"
            if mode == "transport":
                server["transport"] = "stdio"
            if mode == "duplicate":
                server["tools"] *= 2
            if mode == "too_many":
                data["servers"] *= 3
            if mode == "missing_pin":
                server["tools"][0].pop("schema_sha256")
            if mode == "credentials":
                server["token"] = "not-allowed"
            path.write_text(json.dumps(data))
            registry = ToolRegistry()
            register_builtin_tools(registry)
            await register_mcp_tools(registry, path)
            assert registry.names == {
                "calculate",
                "list_files",
                "read_text",
                "write_text",
                "write_todos",
                "task",
            }
            assert any(t["availability"] != "available" for t in registry.list_catalog())

        asyncio.run(scenario())


def test_redirect_and_request_target_are_never_followed():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    hits = []

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/forbidden")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    async def scenario():
        url = f"http://127.0.0.1:{server.server_port}/mcp"
        async with local_http_factory(url)() as client:
            with pytest.raises(ToolPolicyError):
                await client.get(url)
            with pytest.raises(ToolPolicyError):
                await client.get("http://127.0.0.1:1/forbidden")

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert hits == ["/mcp"]


HOSTILE = """
import sys
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations,CallToolResult,TextContent,ImageContent
server=FastMCP('test',host='127.0.0.1',port=int(sys.argv[1]),stateless_http=True,json_response=True,log_level='WARNING')
@server.tool(annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False))
def lookup_fact(topic:str)->CallToolResult:
    if topic=='binary':return CallToolResult(content=[ImageContent(type='image',data='AAAA',mimeType='image/png')])
    if topic=='structured':return CallToolResult(content=[TextContent(type='text',text='ok')],structuredContent={'hidden':'payload'})
    if topic=='error':return CallToolResult(isError=True,content=[TextContent(type='text',text='SENSITIVE_TEST_DETAIL')])
    return CallToolResult(content=[TextContent(type='text',text='x'*8193)])
server.run(transport='streamable-http')
"""


@pytest.mark.parametrize("topic", ["binary", "structured", "error", "large"])
def test_real_mcp_hostile_output(tmp_path, topic):
    with mcp_server(HOSTILE) as (_, port):

        async def scenario():
            path, _ = await approved_config(tmp_path, port)
            registry = ToolRegistry()
            await register_mcp_tools(registry, path)
            registry.freeze()
            async with workspace(tmp_path) as (ws, repo, _):
                result = await invoke(ws, repo, registry, topic)
                assert not result.ok and "ERROR[MCP_" in result.result
                assert "SENSITIVE_TEST_DETAIL" not in result.result and len(result.result) < 256

        asyncio.run(scenario())


def test_remote_schema_refs_rejected():
    from minideerflow.tools.mcp_adapter import validate_local_schema

    validate_local_schema({"$ref": "#/$defs/topic"})
    for ref in ["http://127.0.0.1:8000/secret", "https://example.com/schema", "file:///etc/passwd"]:
        with pytest.raises(ToolPolicyError):
            validate_local_schema({"properties": {"topic": {"$ref": ref}}})


@pytest.mark.parametrize("field", ["description", "schema", "annotations", "write"])
def test_actual_metadata_changes_cannot_reuse_pin(tmp_path, monkeypatch, field):
    from minideerflow.tools import mcp_adapter

    with mcp_server() as (_, port):

        async def scenario():
            path, tools = await approved_config(tmp_path, port)
            original = tools[0]
            if field == "description":
                changed = original.model_copy(update={"description": "changed instructions"})
            elif field == "schema":
                changed = original.model_copy(
                    update={"args_schema": {**original.args_schema, "required": []}}
                )
            else:
                changed = original.model_copy(
                    update={
                        "metadata": {
                            **original.metadata,
                            "readOnlyHint": False,
                            "destructiveHint": True,
                        }
                    }
                )
            if field == "write":
                data = json.loads(path.read_text())
                data["servers"][0]["tools"][0]["schema_sha256"] = tool_digest(changed)
                path.write_text(json.dumps(data))

            async def altered(server):
                return [changed]

            monkeypatch.setattr(mcp_adapter, "discover", altered)
            reg = ToolRegistry()
            register_builtin_tools(reg)
            await register_mcp_tools(reg, path)
            assert "mcp_demo_lookup_fact" not in reg.names
            assert "calculate" in reg.names
            assert (
                next(t for t in reg.list_catalog() if t["source"] == "mcp")["availability"]
                == "MCP_NOT_APPROVED"
            )

        asyncio.run(scenario())


def test_duplicate_mcp_alias_never_overwrites_existing(tmp_path):
    from minideerflow.tools.registry import ToolDefinition

    with mcp_server() as (_, port):

        async def scenario():
            path, tools = await approved_config(tmp_path, port)
            existing = tools[0].model_copy(update={"name": "mcp_demo_lookup_fact"})
            reg = ToolRegistry()
            reg.register(
                ToolDefinition(existing.name, existing, "builtin", "read", 5, "builtin", "existing")
            )
            await register_mcp_tools(reg, path)
            assert reg.get(existing.name).tool is existing
            catalog = reg.list_catalog()
            assert len({t["name"] for t in catalog}) == len(catalog)
            assert any(t["availability"] == "TOOL_DUPLICATE" for t in catalog)

        asyncio.run(scenario())


def test_server_restart_requires_new_registry_discovery(tmp_path):
    with mcp_server() as (process, port):

        async def scenario():
            path, _ = await approved_config(tmp_path, port)
            process.terminate()
            process.wait(timeout=5)
            offline = ToolRegistry()
            register_builtin_tools(offline)
            await register_mcp_tools(offline, path)
            offline.freeze()
            assert "mcp_demo_lookup_fact" not in offline.names
            with mcp_server(port=port):
                recovered = ToolRegistry()
                register_builtin_tools(recovered)
                await register_mcp_tools(recovered, path)
                recovered.freeze()
                assert "mcp_demo_lookup_fact" in recovered.names
                # 已停用的旧快照不会被后台自动重新授权。
                assert "mcp_demo_lookup_fact" not in offline.names

        asyncio.run(scenario())
