"""文件元数据与固定边界；客户端只看显示名/ID，不接触内部磁盘键。"""

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

CHUNK_SIZE = 65536
TEXT_UPLOAD_LIMIT = 2 * 1024 * 1024
PDF_UPLOAD_LIMIT = 10 * 1024 * 1024
THREAD_FILE_LIMIT = 50
THREAD_BYTES_LIMIT = 30 * 1024 * 1024
READ_LIMIT = 64 * 1024
WRITE_LIMIT = 128 * 1024
TEXT_MIMES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
}


class WorkspaceError(Exception):
    """只能向 HTTP/模型传递短消息，不能携带宿主机路径或底层异常。"""

    def __init__(self, code: str, safe_message: str, status: int) -> None:
        super().__init__(safe_message)
        self.code, self.safe_message, self.status = code, safe_message, status


class FileKind(str, Enum):
    UPLOAD = "UPLOAD"
    ARTIFACT = "ARTIFACT"


class FileRecord(BaseModel):
    id: str
    thread_id: str
    display_name: str
    kind: FileKind
    mime: str
    size_bytes: int
    sha256: str
    created_at: str
    storage_key: str = Field(exclude=True)
    run_id: str | None = Field(default=None, exclude=True)


class ArtifactRecord(BaseModel):
    artifact_id: str
    file_id: str
    display_name: str
    size_bytes: int
    mime: str
    run_id: str
    created_at: str
    thread_id: str = Field(exclude=True)


@dataclass(frozen=True)
class WorkspaceContext:
    """仅由 Runner 构造的服务端身份，禁止放入持久 Graph State。"""

    thread_id: str
    run_id: str
    workspace_service: Any


def validate_uuid(value: str) -> str:
    """只接受后端使用的规范 UUID，避免把身份字符串当路径片段。"""
    try:
        if str(UUID(value)) == value:
            return value
    except (ValueError, TypeError, AttributeError):
        pass
    raise WorkspaceError("INVALID_FILE_PATH", "Invalid resource identifier", 422)


def validate_filename(value: str) -> tuple[str, str]:
    """NFC 显示名可以含中文/空格，但任何路径语义、控制字符和歧义都拒绝。"""
    name = unicodedata.normalize("NFC", value)
    if (
        not 1 <= len(name) <= 120
        or name != name.strip()
        or any(c in name for c in ("/", "\\", "\x00", ":", ".."))
        or name == "."
        or any(unicodedata.category(c).startswith("C") for c in name)
    ):
        raise WorkspaceError("INVALID_FILENAME", "Invalid file name", 422)
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    mime = TEXT_MIMES.get(extension)
    if mime is None and extension != ".pdf":
        raise WorkspaceError(
            "UNSUPPORTED_FILE_TYPE", "Supported types: txt, md, csv, json, pdf", 422
        )
    return name, mime or "application/pdf"
