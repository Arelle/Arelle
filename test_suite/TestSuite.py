import argparse
import time
from pathlib import Path

from arelle.ModelValue import QName
from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session
from arelle.logging.handlers.StructuredMessageLogHandler import StructuredMessageLogHandler
from test_suite.ActualError import ActualError
from test_suite.ExpectedErrorConstraint import ExpectedErrorConstraint
from test_suite.ExpectedErrorSet import ExpectedErrorSet
from test_suite.TestcaseResult import TestcaseResult
from test_suite.TestcaseVariation import TestcaseVariation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--index',
        help="Path or URL to the testcase index file.",
        required=True,
        type=str
    )
    parser.add_argument(
        '-p', '--plugins',
        help="Plugins to activate.",
        required=False,
        type=str,
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
        testcaseVariations = []
        for model in models:
            for doc in model.urlDocs.values():
                if hasattr(doc, 'testcaseVariations') and doc.testcaseVariations is not None:
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
                                    errors.append(ExpectedErrorConstraint(
                                        qname=e,
                                        pattern=None,
                                        min=1,
                                        max=1,
                                        warnings=False,
                                        errors=True,
                                    ))
                                elif isinstance(e, str):
                                    errors.append(ExpectedErrorConstraint(
                                        qname=None,
                                        pattern=e,
                                        min=1,
                                        max=1,
                                        warnings=False,
                                        errors=True,
                                    ))
                                else:
                                    raise ValueError(f"Unexpected expected error type: {type(e)}")

                        expectedErrorSet = ExpectedErrorSet(
                            errors=errors,
                            matchAll=True
                        )
                        testcaseVariations.append(TestcaseVariation(
                            id=testcaseVariation.id,
                            name=testcaseVariation.name,
                            description=testcaseVariation.description,
                            base=testcaseVariation.base,
                            readFirstUris=testcaseVariation.readMeFirstUris,
                            status=testcaseVariation.status,
                            expectedErrorSet=expectedErrorSet
                        ))
        return testcaseVariations


def runTestcaseVariations(
    testcaseVariations: list[TestcaseVariation],
) -> list[TestcaseResult]:
    results = []
    for testcaseVariation in testcaseVariations:
        readMeFirstPaths = [
            str(Path(testcaseVariation.base).parent.joinpath(Path(readMeFirstUri)))
            for readMeFirstUri in testcaseVariation.readFirstUris
        ]
        entrypointFile = '|'.join(readMeFirstPaths)
        testcaseVariationOptions = RuntimeOptions(
            entrypointFile=entrypointFile,
            keepOpen=True,
            validate=True,
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
            print(result)
            results.append(result)
    return results


def buildResult(
    testcaseVariation: TestcaseVariation,
    actualErrors: list[ActualError],
    duration_seconds: float,
) -> TestcaseResult:
    diff = {}
    anyPassed = False
    for expectedErrorConstraint in testcaseVariation.expectedErrorSet.errors:
        count = sum(
            1 for error in actualErrors
            if (error.qname == expectedErrorConstraint.qname or
                (expectedErrorConstraint.pattern and expectedErrorConstraint.pattern in error.code))
        )
        if expectedErrorConstraint.min is not None and count < expectedErrorConstraint.min:
            diff[expectedErrorConstraint.qname or expectedErrorConstraint.pattern] = -count
        elif expectedErrorConstraint.max is not None and count > expectedErrorConstraint.max:
            diff[expectedErrorConstraint.qname or expectedErrorConstraint.pattern] = count
        else:
            anyPassed = True
    if testcaseVariation.expectedErrorSet.matchAll:
        passed = len(diff) == 0
    else:
        passed = anyPassed
    return TestcaseResult(
        testcaseVariation=testcaseVariation,
        actualErrors=actualErrors,
        diff=diff,
        passed=passed,
        duration_seconds=duration_seconds,
    )


def run():
    start_ts = time.perf_counter_ns()
    args = parse_args()
    testcaseVariations = loadTestcaseIndex(args.index)
    print(f'Loaded {len(testcaseVariations)} testcase variations from {args.index}')
    results = runTestcaseVariations(testcaseVariations)
    passed = sum(1 for result in results if result.passed)
    failed = sum(1 for result in results if not result.passed)
    test_duration_seconds = sum(result.duration_seconds for result in results)
    duration_seconds = (time.perf_counter_ns() - start_ts) / 1_000_000_000
    print(
        f'Duration (seconds): '
        f'\n\tTest:  \t{test_duration_seconds: .2f} (avg: {(test_duration_seconds / len(results)): .4f})'
        f'\n\tOther: \t{(duration_seconds - test_duration_seconds): .2f}'
        f'\n\tTotal: \t{duration_seconds: .2f}'
    )
    print(
        f'Results: '
        f'\n\tPassed: \t{passed}'
        f'\n\tFailed: \t{failed}'
        f'\n\tTotal:  \t{len(results)}'
    )


if __name__ == "__main__":
    run()

