import importlib.util

import pytest

HAS_C_DECIMAL = importlib.util.find_spec("_decimal") is not None


def pytest_runtest_setup(item: pytest.Item) -> None:
    if not HAS_C_DECIMAL and item.get_closest_marker("requires_c_decimal") is not None:
        pytest.skip("Python was built without the C _decimal module")
