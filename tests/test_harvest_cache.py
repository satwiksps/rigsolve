from __future__ import annotations

from email.message import Message
from urllib.error import HTTPError

from rigsolve.harvest.cache import CachedHTTPClient


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.status = 200
        self.headers = Message()
        self.headers["ETag"] = '"abc"'
        self.headers["Last-Modified"] = "Sat, 15 Aug 2026 00:00:00 GMT"

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int) -> bytes:
        return self.body[:amount]


def test_cache_revalidates_with_etag_and_serves_304_body(tmp_path, monkeypatch) -> None:
    import rigsolve.harvest.cache as cache_module

    seen = []

    def first(request, timeout):
        seen.append(request)
        return _Response(b'{"ok": true}')

    monkeypatch.setattr(cache_module, "urlopen", first)
    client = CachedHTTPClient(tmp_path)
    fresh = client.get("https://example.test/data")
    assert not fresh.from_cache
    assert fresh.etag == '"abc"'

    def second(request, timeout):
        seen.append(request)
        raise HTTPError(request.full_url, 304, "Not Modified", Message(), None)

    monkeypatch.setattr(cache_module, "urlopen", second)
    cached = client.get("https://example.test/data")
    assert cached.from_cache
    assert cached.not_modified
    assert cached.body == fresh.body
    assert seen[-1].get_header("If-none-match") == '"abc"'


def test_cache_has_explicit_offline_mode(tmp_path, monkeypatch) -> None:
    import rigsolve.harvest.cache as cache_module

    monkeypatch.setattr(cache_module, "urlopen", lambda request, timeout: _Response(b"cached"))
    client = CachedHTTPClient(tmp_path)
    client.get("https://example.test/data")
    monkeypatch.setattr(
        cache_module,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network used")),
    )
    assert client.get("https://example.test/data", offline=True).body == b"cached"
