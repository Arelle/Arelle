"""
See COPYRIGHT.md for copyright information.
"""
from typing import Any

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.conformance.ErrorCodeMatcher import errorCodeMatches

CONFORMANCE_NS = "http://xbrl.org/2008/conformance"


def suiteCode(localName: str, prefix: str | None = None, namespaceURI: str = CONFORMANCE_NS) -> QName:
    return QName(prefix, namespaceURI, localName)


@pytest.mark.parametrize(
    "expected,actual,matches",
    [
        # ESEF codes are compared by their final segment.
        (suiteCode("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suiteCode("extensionConceptsNotAnchored, UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suiteCode("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.extensionConceptsNotAnchored", False),
        ("missingCompaniesHouseMandatoryItem", "ESEF.UK.missingCompaniesHouseMandatoryItem", True),
        # UKSEF suite codes are qualified with an authority.
        (suiteCode("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.incorrectTarget", True),
        (suiteCode("xbrl.efr.esef.esma.segmentUsed"), "ESEF.UKFRC8.segmentUsed", True),
        (suiteCode("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.noUKFRSData", False),
        (suiteCode("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "xmlSchema:elementUnexpected", True),
        # Prefixed codes resolve through the suite's namespaces.
        (suiteCode("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldie:PrimaryItemDimensionallyInvalidError", True),
        (suiteCode("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldte:PrimaryItemDimensionallyInvalidError", False),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "eg:aspect-issues", True),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test1}aspect-issues", True),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test2}aspect-issues", False),
        (suiteCode("FORG0001", "err", XbrlConst.xpath2err), "err:FORG0001", True),
        (suiteCode("valueError", namespaceURI=XbrlConst.xdtSchemaErrorNS), "xmlSchema:valueError", True),
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
def test_errorCodeMatches(expected: Any, actual: Any, matches: bool) -> None:
    assert errorCodeMatches(expected, actual) is matches
