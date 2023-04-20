import builtins

import pytest


@pytest.fixture(autouse=True)
def mock_gettext(monkeypatch):
    monkeypatch.setitem(builtins.__dict__, "_", lambda s: s)
    yield
    monkeypatch.delitem(builtins.__dict__, "_")

def pytest_collection_modifyitems(items):
    for item in items:
        test_marked_slow = item.get_closest_marker("slow")
        if test_marked_slow is None:
            item.add_marker(pytest.mark.fast)
