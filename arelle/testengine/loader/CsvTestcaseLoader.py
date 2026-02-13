"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import csv
from io import TextIOWrapper
from pathlib import Path

from arelle.testengine.Constraint import Constraint
from arelle.testengine.ConstraintSet import ConstraintSet
from arelle.testengine.Testcase import Testcase
from arelle.testengine.TestcaseSet import TestcaseSet
from arelle.testengine.loader.TestcaseLoader import TestcaseLoader

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

    def _open(self, index_file: Path) -> TextIOWrapper:
        return open(index_file, 'r')

    def is_loadable(self, index_file: Path) -> bool:
        return index_file.name.lower().endswith('.csv')

    def load(self, index_file: Path) -> TestcaseSet:
        """
        Load testcases from a CSV with predefined supported headers.
        :param index_file:
        :return:
        """
        load_errors = []
        testcases = []
        base = index_file.absolute()
        root_dir = index_file.parent
        canonical_path = index_file.relative_to(root_dir).as_posix()
        with self._open(index_file) as file:
            reader = csv.reader(file)
            header = next(reader)
            missing_headers = sorted(set(REQUIRED_HEADERS) - set(header))
            if missing_headers:
                load_errors.append(f"CSV file {index_file} is missing required header(s): {missing_headers}")
            unsupported_headers = sorted(set(header) - set(SUPPORTED_HEADERS))
            if unsupported_headers:
                load_errors.append(f"CSV file {index_file} has unsupported header(s): {unsupported_headers}")
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
                full_id = f"{canonical_path}:{local_id}"
                constraints = []
                for error in errors.split():
                    constraints.append(Constraint(
                        count=1,
                        pattern=error
                    ))
                constraint_set = ConstraintSet(
                    constraints=constraints,
                    match_all=False,
                )
                testcases.append(Testcase(
                    base=base,
                    blocked_code_pattern="",
                    calc_mode=None,
                    compare_instance_uri=None,
                    description=item.get('description', full_id),
                    expected_instance_count=int(report_count) if report_count is not None else None,
                    full_id=full_id,
                    inline_target=None,
                    local_id=local_id,
                    name=local_id,
                    parameters="",
                    read_first_uris=[str(_input)],
                    status="",
                    constraint_set=constraint_set,
                ))
        return TestcaseSet(
            load_errors=load_errors,
            skipped_testcases=[],
            testcases=testcases
        )
