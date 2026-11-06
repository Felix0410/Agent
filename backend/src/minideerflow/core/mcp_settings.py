"""仅接受事先批准的本机Streamable HTTP，不支持凭据或任意连接配置。"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApprovedTool(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class MCPServer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    transport: Literal["streamable_http"]
    url: str
    tools: list[ApprovedTool] = Field(min_length=1, max_length=4)

    @field_validator("url")
    @classmethod
    def local_url(cls, value):
        """不做DNS解析或URL容错，拒绝所有可改变目的地址的拼写。"""
        match = re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/mcp", value)
        if match is None or not 1 <= int(match[1]) <= 65535:
            raise ValueError("Only explicit local MCP endpoint is supported")
        return value

    @model_validator(mode="after")
    def unique_tools(self):
        if len({t.name for t in self.tools}) != len(self.tools) or any(
            len(f"mcp_{self.id}_{t.name}") > 64 for t in self.tools
        ):
            raise ValueError("Duplicate or invalid tool alias")
        return self


class MCPSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    servers: list[MCPServer] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def unique_servers(self):
        if len({s.id for s in self.servers}) != len(self.servers):
            raise ValueError("Duplicate server ID")
        return self


def _unique_object(pairs):
    """JSON重复key不能悄悄覆盖审批字段。"""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate configuration key")
        result[key] = value
    return result


def load_mcp_settings(path: Path | None) -> MCPSettings:
    """默认无连接；配置只读、有界，不接受密钥或动态扩展字段。"""
    if path is None:
        return MCPSettings()
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError("MCP configuration too large")
    return MCPSettings.model_validate(
        json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    )
