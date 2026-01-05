from __future__ import annotations

import pytest

from arelle.ModelValue import qname
from test_engine.TestcaseCompareContext import TestcaseCompareContext
from test_engine.TestcaseConstraint import TestcaseConstraint

TESTCASE_COMPARE_CONTEXT = TestcaseCompareContext(
    customComparePatterns=[
        (r"^CCA\.1\.2\.3$", r"^xmlSchema:.*$"),  # Standard use case
        (r"^CCB\..*$", r"^~.*$"),  # Expected code swaps in for ~
    ],
    localNameMap={
        "https://www.example.com/abc": {
            "localNameFrom": "localNameTo",
        }
    },
    prefixNamespaceUriMap={
        "abc2": "https://www.example.com/abc",
        "def": "https://www.example.com/def",
    },
)

NAMESPACE_MAP = {
    "abc": "https://www.example.com/abc",
    "def": "https://www.example.com/def",
}

class TestTestcaseCompareContext:

    @pytest.mark.parametrize(
        "name, args",
        [
            ### BASIC
            ('Exact Match', ('A1', 'A1', True)),
            ('Any Match', ('*', 'A1', True)),
            ('Mismatch', ('A1', 'A2', False)),

            ### QNAME
            ('QName: Exact Match', ('abc:localName', 'abc:localName', True)),
            ('QName: Expected Local Name Match', ('localName', 'abc:localName', True)),
            ('QName: Actual Local Name Match', ('abc:localName', 'localName', True)),
            ('QName: Mapped Prefix Match', ('abc:localName', 'abc2:localName', True)),
            ('QName: Mapped Prefix And Local Name Match', ('abc:localNameTo', 'abc2:localNameFrom', True)),
            ('QName: Local Name Mismatch', ('abc:localName', 'abc:localName2', False)),
            ('QName: Namespace Mismatch', ('abc:localName', 'def:localName', False)),

            ### CUSTOM COMPARE PATTERNS
            ('Custom Compare: Match', ('CCA.1.2.3', 'xmlSchema:ERROR', True)),
            ('Custom Compare: Expected Mismatch', ('CCB.1.2.3', 'xmlSchema:ERROR', False)),
            ('Custom Compare: Actual Mismatch', ('CCA.1.2.3', 'xmlSchema2:ERROR', False)),
            ('Custom Compare Swap: Match', ('CCB.1.2.3', 'CCB.1.2.3.4', True)),
            ('Custom Compare Swap: Expected Mismatch', ('CCA.1.2.3', 'CCB.1.2.3.4', False)),
            ('Custom Compare Swap: Actual Mismatch', ('CCB.1.2.3', 'CCA.1.2.3.4', False)),
        ]
    )
    def test_compare(self, name: str, args: tuple[str, str, bool]) -> None:
        expected, actual, result = args
        expectedQName = qname(expected, NAMESPACE_MAP)
        if expectedQName.namespaceURI or expectedQName.prefix:
            constraint = TestcaseConstraint(
                qname=expectedQName,
                min=1,
                max=1,
            )
        else:
            constraint = TestcaseConstraint(
                pattern=expected,
                min=1,
                max=1,
            )
        actual_result = TESTCASE_COMPARE_CONTEXT.compare(constraint, actual)
        assert result == actual_result
