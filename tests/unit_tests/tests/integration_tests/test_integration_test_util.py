from tests.integration_tests.integration_test_util import (
    VariationResult,
    format_failure_message,
    get_actual_assertion_results,
)

# Validate.py appends formula assertion results to a variation's actual codes as a dict.
ACTUAL = ["EFM.6.5.20", "xbrl.4.9 (2)", {"assertion1": (1, 0, 0, 0, 0)}]


def test_get_actual_assertion_results() -> None:
    assert get_actual_assertion_results(ACTUAL) == {"assertion1": {"satisfied": 1, "not satisfied": 0}}


def test_format_failure_message() -> None:
    result = VariationResult(
        test_id="index.xml:V-01",
        expected_failure=False,
        status="fail",
        match_all=True,
        expected='{"ERROR": {"xbrl.4.9": 1}}',
        expected_warnings={"warning.code": 1},
        configured_errors={"EFM.6.5.20": 1},
        actual_codes={"EFM.6.5.20": 1, "xbrl.4.9": 2},
        actual_assertions=get_actual_assertion_results(ACTUAL),
        duration=None,
    )
    assert format_failure_message(result) == (
        "Testcase variation failed (match-all)\n"
        'Expected by the suite: {"ERROR": {"xbrl.4.9": 1}}\n'
        "Expected warnings: {'warning.code': 1}\n"
        "Configured additional errors: {'EFM.6.5.20': 1}\n"
        "Actual codes: {'EFM.6.5.20': 1, 'xbrl.4.9': 2}\n"
        "Actual assertion results: {'assertion1': {'satisfied': 1, 'not satisfied': 0}}"
    )
