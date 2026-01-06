"""
See COPYRIGHT.md for copyright information.
"""
import argparse
import json
from pathlib import Path

from arelle.testengine.TestEngine import TestEngine
from arelle.testengine.TestEngineOptions import TestEngineOptions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--index',
        help="Path or URL to the testcase index file.",
        required=True,
        type=str
    )
    parser.add_argument(
        '--custom-compare-patterns',
        help="Custom comparison of expected/actual error codes. Format: \"{expected}|{actual}\". \"~\" in actual is replaced with the expected code.",
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


if __name__ == "__main__":
    args = parse_args()
    testEngine = TestEngine(TestEngineOptions(
        additionalConstraints=[],
        compareFormulaOutput=False, # TODO
        customComparePatterns=[
            (expected, actual)
            for part in args.custom_compare_patterns
            for expected, sep, actual in (part.partition('|'),)
        ],
        filters=args.filters,
        ignoreLevels=frozenset(), # TODO: CLI arg
        indexFile=args.index,
        logDirectory=Path(args.log_directory) if args.log_directory else None,
        matchAll=args.match_all,
        name=None,
        options=json.loads(args.options),  # TODO
        parallel=args.parallel,
    ))
    testEngine.run()
