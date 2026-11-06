"""Skill元信息是前置要求，不是授权声明。"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")
    description: str = Field(min_length=1, max_length=160)
    allowed_tools: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("allowed_tools")
    @classmethod
    def exact_tool_names(cls, value):
        """工具前置条件用精确名字，不解释通配符或文本权限。"""
        import re

        if len(set(value)) != len(value) or any(
            not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", n) for n in value
        ):
            raise ValueError("Invalid required tool names")
        return value


class SkillError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code
