from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from arelle.Validate import Validate


def _validator(testcaseResultOptions: str | None = None) -> Validate:
    modelXbrl = MagicMock()
    modelXbrl.modelManager.formulaOptions = SimpleNamespace(
        testcaseResultOptions=testcaseResultOptions,
        testcaseExpectedErrors=None,
        testcaseResultsCaptureWarnings=False,
    )
    modelXbrl.modelManager.cntlr.errors = []
    modelXbrl.modelManager.cntlr.errorLevels = {}
    validator = Validate.__new__(Validate)
    validator.modelXbrl = modelXbrl
    validator.useFileSource = MagicMock()
    return validator


def _variation(expected: Any, userExpectedErrors: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        match=None,
        expected=expected,
        expectedCount=None,
        expectedReportCount=None,
        expectedWarnings=[],
        blockedMessageCodes=None,
        ignoredErrors=[],
        assertions=None,
        status=None,
        actual=[],
        setUserExpectedErrors=lambda *args: userExpectedErrors,
    )


def test_prior_assertion_results_pass_a_later_instance_without_errors() -> None:
    validator = _validator()
    variation = _variation({"assertion1": (1, 0)}, [])
    validator.determineTestStatus(variation, [{"assertion1": (1, 0, 0, 0, 0)}])  # type: ignore[arg-type]
    assert variation.status == "pass"
    validator.determineTestStatus(variation, [])  # type: ignore[arg-type]
    assert variation.status == "pass"


def test_prior_assertion_results_dont_satisfy_a_config_expected_error() -> None:
    validator = _validator("match-all")
    variation = _variation({"assertion1": (1, 0)}, ["configured:error"])
    validator.determineTestStatus(variation, [{"assertion1": (1, 0, 0, 0, 0)}])  # type: ignore[arg-type]
    assert variation.status == "fail"
    validator.determineTestStatus(variation, [])  # type: ignore[arg-type]
    assert variation.status == "fail"
