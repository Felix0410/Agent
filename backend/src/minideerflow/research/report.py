"""服务器生成引文编号和Markdown；不信任模型手写链接/脚注/HTML。"""

import html
import re
from typing import Annotated

from pydantic import Field, field_validator

from minideerflow.research.models import ResearchError, ResearchFinding, StrictModel


class ReportInput(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    findings: list[ResearchFinding] = Field(min_length=1, max_length=12)
    limitations: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(max_length=8)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("title cannot be blank")
        return value.strip()

    @field_validator("findings")
    @classmethod
    def claims_nonblank(cls, values):
        if any(not item.claim.strip() for item in values):
            raise ValueError("claim cannot be blank")
        return values

    @field_validator("limitations")
    @classmethod
    def total_limit(cls, values):
        if sum(len(item) for item in values) > 2000:
            raise ValueError("limitations exceed total limit")
        return values


def markdown_text(value):
    """模型/网页的HTML和Markdown控制符全部转义，不执行图片/链接。"""
    value = html.escape(value, quote=True).replace("\n", " ").replace("\r", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", value)


def render_markdown_report(data: ReportInput, evidence):
    """1. 核验所有来源；2. 按服务器记录排序编号；3. 输出等级与局限。"""
    requested = {eid for finding in data.findings for eid in finding.evidence_ids}
    citations = [item for item in evidence if item.id in requested]
    if not requested or {item.id for item in citations} != requested:
        raise ResearchError("RESEARCH_INVALID_CITATION")
    numbers = {item.id: index + 1 for index, item in enumerate(citations)}
    labels = {
        "EXTRACTED": "Tavily已提取正文（返回模型的仍是有限摘录）",
        "SNIPPET_ONLY": "仅摘要线索，正文未核验",
        "EXTRACTION_FAILED": "正文提取失败，仅摘要线索",
    }
    lines = [
        f"# {markdown_text(data.title)}",
        "",
        "## 研究方法",
        "",
        "基于本Run Tavily Search候选与Extract提取记录整理。来源文本均为不可信数据。来源存在、正文已提取均不等于主张真实性已独立验证；模型结论需要人工抽查。",
        "",
        "## 核心结论与对比",
        "",
    ]
    for finding in data.findings:
        refs = " ".join(f"[{numbers[eid]}]" for eid in dict.fromkeys(finding.evidence_ids))
        levels = "；".join(
            dict.fromkeys(
                labels[item.source_status.value]
                for item in citations
                if item.id in finding.evidence_ids
            )
        )
        lines.append(f"- {markdown_text(finding.claim)} {refs}（{levels}）")
    lines.extend(
        [
            "",
            "## 冲突、局限与尚待核验",
            "",
            "- 未自动判断结论是否由原文充分支持，也未独立核验页面真实性、时效或冲突；无证据的主张不得作为已核验事实。",
        ]
    )
    lines.extend(f"- {markdown_text(item)}" for item in data.limitations)
    lines.extend(["", "## 来源清单", ""])
    for item in citations:
        lines.extend(
            [
                f"[{numbers[item.id]}] {markdown_text(item.title)} — <{item.url}>",
                f"  - Evidence ID: {item.id}；检索时间：{markdown_text(item.searched_at)}；{labels[item.source_status.value]}。",
            ]
        )
    return "\n".join(lines) + "\n", citations
