"""MockTransport真实HTTP序列化，不进行公网请求。"""

import json

import httpx
import pytest
from pydantic import SecretStr

from minideerflow.research.models import ResearchError
from minideerflow.research.provider import TavilyProvider


@pytest.mark.anyio
async def test_search_extract_conversion():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.host == "api.tavily.com"
        body = json.loads(request.content)
        if request.url.path == "/search":
            assert body["max_results"] == 5 and body["include_raw_content"] is False
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"url": "https://EXAMPLE.com/a#x", "title": "T", "content": "snippet"},
                        {"url": "https://example.com/a", "title": "dup"},
                        {"url": "http://127.0.0.1", "title": "unsafe"},
                    ]
                },
            )
        assert body["urls"] == ["https://example.com/a"]
        return httpx.Response(
            200, json={"results": [{"url": body["urls"][0], "raw_content": "中" * 10000}]}
        )

    provider = TavilyProvider(SecretStr("test-only"), transport=httpx.MockTransport(handle))
    hits = await provider.search("topic")
    assert len(hits) == 1
    assert len((await provider.extract(hits[0].url)).encode()) <= 20480
    assert len(calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,code",
    [
        (429, "RESEARCH_RATE_LIMITED"),
        (401, "RESEARCH_PROVIDER_UNAVAILABLE"),
        (302, "RESEARCH_PROVIDER_UNAVAILABLE"),
    ],
)
async def test_errors_no_retry(status, code):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "http://127.0.0.1"})

    provider = TavilyProvider(SecretStr("test-only"), transport=httpx.MockTransport(handle))
    with pytest.raises(ResearchError, match=code):
        await provider.search("topic")
    assert len(calls) == 1


@pytest.mark.anyio
async def test_timeout_and_fake_extract():
    def timeout(request):
        raise httpx.ReadTimeout("secret upstream details")

    with pytest.raises(ResearchError, match="RESEARCH_PROVIDER_UNAVAILABLE"):
        await TavilyProvider(SecretStr("fake"), transport=httpx.MockTransport(timeout)).search(
            "topic"
        )
    provider = TavilyProvider(
        SecretStr("fake"),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "results": [{"url": "https://other.com", "raw_content": "fake"}],
                    "failed_results": [{"url": "https://example.com"}],
                },
            )
        ),
    )
    with pytest.raises(ResearchError, match="RESEARCH_EXTRACTION_FAILED"):
        await provider.extract("https://example.com")


@pytest.mark.anyio
async def test_response_size_bound():
    provider = TavilyProvider(
        SecretStr("fake"),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, content=b"x" * (1024 * 1024 + 1), headers={"Content-Type": "application/json"}
            )
        ),
    )
    with pytest.raises(ResearchError, match="RESEARCH_RESPONSE_TOO_LARGE"):
        await provider.search("topic")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {"results": None},
        {
            "results": [{"url": "https://example.com/", "raw_content": "body"}],
            "failed_results": [{"url": "https://example.com/"}],
        },
        {"results": [{"url": "file:///etc/passwd", "raw_content": "bad"}]},
        {"results": [{"url": "https://example.com/", "raw_content": 42}]},
    ],
)
async def test_malformed_or_conflicting_extract_never_succeeds(body):
    provider = TavilyProvider(
        SecretStr("fake"), transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    )
    with pytest.raises(ResearchError):
        await provider.extract("https://example.com/")
