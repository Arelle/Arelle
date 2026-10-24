from typing import Any

import pytest

from tests.integration_tests.integration_test_util import (
    VariationResult,
    format_failure_message,
    get_actual_assertion_results,
    split_expected,
)

# Validate.py appends formula assertion results to a variation's actual codes as a dict.
ACTUAL = ["EFM.6.5.20", "xbrl.4.9 (2)", {"assertion1": (1, 0, 0, 0, 0)}]


def _result(**overrides: Any) -> VariationResult:
    fields: dict[str, Any] = dict(
        test_id="index.xml:V-01",
        expected_failure=False,
        status="fail",
        match_all=True,
        expected_result=None,
        expected_errors={},
        expected_count=None,
        expected_warnings={},
        expected_assertions={},
        ignored_errors=[],
        configured_errors={},
        actual_codes={},
        actual_assertions={},
        unmatched_expected={},
        unmatched_actual={},
        duration=None,
    )
    fields.update(overrides)
    return VariationResult(**fields)


def test_get_actual_assertion_results() -> None:
    assert get_actual_assertion_results(ACTUAL) == {"assertion1": {"satisfied": 1, "not satisfied": 0}}


@pytest.mark.parametrize("expected, split", [
    ("valid", ("valid", {}, {})),
    ("invalid", ("invalid", {}, {})),
    ("EFM.6.05.20", (None, {"EFM.6.05.20": 1}, {})),
    (["xbrl.4.9", "xbrl.4.9", "EFM.6.05.20"], (None, {"xbrl.4.9": 2, "EFM.6.05.20": 1}, {})),
    ({"assertion1": (1, 0)}, (None, {}, {"assertion1": {"satisfied": 1, "not satisfied": 0}})),
    (None, (None, {}, {})),
])
def test_split_expected(expected: Any, split: tuple[Any, ...]) -> None:
    assert split_expected(expected) == split


def test_format_failure_message_match_all() -> None:
    result = _result(
        expected_errors={"xbrl.4.9": 1},
        expected_warnings={"warning.code": 1},
        ignored_errors=["ESEF.ignored"],
        configured_errors={"EFM.6.5.20": 1},
        actual_codes={"EFM.6.5.20": {"ERROR": 1}, "xbrl.4.9": {"ERROR": 1, "WARNING": 1}},
        actual_assertions=get_actual_assertion_results(ACTUAL),
        unmatched_expected={"warning.code": 1},
        unmatched_actual={"xbrl.4.9": 1},
    )
    assert format_failure_message(result) == (
        "Testcase variation failed in match-all mode:\n"
        "Expected by the suite:\n"
        "  error xbrl.4.9: 1\n"
        "  warning warning.code: 1\n"
        "Ignored by the suite:\n"
        "  error ESEF.ignored\n"
        "Expected by the config:\n"
        "  error EFM.6.5.20: 1\n"
        "Raised:\n"
        "  error EFM.6.5.20: 1\n"
        "  error xbrl.4.9: 1\n"
        "  warning xbrl.4.9: 1\n"
        "Expected but not raised:\n"
        "  warning warning.code: 1\n"
        "Raised but not expected:\n"
        "  error/warning xbrl.4.9: 1"
    )


def test_format_failure_message_assertions() -> None:
    result = _result(
        expected_assertions={"assertion1": {"satisfied": 1, "not satisfied": 1}},
        actual_assertions=get_actual_assertion_results(ACTUAL),
    )
    assert format_failure_message(result) == (
        "Testcase variation failed in match-all mode:\n"
        "Expected by the suite:\n"
        "  assertion assertion1: 1 satisfied, 1 not satisfied\n"
        "Raised:\n"
        "  assertion assertion1: 1 satisfied, 0 not satisfied"
    )


def test_format_failure_message_match_any_valid() -> None:
    result = _result(
        match_all=False,
        expected_result="valid",
        actual_codes={"xbrl.4.9": {"UNKNOWN": 2}},
        unmatched_actual={"xbrl.4.9": 2},
    )
    assert format_failure_message(result) == (
        "Testcase variation failed in match-any mode:\n"
        "Expected by the suite:\n"
        "  valid\n"
        "Raised:\n"
        "  unknown xbrl.4.9: 2\n"
        "Raised but not expected:\n"
        "  unknown xbrl.4.9: 2"
    )


def test_format_failure_message_nothing_raised() -> None:
    result = _result(
        expected_errors={"xbrl.4.9": 1},
        expected_count=1,
        unmatched_expected={"xbrl.4.9": 1},
    )
    assert format_failure_message(result) == (
        "Testcase variation failed in match-all mode:\n"
        "Expected by the suite:\n"
        "  error xbrl.4.9: 1\n"
        "  total matching codes: 1\n"
        "Raised:\n"
        "  nothing\n"
        "Expected but not raised:\n"
        "  error xbrl.4.9: 1"
    )
