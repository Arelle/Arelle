import builtins

import pytest


@pytest.fixture(autouse=True)
def mock_gettext(monkeypatch):
    monkeypatch.setitem(builtins.__dict__, "_", lambda s: s)
    yield
    monkeypatch.delitem(builtins.__dict__, "_")
