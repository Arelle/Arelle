import argparse
import json
import multiprocessing
from typing import Any

import time
from pathlib import Path

from mypy.checkexpr import defaultdict

from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.logging.handlers.StructuredMessageLogHandler import StructuredMessageLogHandler
from test_suite.ActualError import ActualError
from test_suite.TestSuiteOptions import TestSuiteOptions
from test_suite.TestcaseConstraint import TestcaseConstraint
from test_suite.TestcaseConstraintResult import TestcaseConstraintResult
from test_suite.TestcaseConstraintSet import TestcaseConstraintSet
from test_suite.TestcaseResult import TestcaseResult
from test_suite.TestcaseVariation import TestcaseVariation


def _longestCommonPrefix(values: list[str]) -> str:
    if not values:
        return ""
    values = sorted(values)
    first = values[0]
    last = values[-1]

    # Use zip to iterate through characters of both strings simultaneously
    prefix = []
    for char1, char2 in zip(first, last):
        if char1 == char2:
            prefix.append(char1)
        else:
            break
    return "".join(prefix)


def _longestCommonSuffix(values: list[str]) -> str:
    values = [v[::-1] for v in values]
    return _longestCommonPrefix(values)[::-1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--index',
        help="Path or URL to the testcase index file.",
        required=True,
        type=str
    )
    parser.add_argument(
        '-p', '--parallel',
        help="Run testcases in parallel.",
        required=False,
        action='store_true',
    )
    parser.add_argument(
        '-o', '--options',
        help="JSON (or path to .json file) defining Arelle runtime options.",
        required=True,
        type=str
    )
    return parser.parse_args()


def loadTestcaseIndex(index_path: str) -> list[TestcaseVariation]:
    options = RuntimeOptions(
        entrypointFile=index_path,
        keepOpen=True,
        internetConnectivity='offline',
        internetRecheck='never',
        disablePersistentConfig=True,
        # validate=True,
    )
    with Session() as session:
        session.run(
            options,
            logHandler=StructuredMessageLogHandler(),
        )
        models = session.get_models()
        logs = session.get_log_messages()
        docs = []
        testcaseVariations = []
        for model in models:
            for doc in model.urlDocs.values():
                if hasattr(doc, 'testcaseVariations') and doc.testcaseVariations is not None:
                    docs.append(doc)
        uris = [doc.uri for doc in docs]
        prefix = _longestCommonPrefix(uris)
        suffix = _longestCommonSuffix(uris)
        for doc in docs:
            docUri = doc.uri.removeprefix(prefix).removesuffix(suffix)
            for testcaseVariation in doc.testcaseVariations:
                expected = testcaseVariation.expected
                errors = []
                if isinstance(expected, list):
                    for e in expected:
                        # TODO: testcase element
                        # TODO: testGroup element
                        # TODO: result element
                        # TODO: assert elements
                        # TODO: assertionTests elements
                        if isinstance(e, QName):
                            errors.append(TestcaseConstraint(
                                qname=e,
                                pattern=None,
                                min=1,
                                max=1,
                                warnings=False,
                                errors=True,
                            ))
                        elif isinstance(e, str):
                            errors.append(TestcaseConstraint(
                                qname=None,
                                pattern=e,
                                min=1,
                                max=1,
                                warnings=False,
                                errors=True,
                            ))
                        else:
                            raise ValueError(f"Unexpected expected error type: {type(e)}")

                testcaseConstraintSet = TestcaseConstraintSet(
                    errors=errors,
                    matchAll=True
                )
                testcaseVariations.append(TestcaseVariation(
                    id=testcaseVariation.id,
                    name=testcaseVariation.name,
                    description=testcaseVariation.description,
                    base=testcaseVariation.base,
                    readFirstUris=testcaseVariation.readMeFirstUris,
                    shortName=f"{docUri}:{testcaseVariation.id}",
                    status=testcaseVariation.status,
                    testcaseConstraintSet=testcaseConstraintSet
                ))
        return testcaseVariations


def runTestcaseVariationArgs(inputArgs: tuple[TestcaseVariation, dict[str, Any]]) -> TestcaseResult:
    testcaseVariation, runtimeOptions = inputArgs
    return runTestcaseVariation(testcaseVariation, runtimeOptions)


def runTestcaseVariation(
    testcaseVariation: TestcaseVariation,
    runtimeOptions: dict[str, Any],
) -> TestcaseResult:
    readMeFirstPaths = [
        str(Path(testcaseVariation.base).parent.joinpath(Path(readMeFirstUri)))
        for readMeFirstUri in testcaseVariation.readFirstUris
    ]
    entrypointFile = '|'.join(readMeFirstPaths)
    testcaseVariationOptions = RuntimeOptions(
        entrypointFile=entrypointFile,
        **runtimeOptions
    )
    with Session() as session:
        start_ts = time.perf_counter_ns()
        session.run(
            testcaseVariationOptions,
            logHandler=StructuredMessageLogHandler(),
        )
        duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
        # logs = session.get_log_messages()
        actualErrors = []
        for error in session._cntlr.errors:
            actualErrors.append(ActualError(
                qname=error if isinstance(error, QName) else None,
                code=str(error)
            ))
        for model in session.get_models():
            for error in model.errors:
                actualErrors.append(ActualError(
                    qname=error if isinstance(error, QName) else None,
                    code=str(error)
                ))
        result = buildResult(
            testcaseVariation=testcaseVariation,
            actualErrors=actualErrors,
            duration_seconds=duration_seconds,
        )
        return result


def runTestcaseVariationsInParallel(
    testcaseVariations: list[TestcaseVariation],
    runtimeOptions: dict[str, Any],
) -> list[TestcaseResult]:
    tasks = [
        (testcaseVariation, runtimeOptions)
        for testcaseVariation in testcaseVariations
    ]
    with multiprocessing.Pool() as pool:
        parallel_results = pool.map(runTestcaseVariationArgs, tasks)
        return parallel_results
    return results


def runTestcaseVariationsInSeries(
        testcaseVariations: list[TestcaseVariation],
        runtimeOptions: dict[str, Any],
) -> list[TestcaseResult]:
    results = []
    for testcaseVariation in testcaseVariations:
        result = runTestcaseVariation(testcaseVariation, runtimeOptions)
        print(result)
        results.append(result)
    return results


def _normalizedConstraints(testcaseVariation: TestcaseVariation) -> list[TestcaseConstraint]:
    normalizedConstraintsMap = {}
    for testcaseConstraint in testcaseVariation.testcaseConstraintSet.errors:
        key = (
            testcaseConstraint.qname,
            testcaseConstraint.pattern,
            testcaseConstraint.warnings,
            testcaseConstraint.errors
        )
        if key not in normalizedConstraintsMap:
            normalizedConstraintsMap[key] = (0, 0)
        minCount, maxCount = normalizedConstraintsMap[key]
        normalizedConstraintsMap[key] = (
            (minCount + (testcaseConstraint.min or 0)),
            (maxCount + (testcaseConstraint.max or 0))
        )
    normalizedConstraints = [
        TestcaseConstraint(
            qname=k[0],
            pattern=k[1],
            min=v[0] if v[0] > 0 else None,
            max=v[1] if v[1] > 0 else None,
            warnings=k[2],
            errors=k[3],
        )
        for k, v in normalizedConstraintsMap.items()
    ]
    return normalizedConstraints


def buildResult(
    testcaseVariation: TestcaseVariation,
    actualErrors: list[ActualError],
    duration_seconds: float,
) -> TestcaseResult:
    diff = {}
    anyPassed = False
    actualErrorCounts = defaultdict(int)
    for actualError in actualErrors:
        actualErrorCounts[actualError.qname or actualError.code] += 1
    constraints = _normalizedConstraints(testcaseVariation)
    for constraint in constraints:
        matchCount = 0
        for actualError, count in list(actualErrorCounts.items()):
            if (
                    (constraint.qname and actualError == constraint.qname) or
                    (constraint.qname and actualError == constraint.qname.localName) or
                    (constraint.pattern and constraint.pattern in actualError)
            ):
                if constraint.max is not None and count > constraint.max:
                    count = constraint.max
                matchCount += count
                actualErrorCounts[actualError] -= count
        if constraint.min is not None and matchCount < constraint.min:
            diff[constraint.qname or constraint.pattern] = matchCount - constraint.min
        elif constraint.max is not None and matchCount > constraint.max:
            diff[constraint.qname or constraint.pattern] = matchCount - constraint.max
        else:
            anyPassed = True
    for actualError, count in actualErrorCounts.items():
        if count == 0:
            continue
        diff[actualError] = count
    if testcaseVariation.testcaseConstraintSet.matchAll:
        diff = {
            k: v for k, v in diff.items() if v != 0
        }
        passed = len(diff) == 0
    else:
        passed = anyPassed
    constraintResults = [
        TestcaseConstraintResult(
            code=k,
            diff=v
        )
        for k, v in diff.items()
        if v != 0
    ]
    return TestcaseResult(
        testcaseVariation=testcaseVariation,
        actualErrors=actualErrors,
        constraintResults=constraintResults,
        passed=passed,
        skip=False,
        duration_seconds=duration_seconds,
    )


def run(options: TestSuiteOptions) -> list[TestcaseResult]:
    start_ts = time.perf_counter_ns()

    runtimeOptions = json.loads(options.options)

    testcaseVariations = loadTestcaseIndex(options.indexFile)
    print(f'Loaded {len(testcaseVariations)} testcase variations from {options.indexFile}')
    test_realtime_ts = time.perf_counter_ns()
    if options.parallel:
        print('Running in parallel...')
        results = runTestcaseVariationsInParallel(testcaseVariations, runtimeOptions)
    else:
        print('Running in series...')
        results = runTestcaseVariationsInSeries(testcaseVariations, runtimeOptions)
    test_realtime_duration_seconds = (time.perf_counter_ns() - test_realtime_ts) / 1_000_000_000
    passed = sum(1 for result in results if result.passed)
    failed = sum(1 for result in results if not result.passed)
    test_duration_seconds = sum(result.duration_seconds for result in results)
    duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
    print(
        f'Duration (seconds): '
        f'\n\tTest (Total):  \t{test_duration_seconds: .2f} (avg: {(test_duration_seconds / len(results)): .4f})'
        f'\n\tTest (Real):  \t{test_realtime_duration_seconds: .2f} (avg: {(test_realtime_duration_seconds / len(results)): .4f})'
        f'\n\tTotal: \t{duration_seconds: .2f}'
    )
    print(
        f'Results: '
        f'\n\tPassed: \t{passed}'
        f'\n\tFailed: \t{failed}'
        f'\n\tTotal:  \t{len(results)}'
    )
    return results


if __name__ == "__main__":
    args = parse_args()
    run(TestSuiteOptions(
        indexFile=args.index,
        options=args.options,
        parallel=args.parallel,
    ))

