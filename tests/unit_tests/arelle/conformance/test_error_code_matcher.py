"""
See COPYRIGHT.md for copyright information.
"""
from typing import Any

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.conformance.ErrorCodeMatcher import errorCodeMatches, filterIgnoredErrors

CONFORMANCE_NS = "http://xbrl.org/2008/conformance"


def suiteCode(localName: str, prefix: str | None = None, namespaceURI: str = CONFORMANCE_NS) -> QName:
    return QName(prefix, namespaceURI, localName)


@pytest.mark.parametrize(
    "expected,actual,matches",
    [
        # Unprefixed suite codes are compared as text.
        (suiteCode("DBA.FR24"), "DBA.FR24", True),
        (suiteCode("DBA.FR24"), "DBA.FR2", False),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "aspect-issues", False),
        # Arelle's ESEF and NL codes are compared by their final segment.
        (suiteCode("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suiteCode("missingOrInvalidTaxonomyPackage"), "ESEF.RTS.Annex.III.3.missingOrInvalidTaxonomyPackage", True),
        (suiteCode("periodWithTimeContent"), "NL.NL-KVK-3.1.2.1.periodWithTimeContent", True),
        (suiteCode("extensionTaxonomyWrongFilesStructure"), "NL.NL-KVK.RTS_Annex_IV_Par_6.extensionTaxonomyWrongFilesStructure", True),
        (suiteCode("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.extensionConceptsNotAnchored", False),
        ("missingCompaniesHouseMandatoryItem", "ESEF.UK.missingCompaniesHouseMandatoryItem", True),
        ("ESEF.UK.missingCompaniesHouseMandatoryItem", "ESEF.UK.missingCompaniesHouseMandatoryItem", True),
        # UKSEF suite codes are qualified with an authority.
        (suiteCode("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.incorrectTarget", True),
        (suiteCode("xbrl.efr.esef.esma.segmentUsed"), "ESEF.UKFRC8.segmentUsed", True),
        (suiteCode("xbrl.efr.esef.esma.UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suiteCode("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.noUKFRSData", False),
        # Prefixed codes resolve through the suite's namespaces.
        (suiteCode("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldie:PrimaryItemDimensionallyInvalidError", True),
        (suiteCode("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldte:PrimaryItemDimensionallyInvalidError", False),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "eg:aspect-issues", True),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test1}aspect-issues", True),
        (suiteCode("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test2}aspect-issues", False),
        (suiteCode("FORG0001", "err", XbrlConst.xpath2err), "err:FORG0001", True),
        (suiteCode("XmlSchemaError", "sche", XbrlConst.xdtSchemaErrorNS), "xmlSchema:valueError", True),
        (suiteCode("XmlSchemaError", "sche", XbrlConst.xdtSchemaErrorNS), "xbrldte:PrimaryItemDimensionallyInvalidError", False),
        # EFM and EXG codes are hierarchical.
        ("EFM.6.05.20", "EFM.6.05.20.periodStartLabel", True),
        ("EXG.3.05", "EXG.3.05.EX98SPACFactsDependency", True),
        ("EFM.6.05.2", "EFM.6.05.20.documentTypeValue", False),
        # Suite codes that Arelle reports as a different code.
        ("html:syntaxError", "lxml.SCHEMAV_ELEMENT_CONTENT", True),
        ("html:syntaxError", "lxml.SCHEMAP_SRC_IMPORT", False),
        ("EFM.6.03.04", "xmlSchema:syntax", True),
        ("EFM.6.03.04", "xmlSchema:valueError", False),
        ("EFM.6.03.05", "EFM.5.02.01.01", True),
        ("EFM.6.03.05", "EFM.5.02.01.011", False),
        ("EFM.6.04.03", "xmlSchema:valueError", True),
        ("EFM.6.05.35", "utre:error-NumericFactUtrInvalid", True),
        (suiteCode("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "xmlSchema:elementUnexpected", True),
        (suiteCode("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "lxml.SCHEMAV_ELEMENT_CONTENT", False),
        (suiteCode("xbrl.core.xml.SchemaValidationError.cvc-complex-type_3_2_2"), "lxml.SCHEMAV_CVC_COMPLEX_TYPE_3_2_1", True),
        (suiteCode("xbrl.core.xml.SchemaValidationError.cvc-complex-type_4"), "lxml.SCHEMAV_CVC_COMPLEX_TYPE_4", True),
        # Plain string codes.
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


def test_filterIgnoredErrors_removes_ignored() -> None:
    errors: list[Any] = [
        "ESEF.UKFRC17.reportPackageNameDoesNotFollowNamingConvention",
        "ESEF.UKFRC8.segmentUsed",
        "ESEF.UKFRC1.incorrectTarget",
        {"assertion": (1, 0, 0, 0, 0)},
    ]
    ignored = [
        suiteCode("xbrl.efr.esef.uk.reportPackageNameDoesNotFollowNamingConvention"),
        suiteCode("xbrl.efr.esef.esma.segmentUsed"),
    ]
    expected: list[Any] = [suiteCode("xbrl.efr.esef.uk.incorrectTarget")]
    assert filterIgnoredErrors(errors, ignored, expected) == [
        "ESEF.UKFRC1.incorrectTarget",
        {"assertion": (1, 0, 0, 0, 0)},
    ]


def test_filterIgnoredErrors_keeps_expected() -> None:
    errors: list[Any] = ["ESEF.UKFRC18.reportFileNameDoesNotFollowNamingConvention"]
    ignored = [suiteCode("xbrl.efr.esef.esma.reportFileNameDoesNotFollowNamingConvention")]
    expected: list[Any] = [suiteCode("xbrl.efr.esef.uk.reportFileNameDoesNotFollowNamingConvention")]
    assert filterIgnoredErrors(errors, ignored, expected) == errors
