"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict

import fnmatch
import json
import multiprocessing
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.UrlUtil import IXDS_DOC_SEPARATOR, IXDS_SURROGATE
from arelle.api.Session import Session
from arelle.testengine.ActualError import ActualError
from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestEngineResult import TestEngineResult
from arelle.testengine.TestcaseCompareContext import TestcaseCompareContext
from arelle.testengine.TestcaseConstraint import TestcaseConstraint
from arelle.testengine.TestcaseConstraintResult import TestcaseConstraintResult
from arelle.testengine.TestcaseConstraintSet import TestcaseConstraintSet
from arelle.testengine.TestcaseResult import TestcaseResult
from arelle.testengine.TestcaseVariation import TestcaseVariation
from arelle.testengine.TestcaseVariationSet import TestcaseVariationSet
from arelle.testengine.loader.TestcaseLoader import TestcaseLoader
from arelle.testengine.loader.XmlTestcaseLoader import XmlTestcaseLoader

CWD = Path.cwd()
DEFAULT_PLUGIN_OPTIONS = {
    'EDGAR/render': {
        'keepFilingOpen': True,
    },
    'xule': {
        "xule_time": 2.0,
        "xule_rule_stats_log": True,
    }
}
PARAMETER_SEPARATOR = '\n'
PROHIBITED_PLUGIN_OPTIONS = frozenset({
    'inlineTarget',
})
PROHIBITED_RUNTIME_OPTIONS = frozenset({
    'compareFormulaOutput',
    'compareInstance',
    'entrypointFile',
    'keepOpen',
    'logFile',
    'parameterSeparator',
    'parameters',
    'validate',
})
TARGET_SUFFIX_SEPARATOR = '|'
TESTCASE_LOADERS: list[TestcaseLoader] = [
    XmlTestcaseLoader()
]


def _block_codes(actual_errors: list[ActualError], pattern: str) -> tuple[list[ActualError], dict[str, int]]:
    results = []
    blocked_codes: dict[str, int] = defaultdict(int)
    if not pattern:
        return actual_errors, blocked_codes
    compiled_pattern = re.compile(re.sub(r'\\(.)', r'\1', pattern))
    for actual_error in actual_errors:
        if compiled_pattern.match(actual_error.code):
            blocked_codes[actual_error.code] += 1
            continue
        results.append(actual_error)
    return results, blocked_codes


def _build_entrypoint_uris(uris: list[Path]) -> list[str]:
    uris = [
        uri.relative_to(Path.cwd()) if uri.is_relative_to(Path.cwd()) else uri
        for uri in uris
    ]
    if len(uris) > 1:
        if all(uri.suffix in ('.htm', '.html', '.xhtml') for uri in uris):
            docset_surrogate_path = _norm_path(uris[0].parent) + os.sep + IXDS_SURROGATE
            return [docset_surrogate_path + IXDS_DOC_SEPARATOR.join(_norm_path(uri) for uri in uris)]
    return [_norm_path(uri) for uri in uris]


def _collect_errors(session: Session) -> list[str | None]:
    errors = []
    assert session._cntlr is not None
    errors.extend(session._cntlr.errors)
    for model in session.get_models():
        errors.extend(model.errors)
    return errors


def _load_testcase_index(test_engine_options: TestEngineOptions) -> TestcaseVariationSet:
    for loader in TESTCASE_LOADERS:
        if loader.is_loadable(test_engine_options):
            return loader.load(test_engine_options)
    raise ValueError(f'No testcase loader available for \"{test_engine_options.index_file}\".')


def _log_filename(name: str) -> str:
    name = re.sub(r'[<>:"|?*\x00-\x1F]', '_', name)
    return name.strip().strip('.')


def _norm_path(path: Path) -> str:
    path = path.relative_to(CWD) if path.is_relative_to(CWD) else path
    path_str = str(path)
    if path_str.startswith("file:\\"):
        path_str = path_str[6:]
    return unquote(path_str)


class TestEngine:
    _test_engine_options: TestEngineOptions

    def __init__(self, options: TestEngineOptions):
        self._test_engine_options = options

    def _build_result(
            self,
            testcase_variation: TestcaseVariation,
            actual_errors: list[ActualError],
            duration_seconds: float,
            additional_constraints: list[tuple[str, list[TestcaseConstraint]]],
    ) -> TestcaseResult:
        actual_error_counts: dict[tuple[str, ErrorLevel], int] = defaultdict(int)
        actual_errors, blocked_errors = _block_codes(actual_errors, testcase_variation.blocked_code_pattern)
        for actual_error in actual_errors:
            actual_error_counts[(actual_error.code, actual_error.level)] += 1
        applied_constraints = list(testcase_variation.testcase_constraint_set.constraints)
        for _filter, constraints in additional_constraints:
            if fnmatch.fnmatch(testcase_variation.full_id, f'*{_filter}'):
                applied_constraints.extend(constraints)
        applied_constraint_set = TestcaseConstraintSet(
            constraints=TestcaseConstraint.normalize_constraints(applied_constraints),
            match_all=testcase_variation.testcase_constraint_set.match_all
        )
        diff = self._get_diff(applied_constraint_set, actual_error_counts)
        if applied_constraint_set.match_all or len(applied_constraint_set.constraints) == 0:
            # Match any vs. all operate the same when there are no constraints (valid testcase).
            passed = all(d == 0 for d in diff.values())
        else:
            passed = any(d == 0 for d in diff.values())
        constraint_results = [
            TestcaseConstraintResult(
                code=_code,
                diff=_diff,
                level=_level,
            )
            for (_code, _level), _diff in diff.items()
        ]
        return TestcaseResult(
            actual_errors=actual_errors,
            applied_constraint_set=applied_constraint_set,
            blocked_errors=blocked_errors,
            constraint_results=constraint_results,
            duration_seconds=duration_seconds,
            passed=passed,
            skip=False,
            testcase_variation=testcase_variation,
        )

    def _filter_testcase_variation_set(self, testcase_variation_set: TestcaseVariationSet) -> TestcaseVariationSet:
        if not self._test_engine_options.filters:
            return testcase_variation_set
        testcase_variations = []
        skipped_testcase_variations = list(testcase_variation_set.skipped_testcase_variations)
        for testcase_variation in testcase_variation_set.testcase_variations:
            if any(
                    fnmatch.fnmatch(testcase_variation.full_id, _filter)
                    for _filter in self._test_engine_options.filters
            ):
                testcase_variations.append(testcase_variation)
            else:
                skipped_testcase_variations.append(testcase_variation)
        return TestcaseVariationSet(
            load_errors=testcase_variation_set.load_errors,
            skipped_testcase_variations=skipped_testcase_variations,
            testcase_variations=testcase_variations,
        )

    def _get_diff(self, testcase_constraint_set: TestcaseConstraintSet, actual_error_counts: dict[tuple[str, ErrorLevel], int] ) -> dict[tuple[str | QName, ErrorLevel], int]:
        diff = {}
        compare_context = TestcaseCompareContext(
            custom_compare_patterns=self._test_engine_options.custom_compare_patterns,
            local_name_map=XbrlConst.errMsgNamespaceLocalNameMap,
            prefix_namespace_uri_map=XbrlConst.errMsgPrefixNS,
        )
        for constraint in testcase_constraint_set.constraints:
            key_val = constraint.qname or constraint.pattern
            assert key_val is not None
            constraint_key = (key_val, constraint.level)
            match_count = 0
            for actual_key, count in actual_error_counts.items():
                actual_error, level = actual_key
                if level != constraint.level:
                    continue
                if compare_context.compare(constraint, actual_error):
                    match_count += count
                    actual_error_counts[actual_key] -= count
            # `count` is effectively a minimum. Occurences greater than `count` are accepted/ignored.
            if match_count < constraint.count:
                diff[constraint_key] = match_count - constraint.count
            else:
                diff[constraint_key] = 0
        for actual_key, count in actual_error_counts.items():
            if count == 0:
                continue
            actual_error, level = actual_key
            if level in (ErrorLevel.SATISIFED, ErrorLevel.OK):
                continue
            diff[actual_key] = count
        return diff

    def _run_testcase_variation(
            self,
            testcase_variation: TestcaseVariation,
    ) -> TestcaseResult:
        entrypoint_uris = _build_entrypoint_uris([
            Path(testcase_variation.base).parent.joinpath(Path(read_me_first_uri))
            for read_me_first_uri in testcase_variation.read_first_uris
        ])

        dynamic_options = dict(self._test_engine_options.options)
        for prohibited_option in PROHIBITED_RUNTIME_OPTIONS:
            assert prohibited_option not in dynamic_options, f'The option "{prohibited_option}" is reserved by the test engine.'
        if not dynamic_options.get('pluginOptions'):
            dynamic_options['pluginOptions'] = {}
        plugin_options = dynamic_options['pluginOptions']
        for prohibited_option in PROHIBITED_PLUGIN_OPTIONS:
            assert prohibited_option not in plugin_options, f'The plugin option "{prohibited_option}" is reserved by the test engine.'

        if testcase_variation.calc_mode is not None:
            assert dynamic_options.get('calcs', testcase_variation.calc_mode) == testcase_variation.calc_mode, \
                'Conflicting "calcs" values from testcase variation and user input.'
            dynamic_options['calcs'] = testcase_variation.calc_mode
        if 'plugins' in dynamic_options:
            for plugin in dynamic_options['plugins'].split('|'):
                plugin_options |= dynamic_options.get('pluginOptions', {}) | DEFAULT_PLUGIN_OPTIONS.get(plugin, {})

        if testcase_variation.inline_target:
            plugin_options['inlineTarget'] = testcase_variation.inline_target

        entrypoint_file = '|'.join(entrypoint_uris)
        runtime_options = RuntimeOptions(
            entrypointFile=entrypoint_file,
            keepOpen=True,
            validate=True,
            logFile=_norm_path(
                self._test_engine_options.log_directory / f"{_log_filename(testcase_variation.short_name)}-log.txt")
            if self._test_engine_options.log_directory else None,
            parameters=testcase_variation.parameters,
            parameterSeparator=PARAMETER_SEPARATOR,
            compareFormulaOutput=_norm_path(testcase_variation.compare_formula_output_uri) if testcase_variation.compare_formula_output_uri else None,
            compareInstance=_norm_path(testcase_variation.compare_instance_uri) if testcase_variation.compare_instance_uri else None,
            **dynamic_options
        )
        runtime_options_json = json.dumps({k: v for k, v in vars(runtime_options).items() if v is not None}, indent=4, sort_keys=True)
        if runtime_options.logFile is not None:
            Path(runtime_options.logFile).parent.mkdir(parents=True, exist_ok=True)
            with open(runtime_options.logFile, 'w') as f:
                f.write(f'Running [{testcase_variation.full_id}] with options:\n{runtime_options_json}\n------\n')
        with Session() as session:
            start_ts = time.perf_counter_ns()
            session.run(
                runtime_options,
            )
            duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
            actual_errors = []
            errors = _collect_errors(session)
            for error in errors:
                if isinstance(error, dict):
                    for code, counts in error.items():
                        assert isinstance(code, str)
                        satisfied_count, not_satisfied_count, ok_count, warning_count, error_count = counts
                        count_map = {
                            ErrorLevel.SATISIFED: satisfied_count,
                            ErrorLevel.NOT_SATISFIED: not_satisfied_count,
                            ErrorLevel.OK: ok_count,
                            ErrorLevel.WARNING: warning_count,
                            # Also captured as a separate "error"
                            # ErrorLevel.ERROR: error_count
                        }
                        for level, count in count_map.items():
                            if level in testcase_variation.ignore_levels:
                                continue
                            for i in range(0, count):
                                actual_errors.append(ActualError(
                                    code=code,
                                    level=level
                                ))
                    continue
                assert isinstance(error, str), f"Received actual error of unexpected type \"{type(error)}\"."
                actual_errors.append(ActualError(
                    code=error,
                    level=ErrorLevel.ERROR,
                ))
            result = self._build_result(
                testcase_variation=testcase_variation,
                actual_errors=actual_errors,
                duration_seconds=duration_seconds,
                additional_constraints=self._test_engine_options.additional_constraints
            )
            return result

    def _run_testcase_variation_args(self, input_args: tuple[TestcaseVariation]) -> TestcaseResult:
        testcase_variation, = input_args
        return self._run_testcase_variation(testcase_variation)

    def _run_testcase_variations_in_parallel(
            self,
            testcase_variations: list[TestcaseVariation],
    ) -> list[TestcaseResult]:
        tasks = [
            (testcase_variation,)
            for testcase_variation in testcase_variations
        ]
        # Some parts of Arelle and it's plugins have global state that is not reset.
        # Setting maxtasksperchild helps ensure global state does not persist between
        # two tasks run by the same child process.
        with multiprocessing.Pool(maxtasksperchild=1) as pool:
            results = pool.map(self._run_testcase_variation_args, tasks)
            for result in results:
                if not result.skip:
                    print(result.report())
            return results

    def _run_testcase_variations_in_series(
            self,
            testcase_variations: list[TestcaseVariation],
    ) -> list[TestcaseResult]:
        results = []
        for testcase_variation in testcase_variations:
            result = self._run_testcase_variation(testcase_variation)
            if not result.skip:
                print(result.report())
            results.append(result)
        return results

    def run(self) -> TestEngineResult:
        start_ts = time.perf_counter_ns()

        if self._test_engine_options.log_directory is not None:
            self._test_engine_options.log_directory.mkdir(parents=True, exist_ok=True)

        testcase_variation_set = _load_testcase_index(self._test_engine_options)
        testcase_variation_set = self._filter_testcase_variation_set(testcase_variation_set)
        testcase_variations = testcase_variation_set.testcase_variations
        print(f'Loaded {len(testcase_variations)} testcase variations from {self._test_engine_options.index_file}')
        test_realtime_ts = time.perf_counter_ns()
        if self._test_engine_options.parallel:
            print('Running in parallel...')
            results = self._run_testcase_variations_in_parallel(testcase_variations)
        else:
            print('Running in series...')
            results = self._run_testcase_variations_in_series(testcase_variations)
        for skipped_testcase_variation in testcase_variation_set.skipped_testcase_variations:
            results.append(TestcaseResult(
                actual_errors=[],
                applied_constraint_set=TestcaseConstraintSet(
                    constraints=[],
                    match_all=self._test_engine_options.match_all,
                ),
                blocked_errors={},
                constraint_results=[],
                duration_seconds=0,
                passed=True,
                skip=True,
                testcase_variation=skipped_testcase_variation,
            ))
        test_realtime_duration_seconds = (time.perf_counter_ns() - test_realtime_ts) / 1_000_000_000
        passed = sum(1 for result in results if result.passed and not result.skip)
        failed = sum(1 for result in results if not result.passed and not result.skip)
        skipped = sum(1 for result in results if result.skip)
        test_duration_seconds = sum(result.duration_seconds for result in results)
        duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
        print(
            f'Duration (seconds): '
            f'\n\tTest (Total):  \t{test_duration_seconds: .2f} (avg: {(test_duration_seconds / (len(results) or 1)): .4f})'
            f'\n\tTest (Real):  \t{test_realtime_duration_seconds: .2f} (avg: {(test_realtime_duration_seconds / (len(results) or 1)): .4f})'
            f'\n\tTotal: \t{duration_seconds: .2f}'
        )
        print(
            f'Results: '
            f'\n\tPassed: \t{passed}'
            f'\n\tFailed: \t{failed}'
            f'\n\tSkipped: \t{skipped}'
            f'\n\tTotal:  \t{len(results)}'
        )
        return TestEngineResult(
            testcase_results=results,
            testcase_variation_set=testcase_variation_set,
        )
