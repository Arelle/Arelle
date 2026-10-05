from __future__ import annotations

from tests.integration_tests.integration_test_util import VariationResult, format_failure_message


def test_conformance_suite(conformance_suite_results: VariationResult) -> None:
    """
    See conftest.py for context around the parameterization of conformance suite results.
    It is critical that this file is not imported or referenced by other modules to ensure that it is not evaluated
    before pytest can evaluate conformance suite results via the pytest_configure hook.
    """
    assert conformance_suite_results.status == "pass", format_failure_message(conformance_suite_results)
