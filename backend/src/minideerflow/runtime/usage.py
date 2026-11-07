"""业务用量持久化：最终回复去重计数，真实Provider与估算分列。"""

import json

from pydantic import BaseModel, Field

from minideerflow.runtime.repository import _run


class UsageCall(BaseModel):
    invocation_id: str
    kind: str
    source: str
    usage_source: str = "unknown"
    estimated_input_tokens: int = 0
    provider_input_tokens: int | None = None
    provider_output_tokens: int | None = None
    elapsed_ms: int = 0
    status: str = "PENDING"


class RunUsage(BaseModel):
    recorded: bool = False
    run_id: str
    model_calls: int = 0
    tool_calls: int = 0
    provider_input_tokens: int | None = None
    provider_output_tokens: int | None = None
    usage_unknown_calls: int = 0
    estimated_input_tokens: int = 0
    elapsed_ms: int = 0
    compaction_count: int = 0
    output_externalized_count: int = 0
    budget: dict = Field(default_factory=dict)


class UsageRepository:
    """同Run调用ID唯一；缺失usage不当作零token或价格。"""

    def __init__(self, database):
        self.database = database

    async def start(self, run_id, budget):
        async with self.database.transaction() as conn:
            await _run(conn, run_id)
            await conn.execute(
                "INSERT OR IGNORE INTO run_usage(run_id,budget_json) VALUES(?,?)",
                (run_id, json.dumps(budget)),
            )

    async def begin(self, run_id, call: UsageCall):
        """先提交调用预留，实际请求失败也保留真实尝试次数。"""
        async with self.database.transaction() as conn:
            await _run(conn, run_id)
            cur = await conn.execute(
                "INSERT OR IGNORE INTO usage_calls(invocation_id,run_id,kind,source,estimated_input_tokens,status) VALUES(?,?,?,?,?,?)",
                (
                    call.invocation_id,
                    run_id,
                    call.kind,
                    call.source,
                    call.estimated_input_tokens,
                    "PENDING",
                ),
            )
            if cur.rowcount:
                column = "model_calls" if call.kind == "model" else "tool_calls"
                await conn.execute(
                    f"UPDATE run_usage SET {column}={column}+1,estimated_input_tokens=estimated_input_tokens+? WHERE run_id=?",
                    (call.estimated_input_tokens, run_id),
                )

    async def finish(self, run_id, call: UsageCall):
        """仅第一次最终回执入账，不在stream chunk再次计费。"""
        async with self.database.transaction() as conn:
            cur = await conn.execute(
                "UPDATE usage_calls SET status=?,elapsed_ms=?,provider_input_tokens=?,provider_output_tokens=?,usage_source=? WHERE invocation_id=? AND run_id=? AND status='PENDING'",
                (
                    call.status,
                    call.elapsed_ms,
                    call.provider_input_tokens,
                    call.provider_output_tokens,
                    call.usage_source,
                    call.invocation_id,
                    run_id,
                ),
            )
            if cur.rowcount and call.kind == "model":
                if call.provider_input_tokens is None:
                    await conn.execute(
                        "UPDATE run_usage SET usage_unknown_calls=usage_unknown_calls+1 WHERE run_id=?",
                        (run_id,),
                    )
                else:
                    await conn.execute(
                        "UPDATE run_usage SET provider_input_tokens=COALESCE(provider_input_tokens,0)+?,provider_output_tokens=COALESCE(provider_output_tokens,0)+? WHERE run_id=?",
                        (call.provider_input_tokens, call.provider_output_tokens, run_id),
                    )

    async def metrics(self, run_id, elapsed_ms, compactions, externalized):
        async with self.database.transaction() as conn:
            await conn.execute(
                "UPDATE run_usage SET elapsed_ms=MAX(elapsed_ms,?),compaction_count=?,output_externalized_count=? WHERE run_id=?",
                (elapsed_ms, compactions, externalized, run_id),
            )

    async def get(self, run_id):
        """读取同Run权威累计，未开始时Provider数字仍为NULL。"""
        async with self.database.transaction() as conn:
            await _run(conn, run_id)
            async with conn.execute("SELECT * FROM run_usage WHERE run_id=?", (run_id,)) as cur:
                row = await cur.fetchone()
            if row is None:
                return RunUsage(run_id=run_id)
            data = dict(row)
            data["recorded"] = True
            data["budget"] = json.loads(data.pop("budget_json"))
            return RunUsage(**data)
