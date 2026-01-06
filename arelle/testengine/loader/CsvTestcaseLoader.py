"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from io import TextIOWrapper

import csv
from pathlib import Path

from arelle.testengine.TestEngineOptions import TestEngineOptions
from arelle.testengine.TestcaseConstraint import TestcaseConstraint
from arelle.testengine.TestcaseConstraintSet import TestcaseConstraintSet
from arelle.testengine.TestcaseVariation import TestcaseVariation
from arelle.testengine.TestcaseVariationSet import TestcaseVariationSet
from arelle.testengine.loader.TestcaseLoader import TestcaseLoader, TESTCASE_LOADER_ERROR_PREFIX

REQUIRED_HEADERS = (
    "input",
    "errors",
)
OPTIONAL_HEADERS = (
    "report_count",
    "description",
)
SUPPORTED_HEADERS = REQUIRED_HEADERS + OPTIONAL_HEADERS

class CsvTestcaseLoader(TestcaseLoader):

    def __init__(self) -> None:
        super().__init__()

    def _open(self, test_engine_options: TestEngineOptions) -> TextIOWrapper:
        return open(test_engine_options.index_file, 'r')

    def is_loadable(self, test_engine_options: TestEngineOptions) -> bool:
        return test_engine_options.index_file.lower().endswith('.csv')

    def load(self, test_engine_options: TestEngineOptions) -> TestcaseVariationSet:
        """
        Load testcase variations from a CSV with predefined supported headers.
        :param test_engine_options:
        :return:
        """
        load_errors = []
        testcase_variations = []
        with self._open(test_engine_options) as file:
            reader = csv.reader(file)
            header = next(reader)
            missing_headers = sorted(set(REQUIRED_HEADERS) - set(header))
            if missing_headers:
                load_errors.append(f"{TESTCASE_LOADER_ERROR_PREFIX}: CSV file {test_engine_options.index_file} is missing required header(s): {missing_headers}")
            unsupported_headers = sorted(set(header) - set(SUPPORTED_HEADERS))
            if unsupported_headers:
                load_errors.append(f"{TESTCASE_LOADER_ERROR_PREFIX}: CSV file {test_engine_options.index_file} has unsupported header(s): {unsupported_headers}")
            items = []
            for row in reader:
                item = {}
                for col_index, value in enumerate(row):
                    col_name = header[col_index]
                    item[col_name] = value
                items.append(item)
            for item_index, item in enumerate(items):
                errors = item.get("errors", "")
                _input = item.get("input", "")
                report_count = item.get("report_count", None)
                local_id = Path(_input).stem
                full_id = f"{test_engine_options.index_file}:{local_id}"
                short_name = f"{Path(test_engine_options.index_file)}:{local_id}"
                testcase_constraints = []
                for error in errors.split():
                    testcase_constraints.append(TestcaseConstraint(
                        count=1,
                        pattern=error
                    ))
                testcase_constraint_set = TestcaseConstraintSet(
                    constraints=testcase_constraints,
                    match_all=test_engine_options.match_all,
                )
                testcase_variations.append(TestcaseVariation(
                    base=test_engine_options.index_file,
                    blocked_code_pattern="",
                    calc_mode=None,
                    compare_formula_output_uri=None,
                    compare_instance_uri=None,
                    description=item.get('description', full_id),
                    full_id=full_id,
                    id=full_id,
                    ignore_levels=test_engine_options.ignore_levels,
                    inline_target=None,
                    name=local_id,
                    parameters="",
                    read_first_uris=[str(_input)],
                    report_count=int(report_count) if report_count is not None else None,
                    short_name=short_name,
                    status="",
                    testcase_constraint_set=testcase_constraint_set,
                ))
        return TestcaseVariationSet(
            load_errors=load_errors,
            skipped_testcase_variations=[],
            testcase_variations=testcase_variations
        )
