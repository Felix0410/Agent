"""工具输出外置：原ID/错误/Command保持，Child永远不借此写文件。"""

import json
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from minideerflow.agents.context import AgentRunContext


class ToolOutputBudgetMiddleware(AgentMiddleware):
    """只转存实际成功的长文本，不执行结果中的任何指令。"""

    async def awrap_tool_call(self, request, handler):
        result = await handler(request)
        if (
            not isinstance(result, ToolMessage)
            or result.status == "error"
            or not isinstance(result.content, str)
            or result.content.startswith("ERROR[")
        ):
            return result
        raw = result.content.encode("utf-8")
        if len(raw) <= 12288:
            return result
        context = request.runtime.context
        try:
            # 1. read_text已有真实来源，不重复占用文件额度；归属再次复核。
            if request.tool_call["name"] == "read_text":
                file_id = request.tool_call["args"]["file_id"]
                record = await context.workspace_service.repository.get_file_for_thread(
                    context.thread_id, file_id
                )
                refs = {"file_id": record.id, "sha256": record.sha256}
            else:
                # 2. 只有获准写入的父Context可以外置其它结果，子代理不能提权。
                policy = getattr(context, "tool_policy", None)
                if (
                    not isinstance(context, AgentRunContext)
                    or policy is None
                    or "write_text" not in policy.allowed_names
                    or "write" not in policy.allowed_permissions
                ):
                    raise ValueError("Not allowed")
                artifact = await context.workspace_service.write_text(
                    context.thread_id,
                    context.run_id,
                    f"tool-output-{uuid4().hex}.md",
                    result.content,
                )
                refs = {"file_id": artifact.file_id, "artifact_id": artifact.artifact_id}
            # 3. 只让短预览进入Graph/ToolTrace；不宣称预览等于全文精读。
            payload = {
                **refs,
                "original_bytes": len(raw),
                "preview": raw[:1024].decode("utf-8", errors="ignore"),
                "notice": "Preview only. Original content remains registered. No chunked-read tool is available; ask for a smaller source to analyze the full content.",
            }
            tracker = getattr(context, "budget_tracker", None)
            if tracker:
                tracker.externalized += 1
                await tracker.flush()
                if tracker.event_sink:
                    await tracker.event_sink(
                        "tool_output_externalized",
                        {"run_id": context.run_id, "file_id": refs["file_id"], "bytes": len(raw)},
                    )
            return result.model_copy(
                update={"content": json.dumps(payload, ensure_ascii=False), "artifact": None}
            )
        except Exception:  # noqa: BLE001 - 存储失败不能泄露原长正文/路径或伪造已保存
            return result.model_copy(
                update={
                    "content": "ERROR[TOOL_OUTPUT_TOO_LARGE]: Original result could not be referenced safely",
                    "status": "error",
                    "artifact": None,
                }
            )
