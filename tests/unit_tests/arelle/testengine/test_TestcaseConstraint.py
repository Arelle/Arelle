"""
See COPYRIGHT.md for copyright information.
"""

import pytest

from arelle.ModelValue import qname
from arelle.testengine.TestcaseConstraint import TestcaseConstraint


class TestTestcaseConstraint:
    def test_normalize_constraints(self) -> None:
        source_constraints = [
            TestcaseConstraint(count=1,pattern='A'),
            TestcaseConstraint(count=2,qname=qname('B')),
            TestcaseConstraint(count=2,pattern='C'),
            TestcaseConstraint(count=1,pattern='A'),
            TestcaseConstraint(count=1,qname=qname('B')),
        ]
        expected_constraints = [
            TestcaseConstraint(count=2,pattern='A'),
            TestcaseConstraint(count=3,qname=qname('B')),
            TestcaseConstraint(count=2,pattern='C'),
        ]
        actual_constraints = TestcaseConstraint.normalize_constraints(source_constraints)
        assert actual_constraints == expected_constraints
