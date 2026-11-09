"""固定根目录安全发现与按名读取；不安装、不执行或自动注入Skill。"""

import hashlib
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, ScalarNode
from yaml.tokens import AliasToken, AnchorToken

from minideerflow.skills.models import SkillError, SkillMeta
from minideerflow.tools.registry import ToolPolicy

MAX_FILE = 16 * 1024
MAX_BODY = 12 * 1024
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "skills/public"


def _identity(value):
    return value.st_dev, value.st_ino


@contextmanager
def _root_fd(path):
    """逐级无跟随打开所有父路径，避免resolve掩盖symlink。"""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise SkillError("SKILL_UNSAFE_PATH")
    absolute = Path(os.path.abspath(path))
    fd = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in absolute.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


@dataclass(frozen=True)
class _Entry:
    directory: str
    root_identity: tuple
    directory_identity: tuple
    file_identity: tuple
    digest: str
    meta: SkillMeta


class SkillCatalog:
    """Skill目录"""

    def __init__(self, registry, root: Path = DEFAULT_ROOT):
        self.registry = registry
        self.root = root
        self._entries: dict[str, _Entry] = {}
        self._warnings: list[dict] = []
        self._discover()

    def _warn(self, name, code):
        """只显示合法逻辑名，绝不暴露本地路径或解析异常正文。"""
        name = name if re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name) else "invalid-skill"
        self._warnings = [item for item in self._warnings if item["name"] != name]
        self._warnings.append(
            {
                "name": name,
                "description": "本地Skill不可用，请检查并重启后端",
                "required_tools": [],
                "availability": code,
            }
        )

    def _read(self, directory, expected=None):
        """有限读取普通单链接文件；每个路径段与读取前后身份均复核。"""
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", directory):
            raise SkillError("SKILL_INVALID")
        # 1. root/子目录锚定fd，拒绝symlink与路径相似前缀绕过。
        with _root_fd(self.root) as rootfd:
            root_id = _identity(os.fstat(rootfd))
            dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=rootfd)
            try:
                dir_id = _identity(os.fstat(dirfd))
                fd = os.open("SKILL.md", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dirfd)
                try:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        raise SkillError("SKILL_UNSAFE_PATH")
                    if before.st_size > MAX_FILE:
                        raise SkillError("SKILL_TOO_LARGE")
                    if expected and (
                        root_id != expected.root_identity
                        or dir_id != expected.directory_identity
                        or _identity(before) != expected.file_identity
                    ):
                        raise SkillError("SKILL_CHANGED")
                    data = bytearray()
                    while len(data) <= MAX_FILE:
                        chunk = os.read(fd, min(4096, MAX_FILE + 1 - len(data)))
                        if not chunk:
                            break
                        data.extend(chunk)
                    after = os.fstat(fd)
                    if len(data) > MAX_FILE:
                        raise SkillError("SKILL_TOO_LARGE")
                    if (_identity(before), before.st_size, before.st_mtime_ns) != (
                        _identity(after),
                        after.st_size,
                        after.st_mtime_ns,
                    ):
                        raise SkillError("SKILL_CHANGED")
                    file_id = _identity(after)
                finally:
                    os.close(fd)
                if (
                    _identity(os.stat(directory, dir_fd=rootfd, follow_symlinks=False)) != dir_id
                    or _identity(os.stat("SKILL.md", dir_fd=dirfd, follow_symlinks=False))
                    != file_id
                ):
                    raise SkillError("SKILL_CHANGED")
            finally:
                os.close(dirfd)
        # 2. 读后重新走可见根路径，旧fd不能掩盖根目录被替换。
        with _root_fd(self.root) as fresh:
            if _identity(os.fstat(fresh)) != root_id:
                raise SkillError("SKILL_CHANGED")
        raw = bytes(data)
        digest = hashlib.sha256(raw).hexdigest()
        if expected and digest != expected.digest:
            raise SkillError("SKILL_CHANGED")
        return raw, (root_id, dir_id, file_id, digest)

    @staticmethod
    def _parse(data):
        """先限制YAML词法，再safe_load和字段白名单，禁止别名/重复key。"""
        text = data.decode("utf-8", errors="strict").replace("\r\n", "\n")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise SkillError("SKILL_INVALID")
        front, body = text[4:].split("\n---\n", 1)
        if not body.strip() or len(body.encode("utf-8")) > MAX_BODY:
            raise SkillError("SKILL_TOO_LARGE")
        tokens = list(yaml.scan(front))
        if len(tokens) > 256 or any(isinstance(t, (AliasToken, AnchorToken)) for t in tokens):
            raise SkillError("SKILL_INVALID")
        node = yaml.compose(front, Loader=yaml.SafeLoader)
        if not isinstance(node, MappingNode) or any(
            not isinstance(k, ScalarNode) for k, _ in node.value
        ):
            raise SkillError("SKILL_INVALID")
        keys = [k.value for k, _ in node.value]
        if len(keys) != len(set(keys)):
            raise SkillError("SKILL_INVALID")
        meta = SkillMeta.model_validate(yaml.safe_load(front))
        return meta, body

    def _discover(self):
        """单Skill失败明确报告，其它合法条目继续；重复名双方均不可用。"""
        # 1. 目录发现有总数上限；根不安全时不加载任何正文。
        try:
            with _root_fd(self.root) as fd:
                directories = sorted(
                    n
                    for n in os.listdir(fd)
                    if not stat.S_ISREG(os.stat(n, dir_fd=fd, follow_symlinks=False).st_mode)
                )
            if len(directories) > 10:
                raise SkillError("SKILL_LIMIT")
        except Exception as exc:  # noqa: BLE001 - 只输出脱敏目录状态
            self._warn("catalog", exc.code if isinstance(exc, SkillError) else "SKILL_UNSAFE_PATH")
            return
        # 2. 单项解析失败只产生脱敏警告，不影响其它合法Skill。
        duplicates = set()
        for directory in directories:
            try:
                raw, ids = self._read(directory)
                meta, _ = self._parse(raw)
                if not set(meta.allowed_tools) <= self.registry.names:
                    raise SkillError("SKILL_UNKNOWN_TOOL")
                if meta.name in self._entries or meta.name in duplicates:
                    self._entries.pop(meta.name, None)
                    duplicates.add(meta.name)
                    raise SkillError("SKILL_DUPLICATE")
                self._entries[meta.name] = _Entry(directory, *ids, meta)
            except Exception as exc:  # noqa: BLE001 - 不能记录YAML正文/宿主路径
                self._warn(directory, exc.code if isinstance(exc, SkillError) else "SKILL_INVALID")
        # 3. 同名的全部条目拒绝，不能依赖目录遍历顺序决定加载哪份。
        for name in duplicates:
            self._entries.pop(name, None)

    def _allowed(self, entry, policy):
        needed = set(entry.meta.allowed_tools)
        return (
            needed <= policy.allowed_names
            and needed <= self.registry.names
            and all(self.registry.get(n).permission in policy.allowed_permissions for n in needed)
        )

    def list_skills(self, policy):
        """返回所有Skill的元数据列表"""
        return [
            {
                "name": e.meta.name,
                "description": e.meta.description,
                "required_tools": e.meta.allowed_tools,
                "availability": "available",
            }
            for _, e in sorted(self._entries.items())
            if self._allowed(e, policy)
        ]

    def catalog(self):
        """返回所有Skill的元数据列表"""
        policy = ToolPolicy(
            "", "", self.registry.names, frozenset({"read", "write", "orchestrate"})
        )
        return self.list_skills(policy) + self._warnings

    def load_skill(self, name, policy):
        """加载Skill正文"""
        entry = self._entries.get(name)
        if entry is None or not self._allowed(entry, policy):
            raise SkillError("SKILL_NOT_ALLOWED")
        try:
            raw, _ = self._read(entry.directory, entry)
            _, body = self._parse(raw)
            return body
        except Exception as exc:  # noqa: BLE001 - 变更后安全停用，重启才可重新发现
            self._entries.pop(name, None)
            code = exc.code if isinstance(exc, SkillError) else "SKILL_UNSAFE_PATH"
            self._warn(name, code)
            raise SkillError(code) from None
