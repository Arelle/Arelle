from __future__ import annotations
from typing import Any


def test_script(script_results: dict[str, Any]) -> None:
    """
    See conftest.py for context around the parameterization of conformance suite results.
    It is critical that this file is not imported or referenced by other modules to ensure that it is not evaluated
    before pytest can evaluate conformance suite results via the pytest_configure hook.
    """
    assert script_results.get('returncode') == 0, script_results.get('stderr')
