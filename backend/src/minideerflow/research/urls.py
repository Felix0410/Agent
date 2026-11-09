"""仅校验引用/Extract候选；绝不解析DNS后直接HTTP访问该来源。"""

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from minideerflow.research.models import ResearchError


def canonical_url(value: str) -> str:
    """只保留正常公网http(s)地址；同URL片段不产生新证据。"""
    try:
        if (
            not isinstance(value, str)
            or len(value) > 2048
            or re.search(r'[\s\\\x00-\x1f<>"`]', value)
        ):
            raise ValueError
        parsed = urlsplit(value)
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode().lower()
        if (
            parsed.scheme not in ("http", "https")
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError
        if parsed.port not in (None, 80 if parsed.scheme == "http" else 443):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # 禁止localhost/内部后缀、数字混淆IP、单标签及百分号编码主机。
            if (
                not re.fullmatch(r"[a-z0-9.-]+", host)
                or "." not in host
                or not re.search(r"[a-z]", host.rsplit(".", 1)[-1])
                or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
                or any(
                    not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in host.split(".")
                )
            ):
                raise ValueError from None
        else:
            if not address.is_global or address.is_multicast or address.is_reserved:
                raise ValueError
            host = f"[{host}]" if address.version == 6 else host
        return urlunsplit((parsed.scheme, host, parsed.path or "/", parsed.query, ""))
    except (ValueError, UnicodeError):
        raise ResearchError("RESEARCH_UNSAFE_URL") from None
