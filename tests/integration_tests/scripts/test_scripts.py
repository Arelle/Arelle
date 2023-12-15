from __future__ import annotations
from typing import Any


def test_script(script_results: dict[str, Any]) -> None:
    """
    See conftest.py for context around the parameterization of conformance suite results.
    It is critical that this file is not imported or referenced by other modules to ensure that it is not evaluated
    before pytest can evaluate conformance suite results via the pytest_configure hook.
    """
    assert script_results.get('status') == 'pass', \
        'Expected these validation suffixes: {}, but received these validations: {}'.format(
            script_results.get('expected'), script_results.get('actual')
        )
