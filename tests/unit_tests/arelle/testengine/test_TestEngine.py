"""
See COPYRIGHT.md for copyright information.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from arelle.api.Session import Session
from arelle.testengine.ActualError import ActualError
from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestEngine import _block_codes, _build_entrypoint_uris, TestEngine
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestcaseConstraint import TestcaseConstraint
from arelle.testengine.TestcaseConstraintSet import TestcaseConstraintSet
from arelle.testengine.TestcaseVariation import TestcaseVariation
from arelle.testengine.TestcaseVariationSet import TestcaseVariationSet


def _build_test_variation(
        name: str,
        testcase_constraints: list[TestcaseConstraint] | None = None,
        match_all: bool = True,
) -> TestcaseVariation:
    return TestcaseVariation(
        base='base',
        blocked_code_pattern="",
        calc_mode=None,
        compare_formula_output_uri=None,
        compare_instance_uri=None,
        description='desc',
        full_id=f'base/input.zip:{name}',
        id=f'base/input.zip:{name}',
        ignore_levels=frozenset(),
        inline_target=None,
        name=name,
        parameters="",
        read_first_uris=['input.zip'],
        report_count=None,
        short_name=f'input.zip:{name}',
        status="",
        testcase_constraint_set=TestcaseConstraintSet(
            constraints=testcase_constraints or [],
            match_all=match_all
        ),
    )


@dataclass(frozen=True)
class RunTestcase:
    testcase_variation: TestcaseVariation
    errors: list[str]
    passed: bool
    skipped: bool


RUN_TESTCASES = [
    RunTestcase(_build_test_variation('valid-pass'), [], True, False),
    RunTestcase(_build_test_variation('valid-fail'), ['ERROR'], False, False),
    RunTestcase(
        _build_test_variation('invalid-all-pass', [
            TestcaseConstraint(pattern="ERROR1"), TestcaseConstraint(pattern="ERROR2")
        ]),
        ['ERROR1', 'ERROR2'], True, False
    ),
    RunTestcase(
        _build_test_variation('invalid-all-fail', [
            TestcaseConstraint(pattern="ERROR1"), TestcaseConstraint(pattern="ERROR2")
        ]),
        ['ERROR1'], False, False
    ),
    RunTestcase(
        _build_test_variation('invalid-any-pass', [
            TestcaseConstraint(pattern="ERROR1"), TestcaseConstraint(pattern="ERROR2"),
        ], match_all=False),
        ['ERROR1'], True, False
    ),
    RunTestcase(
        _build_test_variation('invalid-any-fail', [
            TestcaseConstraint(pattern="ERROR1"),
        ], match_all=False),
        [], False, False
    ),
    RunTestcase(_build_test_variation('skip'), [], True, True),
]


class TestTestEngine:
    def test_block_codes(self) -> None:
        passed_errors = [
            ActualError(code='code3', level=ErrorLevel.ERROR),
        ]
        blocked_errors = [
            ActualError(code='code1', level=ErrorLevel.ERROR),
            ActualError(code='code1', level=ErrorLevel.ERROR),
            ActualError(code='code2', level=ErrorLevel.ERROR),
        ]
        actual_results, blocked_codes = _block_codes(
            actual_errors=passed_errors + blocked_errors,
            pattern='^(code1|code2)'
        )
        assert actual_results == passed_errors
        assert blocked_codes == {
            'code1': 2,
            'code2': 1,
        }

    @pytest.mark.parametrize(
        "uris, results",
        [
            (
                    ['a.html'],
                    ['a.html']
            ),
            (
                    ['a.zip'],
                    ['a.zip']
            ),
            (
                    ['a.html', 'b.htm', 'c.xhtml'],
                    ['./_IXDS#?#a.html#?#b.htm#?#c.xhtml'],
            ),
            (
                    ['a.html', 'b.htm', 'c.xhtml', 'd.zip'],
                    ['a.html', 'b.htm', 'c.xhtml', 'd.zip'],
            ),
        ]
    )
    def test_build_entrypoint_uris(self, uris: list[str], results: list[str]) -> None:
        paths = [Path(uri) for uri in uris]
        actual_results = _build_entrypoint_uris(paths)
        assert actual_results == results

    @pytest.mark.parametrize('testcase', RUN_TESTCASES, ids=lambda x: x.testcase_variation.name)
    @patch('arelle.testengine.TestEngine._collect_errors')
    @patch('arelle.testengine.TestEngine._load_testcase_index')
    @patch('arelle.api.Session.Session.run')
    def test_run(self, mock_run, mock_load_testcase_index, mock_collect_errors, testcase) -> None:
        # Prevent Session from actually executing
        mock_run.return_value = True
        # Override testcase variation loading
        mock_load_testcase_index.return_value = TestcaseVariationSet(
            load_errors=[],
            skipped_testcase_variations=[],
            testcase_variations=[testcase.testcase_variation]
        )
        def collect_errors(session: Session):
            return testcase.errors
        # Override error results
        mock_collect_errors.side_effect = collect_errors
        test_engine = TestEngine(TestEngineOptions(
            filters=['*-pass', '*-fail'],
            index_file='index.xml',
            name='test',
        ))
        result = test_engine.run()
        actual_results = [
            (
                testcase_result.testcase_variation,
                [_e.code for _e in testcase_result.actual_errors],
                testcase_result.passed,
                testcase_result.skip
            )
            for testcase_result in result.testcase_results
        ]
        expected_results = [
            (
                testcase.testcase_variation,
                testcase.errors,
                testcase.passed,
                testcase.skipped
            )
        ]
        assert actual_results == expected_results
