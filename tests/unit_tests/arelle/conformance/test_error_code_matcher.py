"""
See COPYRIGHT.md for copyright information.
"""
from typing import Any

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.conformance.error_code_matcher import error_code_matches

CONFORMANCE_NS = "http://xbrl.org/2008/conformance"


def suite_code(local_name: str, prefix: str | None = None, namespace_uri: str = CONFORMANCE_NS) -> QName:
    return QName(prefix, namespace_uri, local_name)


@pytest.mark.parametrize(
    "expected,actual,matches",
    [
        # Unprefixed suite codes are compared as text.
        (suite_code("DBA.FR24"), "DBA.FR24", True),
        (suite_code("DBA.FR24"), "DBA.FR2", False),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "aspect-issues", False),
        # ESEF codes are compared by their final segment.
        (suite_code("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suite_code("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.extensionConceptsNotAnchored", False),
        ("missingCompaniesHouseMandatoryItem", "ESEF.UK.missingCompaniesHouseMandatoryItem", True),
        # UKSEF suite codes are qualified with an authority.
        (suite_code("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.incorrectTarget", True),
        (suite_code("xbrl.efr.esef.esma.segmentUsed"), "ESEF.UKFRC8.segmentUsed", True),
        (suite_code("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.noUKFRSData", False),
        (suite_code("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "xmlSchema:elementUnexpected", True),
        # Prefixed codes resolve through the suite's namespaces.
        (suite_code("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldie:PrimaryItemDimensionallyInvalidError", True),
        (suite_code("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldte:PrimaryItemDimensionallyInvalidError", False),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "eg:aspect-issues", True),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test1}aspect-issues", True),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test2}aspect-issues", False),
        (suite_code("FORG0001", "err", XbrlConst.xpath2err), "err:FORG0001", True),
        (suite_code("valueError", namespace_uri=XbrlConst.xdtSchemaErrorNS), "xmlSchema:valueError", True),
        # Plain string codes.
        ("EFM.6.05.20", "EFM.6.05.20.periodStartLabel", True),
        ("EFM.6.03.04", "xmlSchema:valueError", True),
        ("html:syntaxError", "lxml.SCHEMAV_ELEMENT_CONTENT", True),
        ("xbrl:multipleTopLevelSchemasForNamespace", "xbrl:multipleTopLevelSchemasForNamespace", True),
        ("xbrl:multipleTopLevelSchemasForNamespace", "info:duplicatedSchema", False),
        # Assertion results.
        ({"assertion": (1, 0)}, {"assertion": (1, 0, 0, 0, 0)}, True),
        ({"assertion": (1, 0)}, {"assertion": (0, 1, 0, 0, 0)}, False),
        ({"assertion": (1, 0)}, "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", False),
    ],
)
def test_error_code_matches(expected: Any, actual: Any, matches: bool) -> None:
    assert error_code_matches(expected, actual) is matches
