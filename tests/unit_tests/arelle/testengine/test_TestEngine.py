"""
See COPYRIGHT.md for copyright information.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from arelle.api.Session import Session
from arelle.testengine.ActualError import ActualError
from arelle.testengine.Constraint import Constraint
from arelle.testengine.ConstraintSet import ConstraintSet
from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestEngine import _block_codes, _build_entrypoint_uris, TestEngine
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.Testcase import Testcase
from arelle.testengine.TestcaseSet import TestcaseSet


def _build_test_variation(
        name: str,
        constraints: list[Constraint] | None = None,
        match_all: bool = True,
) -> Testcase:
    return Testcase(
        base=Path('base'),
        blocked_code_pattern="",
        calc_mode=None,
        compare_instance_uri=None,
        description='desc',
        expected_instance_count=None,
        full_id=f'base/{name}.zip:{name}',
        inline_target=None,
        local_id=name,
        name=name,
        parameters="",
        read_first_uris=[f'{name}.zip'],
        status="",
        constraint_set=ConstraintSet(
            constraints=constraints or [],
            match_all=match_all
        ),
    )


@dataclass(frozen=True)
class RunTestcase:
    testcase: Testcase
    errors: list[str]
    passed: bool
    skipped: bool


RUN_TESTCASES = [
    RunTestcase(_build_test_variation('valid-pass'), [], True, False),
    RunTestcase(_build_test_variation('valid-fail'), ['ERROR'], False, False),
    RunTestcase(
        _build_test_variation('invalid-all-pass', [
            Constraint(pattern="ERROR1"), Constraint(pattern="ERROR2")
        ]),
        ['ERROR1', 'ERROR2'], True, False
    ),
    RunTestcase(
        _build_test_variation('invalid-all-fail', [
            Constraint(pattern="ERROR1"), Constraint(pattern="ERROR2")
        ]),
        ['ERROR1'], False, False
    ),
    RunTestcase(
        _build_test_variation('invalid-any-pass', [
            Constraint(pattern="ERROR1"), Constraint(pattern="ERROR2"),
        ], match_all=False),
        ['ERROR1'], True, False
    ),
    RunTestcase(
        _build_test_variation('invalid-any-fail', [
            Constraint(pattern="ERROR1"),
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
        actual_results = [r.replace('\\', '/') for r in actual_results]
        assert actual_results == results

    @pytest.mark.parametrize('testcase', RUN_TESTCASES, ids=lambda x: x.testcase.name)
    @patch('arelle.testengine.TestEngine._collect_errors')
    @patch('arelle.testengine.TestEngine.load_testcase_index')
    @patch('arelle.api.Session.Session.run')
    def test_run(self, mock_run, mock_load_testcase_index, mock_collect_errors, testcase) -> None:
        # Prevent Session from actually executing
        mock_run.return_value = True
        # Override testcase variation loading
        mock_load_testcase_index.return_value = TestcaseSet(
            load_errors=[],
            skipped_testcases=[],
            testcases=[testcase.testcase]
        )
        def collect_errors(session: Session):
            return testcase.errors
        # Override error results
        mock_collect_errors.side_effect = collect_errors
        test_engine = TestEngine(TestEngineOptions(
            filters=['*-pass', '*-fail'],
            index_file=Path('index.xml'),
            name='test',
            match_all=testcase.testcase.constraint_set.match_all,
        ))
        result = test_engine.run()
        actual_results = [
            (
                testcase_result.testcase,
                [_e.code for _e in testcase_result.actual_errors],
                testcase_result.passed,
                testcase_result.skip
            )
            for testcase_result in result.testcase_results
        ]
        expected_results = [
            (
                testcase.testcase,
                testcase.errors,
                testcase.passed,
                testcase.skipped
            )
        ]
        assert actual_results == expected_results
