from __future__ import annotations

from collections import Counter

import fnmatch
import json
import locale
import pytest
import re
import urllib.parse
from typing import TYPE_CHECKING

from arelle import PackageManager, PluginManager
from arelle.testengine.TestEngine import TestEngine
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestcaseSet import TestcaseSet

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
        testcase_set: TestcaseSet,
        expected_failure_ids: frozenset[str] = frozenset(),
        required_locale_by_ids: dict[str, re.Pattern[str]] | None = None,
) -> list[ParameterSet]:
    """
    Produces a list of Pytest Params that can be fed into a parameterized pytest function

    :param test_engine_options: The args to be parsed by arelle in order to correctly produce the desired result set
    :param testcase_set: The preloaded testcase set to validate
    :param expected_failure_ids: The set of string test IDs that are expected to fail
    :param required_locale_by_ids: The dict of IDs for tests which require a system locale matching a regex pattern.
    :return: A list of PyTest Params that can be used to run a parameterized pytest function
    """
    if required_locale_by_ids is None:
        required_locale_by_ids = {}
    test_engine = TestEngine(test_engine_options)
    test_engine_result = test_engine.run(testcase_set)
    testcase_results = test_engine_result.testcase_results
    try:
        system_locale = locale.setlocale(locale.LC_CTYPE)
        results: list[ParameterSet] = []

        for testcase_result in sorted(testcase_results, key=lambda x: x.testcase.full_id):
            full_id = testcase_result.testcase.full_id
            if testcase_result.status == 'skip':
                continue  # don't report variations skipped due to shards
            marks = []
            if (
                    is_expected_failure(full_id, expected_failure_ids) or
                    is_locale_required(full_id, required_locale_by_ids, system_locale)
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
                id=testcase_result.testcase.full_id,
                marks=marks,
            )
            results.append(param)
        return results
    finally:
        PackageManager.close()  # type: ignore[no-untyped-call]
        PluginManager.close()


def test_id_matches(test_id: str, patterns: frozenset[str]) -> bool:
    if test_id in patterns:
        return True
    if any(fnmatch.fnmatch(test_id, pattern) for pattern in patterns):
        return True
    return False


def is_expected_failure(
        test_id: str,
        expected_failure_ids: frozenset[str],
) -> bool:
    return test_id_matches(test_id, expected_failure_ids)


def is_locale_required(
        test_id: str,
        required_locale_by_ids: dict[str, re.Pattern[str]],
        system_locale: str,
) -> bool:
    if test_id_matches(test_id, frozenset(required_locale_by_ids)):
        if not required_locale_by_ids[test_id].search(system_locale):
            return True
    return False
