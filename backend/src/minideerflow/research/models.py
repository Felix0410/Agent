"""研究对象只承载真实来源，提取正文不等于事实核真。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ResearchError(Exception):
    """边界只传播稳定错误码，不泄露提供方正文或凭据。"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class SourceStatus(StrEnum):
    SNIPPET_ONLY = "SNIPPET_ONLY"
    EXTRACTED = "EXTRACTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ResearchRequest(StrictModel):
    topic: str = Field(min_length=1, max_length=400)
    scope: str | None = Field(default=None, max_length=500)
    report_format: str = Field(default="markdown", pattern="^markdown$")


class SearchHit(StrictModel):
    title: str = Field(max_length=200)
    url: str = Field(min_length=1, max_length=2048)
    snippet: str = Field(max_length=500)
    searched_at: str


class EvidenceRecord(SearchHit):
    id: str
    source_status: SourceStatus
    excerpt: str = Field(max_length=1500)
    extracted_at: str | None = None
    content_sha256: str | None = None


class ResearchFinding(StrictModel):
    claim: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class ResearchReport(StrictModel):
    artifact_id: str
    title: str
    citations: list[EvidenceRecord]
    limitations: list[str]
