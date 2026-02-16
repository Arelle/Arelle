"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from arelle.ModelValue import QName
from arelle.testengine.Constraint import Constraint


@dataclass(frozen=True)
class CompareContext:
    custom_compare_patterns: list[tuple[str, str]] = field(default_factory=list)
    local_name_map: dict[str | None, dict[str, str]] = field(default_factory=dict)
    prefix_namespace_uri_map: dict[str | None, str] = field(default_factory=dict)

    @staticmethod
    def _compare_code(constraint: Constraint, code: str) -> bool:
        if constraint.qname is not None:
            if str(constraint.qname) == code:
                return True
            if constraint.qname.localName == code:
                return True
        if constraint.pattern is not None:
            if constraint.pattern == code:
                return True
        return False

    @staticmethod
    def _compare_qname(constraint: Constraint, qname: QName) -> bool:
        if qname is None:
            return False
        if constraint.qname is None:
            if constraint.qname is None:
                return constraint.pattern == qname.localName
        if constraint.qname == qname:
            return True
        return False

    def _compare_custom_patterns(self, expected: str, actual: str) -> bool:
        for expected_pattern, actual_pattern in self.custom_compare_patterns:
            if re.fullmatch(expected_pattern, expected):
                actual_pattern = actual_pattern.replace('~', expected)
                if re.fullmatch(actual_pattern, actual):
                    return True
        return False

    def compare(self, constraint: Constraint, actual_error: str) -> bool:
        if constraint.pattern == "*":
            return True
        if CompareContext._compare_code(constraint, actual_error):
            return True
        qname = self.map_to_qname(actual_error)
        if self._compare_qname(constraint, qname):
            return True
        return self._compare_custom_patterns(constraint.pattern or str(constraint.qname), actual_error)

    def map_to_qname(self, actual_error: str) -> QName:
        prefix, sep, local_name = actual_error.rpartition(':')
        namespace_uri = self.prefix_namespace_uri_map.get(prefix)
        local_name = self.local_name_map.get(namespace_uri, {}).get(local_name, local_name)
        return QName(prefix, namespace_uri, local_name)
