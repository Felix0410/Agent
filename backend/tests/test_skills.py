"""临时Skill目录，安全解析与真实ToolRuntime按需读取。"""

import asyncio
import json
import os
from dataclasses import replace

import pytest
from langchain_core.messages import AIMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.skills.loader import SkillCatalog
from minideerflow.skills.models import SkillError
from minideerflow.tools.executor import ToolGuardMiddleware
from minideerflow.tools.registry import ToolPolicy, ToolRegistry, register_builtin_tools
from minideerflow.tools.skill_tools import list_skills, read_skill, register_skill_tools


def registry():
    result = ToolRegistry()
    register_builtin_tools(result)
    register_skill_tools(result)
    return result.freeze()


def write_skill(root, name="file-analysis", metadata=None, body="PRIVATE_WORKFLOW_BODY"):
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = (
        metadata
        or "name: file-analysis\ndescription: safe workflow\nallowed_tools: [list_files, read_text]"
    )
    path.write_text("---\n" + meta + "\n---\n" + body)
    return path


def policy(reg):
    return ToolPolicy("run", "thread", reg.names, frozenset({"read", "write", "orchestrate"}))


def test_metadata_only_permissions_and_no_escalation(tmp_path):
    write_skill(tmp_path)
    reg = registry()
    catalog = SkillCatalog(reg, tmp_path)
    p = policy(reg)
    assert catalog.list_skills(p)[0]["name"] == "file-analysis"
    assert "PRIVATE_WORKFLOW_BODY" not in str(catalog.list_skills(p))
    assert catalog.load_skill("file-analysis", p) == "PRIVATE_WORKFLOW_BODY"
    denied = replace(p, allowed_names=frozenset({"list_skills", "read_skill"}))
    assert catalog.list_skills(denied) == []
    with pytest.raises(SkillError):
        catalog.load_skill("file-analysis", denied)
    for name in ["../file-analysis", "/etc/passwd", "file-analysis-other", "unknown"]:
        with pytest.raises(SkillError):
            catalog.load_skill(name, p)
    assert p == policy(reg)


@pytest.mark.parametrize(
    "mode",
    [
        "unknown_key",
        "duplicate_key",
        "anchor",
        "alias",
        "encoding",
        "file_large",
        "body_large",
        "unknown_tool",
        "name",
        "description",
        "duplicate_name",
        "symlink",
        "directory_link",
        "hardlink",
    ],
)
def test_invalid_skills_fail_closed(tmp_path, mode):
    root = tmp_path / "skills"
    path = write_skill(root)
    if mode == "unknown_key":
        path.write_text(
            path.read_text().replace("name: file-analysis", "name: file-analysis\nexecute: shell")
        )
    if mode == "duplicate_key":
        path.write_text(
            path.read_text().replace("name: file-analysis", "name: file-analysis\nname: other")
        )
    if mode == "anchor":
        path.write_text(
            path.read_text().replace("description: safe workflow", "description: &a safe workflow")
        )
    if mode == "alias":
        path.write_text(path.read_text().replace("description: safe workflow", "description: *a"))
    if mode == "encoding":
        path.write_bytes(b"\xff\xfe")
    if mode == "file_large":
        path.write_bytes(b"x" * 16385)
    if mode == "body_large":
        write_skill(root, body="x" * 12289)
    if mode == "unknown_tool":
        path.write_text(path.read_text().replace("list_files", "shell"))
    if mode == "name":
        path.write_text(path.read_text().replace("name: file-analysis", "name: ../escape"))
    if mode == "description":
        path.write_text(path.read_text().replace("safe workflow", "x" * 161))
    if mode == "duplicate_name":
        write_skill(root, "second")
    if mode == "symlink":
        path.unlink()
        path.symlink_to(tmp_path / "secret")
    if mode == "directory_link":
        path.unlink()
        path.parent.rmdir()
        path.parent.symlink_to(tmp_path, target_is_directory=True)
    if mode == "hardlink":
        os.link(path, tmp_path / "link")
    catalog = SkillCatalog(registry(), root)
    assert catalog.list_skills(policy(registry())) == []
    assert catalog.catalog() and all(s["availability"] != "available" for s in catalog.catalog())


@pytest.mark.parametrize(
    "mode", ["content", "inode", "directory", "root", "symlink", "root_symlink"]
)
def test_recheck_before_read(tmp_path, mode):
    root = tmp_path / "skills"
    path = write_skill(root)
    reg = registry()
    catalog = SkillCatalog(reg, root)
    if mode == "content":
        path.write_text(path.read_text() + "changed")
    if mode == "inode":
        data = path.read_bytes()
        path.unlink()
        path.write_bytes(data)
    if mode == "directory":
        path.parent.rename(root / "old")
        write_skill(root)
    if mode == "root":
        root.rename(tmp_path / "old")
        write_skill(root)
    if mode == "symlink":
        path.unlink()
        path.symlink_to(tmp_path / "secret")
    if mode == "root_symlink":
        root.rename(tmp_path / "old")
        root.symlink_to(tmp_path / "old", target_is_directory=True)
    with pytest.raises(SkillError):
        catalog.load_skill("file-analysis", policy(reg))
    assert catalog.list_skills(policy(reg)) == []


def test_limit_and_other_valid_skill_survives(tmp_path):
    root = tmp_path / "skills"
    write_skill(root)
    write_skill(root, "broken", metadata="name: broken\ndescription: bad\nunknown: field")
    reg = registry()
    catalog = SkillCatalog(reg, root)
    assert len(catalog.list_skills(policy(reg))) == 1
    for n in range(9):
        write_skill(root, f"extra-{n}")
    catalog = SkillCatalog(reg, root)
    assert (
        catalog.list_skills(policy(reg)) == []
        and catalog.catalog()[0]["availability"] == "SKILL_LIMIT"
    )


def test_real_tools_only_requested_body_and_frozen_permissions(tmp_path):
    async def scenario():
        skillroot = tmp_path / "skills"
        write_skill(skillroot, body="Use read_text; this text mentions shell but cannot grant it.")
        reg = registry()
        catalog = SkillCatalog(reg, skillroot)
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            p = replace(policy(reg), run_id=run.id, thread_id=thread.id)
            ctx = AgentRunContext(thread.id, run.id, ws, None, tool_policy=p, skill_service=catalog)
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="", tool_calls=[{"name": "list_skills", "args": {}, "id": "list"}]
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "read_skill", "args": {"name": "file-analysis"}, "id": "read"}
                        ],
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "shell",
                                "args": {"command": "not executed"},
                                "id": "forbidden",
                            }
                        ],
                    ),
                    AIMessage(content="done"),
                ]
            )
            graph = build_lead_agent(
                model,
                reg.list_allowed(p),
                context_schema=AgentRunContext,
                middleware=[ToolGuardMiddleware(reg)],
            )
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": "workflow"}]}, context=ctx
            )
            from minideerflow.agents.service import extract_run_tool_traces

            traces = extract_run_tool_traces(result["messages"])
            assert (
                all(t.ok for t in traces[:2])
                and not traces[2].ok
                and "Use read_text" not in traces[0].result
            )
            assert "Use read_text" in json.loads(traces[1].result)["content"]
            assert "Use read_text" not in str(model.seen[0])
            assert p.allowed_names == reg.names and "shell" not in reg.names

    asyncio.run(scenario())
    assert list_skills.tool_call_schema.model_json_schema()["properties"] == {}
    assert set(read_skill.tool_call_schema.model_json_schema()["properties"]) == {"name"}


def test_write_requirement_does_not_grant_permission(tmp_path):
    reg = registry()
    write_skill(
        tmp_path,
        metadata="name: file-analysis\ndescription: write requirement\nallowed_tools: [write_text]",
    )
    catalog = SkillCatalog(reg, tmp_path)
    read_only = replace(policy(reg), allowed_permissions=frozenset({"read"}))
    assert catalog.list_skills(read_only) == []
    with pytest.raises(SkillError):
        catalog.load_skill("file-analysis", read_only)
    assert read_only.allowed_permissions == {"read"}
