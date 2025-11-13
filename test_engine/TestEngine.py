import argparse
import fnmatch
import json
import multiprocessing
import os
from collections import defaultdict
from pathlib import Path

import regex
import time

from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.logging.handlers.StructuredMessageLogHandler import StructuredMessageLogHandler
from arelle.plugin.inlineXbrlDocumentSet import IXDS_SURROGATE, IXDS_DOC_SEPARATOR
from test_engine.ActualError import ActualError
from test_engine.TestEngineOptions import TestEngineOptions
from test_engine.TestcaseConstraint import TestcaseConstraint
from test_engine.TestcaseConstraintResult import TestcaseConstraintResult
from test_engine.TestcaseConstraintSet import TestcaseConstraintSet
from test_engine.TestcaseResult import TestcaseResult
from test_engine.TestcaseVariation import TestcaseVariation


def _longestCommonPrefix(values: list[str]) -> str:
    if not values:
        return ""
    values = sorted(values)
    first = Path(values[0]).parts
    last = Path(values[-1]).parts

    # Use zip to iterate through characters of both strings simultaneously
    prefix = []
    for char1, char2 in zip(first, last):
        if char1 == char2:
            prefix.append(char1)
        else:
            break
    return str(Path(*prefix)) + os.sep


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
        '-f', '--filters',
        help="Filter patterns to determine testcase variations to include.",
        required=False,
        action='append',
    )
    parser.add_argument(
        '-l', '--log-directory',
        help="Directory to write log files and test reports to.",
        required=False,
        type=str
    )
    parser.add_argument(
        '-m', '--match-all',
        help="Whether tests results need to match all of the expected errors/warnings to pass.",
        required=False,
        action='store_true',
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


def buildEntrypointUris(uris: list[str]) -> list[str]:
    if len(uris) > 1:
        paths = [Path(uri) for uri in uris]
        if all(path.suffix in ('.htm', '.html', '.xhtml') for path in paths):
            docsetSurrogatePath = os.path.join(os.path.dirname(uris[0]), IXDS_SURROGATE)
            return [docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(uris)]
    return uris


def loadTestcaseIndex(index_path: str, testEngineOptions: TestEngineOptions) -> list[TestcaseVariation]:
    runtimeOptions = RuntimeOptions(
        entrypointFile=index_path,
        keepOpen=True,
        # internetConnectivity='offline',
        # internetRecheck='never',
        # disablePersistentConfig=True,
        # validate=True,
    )
    with Session() as session:
        session.run(
            runtimeOptions,
            # logHandler=StructuredMessageLogHandler(), TODO
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
                fullId = f"{testcaseVariation.base}:{testcaseVariation.id}" # TODO: Defined twice
                if testEngineOptions.filters:
                    if not any(fnmatch.fnmatch(fullId, filter) for filter in testEngineOptions.filters):
                        continue # TODO: Only filter here

                # TODO: Improve
                from arelle import XmlUtil
                resultElt = XmlUtil.descendant(testcaseVariation, None, "result")
                calcMode = resultElt.attr('{https://xbrl.org/2023/conformance}mode')
                if calcMode == 'truncate':
                    calcMode = 'truncation'

                expected = testcaseVariation.expected
                constraints = []
                if expected == 'invalid':
                    constraints.append(TestcaseConstraint(
                        qname=None,
                        pattern='',  # matches any code
                        min=1,
                        max=None,
                        warnings=False,
                        errors=True,
                    ))
                elif isinstance(expected, list):
                    for e in expected:
                        # TODO: testcase element
                        # TODO: testGroup element
                        # TODO: result element
                        # TODO: assert elements
                        # TODO: assertionTests elements
                        if isinstance(e, QName):
                            constraints.append(TestcaseConstraint(
                                qname=e,
                                pattern=None,
                                min=1,
                                max=None,
                                warnings=False,
                                errors=True,
                            ))
                        elif isinstance(e, str):
                            constraints.append(TestcaseConstraint(
                                qname=None,
                                pattern=e,
                                min=1,
                                max=None,
                                warnings=False,
                                errors=True,
                            ))
                        else:
                            raise ValueError(f"Unexpected expected error type: {type(e)}")
                expectedWarnings = testcaseVariation.expectedWarnings or []
                for warning in expectedWarnings:
                    if isinstance(warning, QName):
                        constraints.append(TestcaseConstraint(
                            qname=warning,
                            pattern=None,
                            min=1,
                            max=None,
                            warnings=True,
                            errors=False,
                        ))
                    elif isinstance(warning, str):
                        constraints.append(TestcaseConstraint(
                            qname=None,
                            pattern=warning,
                            min=1,
                            max=None,
                            warnings=True,
                            errors=False,
                        ))

                blockedCodePattern = testcaseVariation.blockedMessageCodes # restricts codes examined when provided

                testcaseConstraintSet = TestcaseConstraintSet(
                    constraints=constraints,
                    matchAll=testEngineOptions.matchAll,
                )
                testcaseVariations.append(TestcaseVariation(
                    id=testcaseVariation.id,
                    name=testcaseVariation.name,
                    description=testcaseVariation.description,
                    base=testcaseVariation.base,
                    readFirstUris=testcaseVariation.readMeFirstUris,
                    shortName=f"{docUri}:{testcaseVariation.id}",
                    status=testcaseVariation.status,
                    testcaseConstraintSet=testcaseConstraintSet,
                    blockedCodePattern=blockedCodePattern,
                    calcMode=calcMode,
                ))
        return testcaseVariations


def runTestcaseVariationArgs(inputArgs: tuple[TestcaseVariation, TestEngineOptions]) -> TestcaseResult:
    testcaseVariation, testEngineOptions = inputArgs
    return runTestcaseVariation(testcaseVariation, testEngineOptions)


def filterTestcaseVariation(testcaseVariation: TestcaseVariation, filters: list[str]) -> bool:
    if not filters:
        return True
    variationId = testcaseVariation.fullId
    for filter in filters:
        if fnmatch.fnmatch(variationId, filter):
            return True
    return False


def logFilename(name: str) -> str:
    name = regex.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)
    return name.strip().strip('.')


def runTestcaseVariation(
    testcaseVariation: TestcaseVariation,
    testEngineOptions: TestEngineOptions,
) -> TestcaseResult:
    if not filterTestcaseVariation(testcaseVariation, testEngineOptions.filters):
        return TestcaseResult(
            testcaseVariation=testcaseVariation,
            appliedConstraintSet=TestcaseConstraintSet(constraints=[], matchAll=testEngineOptions.matchAll),
            actualErrors=[],
            constraintResults=[],
            passed=True,
            skip=True,
            duration_seconds=0,
            blockedErrors={},
        )
    entrypointUris = buildEntrypointUris([
        str(Path(testcaseVariation.base).parent.joinpath(Path(readMeFirstUri)))
        for readMeFirstUri in testcaseVariation.readFirstUris
    ])
    dynamicOptions = dict(testEngineOptions.options)
    if testcaseVariation.calcMode is not None:
        dynamicOptions['calcs'] = testcaseVariation.calcMode
    entrypointFile = '|'.join(entrypointUris)
    runtimeOptions = RuntimeOptions(
        entrypointFile=entrypointFile,
        logFile=str(testEngineOptions.logDirectory / f"{logFilename(testcaseVariation.shortName)}-log.txt"),
        **dynamicOptions
    )
    print("Running with options: ", json.dumps({k: v for k, v in vars(runtimeOptions).items() if v is not None}, indent=4, sort_keys=True))
    with Session() as session:
        start_ts = time.perf_counter_ns()
        session.run(
            runtimeOptions,
            # logHandler=StructuredMessageLogHandler() if 'logFile' not in testEngineOptions.options else None, TODO
        )
        duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
        # logs = session.get_log_messages()
        actualErrors = []
        for error in session._cntlr.errors:
            actualErrors.append(ActualError(
                assertions=error if isinstance(error, dict) else None,
                code=error if isinstance(error, str) else None,
                qname=error if isinstance(error, QName) else None,
            ))
        for model in session.get_models():
            for error in model.errors:
                actualErrors.append(ActualError(
                    assertions=error if isinstance(error, dict) else None,
                    code=error if isinstance(error, str) else None,
                    qname=error if isinstance(error, QName) else None,
                ))
        result = buildResult(
            testcaseVariation=testcaseVariation,
            actualErrors=actualErrors,
            duration_seconds=duration_seconds,
            additionalConstraints=testEngineOptions.additionalConstraints
        )
        return result


def runTestcaseVariationsInParallel(
    testcaseVariations: list[TestcaseVariation],
    testEngineOptions: TestEngineOptions,
) -> list[TestcaseResult]:
    tasks = [
        (testcaseVariation, testEngineOptions)
        for testcaseVariation in testcaseVariations
    ]
    with multiprocessing.Pool() as pool:
        results = pool.map(runTestcaseVariationArgs, tasks)
        for result in results:
            if not result.skip:
                print(result.report())
        return results

def runTestcaseVariationsInSeries(
        testcaseVariations: list[TestcaseVariation],
        testEngineOptions: TestEngineOptions,
) -> list[TestcaseResult]:
    results = []
    for testcaseVariation in testcaseVariations:
        result = runTestcaseVariation(testcaseVariation, testEngineOptions)
        if not result.skip:
            print(result.report())
        results.append(result)
    return results


def _normalizedConstraints(
        constraints: list[TestcaseConstraint]
) -> list[TestcaseConstraint]:
    normalizedConstraintsMap = {}
    for constraint in constraints:
        key = (
            constraint.qname,
            constraint.pattern,
            constraint.warnings,
            constraint.errors
        )
        if key not in normalizedConstraintsMap:
            normalizedConstraintsMap[key] = (None, None)
        minCount, maxCount = normalizedConstraintsMap[key]
        normalizedConstraintsMap[key] = (
            constraint.min if minCount is None else (minCount + (constraint.min or 0)),
            constraint.max if maxCount is None else (maxCount + (constraint.max or 0))
        )
    normalizedConstraints = [
        TestcaseConstraint(
            qname=k[0],
            pattern=k[1],
            min=v[0],
            max=v[1],
            warnings=k[2],
            errors=k[3],
        )
        for k, v in normalizedConstraintsMap.items()
    ]
    return normalizedConstraints


def blockCodes(actualErrors: list[ActualError], pattern: str) -> tuple[list[ActualError], dict[str, int]]:
    results = []
    blockedCodes = defaultdict(int)
    if not pattern:
        return actualErrors, blockedCodes
    compiledPattern = regex.compile(regex.sub(r'\\(.)', r'\1', pattern))
    for actualError in actualErrors:
        value = str(actualError.qname or actualError.code or actualError.assertions)
        if compiledPattern.match(value):
            blockedCodes[value] += 1
            continue
        results.append(actualError)
    return results, blockedCodes

def buildResult(
    testcaseVariation: TestcaseVariation,
    actualErrors: list[ActualError],
    duration_seconds: float,
    additionalConstraints: list[tuple[str, list[TestcaseConstraint]]],
) -> TestcaseResult:
    diff = {}
    actualErrorCounts = defaultdict(int)
    actualErrors, blockedErrors = blockCodes(actualErrors, testcaseVariation.blockedCodePattern)
    for actualError in actualErrors:
        if actualError.assertions is not None:
            # TODO:  Whether or not to validate formula assertions
            # Look into formula conformance suite:
            #   <assertionTests
            #          assertionID="assertion"
            #          countSatisfied="0"
            #          countNotSatisfied="1" />
            if False:
                for code, counts in actualError.assertions.items():
                    satisfiedCount, notSatisfiedCount, okCount, warningCount, errorCount = counts
                    actualErrorCounts[code] += notSatisfiedCount + warningCount + errorCount
        else:
            actualErrorCounts[actualError.qname or actualError.code] += 1
    appliedConstraints = list(testcaseVariation.testcaseConstraintSet.constraints)
    for filter, constraints in additionalConstraints:
        if fnmatch.fnmatch(testcaseVariation.fullId, f'*{filter}'):
            appliedConstraints.extend(constraints)
    appliedConstraintSet = TestcaseConstraintSet(
        constraints=_normalizedConstraints(appliedConstraints),
        matchAll=testcaseVariation.testcaseConstraintSet.matchAll
    )
    anyPassed = False
    for constraint in appliedConstraintSet.constraints:
        matchCount = 0
        for actualError, count in list(actualErrorCounts.items()):
            if (
                    (constraint.qname is not None and actualError == constraint.qname) or
                    (constraint.qname is not None and actualError == str(constraint.qname)) or
                    (constraint.qname is not None and actualError == constraint.qname.localName) or
                    (constraint.qname is not None and actualError.split('.')[-1] == constraint.qname.localName) or
                    (constraint.pattern is not None and constraint.pattern in actualError)
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
    if appliedConstraintSet.matchAll: #TODO: matchAll/Any?
        passed = all(d == 0 for d in diff.values())
    else:
        if len(appliedConstraintSet.constraints) > 0:
            passed = anyPassed
        else:
            passed = True
    constraintResults = [
        TestcaseConstraintResult(
            code=k,
            diff=v
        )
        for k, v in diff.items()
    ]
    return TestcaseResult(
        testcaseVariation=testcaseVariation,
        appliedConstraintSet=appliedConstraintSet,
        actualErrors=actualErrors,
        constraintResults=constraintResults,
        passed=passed,
        skip=False,
        duration_seconds=duration_seconds,
        blockedErrors=blockedErrors,
    )


def run(testEngineOptions: TestEngineOptions) -> list[TestcaseResult]:
    start_ts = time.perf_counter_ns()

    if testEngineOptions.logDirectory is not None:
        testEngineOptions.logDirectory.mkdir(parents=True, exist_ok=True)

    testcaseVariations = loadTestcaseIndex(testEngineOptions.indexFile, testEngineOptions)
    print(f'Loaded {len(testcaseVariations)} testcase variations from {testEngineOptions.indexFile}')
    test_realtime_ts = time.perf_counter_ns()
    if testEngineOptions.parallel:
        print('Running in parallel...')
        results = runTestcaseVariationsInParallel(testcaseVariations, testEngineOptions)
    else:
        print('Running in series...')
        results = runTestcaseVariationsInSeries(testcaseVariations, testEngineOptions)
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
    return results


if __name__ == "__main__":
    args = parse_args()
    run(TestEngineOptions(
        additionalConstraints=[],
        filters=args.filters,
        indexFile=args.index,
        logDirectory=Path(args.log_directory),
        matchAll=args.match_all,
        options=json.loads(args.options),
        parallel=args.parallel,
    ))

