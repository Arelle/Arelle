"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
import argparse
import fnmatch
import json
import multiprocessing
import os
from collections import defaultdict
from pathlib import Path

import re
import time
from urllib.parse import unquote

from arelle.ModelObject import ModelObject
from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.UrlUtil import IXDS_DOC_SEPARATOR, IXDS_SURROGATE
from arelle.api.Session import Session
from test_engine.ActualError import ActualError
from test_engine.ErrorLevel import ErrorLevel
from test_engine.TestEngineOptions import TestEngineOptions
from test_engine.TestcaseConstraint import TestcaseConstraint
from test_engine.TestcaseConstraintResult import TestcaseConstraintResult
from test_engine.TestcaseConstraintSet import TestcaseConstraintSet
from test_engine.TestcaseResult import TestcaseResult
from test_engine.TestcaseVariation import TestcaseVariation

CWD = Path.cwd()
PARAMETER_SEPARATOR = '\n'
TARGET_SUFFIX_SEPARATOR = '|'
DEFAULT_PLUGIN_OPTIONS = {
    'EDGAR/render': {
        'keepFilingOpen': True,
    },
    'xule': {
        "xule_time": 2.0,
        "xule_rule_stats_log": True,
    }
}
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


def _hardcodedMatch(expected: str, actual: str) -> bool:
    # TODO: Sourced from legacy testcase variation processor. Replace with config.
    return (
            (expected == "EFM.6.03.04" and actual.startswith("xmlSchema:")) or
            (expected == "EFM.6.03.05" and (actual.startswith("xmlSchema:") or actual == "EFM.5.02.01.01")) or
            (expected == "EFM.6.04.03" and (actual.startswith("xmlSchema:") or actual.startswith("utr:") or actual.startswith("xbrl.") or actual.startswith("xlink:"))) or
            (expected == "EFM.6.05.35" and actual.startswith("utre:")) or
            (expected == "html:syntaxError" and actual.startswith("lxml.SCHEMA")) or
            (expected == "vere:invalidDTSIdentifier" and actual.startswith("xbrl")) or
            (expected.startswith("EFM.") and actual.startswith(expected)) or
            (expected.startswith("EXG.") and actual.startswith(expected))
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--index',
        help="Path or URL to the testcase index file.",
        required=True,
        type=str
    )
    parser.add_argument(
        '-e', '--error-code-substitutions',
        help="Replacement regex patterns to apply to error codes. Format: \"{pattern}|{replacement}\".",
        required=False,
        action='append',
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


def normPath(path: Path) -> str:
    path = path.relative_to(CWD) if path.is_relative_to(CWD) else path
    pathStr = str(path)
    if pathStr.startswith("file:\\"):
        pathStr = pathStr[6:]
    return unquote(pathStr)


def buildEntrypointUris(uris: list[Path]) -> list[str]:
    uris = [
        uri.relative_to(Path.cwd()) if uri.is_relative_to(Path.cwd()) else uri
        for uri in uris
    ]
    if len(uris) > 1:
        if all(uri.suffix in ('.htm', '.html', '.xhtml') for uri in uris):
            docsetSurrogatePath = normPath(uris[0].parent) + os.sep + IXDS_SURROGATE
            return [docsetSurrogatePath + IXDS_DOC_SEPARATOR.join(normPath(uri) for uri in uris)]
    return [normPath(uri) for uri in uris]


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
        for doc in docs:
            docPath = Path(doc.uri)
            docPath = docPath.relative_to(CWD) if docPath.is_relative_to(CWD) else docPath
            for testcaseVariation in doc.testcaseVariations:
                base = testcaseVariation.base
                assert base is not None
                if base.startswith("file:\\"):
                    base = base[6:]

                inlineTargets = [
                    instElt.get("target")
                    for resultElt in testcaseVariation.iterdescendants("{*}result")
                    for instElt in resultElt.iterdescendants("{*}instance")
                ] or [None]
                for inlineTarget in inlineTargets:
                    if len(inlineTargets) > 1 and inlineTarget is None:
                        inlineTarget = "(default)"
                    testcaseVariation.ixdsTarget = inlineTarget
                    assert TARGET_SUFFIX_SEPARATOR not in testcaseVariation.id, \
                        f"The '{TARGET_SUFFIX_SEPARATOR}' character is used internally as a separator " + \
                        "and can not be included in a testcase variation ID."
                    localId = f"{testcaseVariation.id}" + (f"{TARGET_SUFFIX_SEPARATOR}{inlineTarget}" if inlineTarget else "")
                    fullId = f"{base}:{localId}"

                    if testEngineOptions.filters:
                        if not any(fnmatch.fnmatch(fullId, _filter) for _filter in testEngineOptions.filters):
                            continue # TODO: Only filter here

                    # TODO: Improve
                    from arelle import XmlUtil
                    calcMode = None
                    resultElt = XmlUtil.descendant(testcaseVariation, None, "result")
                    if isinstance(resultElt, ModelObject):
                        calcMode = resultElt.attr('{https://xbrl.org/2023/conformance}mode')
                    if calcMode == 'truncate':
                        calcMode = 'truncation'

                    constraints = []
                    expected = testcaseVariation.expected or 'valid'
                    if not isinstance(expected, list):
                        expected = [expected]
                    for e in expected:
                        # TODO: table element
                        # TODO: testcase element
                        # TODO: testGroup element
                        # TODO: result element
                        # TODO: assert elements
                        # TODO: assertionTests elements
                        if e == 'valid':
                            pass
                        elif e == 'invalid':
                            constraints.append(TestcaseConstraint(
                                pattern='',  # matches any code
                                min=1,
                            ))
                        elif isinstance(e, QName):
                            constraints.append(TestcaseConstraint(
                                qname=e,
                                min=1,
                            ))
                        elif isinstance(e, str):
                            constraints.append(TestcaseConstraint(
                                pattern=e,
                                min=1,
                            ))
                        elif isinstance(e, dict):
                            for pattern, assertions in e.items():
                                satisfiedCount, notSatisfiedCount = assertions
                                countMap = {
                                    ErrorLevel.SATISIFED: satisfiedCount,
                                    ErrorLevel.NOT_SATISFIED: notSatisfiedCount,
                                }
                                for level, count in countMap.items():
                                    for i in range(0, count):
                                        constraints.append(TestcaseConstraint(
                                            pattern=pattern,
                                            level=level,
                                        ))
                        else:
                            raise ValueError(f"Unexpected expected error type: {type(e)}")

                    if testcaseVariation.resultTableUri is not None:
                        # Result table URIs are not currently validated
                        pass

                    expectedWarnings = testcaseVariation.expectedWarnings or []
                    for warning in expectedWarnings:
                        if isinstance(warning, QName):
                            constraints.append(TestcaseConstraint(
                                qname=warning,
                                min=1,
                                level=ErrorLevel.ERROR,  # TODO: Differentiate between errors and warnings
                            ))
                        elif isinstance(warning, str):
                            constraints.append(TestcaseConstraint(
                                pattern=warning,
                                min=1,
                                level=ErrorLevel.ERROR,  # TODO: Differentiate between errors and warnings
                            ))
                        else:
                            raise ValueError(f"Unexpected expected warning type: {type(e)}")

                    blockedCodePattern = testcaseVariation.blockedMessageCodes # restricts codes examined when provided

                    parameters = [
                        f'{k.clarkNotation}={v[1]}'
                        for k, v in testcaseVariation.parameters.items()
                    ]
                    if any(PARAMETER_SEPARATOR in parameter for parameter in parameters):
                        raise ValueError('Parameter separator found in parameter key or value.')

                    compareInstanceUri = None
                    compareFormulaOutputUri = None
                    instanceUri = testcaseVariation.resultXbrlInstanceUri
                    if instanceUri:
                        compareInstanceUri = Path(doc.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(instanceUri, testcaseVariation.base))
                        if testEngineOptions.compareFormulaOutput:
                            compareFormulaOutputUri = compareInstanceUri
                            compareInstanceUri = None

                    testcaseConstraintSet = TestcaseConstraintSet(
                        constraints=constraints,
                        matchAll=testEngineOptions.matchAll,
                    )
                    testcaseVariations.append(TestcaseVariation(
                        id=localId,
                        fullId=fullId,
                        name=testcaseVariation.name,
                        description=testcaseVariation.description,
                        base=base,
                        readFirstUris=testcaseVariation.readMeFirstUris,
                        shortName=f"{docPath}:{localId}",
                        status=testcaseVariation.status,
                        testcaseConstraintSet=testcaseConstraintSet,
                        blockedCodePattern=blockedCodePattern,
                        calcMode=calcMode,
                        parameters=PARAMETER_SEPARATOR.join(parameters),
                        ignoreLevels=testEngineOptions.ignoreLevels,
                        compareInstanceUri=compareInstanceUri,
                        compareFormulaOutputUri=compareFormulaOutputUri,
                        inlineTarget=inlineTarget,
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
    name = re.sub(r'[<>:"|?*\x00-\x1F]', '_', name)
    return name.strip().strip('.')

def buildActualError(
        testEngineOptions: TestEngineOptions,
        code: str,
        level: ErrorLevel,
) -> ActualError:
    if code is not None:
        for pattern, replacement in testEngineOptions.errorCodeSubstitutions:
            code = re.sub(pattern, replacement, code)
    return ActualError(
        code=code,
        level=level
    )


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
        Path(testcaseVariation.base).parent.joinpath(Path(readMeFirstUri))
        for readMeFirstUri in testcaseVariation.readFirstUris
    ])

    dynamicOptions = dict(testEngineOptions.options)
    for prohibitedOption in PROHIBITED_RUNTIME_OPTIONS:
        assert prohibitedOption not in dynamicOptions, f'The option "{prohibitedOption}" is reserved by the test engine.'
    if not dynamicOptions.get('pluginOptions'):
        dynamicOptions['pluginOptions'] = {}
    pluginOptions = dynamicOptions['pluginOptions']
    for prohibitedOption in PROHIBITED_PLUGIN_OPTIONS:
        assert prohibitedOption not in pluginOptions, f'The plugin option "{prohibitedOption}" is reserved by the test engine.'

    if testcaseVariation.calcMode is not None:
        assert dynamicOptions.get('calcs', testcaseVariation.calcMode) == testcaseVariation.calcMode, \
            'Conflicting "calcs" values from testcase variation and user input.'
        dynamicOptions['calcs'] = testcaseVariation.calcMode
    if 'plugins' in dynamicOptions:
        for plugin in dynamicOptions['plugins'].split('|'):
            pluginOptions |= dynamicOptions.get('pluginOptions', {}) | DEFAULT_PLUGIN_OPTIONS.get(plugin, {})

    if testcaseVariation.inlineTarget:
        pluginOptions['inlineTarget'] = testcaseVariation.inlineTarget

    entrypointFile = '|'.join(entrypointUris)
    runtimeOptions = RuntimeOptions(
        entrypointFile=entrypointFile,
        keepOpen=True,
        validate=True,
        logFile=normPath(testEngineOptions.logDirectory / f"{logFilename(testcaseVariation.shortName)}-log.txt") if testEngineOptions.logDirectory else None,
        parameters=testcaseVariation.parameters,
        parameterSeparator=PARAMETER_SEPARATOR,
        compareFormulaOutput=normPath(testcaseVariation.compareFormulaOutputUri) if testcaseVariation.compareFormulaOutputUri else None,
        compareInstance=normPath(testcaseVariation.compareInstanceUri) if testcaseVariation.compareInstanceUri else None,
        **dynamicOptions
    )
    runtimeOptionsJson = json.dumps({k: v for k, v in vars(runtimeOptions).items() if v is not None}, indent=4, sort_keys=True)
    if runtimeOptions.logFile is not None:
        Path(runtimeOptions.logFile).parent.mkdir(parents=True, exist_ok=True)
        with open(runtimeOptions.logFile, 'w') as f:
            f.write(f'Running [{testcaseVariation.fullId}] with options:\n{runtimeOptionsJson}\n------\n')
    with Session() as session:
        start_ts = time.perf_counter_ns()
        session.run(
            runtimeOptions,
            # logHandler=StructuredMessageLogHandler() if 'logFile' not in testEngineOptions.options else None, TODO
        )
        duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
        # logs = session.get_log_messages()
        actualErrors = []
        errors: list[str | None] = []
        assert session._cntlr is not None
        errors.extend(session._cntlr.errors)
        for model in session.get_models():
            errors.extend(model.errors)
        for error in errors:
            if isinstance(error, dict):
                for code, counts in error.items():
                    assert isinstance(code, str)
                    satisfiedCount, notSatisfiedCount, okCount, warningCount, errorCount = counts
                    countMap = {
                        ErrorLevel.SATISIFED: satisfiedCount,
                        ErrorLevel.NOT_SATISFIED: notSatisfiedCount,
                        ErrorLevel.OK: okCount,
                        ErrorLevel.WARNING: warningCount,
                        # Also captured as a separate "error"
                        # ErrorLevel.ERROR: errorCountÎ
                    }
                    for level, count in countMap.items():
                        if level in testcaseVariation.ignoreLevels:
                            continue
                        for i in range(0, count):
                            actualErrors.append(buildActualError(
                                testEngineOptions=testEngineOptions,
                                code=code,
                                level=level,
                            ))
                continue
            assert isinstance(error, str), f"Received actual error of unexpected type \"{type(error)}\"."
            # if error is None:
            #     print("Warning: Detected \"None\" actual error. Defaulted to \"ERROR\"")  # TODO
            #     error = "ERROR"
            # if isinstance(error, QName) or error is None:
            #     print(f"Warning: Flattened actual error QName to string: {error.clarkNotation}")  # TODO
            #     error = str(error)
            actualErrors.append(buildActualError(
                testEngineOptions=testEngineOptions,
                code=error,
                level=ErrorLevel.ERROR,
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
    # Some parts of Arelle and it's plugins have global state that is not reset.
    # Setting maxtasksperchild helps ensure global state does not persist between
    # two tasks run by the same child process.
    with multiprocessing.Pool(maxtasksperchild=1) as pool:
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
    normalizedConstraintsMap: dict[tuple[QName | None, str | None, ErrorLevel], tuple[int | None, int | None]] = {}
    for constraint in constraints:
        key = (
            constraint.qname,
            constraint.pattern,
            constraint.level,
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
            qname=_qname,
            pattern=_pattern,
            min=_min,
            max=_max,
            level=_level,
        )
        for (
            _qname,
            _pattern,
            _level,
        ), (_min, _max) in normalizedConstraintsMap.items()
    ]
    return normalizedConstraints


def blockCodes(actualErrors: list[ActualError], pattern: str) -> tuple[list[ActualError], dict[str, int]]:
    results = []
    blockedCodes: dict[str, int] = defaultdict(int)
    if not pattern:
        return actualErrors, blockedCodes
    compiledPattern = re.compile(re.sub(r'\\(.)', r'\1', pattern))
    for actualError in actualErrors:
        if compiledPattern.match(actualError.code):
            blockedCodes[actualError.code] += 1
            continue
        results.append(actualError)
    return results, blockedCodes

def getDiff(testcaseConstraintSet: TestcaseConstraintSet, actualErrorCounts: dict[tuple[str | QName, ErrorLevel], int] ) -> dict[tuple[str | QName, ErrorLevel], int]:
    diff = {}
    for constraint in testcaseConstraintSet.constraints:
        keyVal = constraint.qname or constraint.pattern
        assert keyVal is not None
        constraintKey = (keyVal, constraint.level)
        matchCount = 0
        for actualKey, count in actualErrorCounts.items():
            actualError, level = actualKey
            if level != constraint.level:
                continue
            if (
                    (isinstance(actualError, QName) and constraint.compareQname(actualError)) or
                    (isinstance(actualError, str) and constraint.compareCode(actualError)) or
                    (isinstance(actualError, str) and _hardcodedMatch(constraint.pattern or str(constraint.qname), actualError))
            ):
                if constraint.max is not None and count > constraint.max:
                    count = constraint.max
                matchCount += count
                actualErrorCounts[actualKey] -= count
        if constraint.min is not None and matchCount < constraint.min:
            diff[constraintKey] = matchCount - constraint.min
        elif constraint.max is not None and matchCount > constraint.max:
            diff[constraintKey] = matchCount - constraint.max
        else:
            diff[constraintKey] = 0
    for actualKey, count in actualErrorCounts.items():
        if count == 0:
            continue
        actualError, level = actualKey
        if level in (ErrorLevel.SATISIFED, ErrorLevel.OK):
            continue
        diff[actualKey] = count
    return diff

def buildResult(
    testcaseVariation: TestcaseVariation,
    actualErrors: list[ActualError],
    duration_seconds: float,
    additionalConstraints: list[tuple[str, list[TestcaseConstraint]]],
) -> TestcaseResult:
    actualErrorCounts: dict[tuple[QName | str, ErrorLevel], int] = defaultdict(int)
    actualErrors, blockedErrors = blockCodes(actualErrors, testcaseVariation.blockedCodePattern)
    for actualError in actualErrors:
        actualErrorCounts[(actualError.code, actualError.level)] += 1
    appliedConstraints = list(testcaseVariation.testcaseConstraintSet.constraints)
    for filter, constraints in additionalConstraints:
        if fnmatch.fnmatch(testcaseVariation.fullId, f'*{filter}'):
            appliedConstraints.extend(constraints)
    appliedConstraintSet = TestcaseConstraintSet(
        constraints=_normalizedConstraints(appliedConstraints),
        matchAll=testcaseVariation.testcaseConstraintSet.matchAll
    )
    diff = getDiff(appliedConstraintSet, actualErrorCounts)
    if appliedConstraintSet.matchAll or len(appliedConstraintSet.constraints) == 0: #TODO: matchAll/Any?
        # Match any vs. all operate the same when there are no constraints (valid testcase).
        passed = all(d == 0 for d in diff.values())
    else:
        passed = any(d == 0 for d in diff.values())
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
        compareFormulaOutput=False, # TODO
        errorCodeSubstitutions=[
            (re.compile(pattern), replacement)
            for part in args.error_code_subsitutions
            for pattern,sep,replacement in (part.partition('|'),)
        ],
        filters=args.filters,
        ignoreLevels=frozenset(), # TODO: CLI arg
        indexFile=args.index,
        logDirectory=Path(args.log_directory) if args.log_directory else None,
        matchAll=args.match_all,
        name=None,
        options=json.loads(args.options),
        parallel=args.parallel,
    ))
