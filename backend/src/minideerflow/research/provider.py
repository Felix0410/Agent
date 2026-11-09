"""只连固定Tavily端点，来源网页由提供方提取；无任意URL请求入口。"""

import asyncio
import json
from datetime import UTC, datetime

import httpx
from pydantic import SecretStr

from minideerflow.research.models import ResearchError, SearchHit
from minideerflow.research.urls import canonical_url


def bounded_text(text, limit):
    """UTF8字节裁剪不会产生半个字符；提供方对象不能冒充正文。"""
    if not isinstance(text, str):
        raise ResearchError("RESEARCH_INVALID_RESPONSE")
    return text.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


class TavilyProvider:
    """单次总时限12秒、最大1MiB响应、零重试、禁代理和跳转。"""

    def __init__(self, key: SecretStr, *, transport=None):
        self._key = key
        self._transport = transport

    async def _post(self, endpoint, payload):
        try:
            async with (
                asyncio.timeout(12),
                httpx.AsyncClient(
                    timeout=httpx.Timeout(12, connect=5),
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream(
                    "POST",
                    "https://api.tavily.com/" + endpoint,
                    headers={"Authorization": "Bearer " + self._key.get_secret_value()},
                    json=payload,
                ) as response,
            ):
                if response.status_code == 429:
                    raise ResearchError("RESEARCH_RATE_LIMITED")
                if response.status_code != 200:
                    raise ResearchError("RESEARCH_PROVIDER_UNAVAILABLE")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise ResearchError("RESEARCH_INVALID_RESPONSE")
                raw = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    raw.extend(chunk)
                    if len(raw) > 1024 * 1024:
                        raise ResearchError("RESEARCH_RESPONSE_TOO_LARGE")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ResearchError("RESEARCH_INVALID_RESPONSE")
                return data
        except (httpx.HTTPError, TimeoutError, ValueError):
            raise ResearchError("RESEARCH_PROVIDER_UNAVAILABLE") from None

    async def search(self, query: str, max_results: int = 5):
        """只请求basic候选；无raw content，无提供方生成答案。"""
        data = await self._post(
            "search",
            {
                "query": query,
                "max_results": min(5, max_results),
                "search_depth": "basic",
                "include_raw_content": False,
                "include_answer": False,
            },
        )
        rows = data.get("results")
        if not isinstance(rows, list):
            raise ResearchError("RESEARCH_INVALID_RESPONSE")
        hits, seen = [], set()
        now = datetime.now(UTC).isoformat()
        for item in rows[:5]:
            if not isinstance(item, dict):
                continue
            try:
                url = canonical_url(item.get("url"))
                hit = SearchHit(
                    title=bounded_text(item.get("title", ""), 800)[:200],
                    url=url,
                    snippet=bounded_text(item.get("content", ""), 2000)[:500],
                    searched_at=now,
                )
            except ResearchError:
                continue
            if url not in seen:
                hits.append(hit)
                seen.add(url)
        return hits

    async def extract(self, url: str):
        """响应URL必须真实匹配登记URL，不能用另一个页面充当成功。"""
        url = canonical_url(url)
        data = await self._post(
            "extract", {"urls": [url], "extract_depth": "basic", "format": "text"}
        )
        results = data.get("results", [])
        if not isinstance(results, list):
            raise ResearchError("RESEARCH_INVALID_RESPONSE")
        failures = data.get("failed_results", [])
        if not isinstance(failures, list):
            raise ResearchError("RESEARCH_INVALID_RESPONSE")
        for failure in failures:
            if not isinstance(failure, dict):
                continue
            try:
                failed_url = canonical_url(failure.get("url"))
            except ResearchError:
                continue
            if failed_url == url:
                raise ResearchError("RESEARCH_EXTRACTION_FAILED")
        for item in results:
            if not isinstance(item, dict):
                continue
            try:
                matched = canonical_url(item.get("url")) == url
            except ResearchError:
                continue
            if matched:
                text = bounded_text(item.get("raw_content", ""), 20 * 1024).strip()
                if text:
                    return text
        # failed_results或没有对应URL都不能升级为EXTRACTED。
        raise ResearchError("RESEARCH_EXTRACTION_FAILED")
