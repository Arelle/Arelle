"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from arelle.ModelValue import QName
from arelle.testengine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestcaseCompareContext:
    custom_compare_patterns: list[tuple[str, str]] = field(default_factory=list)
    local_name_map: dict[str | None, dict[str, str]] = field(default_factory=dict)
    prefix_namespace_uri_map: dict[str | None, str] = field(default_factory=dict)

    @staticmethod
    def _compare_code(testcase_constraint: TestcaseConstraint, code: str) -> bool:
        if testcase_constraint.qname is not None:
            if str(testcase_constraint.qname) == code:
                return True
            if testcase_constraint.qname.localName == code:
                return True
        if testcase_constraint.pattern is not None:
            if testcase_constraint.pattern == code:
                return True
        return False

    @staticmethod
    def _compare_qname(testcase_constraint: TestcaseConstraint, qname: QName) -> bool:
        if qname is None:
            return False
        if testcase_constraint.qname is None:
            if testcase_constraint.pattern == qname.localName:
                return True
        if testcase_constraint.qname == qname:
            return True
        return False

    def _compare_custom_patterns(self, expected: str, actual: str) -> bool:
        for expected_pattern, actual_pattern in self.custom_compare_patterns:
            if re.fullmatch(expected_pattern, expected):
                actual_pattern = actual_pattern.replace('~', expected)
                if re.fullmatch(actual_pattern, actual):
                    return True
        return False

    def compare(self, testcase_constraint: TestcaseConstraint, actual_error: str) -> bool:
        if testcase_constraint.pattern == "*":
            return True
        if TestcaseCompareContext._compare_code(testcase_constraint, actual_error):
            return True
        qname = self.map_to_qname(actual_error)
        if self._compare_qname(testcase_constraint, qname):
            return True
        return self._compare_custom_patterns(testcase_constraint.pattern or str(testcase_constraint.qname), actual_error)

    def map_to_qname(self, actual_error: str) -> QName:
        prefix, sep, local_name = actual_error.rpartition(':')
        namespace_uri = self.prefix_namespace_uri_map.get(prefix)
        local_name = self.local_name_map.get(namespace_uri, {}).get(local_name, local_name)
        return QName(prefix, namespace_uri, local_name)
