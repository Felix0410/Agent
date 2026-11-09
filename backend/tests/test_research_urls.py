"""引用URL不能引入内网目标、编码混淆或可执行scheme。"""

import pytest

from minideerflow.research.models import ResearchError
from minideerflow.research.urls import canonical_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://localhost",
        "http://a.local",
        "http://127.0.0.1",
        "http://169.254.169.254",
        "http://10.0.0.1",
        "http://[::1]",
        "https://user:pass@example.com",
        "https://example.com:8443",
        "http://2130706433",
        "http://0177.0.0.1",
        "https://example.com\\@127.0.0.1",
        "https://%31%32%37.0.0.1",
        "https://a.internal",
        "http://[::ffff:127.0.0.1]",
    ],
)
def test_unsafe(url):
    with pytest.raises(ResearchError):
        canonical_url(url)


def test_normalization():
    assert canonical_url("https://EXAMPLE.com:443/page#part") == "https://example.com/page"
