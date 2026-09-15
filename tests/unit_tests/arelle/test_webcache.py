"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Callable
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from arelle import WebCache as WebCacheModule
from arelle.WebCache import TRANSIENT_RETRY_WAIT_BUDGET_SECONDS, WebCache

URL = "https://www.sec.gov/Archives/edgar/data/1/000000000026000001/0000000000-26-000001-xbrl.zip"
SUCCESS = object()


def _httpError(code: int, retryAfter: str | None = None) -> HTTPError:
    headers = Message()
    if retryAfter is not None:
        headers["Retry-After"] = retryAfter
    return HTTPError(URL, code, "error", headers, None)


def _retrieveOutcomes(*outcomes: object) -> Callable[..., tuple[str | None, dict[str, str], bytes]]:
    """A stand-in for WebCache.retrieve giving each outcome in turn, repeating the last: an exception is raised,
    and SUCCESS writes the temporary download file as retrieve would."""
    remaining = list(outcomes)

    def retrieve(url: str, filename: str | None = None, **kwargs: object) -> tuple[str | None, dict[str, str], bytes]:
        outcome = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        if isinstance(outcome, BaseException):
            raise outcome
        assert filename is not None
        Path(filename).write_bytes(b"PK")
        return filename, {}, b"PK"
    return retrieve


@pytest.fixture
def webCache(tmp_path: Path) -> WebCache:
    cntlr = Mock(isGAE=False, userAppDir=str(tmp_path), hasFileSystem=False, disablePersistentConfig=True)
    return WebCache(cntlr, None)


@pytest.fixture
def filepath(tmp_path: Path) -> str:
    return str(tmp_path / "cache" / "filing.zip")


def _loggedCodes(webCache: WebCache) -> list[str]:
    return [call.kwargs.get("messageCode") for call in webCache.cntlr.addToLog.call_args_list]


def _download(
        webCache: WebCache,
        filepath: str,
        *outcomes: object,
        retrievingDueToRecheckInterval: bool = False
    ) -> tuple[bool, Mock, list[float]]:
    with patch.object(webCache, "retrieve", side_effect=_retrieveOutcomes(*outcomes)) as retrieve, \
            patch.object(WebCacheModule.time, "sleep") as sleep:
        result = webCache._downloadFile(URL, filepath, retrievingDueToRecheckInterval=retrievingDueToRecheckInterval)
    return result, retrieve, [call.args[0] for call in sleep.call_args_list]


class TestTransientRetrieval:
    def test_service_unavailable_is_retried(self, webCache: WebCache, filepath: str) -> None:
        result, retrieve, delays = _download(webCache, filepath, _httpError(503), SUCCESS)
        assert result and Path(filepath).exists()
        assert retrieve.call_count == 2
        assert delays == [1.0]
        assert _loggedCodes(webCache) == ["webCache:retryingOperation"]

    def test_not_found_is_not_retried(self, webCache: WebCache, filepath: str) -> None:
        result, retrieve, delays = _download(webCache, filepath, _httpError(404))
        assert not result
        assert retrieve.call_count == 1
        assert delays == []
        assert _loggedCodes(webCache) == ["webCache:retrievalError"]

    def test_delays_double_until_retries_are_used(self, webCache: WebCache, filepath: str) -> None:
        result, retrieve, delays = _download(webCache, filepath, _httpError(503))
        assert not result
        assert retrieve.call_count == 5
        assert delays == [1.0, 2.0, 4.0, 8.0]
        assert _loggedCodes(webCache)[-1] == "webCache:retrievalError"

    def test_retry_after_seconds_is_honored(self, webCache: WebCache, filepath: str) -> None:
        result, _retrieve, delays = _download(webCache, filepath, _httpError(429, retryAfter="3"), SUCCESS)
        assert result
        assert delays == [3.0]

    def test_retries_end_when_the_next_wait_exceeds_the_budget(self, webCache: WebCache, filepath: str) -> None:
        # two waits of 15 seconds exceed the budget, and a wait is never shortened to fit it
        result, retrieve, delays = _download(webCache, filepath, _httpError(503, retryAfter="15"))
        assert not result
        assert delays == [15.0]
        assert retrieve.call_count == 2
        assert _loggedCodes(webCache)[-1] == "webCache:retrievalError"

    def test_retry_after_longer_than_the_budget_is_not_retried(self, webCache: WebCache, filepath: str) -> None:
        retryAfter = str(int(TRANSIENT_RETRY_WAIT_BUDGET_SECONDS) + 5)
        result, retrieve, delays = _download(webCache, filepath, _httpError(429, retryAfter=retryAfter))
        assert not result
        assert retrieve.call_count == 1
        assert delays == []  # retrying before the server's delay risks its penalties
        assert _loggedCodes(webCache) == ["webCache:retrievalError"]

    def test_dropped_connection_is_retried(self, webCache: WebCache, filepath: str) -> None:
        result, retrieve, _delays = _download(webCache, filepath, URLError(ConnectionResetError()), SUCCESS)
        assert result
        assert retrieve.call_count == 2

    def test_cache_recheck_does_not_wait(self, webCache: WebCache, filepath: str) -> None:
        result, _retrieve, delays = _download(webCache, filepath, _httpError(503), retrievingDueToRecheckInterval=True)
        assert result
        assert delays == []

    @pytest.mark.parametrize("err, expected", [
        (_httpError(503), True),
        (_httpError(429), True),
        (_httpError(408), True),
        (_httpError(404), False),
        (_httpError(401), False),
        (URLError(TimeoutError()), True),
        (URLError("unknown url type"), False),
    ])
    def test_transient_classification(self, err: URLError, expected: bool) -> None:
        assert WebCache._isTransientRetrievalError(err) is expected
