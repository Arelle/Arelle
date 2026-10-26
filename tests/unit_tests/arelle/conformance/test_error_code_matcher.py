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
        # Arelle's ESEF and NL codes are compared by their final segment.
        (suite_code("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suite_code("missingOrInvalidTaxonomyPackage"), "ESEF.RTS.Annex.III.3.missingOrInvalidTaxonomyPackage", True),
        (suite_code("periodWithTimeContent"), "NL.NL-KVK-3.1.2.1.periodWithTimeContent", True),
        (suite_code("extensionTaxonomyWrongFilesStructure"), "NL.NL-KVK.RTS_Annex_IV_Par_6.extensionTaxonomyWrongFilesStructure", True),
        (suite_code("UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.extensionConceptsNotAnchored", False),
        ("missingCompaniesHouseMandatoryItem", "ESEF.UK.missingCompaniesHouseMandatoryItem", True),
        ("ESEF.UK.missingCompaniesHouseMandatoryItem", "ESEF.UK.missingCompaniesHouseMandatoryItem", True),
        ("ESMA.2.5.1", "ESEF.2.5.1", False),
        # UKSEF suite codes are qualified with an authority.
        (suite_code("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.incorrectTarget", True),
        (suite_code("xbrl.efr.esef.esma.segmentUsed"), "ESEF.UKFRC8.segmentUsed", True),
        (suite_code("xbrl.efr.esef.esma.UsableConceptsNotAppliedByTaggedFacts"), "ESEF.3.4.2.UsableConceptsNotAppliedByTaggedFacts", True),
        (suite_code("xbrl.efr.esef.uk.incorrectTarget"), "ESEF.UKFRC1.noUKFRSData", False),
        # Where the UKSEF suite gives a name to both authorities, Arelle's code must be from the same authority's rule.
        (suite_code("xbrl.efr.esef.uk.reportFileNameDoesNotFollowNamingConvention"), "ESEF.UKFRC18.reportFileNameDoesNotFollowNamingConvention", True),
        (suite_code("xbrl.efr.esef.esma.reportFileNameDoesNotFollowNamingConvention"), "ESEF.UKFRC18.reportFileNameDoesNotFollowNamingConvention", False),
        (suite_code("xbrl.efr.esef.esma.invalidIdentifier"), "ESEF.UKFRC6.invalidIdentifier", True),
        (suite_code("xbrl.efr.esef.esma.invalidIdentifier"), "ESEF.UKFRC7.invalidIdentifier", False),
        (suite_code("xbrl.efr.esef.uk.invalidIdentifier"), "ESEF.UKFRC7.invalidIdentifier", True),
        (suite_code("xbrl.efr.esef.uk.invalidIdentifier"), "ESEF.UKFRC6.invalidIdentifier", False),
        (suite_code("xbrl.efr.esef.uk.invalidIdentifier"), "ESEF.2.1.1.invalidIdentifier", False),
        # Prefixed codes resolve through the suite's namespaces.
        (suite_code("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldie:PrimaryItemDimensionallyInvalidError", True),
        (suite_code("PrimaryItemDimensionallyInvalidError", "xbrldie", "http://xbrl.org/2005/xbrldi/errors"), "xbrldte:PrimaryItemDimensionallyInvalidError", False),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "eg:aspect-issues", True),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test1}aspect-issues", True),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "{http://abc.com/test2}aspect-issues", False),
        (suite_code("aspect-issues", "eg", "http://abc.com/test1"), "undeclared:aspect-issues", False),
        (suite_code("FORG0001", "err", XbrlConst.xpath2err), "err:FORG0001", True),
        (suite_code("XmlSchemaError", "sche", XbrlConst.xdtSchemaErrorNS), "xmlSchema:valueError", True),
        (suite_code("XmlSchemaError", "sche", XbrlConst.xdtSchemaErrorNS), "xbrldte:PrimaryItemDimensionallyInvalidError", False),
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
        ("EFM.6.04.03", "xmlSchema:syntax", False),
        ("EFM.6.04.03", "utre:error-NumericFactUtrInvalid", False),
        ("EFM.6.04.03", "xlink:sourceNotFound", False),
        ("EFM.6.05.35", "utre:error-NumericFactUtrInvalid", True),
        (suite_code("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "xmlSchema:elementUnexpected", True),
        (suite_code("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "lxml.SCHEMAV_ELEMENT_CONTENT", False),
        (suite_code("xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a"), "xmlSchema:valueError", False),
        # Plain string codes.
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
