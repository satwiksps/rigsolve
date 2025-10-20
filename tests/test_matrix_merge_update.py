from __future__ import annotations

from email.message import Message
from urllib.error import HTTPError

from rigsolve.matrix import MatrixStore
from rigsolve.matrix.update import fetch_update


def _matrix(version: str, fact_version: str) -> str:
    return f'''
[meta]
schema_version = 1
matrix_version = "{version}"
generated = "2026-08-15"

[[wheel]]
package = "example"
version = "{fact_version}"
url = "https://example.test/example-{fact_version}.whl"
tier = 0
[wheel.source]
kind = "pypi-json"
url = "https://pypi.org/pypi/example/{fact_version}/json"
harvested = "2026-08-15"
'''


def test_merge_is_deterministic_and_keeps_both_distinct_facts() -> None:
    left = MatrixStore.from_toml(_matrix("one", "1.0"))
    right = MatrixStore.from_toml(_matrix("two", "2.0"))
    merged = left.merge(right)
    assert merged.matrix_version == "two"
    assert [fact.version for fact in merged.wheels] == ["1.0", "2.0"]
    assert left.merge(right).digest == left.merge(right).digest


class _Response:
    def __init__(self, body: bytes, etag: str) -> None:
        self._body = body
        self.headers = Message()
        self.headers["ETag"] = etag
        self.status = 200

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._body[:amount] if amount >= 0 else self._body


def test_update_validates_caches_and_uses_etag(tmp_path, monkeypatch) -> None:
    import rigsolve.matrix.update as update_module

    requests = []
    payload = _matrix("remote", "1.0").encode()

    def first(request, timeout):
        requests.append(request)
        return _Response(payload, '"matrix-etag"')

    monkeypatch.setattr(update_module, "urlopen", first)
    result = fetch_update("https://example.test/matrix.toml", cache_dir=tmp_path, merge=False)
    assert result.changed
    assert result.etag == '"matrix-etag"'
    assert result.cache_path and result.cache_path.exists()

    def second(request, timeout):
        requests.append(request)
        raise HTTPError(request.full_url, 304, "Not Modified", Message(), None)

    monkeypatch.setattr(update_module, "urlopen", second)
    unchanged = fetch_update("https://example.test/matrix.toml", cache_dir=tmp_path, merge=False)
    assert unchanged.not_modified
    assert not unchanged.changed
    assert requests[-1].get_header("If-none-match") == '"matrix-etag"'
