from __future__ import annotations

from collections import Counter

import fnmatch
import json
import locale
import pytest
import re
import urllib.parse
from typing import TYPE_CHECKING, cast

from arelle import PackageManager, PluginManager
from arelle.testengine.TestEngine import TestEngine
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.loader.TestcaseLoader import TESTCASE_LOADER_ERROR_PREFIX

if TYPE_CHECKING:
    from _pytest.mark import ParameterSet


def get_s3_uri(path: str, version_id: str | None = None) -> str:
    path = urllib.parse.quote(path)
    uri = f'https://arelle-public.s3.amazonaws.com/{path}'
    if version_id is not None:
        uri += f'?versionId={version_id}'
    return uri


def get_test_data(
        test_engine_options: TestEngineOptions,
        expected_failure_ids: frozenset[str] = frozenset(),
        required_locale_by_ids: dict[str, re.Pattern[str]] | None = None,
        strict_testcase_index: bool = True,
) -> list[ParameterSet]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param test_engine_options: The args to be parsed by arelle in order to correctly produce the desired result set
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param required_locale_by_ids: The dict of IDs for tests which require a system locale matching a regex pattern.
    :param strict_testcase_index: Don't allow IOerrors when loading the testcase index
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    """
    if required_locale_by_ids is None:
        required_locale_by_ids = {}
    test_engine = TestEngine(test_engine_options)
    test_engine_result = test_engine.run()
    testcase_results = test_engine_result.testcase_results
    matched_expected_failure_ids: set[str] = set()
    matched_required_locale_by_ids: set[str] = set()
    try:
        system_locale = locale.setlocale(locale.LC_CTYPE)
        results: list[ParameterSet] = []

        if strict_testcase_index:
            assert 'IOerror' not in test_engine_result.testcase_variation_set.load_errors, \
                "One or more testcases were not found."

        for testcase_result in sorted(testcase_results, key=lambda x: x.testcase_variation.full_id):
            full_id = testcase_result.testcase_variation.full_id
            marks = []
            if (
                    is_expected_failure(full_id, expected_failure_ids, matched_expected_failure_ids) or
                    is_locale_required(full_id, required_locale_by_ids, matched_required_locale_by_ids, system_locale)
            ):
                marks.append(pytest.mark.xfail())
            expected_results = [
                str(e)
                for e in testcase_result.applied_constraint_set.constraints
            ]
            message = ',\n'.join([
                str(e)
                for e in testcase_result.constraint_results
                if e.diff != 0
            ])
            # Arelle adds message code frequencies to the end, but conformance suites usually don't.
            # Skip assertion results dictionaries.
            actual = [
                re.sub(r' \(\d+\)$', '',  actual_error.code)
                for actual_error in testcase_result.actual_errors
            ]
            param = pytest.param(
                {
                    'status': testcase_result.status,
                    'expected': json.dumps(expected_results),
                    'actual': json.dumps(dict(Counter(actual))),
                    'duration': testcase_result.duration_seconds,
                    'message': message,
                },
                id=f'{testcase_result.testcase_variation.short_name}',
                marks=marks,
            )
            results.append(param)
        testcase_loader_errors = [
            error
            for error in test_engine_result.testcase_variation_set.load_errors
            if error.startswith(TESTCASE_LOADER_ERROR_PREFIX)
        ]
        if testcase_loader_errors:
            raise Exception(f"Some errors occurred during testcase loading: {sorted(testcase_loader_errors)}.")
        test_id_frequencies = Counter(cast(str, p.id) for p in results)
        nonunique_test_ids = {test_id: count for test_id, count in test_id_frequencies.items() if count > 1}
        if nonunique_test_ids:
            raise Exception(f'Some test IDs are not unique.  Frequencies of nonunique test IDs: {nonunique_test_ids}.')
        nonexistent_expected_failure_ids = expected_failure_ids - matched_expected_failure_ids
        if nonexistent_expected_failure_ids:
            raise Exception(f"Some expected failure IDs don't match any test cases: {sorted(nonexistent_expected_failure_ids)}.")
        nonexistent_required_locale_testcase_ids = required_locale_by_ids.keys() - matched_required_locale_by_ids
        if nonexistent_required_locale_testcase_ids:
            raise Exception(f"Some required locale IDs don't match any test cases: {sorted(nonexistent_required_locale_testcase_ids)}.")
        return results
    finally:
        PackageManager.close()  # type: ignore[no-untyped-call]
        PluginManager.close()


def is_expected_failure(
        test_id: str,
        expected_failure_ids: frozenset[str],
        matched_expected_failure_ids: set[str],
) -> bool:
    if test_id in expected_failure_ids:
        matched_expected_failure_ids.add(test_id)
        return True
    for pattern in expected_failure_ids:
        if fnmatch.fnmatch(test_id, f'*{pattern}'):
            matched_expected_failure_ids.add(pattern)
            return True
    return False


def is_locale_required(
        test_id: str,
        required_locale_by_ids: dict[str, re.Pattern[str]],
        matched_required_locale_by_ids: set[str],
        system_locale: str,
) -> bool:
    if test_id in required_locale_by_ids:
        if not required_locale_by_ids[test_id].search(system_locale):
            matched_required_locale_by_ids.add(test_id)
            return True
    return False
