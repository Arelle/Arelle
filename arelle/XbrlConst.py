"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

import regex as re

from arelle.ModelValue import QName, qname
from arelle.typing import TypeGetText
from arelle.utils.deprecation import ModuleDeprecations

if TYPE_CHECKING:
    from arelle.ModelObject import ModelObject

_: TypeGetText


# Not a normative XBRL constant, but a value used internally in Arelle
# to represent the default/unspecified target name in multi-target filings.
DEFAULT_TARGET = "(default)"


xsd = "http://www.w3.org/2001/XMLSchema"
_XSD_PREFIX = "xsd"
qnXsdComplexType = QName.fromParts("complexType", xsd, _XSD_PREFIX)
qnXsdDocumentation = QName.fromParts("documentation", xsd, _XSD_PREFIX)
qnXsdInclude = QName.fromParts("include", xsd, _XSD_PREFIX)
qnXsdImport = QName.fromParts("import", xsd, _XSD_PREFIX)
qnXsdSchema = QName.fromParts("schema", xsd, _XSD_PREFIX)
qnXsdAppinfo = QName.fromParts("appinfo", xsd, _XSD_PREFIX)
qnXsdDefaultType = QName.fromParts("anyType", xsd, _XSD_PREFIX)
qnXsdElement = QName.fromParts("element", xsd, _XSD_PREFIX)
qnXsdAttribute = QName.fromParts("attribute", xsd, _XSD_PREFIX)
xsi = "http://www.w3.org/2001/XMLSchema-instance"
_XSI_PREFIX = "xsi"
qnXsiNil = QName.fromParts("nil", xsi, _XSI_PREFIX)
qnXsiType = QName.fromParts("type", xsi, _XSI_PREFIX)
qnXsiSchemaLocation = QName.fromParts("schemaLocation", xsi, _XSI_PREFIX)
qnXsiNoNamespaceSchemaLocation = QName.fromParts("noNamespaceSchemaLocation", xsi, _XSI_PREFIX)
xml = "http://www.w3.org/XML/1998/namespace"
qnXmlLang = QName.fromParts("lang", xml, "xml")
builtinAttributes = frozenset({
    qnXsiNil,
    qnXsiType,
    qnXsiSchemaLocation,
    qnXsiNoNamespaceSchemaLocation,
})
ref2004 = "http://www.xbrl.org/2004/ref"
ref2006 = "http://www.xbrl.org/2006/ref"
svg = "http://www.w3.org/2000/svg"
xbrli = "http://www.xbrl.org/2003/instance"
xhtmlBaseIdentifier = "{http://www.w3.org/1999/xhtml}base"
xmlBaseIdentifier = "{http://www.w3.org/XML/1998/namespace}base"
eurofilingModelNamespace = "http://www.eurofiling.info/xbrl/ext/model"
eurofilingModelPrefix = "model"
qnNsmap = QName.fromParts("nsmap")  # artificial parent for insertion of xmlns in saving xml documents
qnXbrlScenario = QName.fromParts("scenario", xbrli)
_XBRLI_PREFIX = "xbrli"
qnXbrliXbrl = QName.fromParts("xbrl", xbrli, _XBRLI_PREFIX)
qnPrototypeXbrliXbrl = QName.fromParts("xbrl", "http://arelle.org/prototype/xbrli")  # prototype for inline derived xbrl instance
qnXbrliItem = QName.fromParts("item", xbrli, _XBRLI_PREFIX)
qnXbrliNumerator = QName.fromParts("numerator", xbrli, _XBRLI_PREFIX)
qnXbrliDenominator = QName.fromParts("denominator", xbrli, _XBRLI_PREFIX)
qnXbrliTuple = QName.fromParts("tuple", xbrli, _XBRLI_PREFIX)
qnXbrliContext = QName.fromParts("context", xbrli, _XBRLI_PREFIX)
qnXbrliPeriod = QName.fromParts("period", xbrli, _XBRLI_PREFIX)
qnXbrliStartDate = QName.fromParts("startDate", xbrli, _XBRLI_PREFIX)
qnXbrliEndDate = QName.fromParts("endDate", xbrli, _XBRLI_PREFIX)
qnXbrliInstant = QName.fromParts("instant", xbrli, _XBRLI_PREFIX)
xbrliPeriodElementTags = (qnXbrliStartDate.clarkNotation, qnXbrliEndDate.clarkNotation, qnXbrliInstant.clarkNotation)
qnXbrliForever = QName.fromParts("forever", xbrli, _XBRLI_PREFIX)
qnXbrliIdentifier = QName.fromParts("identifier", xbrli, _XBRLI_PREFIX)
qnXbrliUnit = QName.fromParts("unit", xbrli, _XBRLI_PREFIX)
qnXbrliStringItemType = QName.fromParts("stringItemType", xbrli, _XBRLI_PREFIX)
qnXbrliMonetaryItemType = QName.fromParts("monetaryItemType", xbrli, _XBRLI_PREFIX)
qnXbrliDateItemType = QName.fromParts("dateItemType", xbrli, _XBRLI_PREFIX)
qnXbrliDurationItemType = QName.fromParts("durationItemType", xbrli, _XBRLI_PREFIX)
qnXbrliBooleanItemType = QName.fromParts("booleanItemType", xbrli, _XBRLI_PREFIX)
qnXbrliQNameItemType = QName.fromParts("QNameItemType", xbrli, _XBRLI_PREFIX)
qnXbrliPure = QName.fromParts("pure", xbrli, _XBRLI_PREFIX)
qnXbrliShares = QName.fromParts("shares", xbrli, _XBRLI_PREFIX)
qnInvalidMeasure = QName.fromParts("invalidMeasureQName", "http://arelle.org", "arelle")
qnXbrliDateUnion = QName.fromParts("dateUnion", xbrli, _XBRLI_PREFIX)
qnDateUnionXsdTypes = [
    QName.fromParts("date", xsd, _XSD_PREFIX),
    QName.fromParts("dateTime", xsd, _XSD_PREFIX),
]
qnXbrliDecimalsUnion = QName.fromParts("decimalsType", xbrli, _XBRLI_PREFIX)
qnXbrliPrecisionUnion = QName.fromParts("precisionType", xbrli, _XBRLI_PREFIX)
qnXbrliNonZeroDecimalUnion = QName.fromParts("nonZeroDecimal", xbrli, _XBRLI_PREFIX)
link = "http://www.xbrl.org/2003/linkbase"
_LINK_PREFIX = "link"
qnLinkArcroleRef = QName.fromParts("arcroleRef", link, _LINK_PREFIX)
qnLinkLinkbase = QName.fromParts("linkbase", link, _LINK_PREFIX)
qnLinkLinkbaseRef = QName.fromParts("linkbaseRef", link, _LINK_PREFIX)
qnLinkLoc = QName.fromParts("loc", link, _LINK_PREFIX)
qnLinkLabelLink = QName.fromParts("labelLink", link, _LINK_PREFIX)
qnLinkLabelArc = QName.fromParts("labelArc", link, _LINK_PREFIX)
qnLinkLabel = QName.fromParts("label", link, _LINK_PREFIX)
qnLinkReferenceLink = QName.fromParts("referenceLink", link, _LINK_PREFIX)
qnLinkReferenceArc = QName.fromParts("referenceArc", link, _LINK_PREFIX)
qnLinkReference = QName.fromParts("reference", link, _LINK_PREFIX)
qnLinkRoleRef = QName.fromParts("roleRef", link, _LINK_PREFIX)
qnLinkSchemaRef = QName.fromParts("schemaRef", link, _LINK_PREFIX)
qnLinkPart = QName.fromParts("part", link, _LINK_PREFIX)
qnLinkFootnoteLink = QName.fromParts("footnoteLink", link, _LINK_PREFIX)
qnLinkFootnoteArc = QName.fromParts("footnoteArc", link, _LINK_PREFIX)
qnLinkFootnote = QName.fromParts("footnote", link, _LINK_PREFIX)
qnLinkPresentationLink = QName.fromParts("presentationLink", link, _LINK_PREFIX)
qnLinkPresentationArc = QName.fromParts("presentationArc", link, _LINK_PREFIX)
qnLinkCalculationLink = QName.fromParts("calculationLink", link, _LINK_PREFIX)
qnLinkCalculationArc = QName.fromParts("calculationArc", link, _LINK_PREFIX)
qnLinkDefinitionLink = QName.fromParts("definitionLink", link, _LINK_PREFIX)
qnLinkDefinitionArc = QName.fromParts("definitionArc", link, _LINK_PREFIX)
gen = "http://xbrl.org/2008/generic"
_GEN_PREFIX = "gen"
qnGenLink = QName.fromParts("link", gen, _GEN_PREFIX)
qnGenArc = QName.fromParts("arc", gen, _GEN_PREFIX)
elementReference = "http://xbrl.org/arcrole/2008/element-reference"
genReference = "http://xbrl.org/2008/reference"
qnGenReference = QName.fromParts("reference", genReference)
elementLabel = "http://xbrl.org/arcrole/2008/element-label"
genLabel = "http://xbrl.org/2008/label"
qnGenLabel = QName.fromParts("label", genLabel)
xbrldt = "http://xbrl.org/2005/xbrldt"
_XBRLDT_PREFIX = "xbrldt"
qnXbrldtClosed = QName.fromParts("closed", xbrldt, _XBRLDT_PREFIX)
qnXbrldtHypercubeItem = QName.fromParts("hypercubeItem", xbrldt, _XBRLDT_PREFIX)
qnXbrldtDimensionItem = QName.fromParts("dimensionItem", xbrldt, _XBRLDT_PREFIX)
qnXbrldtContextElement = QName.fromParts("contextElement", xbrldt, _XBRLDT_PREFIX)
xbrldi = "http://xbrl.org/2006/xbrldi"
_XBRLDI_PREFIX = "xbrldi"
qnXbrldiExplicitMember = QName.fromParts("explicitMember", xbrldi, _XBRLDI_PREFIX)
qnXbrldiTypedMember = QName.fromParts("typedMember", xbrldi, _XBRLDI_PREFIX)
xlink = "http://www.w3.org/1999/xlink"
_XLINK_PREFIX = "xlink"
qnXlinkArcRole = QName.fromParts("arcrole", xlink, _XLINK_PREFIX)
qnXlinkFrom = QName.fromParts("from", xlink, _XLINK_PREFIX)
qnXlinkHref = QName.fromParts("href", xlink, _XLINK_PREFIX)
qnXlinkLabel = QName.fromParts("label", xlink, _XLINK_PREFIX)
qnXlinkRole = QName.fromParts("role", xlink, _XLINK_PREFIX)
qnXlinkTo = QName.fromParts("to", xlink, _XLINK_PREFIX)
qnXlinkType = QName.fromParts("type", xlink, _XLINK_PREFIX)
xl = "http://www.xbrl.org/2003/XLink"
_XL_PREFIX = "xl"
qnXlExtended = QName.fromParts("extended", xl, _XL_PREFIX)
qnXlLocator = QName.fromParts("locator", xl, _XL_PREFIX)
qnXlResource = QName.fromParts("resource", xl, _XL_PREFIX)
qnXlExtendedType = QName.fromParts("extendedType", xl, _XL_PREFIX)
qnXlLocatorType = QName.fromParts("locatorType", xl, _XL_PREFIX)
qnXlResourceType = QName.fromParts("resourceType", xl, _XL_PREFIX)
qnXlArcType = QName.fromParts("arcType", xl, _XL_PREFIX)
xhtml = "http://www.w3.org/1999/xhtml"
qnXhtmlMeta = QName.fromParts("meta", xhtml)
qnXhtmlImg = QName.fromParts("img", xhtml)
qnXhtmlDel = QName.fromParts("del", xhtml)
ixbrl = "http://www.xbrl.org/2008/inlineXBRL"
ixbrl11 = "http://www.xbrl.org/2013/inlineXBRL"
ixbrlAll = frozenset({ixbrl, ixbrl11})
ixbrlTags = ("{http://www.xbrl.org/2013/inlineXBRL}*", "{http://www.xbrl.org/2008/inlineXBRL}*")
ixbrlTagPattern = re.compile("[{]http://www.xbrl.org/(2008|2013)/inlineXBRL[}]")
ixt = "http://www.xbrl.org/inlineXBRL/transformation/2010-04-20"
qnIXbrlResources = QName.fromParts("resources", ixbrl)
qnIXbrlTuple = QName.fromParts("tuple", ixbrl)
qnIXbrlNonNumeric = QName.fromParts("nonNumeric", ixbrl)
qnIXbrlNonFraction = QName.fromParts("nonFraction", ixbrl)
qnIXbrlFraction = QName.fromParts("fraction", ixbrl)
qnIXbrlNumerator = QName.fromParts("numerator", ixbrl)
qnIXbrlDenominator = QName.fromParts("denominator", ixbrl)
qnIXbrlFootnote = QName.fromParts("footnote", ixbrl)
qnIXbrl11Resources = QName.fromParts("resources", ixbrl11)
qnIXbrl11Tuple = QName.fromParts("tuple", ixbrl11)
qnIXbrl11NonNumeric = QName.fromParts("nonNumeric", ixbrl11)
qnIXbrl11NonFraction = QName.fromParts("nonFraction", ixbrl11)
qnIXbrl11Fraction = QName.fromParts("fraction", ixbrl11)
qnIXbrl11Numerator = QName.fromParts("numerator", ixbrl11)
qnIXbrl11Denominator = QName.fromParts("denominator", ixbrl11)
qnIXbrl11Footnote = QName.fromParts("footnote", ixbrl11)
qnIXbrl11Relationship = QName.fromParts("relationship", ixbrl11)
qnIXbrl11Hidden = QName.fromParts("hidden", ixbrl11)
ixAttributes = frozenset(
    QName.fromParts(n)
    for n in (
        "continuedAt",
        "escape",
        "footnoteRefs",
        "format",
        "name",
        "order",
        "scale",
        "sign",
        "target",
        "tupleRef",
        "tupleID",
    )
)
ixbrlTargetElements = frozenset({
    qnIXbrlFraction,
    qnIXbrlNonFraction,
    qnIXbrlNonNumeric,
    qnIXbrlResources,
    qnIXbrlTuple,
})
ixbrl11TargetElements = frozenset({
    qnIXbrl11Fraction,
    qnIXbrl11NonFraction,
    qnIXbrl11NonNumeric,
    qnIXbrl11Resources,
    qnIXbrl11Tuple,
})
ixbrlAllTargetElements = ixbrlTargetElements | ixbrl11TargetElements
conceptLabel = "http://www.xbrl.org/2003/arcrole/concept-label"
conceptReference = "http://www.xbrl.org/2003/arcrole/concept-reference"
footnote = "http://www.xbrl.org/2003/role/footnote"
factFootnote = "http://www.xbrl.org/2003/arcrole/fact-footnote"
factExplanatoryFact = "http://www.xbrl.org/2009/arcrole/fact-explanatoryFact"
parentChild = "http://www.xbrl.org/2003/arcrole/parent-child"
summationItem = "http://www.xbrl.org/2003/arcrole/summation-item"
summationItem11 = "https://xbrl.org/2023/arcrole/summation-item"
summationItems = (summationItem, summationItem11)
essenceAlias = "http://www.xbrl.org/2003/arcrole/essence-alias"
similarTuples = "http://www.xbrl.org/2003/arcrole/similar-tuples"
requiresElement = "http://www.xbrl.org/2003/arcrole/requires-element"
generalSpecial = "http://www.xbrl.org/2003/arcrole/general-special"
all = "http://xbrl.org/int/dim/arcrole/all"
notAll = "http://xbrl.org/int/dim/arcrole/notAll"
hypercubeDimension = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
dimensionDomain = "http://xbrl.org/int/dim/arcrole/dimension-domain"
domainMember = "http://xbrl.org/int/dim/arcrole/domain-member"
dimensionDefault = "http://xbrl.org/int/dim/arcrole/dimension-default"
defaultLinkRole = "http://www.xbrl.org/2003/role/link"
defaultGenLinkRole = "http://www.xbrl.org/2008/role/link"
iso4217 = "http://www.xbrl.org/2003/iso4217"
iso17442 = "http://standards.iso.org/iso/17442"


def qnIsoCurrency(token: str | None) -> QName | None:
    return qname(iso4217, "iso4217:" + token) if token else None


standardLabel = "http://www.xbrl.org/2003/role/label"
genStandardLabel = "http://www.xbrl.org/2008/role/label"
documentationLabel = "http://www.xbrl.org/2003/role/documentation"
genDocumentationLabel = "http://www.xbrl.org/2008/role/documentation"
standardReference = "http://www.xbrl.org/2003/role/reference"
genStandardReference = "http://www.xbrl.org/2010/role/reference"
periodStartLabel = "http://www.xbrl.org/2003/role/periodStartLabel"
periodEndLabel = "http://www.xbrl.org/2003/role/periodEndLabel"
verboseLabel = "http://www.xbrl.org/2003/role/verboseLabel"
terseLabel = "http://www.xbrl.org/2003/role/terseLabel"
conceptNameLabelRole = "XBRL-concept-name"  # fake label role to show concept QName instead of label
xlinkLinkbase = "http://www.w3.org/1999/xlink/properties/linkbase"

utr = "http://www.xbrl.org/2009/utr"


_dtrTypesStartsWith = "http://www.xbrl.org/dtr/type/"

def isDtrTypeNamespace(namespace: str | None) -> bool:
    return namespace.startswith(_dtrTypesStartsWith) if namespace else False

dtr = "http://www.xbrl.org/2009/dtr"
dtrNumeric = "http://www.xbrl.org/dtr/type/numeric"
dtrTypeNamespace_2018_01_17_CR = f"{_dtrTypesStartsWith}CR/2018-01-17"
dtrTypeNamespace_2018_07_11_CR = f"{_dtrTypesStartsWith}CR/2018-07-11"
dtrTypeNamespace_2019_04_19_CR = f"{_dtrTypesStartsWith}CR/2019-04-19"
dtrTypeNamespace_2020_01_21 = f"{_dtrTypesStartsWith}2020-01-21"
dtrTypeNamespace_2021_12_08_CR = f"{_dtrTypesStartsWith}CR/2021-12-08"
dtrTypeNamespace_2022_03_31 = f"{_dtrTypesStartsWith}2022-03-31"
dtrTypeNamespace_2023_12_20_CR = f"{_dtrTypesStartsWith}CR/2023-12-20"
dtrTypeNamespace_2024_01_31 = f"{_dtrTypesStartsWith}2024-01-31"
dtrTypeNamespace_WGWD = f"{_dtrTypesStartsWith}WGWD/YYYY-MM-DD"

_dtrTypeNamespaces2019AndNewer = frozenset({
    dtrTypeNamespace_2019_04_19_CR,
    dtrTypeNamespace_2020_01_21,
    dtrTypeNamespace_2021_12_08_CR,
    dtrTypeNamespace_2022_03_31,
    dtrTypeNamespace_2023_12_20_CR,
    dtrTypeNamespace_2024_01_31,
    dtrTypeNamespace_WGWD,
})
_dtrTypeNamespaces2018_07_11AndNewer = _dtrTypeNamespaces2019AndNewer | frozenset({dtrTypeNamespace_2018_07_11_CR})
_dtrTypeNamespacesAll = _dtrTypeNamespaces2018_07_11AndNewer | frozenset({dtrTypeNamespace_2018_01_17_CR})

dtrNoDecimalsItemTypes = frozenset(
    QName.fromParts(typeName, namespace)
    for namespace in _dtrTypeNamespaces2018_07_11AndNewer
    for typeName in [
        "noDecimalsMonetaryItemType",
        "nonNegativeNoDecimalsMonetaryItemType",
    ]
)
dtrPrefixedContentItemTypes = frozenset(
    QName.fromParts("prefixedContentItemType", namespace)
    for namespace in _dtrTypeNamespaces2019AndNewer
)
dtrPrefixedContentTypes = frozenset(
    QName.fromParts("prefixedContentType", namespace)
    for namespace in _dtrTypeNamespaces2019AndNewer
)
dtrSQNameItemTypes = frozenset(
    QName.fromParts("SQNameItemType", namespace)
    for namespace in _dtrTypeNamespaces2018_07_11AndNewer
)
dtrSQNameTypes = frozenset(
    QName.fromParts("SQNameType", namespace)
    for namespace in _dtrTypeNamespaces2019AndNewer
)
dtrSQNamesItemTypes = frozenset(
    QName.fromParts("SQNamesItemType", namespace)
    for namespace in _dtrTypeNamespaces2019AndNewer
)
dtrSQNamesTypes = frozenset(
    QName.fromParts("SQNamesType", namespace)
    for namespace in _dtrTypeNamespaces2019AndNewer
)
dtrSQNameNamesItemTypes = dtrSQNameItemTypes | dtrSQNamesItemTypes
dtrSQNameNamesTypes = dtrSQNameTypes | dtrSQNamesTypes

wgnStringItemTypeNames = frozenset({"stringItemType", "normalizedStringItemType"})
dtrNoLangItemTypeNames = frozenset({"domainItemType", "noLangTokenItemType", "noLangStringItemType"})
xsdNoLangTypeNames = frozenset({"language", "Name"})
xsdStringTypeNames = frozenset({
    "string",
    "normalizedString",
    "token",
    "language",
    "Name",
    "NCName",
    "ID",
    "IDREF",
    "IDREFS",
    "ENTITY",
    "ENTITIES",
    "NMTOKEN",
    "NMTOKENS",
})

ver10 = "http://xbrl.org/2010/versioning-base"
# 2010 names
vercb = "http://xbrl.org/2010/versioning-concept-basic"
verce = "http://xbrl.org/2010/versioning-concept-extended"
verrels = "http://xbrl.org/2010/versioning-relationship-sets"
veria = "http://xbrl.org/2010/versioning-instance-aspects"
# 2013 names
ver = "http://xbrl.org/2013/versioning-base"
vercu = "http://xbrl.org/2013/versioning-concept-use"
vercd = "http://xbrl.org/2013/versioning-concept-details"
verdim = "http://xbrl.org/2013/versioning-dimensions"

verPrefixNS: dict[str, str] = {
    "ver": ver,
    "vercu": vercu,
    "vercd": vercd,
    "verrels": verrels,
    "verdim": verdim,
}

# extended enumeration spec
_ENUM_2014_NAMESPACE = "http://xbrl.org/2014/extensible-enumerations"
_ENUM_2020_NAMESPACE = "http://xbrl.org/2020/extensible-enumerations-2.0"
_ENUM_YYYY_NAMESPACE = "http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0"
_ENUM_11_YYYY_NAMESPACE = "http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1"
_ENUM_2016_NAMESPACE = "http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1"
enum2s = frozenset({
    _ENUM_2020_NAMESPACE,
    _ENUM_YYYY_NAMESPACE,
})
enum_1x = frozenset({
    _ENUM_2014_NAMESPACE,
    _ENUM_2016_NAMESPACE,
    _ENUM_11_YYYY_NAMESPACE,
})
enums = enum_1x | enum2s

_ENUM_PREFIX = "enum"
qnEnumerationItemType2014 = QName.fromParts("enumerationItemType", _ENUM_2014_NAMESPACE, _ENUM_PREFIX)
_ENUM2_PREFIX = "enum2"
qnEnumerationItemType2020 = QName.fromParts("enumerationItemType", _ENUM_2020_NAMESPACE, _ENUM2_PREFIX)
qnEnumerationItemTypeYYYY = QName.fromParts(
    "enumerationItemType", _ENUM_YYYY_NAMESPACE, _ENUM2_PREFIX
)
qnEnumerationSetItemType2020 = QName.fromParts(
    "enumerationSetItemType", _ENUM_2020_NAMESPACE, _ENUM2_PREFIX
)
qnEnumerationSetItemTypeYYYY = QName.fromParts(
    "enumerationSetItemType", _ENUM_YYYY_NAMESPACE, _ENUM2_PREFIX
)
qnEnumerationSetValDimType2020 = QName.fromParts(
    "setValueDimensionType", _ENUM_2020_NAMESPACE, _ENUM2_PREFIX
)
qnEnumerationSetValDimTypeYYYY = QName.fromParts(
    "setValueDimensionType", _ENUM_YYYY_NAMESPACE, _ENUM2_PREFIX
)
qnEnumerationItemType11YYYY = QName.fromParts(
    "enumerationItemType", _ENUM_11_YYYY_NAMESPACE, _ENUM_PREFIX
)
qnEnumerationSetItemType11YYYY = QName.fromParts(
    "enumerationSetItemType", _ENUM_11_YYYY_NAMESPACE, _ENUM_PREFIX
)
qnEnumerationListItemType11YYYY = QName.fromParts(
    "enumerationListItemType", _ENUM_11_YYYY_NAMESPACE, _ENUM_PREFIX
)
qnEnumerationItemType2016 = QName.fromParts(
    "enumerationItemType", _ENUM_2016_NAMESPACE, _ENUM_PREFIX
)
qnEnumerationsItemType2016 = QName.fromParts(
    "enumerationsItemType", _ENUM_2016_NAMESPACE, _ENUM_PREFIX
)
qnEnumerationListItemTypes = frozenset({
    qnEnumerationListItemType11YYYY,
    qnEnumerationSetItemType11YYYY,
    qnEnumerationsItemType2016,
})
qnEnumerationSetItemTypes = frozenset({
    qnEnumerationSetItemType11YYYY,
    qnEnumerationSetItemType2020,
    qnEnumerationSetItemTypeYYYY,
})
qnEnumerationItemTypes = frozenset({
    qnEnumerationItemType2014,
    qnEnumerationItemType2020,
    qnEnumerationItemTypeYYYY,
    qnEnumerationSetItemType2020,
    qnEnumerationSetItemTypeYYYY,
    qnEnumerationItemType11YYYY,
    qnEnumerationSetItemType11YYYY,
    qnEnumerationListItemType11YYYY,
    qnEnumerationItemType2016,
    qnEnumerationsItemType2016,
})
qnEnumerationTypes = qnEnumerationItemTypes | {
    qnEnumerationSetValDimType2020,
    qnEnumerationSetValDimTypeYYYY,
}
qnEnumeration2ItemTypes = frozenset({qnEnumerationItemType2020, qnEnumerationSetItemType2020})
attrEnumerationDomain2014 = "{http://xbrl.org/2014/extensible-enumerations}domain"
attrEnumerationDomain2020 = "{http://xbrl.org/2020/extensible-enumerations-2.0}domain"
attrEnumerationDomainYYYY = "{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0}domain"
attrEnumerationDomain11YYYY = "{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1}domain"
attrEnumerationDomain2016 = "{http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1}domain"
attrEnumerationLinkrole2014 = "{http://xbrl.org/2014/extensible-enumerations}linkrole"
attrEnumerationLinkrole2020 = "{http://xbrl.org/2020/extensible-enumerations-2.0}linkrole"
attrEnumerationLinkroleYYYY = "{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0}linkrole"
attrEnumerationLinkrole11YYYY = "{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1}linkrole"
attrEnumerationLinkrole2016 = "{http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1}linkrole"
attrEnumerationUsable2014 = "{http://xbrl.org/2014/extensible-enumerations}headUsable"
attrEnumerationUsable2020 = "{http://xbrl.org/2020/extensible-enumerations-2.0}headUsable"
attrEnumerationUsableYYYY = "{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0}headUsable"
attrEnumerationUsable11YYYY = "{http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1}headUsable"
attrEnumerationUsable2016 = "{http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1}headUsable"

# formula specs
variable = "http://xbrl.org/2008/variable"
_VARIABLE_PREFIX = "variable"
qnVariableSet = QName.fromParts("variableSet", variable, _VARIABLE_PREFIX)
qnVariableVariable = QName.fromParts("variable", variable, _VARIABLE_PREFIX)
qnVariableFilter = QName.fromParts("filter", variable, _VARIABLE_PREFIX)
qnVariableFilterArc = QName.fromParts("variableFilterArc", variable, _VARIABLE_PREFIX)
qnParameter = QName.fromParts("parameter", variable, _VARIABLE_PREFIX)
qnFactVariable = QName.fromParts("factVariable", variable, _VARIABLE_PREFIX)
qnGeneralVariable = QName.fromParts("generalVariable", variable, _VARIABLE_PREFIX)
qnPrecondition = QName.fromParts("precondition", variable, _VARIABLE_PREFIX)
qnEqualityDefinition = QName.fromParts("equalityDefinition", variable, _VARIABLE_PREFIX)
_ASPECT_TEST_NAMESPACE = "http://xbrl.org/2008/variable/aspectTest"
_ASPECT_TEST_PREFIX = "aspectTest"
qnEqualityTestA = QName.fromParts("a", _ASPECT_TEST_NAMESPACE, _ASPECT_TEST_PREFIX)
qnEqualityTestB = QName.fromParts("b", _ASPECT_TEST_NAMESPACE, _ASPECT_TEST_PREFIX)
formula = "http://xbrl.org/2008/formula"
formulaTuple = "http://xbrl.org/2010/formula/tuple"
_FORMULA_PREFIX = "formula"
qnFormula = QName.fromParts("formula", formula, _FORMULA_PREFIX)
qnTuple = QName.fromParts("tuple", formulaTuple, "tuple")
qnFormulaUncovered = QName.fromParts("uncovered", formula, _FORMULA_PREFIX)
qnFormulaDimensionSAV = QName.fromParts("DimensionSAV", formula)  # signal that dimension aspect should use SAV of this dimension
qnFormulaOccEmpty = QName.fromParts("occEmpty", formula)  # signal that OCC aspect should omit the SAV values
ca = "http://xbrl.org/2008/assertion/consistency"
_CA_PREFIX = "ca"
qnConsistencyAssertion = QName.fromParts("consistencyAssertion", ca, _CA_PREFIX)
qnCaAspectMatchedFacts = QName.fromParts("aspect-matched-facts", ca, _CA_PREFIX)
qnCaAcceptanceRadius = QName.fromParts("acceptance-radius", ca, _CA_PREFIX)
qnCaAbsoluteAcceptanceRadiusExpression = QName.fromParts(
    "absolute-acceptance-radius-expression", ca, _CA_PREFIX
)
qnCaProportionalAcceptanceRadiusExpression = QName.fromParts(
    "proportional-acceptance-radius-expression", ca, _CA_PREFIX
)
ea = "http://xbrl.org/2008/assertion/existence"
qnExistenceAssertion = QName.fromParts("existenceAssertion", ea, "ea")
qnEaTestExpression = QName.fromParts("test-expression", ea)
va = "http://xbrl.org/2008/assertion/value"
qnValueAssertion = QName.fromParts("valueAssertion", va, "va")
qnVaTestExpression = QName.fromParts("test-expression", va)
formulaStartsWith = "http://xbrl.org/arcrole/20"
equalityDefinition = "http://xbrl.org/arcrole/2008/equality-definition"
variableSet = "http://xbrl.org/arcrole/2008/variable-set"
variableSetFilter = "http://xbrl.org/arcrole/2008/variable-set-filter"
variableFilter = "http://xbrl.org/arcrole/2008/variable-filter"
variableSetPrecondition = "http://xbrl.org/arcrole/2008/variable-set-precondition"
consistencyAssertionFormula = "http://xbrl.org/arcrole/2008/consistency-assertion-formula"
consistencyAssertionParameter = "http://xbrl.org/arcrole/2008/consistency-assertion-parameter"
validation = "http://xbrl.org/2008/validation"
_VALIDATION_PREFIX = "validation"
qnAssertion = QName.fromParts("assertion", validation, _VALIDATION_PREFIX)
qnVariableSetAssertion = QName.fromParts("variableSetAssertion", validation, _VALIDATION_PREFIX)
qnAssertionSet = QName.fromParts("assertionSet", validation, _VALIDATION_PREFIX)
assertionSet = "http://xbrl.org/arcrole/2008/assertion-set"
assertionUnsatisfiedSeverity = "http://xbrl.org/arcrole/2016/assertion-unsatisfied-severity"
assertionUnsatisfiedSeverity20 = "http://xbrl.org/arcrole/2022/assertion-unsatisfied-severity"
assertionUnsatisfiedSeverities = (assertionUnsatisfiedSeverity, assertionUnsatisfiedSeverity20)
_SEV_NAMESPACE = "http://xbrl.org/2016/assertion-severity"
_SEV_20_NAMESPACE = "http://xbrl.org/2022/assertion-severity"
_SEV_PREFIX = "sev"
qnAssertionSeverityError = QName.fromParts("error", _SEV_NAMESPACE, _SEV_PREFIX)
qnAssertionSeverityWarning = QName.fromParts("warning", _SEV_NAMESPACE, _SEV_PREFIX)
qnAssertionSeverityOk = QName.fromParts("ok", _SEV_NAMESPACE, _SEV_PREFIX)
qnAssertionSeverityError20 = QName.fromParts("error", _SEV_20_NAMESPACE, _SEV_PREFIX)
qnAssertionSeverityWarning20 = QName.fromParts("warning", _SEV_20_NAMESPACE, _SEV_PREFIX)
qnAssertionSeverityOk20 = QName.fromParts("ok", _SEV_20_NAMESPACE, _SEV_PREFIX)
qnAssertionSeverityExpression20 = QName.fromParts("expression", _SEV_20_NAMESPACE, _SEV_PREFIX)

acf = "http://xbrl.org/2010/filter/aspect-cover"
qnAspectCover = QName.fromParts("aspectCover", acf, "acf")
bf = "http://xbrl.org/2008/filter/boolean"
_BF_PREFIX = "bf"
qnAndFilter = QName.fromParts("andFilter", bf, _BF_PREFIX)
qnOrFilter = QName.fromParts("orFilter", bf, _BF_PREFIX)
booleanFilter = "http://xbrl.org/arcrole/2008/boolean-filter"
cfi = "http://xbrl.org/2010/custom-function"
functionImplementation = "http://xbrl.org/arcrole/2010/function-implementation"
_CFI_PREFIX = "cfi"
qnCustomFunctionSignature = QName.fromParts("function", variable, _CFI_PREFIX)
qnCustomFunctionImplementation = QName.fromParts("implementation", cfi, _CFI_PREFIX)
crf = "http://xbrl.org/2010/filter/concept-relation"
qnConceptRelation = QName.fromParts("conceptRelation", crf, "crf")
cf = "http://xbrl.org/2008/filter/concept"
_CF_PREFIX = "cf"
qnConceptName = QName.fromParts("conceptName", cf, _CF_PREFIX)
qnConceptPeriodType = QName.fromParts("conceptPeriodType", cf, _CF_PREFIX)
qnConceptBalance = QName.fromParts("conceptBalance", cf, _CF_PREFIX)
qnConceptCustomAttribute = QName.fromParts("conceptCustomAttribute", cf, _CF_PREFIX)
qnConceptDataType = QName.fromParts("conceptDataType", cf, _CF_PREFIX)
qnConceptSubstitutionGroup = QName.fromParts("conceptSubstitutionGroup", cf, _CF_PREFIX)
cfcn = "http://xbrl.org/2008/conformance/function"
df = "http://xbrl.org/2008/filter/dimension"
_DF_PREFIX = "df"
qnExplicitDimension = QName.fromParts("explicitDimension", df, _DF_PREFIX)
qnTypedDimension = QName.fromParts("typedDimension", df, _DF_PREFIX)
ef = "http://xbrl.org/2008/filter/entity"
_EF_PREFIX = "ef"
qnEntityIdentifier = QName.fromParts("identifier", ef, _EF_PREFIX)
qnEntitySpecificIdentifier = QName.fromParts("specificIdentifier", ef, _EF_PREFIX)
qnEntitySpecificScheme = QName.fromParts("specificScheme", ef, _EF_PREFIX)
qnEntityRegexpIdentifier = QName.fromParts("regexpIdentifier", ef, _EF_PREFIX)
qnEntityRegexpScheme = QName.fromParts("regexpScheme", ef, _EF_PREFIX)
function = "http://xbrl.org/2008/function"
fn = "http://www.w3.org/2005/xpath-functions"
xfi = "http://www.xbrl.org/2008/function/instance"
qnXfiRoot = QName.fromParts("root", xfi, "xfi")
xff = "http://www.xbrl.org/2010/function/formula"
gf = "http://xbrl.org/2008/filter/general"
qnGeneral = QName.fromParts("general", gf, "gf")
instances = "http://xbrl.org/2010/variable/instance"
_INSTANCES_PREFIX = "instances"
qnInstance = QName.fromParts("instance", instances, _INSTANCES_PREFIX)
instanceVariable = "http://xbrl.org/arcrole/2010/instance-variable"
formulaInstance = "http://xbrl.org/arcrole/2010/formula-instance"
qnStandardInputInstance = QName.fromParts("standard-input-instance", instances, _INSTANCES_PREFIX)
qnStandardOutputInstance = QName.fromParts("standard-output-instance", instances, _INSTANCES_PREFIX)
mf = "http://xbrl.org/2008/filter/match"
_MF_PREFIX = "mf"
qnMatchConcept = QName.fromParts("matchConcept", mf, _MF_PREFIX)
qnMatchDimension = QName.fromParts("matchDimension", mf, _MF_PREFIX)
qnMatchEntityIdentifier = QName.fromParts("matchEntityIdentifier", mf, _MF_PREFIX)
qnMatchLocation = QName.fromParts("matchLocation", mf, _MF_PREFIX)
qnMatchPeriod = QName.fromParts("matchPeriod", mf, _MF_PREFIX)
qnMatchSegment = QName.fromParts("matchSegment", mf, _MF_PREFIX)
qnMatchScenario = QName.fromParts("matchScenario", mf, _MF_PREFIX)
qnMatchNonXDTSegment = QName.fromParts("matchNonXDTSegment", mf, _MF_PREFIX)
qnMatchNonXDTScenario = QName.fromParts("matchNonXDTScenario", mf, _MF_PREFIX)
qnMatchUnit = QName.fromParts("matchUnit", mf, _MF_PREFIX)
msg = "http://xbrl.org/2010/message"
qnMessage = QName.fromParts("message", msg)
assertionSatisfiedMessage = "http://xbrl.org/arcrole/2010/assertion-satisfied-message"
assertionUnsatisfiedMessage = "http://xbrl.org/arcrole/2010/assertion-unsatisfied-message"
standardMessage = "http://www.xbrl.org/2010/role/message"
terseMessage = "http://www.xbrl.org/2010/role/terseMessage"
verboseMessage = "http://www.xbrl.org/2010/role/verboseMessage"
pf = "http://xbrl.org/2008/filter/period"
_PF_PREFIX = "pf"
qnPeriod = QName.fromParts("period", pf, _PF_PREFIX)
qnPeriodStart = QName.fromParts("periodStart", pf, _PF_PREFIX)
qnPeriodEnd = QName.fromParts("periodEnd", pf, _PF_PREFIX)
qnPeriodInstant = QName.fromParts("periodInstant", pf, _PF_PREFIX)
qnForever = QName.fromParts("forever", pf, _PF_PREFIX)
qnInstantDuration = QName.fromParts("instantDuration", pf, _PF_PREFIX)
registry = "http://xbrl.org/2008/registry"
rf = "http://xbrl.org/2008/filter/relative"
qnRelativeFilter = QName.fromParts("relativeFilter", rf, "rf")
ssf = "http://xbrl.org/2008/filter/segment-scenario"
_SSF_PREFIX = "ssf"
qnSegmentFilter = QName.fromParts("segment", ssf, _SSF_PREFIX)
qnScenarioFilter = QName.fromParts("scenario", ssf, _SSF_PREFIX)
tf = "http://xbrl.org/2008/filter/tuple"
_TF_PREFIX = "tf"
qnAncestorFilter = QName.fromParts("ancestorFilter", tf, _TF_PREFIX)
qnLocationFilter = QName.fromParts("locationFilter", tf, _TF_PREFIX)
qnParentFilter = QName.fromParts("parentFilter", tf, _TF_PREFIX)
qnSiblingFilter = QName.fromParts("siblingFilter", tf, _TF_PREFIX)
uf = "http://xbrl.org/2008/filter/unit"
_UF_PREFIX = "uf"
qnSingleMeasure = QName.fromParts("singleMeasure", uf, _UF_PREFIX)
qnGeneralMeasures = QName.fromParts("generalMeasures", uf, _UF_PREFIX)
vf = "http://xbrl.org/2008/filter/value"
_VF_PREFIX = "vf"
qnNilFilter = QName.fromParts("nil", vf, _VF_PREFIX)
qnPrecisionFilter = QName.fromParts("precision", vf, _VF_PREFIX)
xpath2err = "http://www.w3.org/2005/xqt-errors"
variablesScope = "http://xbrl.org/arcrole/2010/variables-scope"

# 2014-MM-DD current IWD
tableMMDD = "http://xbrl.org/PWD/2016-MM-DD/table"
tableModelMMDD = "http://xbrl.org/PWD/2016-MM-DD/table/model"
tableBreakdownMMDD = "http://xbrl.org/arcrole/PWD/2014-MM-DD/table-breakdown"
tableBreakdownTreeMMDD = "http://xbrl.org/arcrole/PWD/2014-MM-DD/breakdown-tree"
tableDefinitionNodeSubtreeMMDD = "http://xbrl.org/arcrole/PWD/2014-MM-DD/definition-node-subtree"
tableFilterMMDD = "http://xbrl.org/arcrole/PWD/2014-MM-DD/table-filter"
tableAspectNodeFilterMMDD = "http://xbrl.org/arcrole/PWD/2014-MM-DD/aspect-node-filter"
tableParameterMMDD = "http://xbrl.org/arcrole/PWD/2014-MM-DD/table-parameter"
_TABLE_PREFIX = "table"
qnTableTableMMDD = QName.fromParts("table", tableMMDD, _TABLE_PREFIX)
qnTableBreakdownMMDD = QName.fromParts("breakdown", tableMMDD, _TABLE_PREFIX)
qnTableRuleNodeMMDD = QName.fromParts("ruleNode", tableMMDD, _TABLE_PREFIX)
qnTableRuleSetMMDD = QName.fromParts("ruleSet", tableMMDD, _TABLE_PREFIX)
qnTableDefinitionNodeMMDD = QName.fromParts("definitionNode", tableMMDD, _TABLE_PREFIX)
qnTableClosedDefinitionNodeMMDD = QName.fromParts("closedDefinitionNode", tableMMDD, _TABLE_PREFIX)
qnTableConceptRelationshipNodeMMDD = QName.fromParts("conceptRelationshipNode", tableMMDD, _TABLE_PREFIX)
qnTableDimensionRelationshipNodeMMDD = QName.fromParts(
    "dimensionRelationshipNode", tableMMDD, _TABLE_PREFIX
)
qnTableAspectNodeMMDD = QName.fromParts("aspectNode", tableMMDD, _TABLE_PREFIX)

# REC
table = "http://xbrl.org/2014/table"
tableModel = "http://xbrl.org/2014/table/model"
tableBreakdown = "http://xbrl.org/arcrole/2014/table-breakdown"
tableBreakdownTree = "http://xbrl.org/arcrole/2014/breakdown-tree"
tableDefinitionNodeSubtree = "http://xbrl.org/arcrole/2014/definition-node-subtree"
tableFilter = "http://xbrl.org/arcrole/2014/table-filter"
tableAspectNodeFilter = "http://xbrl.org/arcrole/2014/aspect-node-filter"
tableParameter = "http://xbrl.org/arcrole/2014/table-parameter"
qnTableTable = QName.fromParts("table", table, _TABLE_PREFIX)
qnTableBreakdown = QName.fromParts("breakdown", table, _TABLE_PREFIX)
qnTableRuleNode = QName.fromParts("ruleNode", table, _TABLE_PREFIX)
qnTableRuleSet = QName.fromParts("ruleSet", table, _TABLE_PREFIX)
qnTableDefinitionNode = QName.fromParts("definitionNode", table, _TABLE_PREFIX)
qnTableClosedDefinitionNode = QName.fromParts("closedDefinitionNode", table, _TABLE_PREFIX)
qnTableConceptRelationshipNode = QName.fromParts("conceptRelationshipNode", table, _TABLE_PREFIX)
qnTableDimensionRelationshipNode = QName.fromParts("dimensionRelationshipNode", table, _TABLE_PREFIX)
qnTableAspectNode = QName.fromParts("aspectNode", table, _TABLE_PREFIX)

# current PWD 1.1
tableMMDD = "http://xbrl.org/PWD/2017-07-12/table-1.1"
tableModelMMDD = "http://xbrl.org/PWD/2017-07-12/table-1.1/model"
tableBreakdownMMDD = "http://xbrl.org/arcrole/PWD/2017-07-12/table-breakdown-1.1"
tableBreakdownTreeMMDD = "http://xbrl.org/arcrole/PWD/2017-07-12/breakdown-tree-1.1"
tableDefinitionNodeSubtreeMMDD = "http://xbrl.org/arcrole/PWD/2017-07-12/definition-node-subtree-1.1"
tableFilterMMDD = "http://xbrl.org/arcrole/PWD/2017-07-12/table-filter-1.1"
tableAspectNodeFilterMMDD = "http://xbrl.org/arcrole/PWD/2017-07-12/aspect-node-filter-1.1"
tableParameterMMDD = "http://xbrl.org/arcrole/PWD/2017-07-12/table-parameter-1.1"
qnTableTableMMDD = QName.fromParts("table", tableMMDD, _TABLE_PREFIX)
qnTableBreakdownMMDD = QName.fromParts("breakdown", tableMMDD, _TABLE_PREFIX)
qnTableRuleNodeMMDD = QName.fromParts("ruleNode", tableMMDD, _TABLE_PREFIX)
qnTableRuleSetMMDD = QName.fromParts("ruleSet", tableMMDD, _TABLE_PREFIX)
qnTableDefinitionNodeMMDD = QName.fromParts("definitionNode", tableMMDD, _TABLE_PREFIX)
qnTableClosedDefinitionNodeMMDD = QName.fromParts("closedDefinitionNode", tableMMDD, _TABLE_PREFIX)
qnTableConceptRelationshipNodeMMDD = QName.fromParts("conceptRelationshipNode", tableMMDD, _TABLE_PREFIX)
qnTableDimensionRelationshipNodeMMDD = QName.fromParts("dimensionRelationshipNode", tableMMDD, _TABLE_PREFIX)
qnTableAspectNodeMMDD = QName.fromParts("aspectNode", tableMMDD, _TABLE_PREFIX)

booleanValueTrue = "true"
booleanValueFalse = "false"

# Eurofiling 2010 table linkbase
euRend = "http://www.eurofiling.info/2010/rendering"
euTableAxis = "http://www.eurofiling.info/arcrole/2010/table-axis"
euAxisMember = "http://www.eurofiling.info/arcrole/2010/axis-member"
_RENDERING_PREFIX = "rendering"
qnEuTable = QName.fromParts("table", euRend, _RENDERING_PREFIX)
qnEuAxisCoord = QName.fromParts("axisCoord", euRend, _RENDERING_PREFIX)
euGroupTable = "http://www.eurofiling.info/xbrl/arcrole/group-table"

# Anchoring (ESEF and allowed by SEC)
widerNarrower = "http://www.esma.europa.eu/xbrl/esef/arcrole/wider-narrower"

xdtSchemaErrorNS = "http://www.xbrl.org/2005/genericXmlSchemaError"
errMsgPrefixNS = {  # err prefixes which are not declared, such as XPath's "err" prefix
    "err": xpath2err,
    "xmlSchema": xdtSchemaErrorNS,
    "utre": "http://www.xbrl.org/2009/utr/errors",
}

# Filing Indicators
_EF_FIND_NAMESPACE = "http://www.eurofiling.info/xbrl/ext/filing-indicators"
_EF_FIND_PREFIX = "ef-find"
qnEuFiTuple = QName.fromParts("fIndicators", _EF_FIND_NAMESPACE, _EF_FIND_PREFIX)
qnEuFiIndFact = QName.fromParts("filingIndicator", _EF_FIND_NAMESPACE, _EF_FIND_PREFIX)
cnEuFiIndAttr = "{http://www.eurofiling.info/xbrl/ext/filing-indicators}filed"  # clark name
_FI_NAMESPACE = "http://www.xbrl.org/taxonomy/int/filing-indicators/REC/2021-02-03"
_FI_PREFIX = "fi"
qnFiFact = QName.fromParts("filed", _FI_NAMESPACE, _FI_PREFIX)
qnFiDim = QName.fromParts("template", _FI_NAMESPACE, _FI_PREFIX)

defaultLocale = "en-GB"

standardNamespaces = frozenset({xsd, xbrli, link, gen, xbrldt, xbrldi})
xsdOrXbrliNamespaces = frozenset({xsd, xbrli})

def isStandardNamespace(namespaceURI: str | None) -> bool:
    return namespaceURI in standardNamespaces

def isXsdOrXbrliNamespace(namespaceURI: str | None) -> bool:
    return namespaceURI in xsdOrXbrliNamespaces

def isUSTypesNamespace(namespaceURI: str | None) -> bool:
    return "/us-types/" in namespaceURI if namespaceURI else False

standardNamespaceSchemaLocations: dict[str, str] = {
    xbrli: "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd",
    link: "http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd",
    xl: "http://www.xbrl.org/2003/xl-2003-12-31.xsd",
    xlink: "http://www.xbrl.org/2003/xlink-2003-12-31.xsd",
    xbrldt: "http://www.xbrl.org/2005/xbrldt-2005.xsd",
    xbrldi: "http://www.xbrl.org/2006/xbrldi-2006.xsd",
    gen: "http://www.xbrl.org/2008/generic-link.xsd",
    genLabel: "http://www.xbrl.org/2008/generic-label.xsd",
    genReference: "http://www.xbrl.org/2008/generic-reference.xsd",
}


numericXsdTypes = frozenset({
        "integer",
        "positiveInteger",
        "negativeInteger",
        "nonNegativeInteger",
        "nonPositiveInteger",
        "long",
        "unsignedLong",
        "int",
        "unsignedInt",
        "short",
        "unsignedShort",
        "byte",
        "unsignedByte",
        "decimal",
        "float",
        "double",
    }
)
decimalXsdTypes = frozenset({
        "integer",
        "positiveInteger",
        "negativeInteger",
        "nonNegativeInteger",
        "nonPositiveInteger",
        "long",
        "unsignedLong",
        "int",
        "unsignedInt",
        "short",
        "unsignedShort",
        "byte",
        "unsignedByte",
        "decimal",
    }
)
integerXsdTypes = frozenset({
        "integer",
        "positiveInteger",
        "negativeInteger",
        "nonNegativeInteger",
        "nonPositiveInteger",
        "long",
        "unsignedLong",
        "int",
        "unsignedInt",
        "short",
        "unsignedShort",
        "byte",
        "unsignedByte",
    }
)

def isNumericXsdType(xsdType: str | None) -> bool:
    return xsdType in numericXsdTypes


def isDecimalXsdType(xsdType: str | None) -> bool:
    return xsdType in decimalXsdTypes


def isIntegerXsdType(xsdType: str | None) -> bool:
    return xsdType in integerXsdTypes


baseXbrliTypes = frozenset({
    "decimalItemType", "floatItemType", "doubleItemType", "integerItemType",
    "nonPositiveIntegerItemType", "negativeIntegerItemType", "longItemType", "intItemType",
    "shortItemType", "byteItemType", "nonNegativeIntegerItemType", "unsignedLongItemType",
    "unsignedIntItemType", "unsignedShortItemType", "unsignedByteItemType",
    "positiveIntegerItemType", "monetaryItemType", "sharesItemType", "pureItemType",
    "fractionItemType", "stringItemType", "booleanItemType", "hexBinaryItemType",
    "base64BinaryItemType", "anyURIItemType", "QNameItemType", "durationItemType",
    "dateTimeItemType", "timeItemType", "dateItemType", "gYearMonthItemType",
    "gYearItemType", "gMonthDayItemType", "gDayItemType", "gMonthItemType",
    "normalizedStringItemType", "tokenItemType", "languageItemType", "NameItemType", "NCNameItemType"
})
standardLabelRoles = frozenset({
    "http://www.xbrl.org/2003/role/label",
    "http://www.xbrl.org/2003/role/terseLabel",
    "http://www.xbrl.org/2003/role/verboseLabel",
    "http://www.xbrl.org/2003/role/positiveLabel",
    "http://www.xbrl.org/2003/role/positiveTerseLabel",
    "http://www.xbrl.org/2003/role/positiveVerboseLabel",
    "http://www.xbrl.org/2003/role/negativeLabel",
    "http://www.xbrl.org/2003/role/negativeTerseLabel",
    "http://www.xbrl.org/2003/role/negativeVerboseLabel",
    "http://www.xbrl.org/2003/role/zeroLabel",
    "http://www.xbrl.org/2003/role/zeroTerseLabel",
    "http://www.xbrl.org/2003/role/zeroVerboseLabel",
    "http://www.xbrl.org/2003/role/totalLabel",
    "http://www.xbrl.org/2003/role/periodStartLabel",
    "http://www.xbrl.org/2003/role/periodEndLabel",
    "http://www.xbrl.org/2003/role/documentation",
    "http://www.xbrl.org/2003/role/definitionGuidance",
    "http://www.xbrl.org/2003/role/disclosureGuidance",
    "http://www.xbrl.org/2003/role/presentationGuidance",
    "http://www.xbrl.org/2003/role/measurementGuidance",
    "http://www.xbrl.org/2003/role/commentaryGuidance",
    "http://www.xbrl.org/2003/role/exampleGuidance",
})
standardReferenceRoles = frozenset({
    "http://www.xbrl.org/2003/role/reference",
    "http://www.xbrl.org/2003/role/definitionRef",
    "http://www.xbrl.org/2003/role/disclosureRef",
    "http://www.xbrl.org/2003/role/mandatoryDisclosureRef",
    "http://www.xbrl.org/2003/role/recommendedDisclosureRef",
    "http://www.xbrl.org/2003/role/unspecifiedDisclosureRef",
    "http://www.xbrl.org/2003/role/presentationRef",
    "http://www.xbrl.org/2003/role/measurementRef",
    "http://www.xbrl.org/2003/role/commentaryRef",
    "http://www.xbrl.org/2003/role/exampleRef",
})
standardLinkbaseRefRoles = frozenset({
    "http://www.xbrl.org/2003/role/calculationLinkbaseRef",
    "http://www.xbrl.org/2003/role/definitionLinkbaseRef",
    "http://www.xbrl.org/2003/role/labelLinkbaseRef",
    "http://www.xbrl.org/2003/role/presentationLinkbaseRef",
    "http://www.xbrl.org/2003/role/referenceLinkbaseRef",
})
standardRoles = (
    standardLabelRoles
    | standardReferenceRoles
    | standardLinkbaseRefRoles
    | {"http://www.xbrl.org/2003/role/link", "http://www.xbrl.org/2003/role/footnote"}
)
totalRoles = frozenset({
        "http://www.xbrl.org/2003/role/totalLabel",
        "http://xbrl.us/us-gaap/role/label/negatedTotal",
        "http://www.xbrl.org/2009/role/negatedTotalLabel",
    })
netRoles = frozenset(
    {
        "http://www.xbrl.org/2009/role/netLabel",
        "http://www.xbrl.org/2009/role/negatedNetLabel"
    }
)
numericRoles = frozenset(
    {
        "http://www.xbrl.org/2003/role/totalLabel",
        "http://www.xbrl.org/2003/role/positiveLabel",
        "http://www.xbrl.org/2003/role/negativeLabel",
        "http://www.xbrl.org/2003/role/zeroLabel",
        "http://www.xbrl.org/2003/role/positiveTerseLabel",
        "http://www.xbrl.org/2003/role/negativeTerseLabel",
        "http://www.xbrl.org/2003/role/zeroTerseLabel",
        "http://www.xbrl.org/2003/role/positiveVerboseLabel",
        "http://www.xbrl.org/2003/role/negativeVerboseLabel",
        "http://www.xbrl.org/2003/role/zeroVerboseLabel",
        "http://www.xbrl.org/2009/role/negatedLabel",
        "http://www.xbrl.org/2009/role/negatedPeriodEndLabel",
        "http://www.xbrl.org/2009/role/negatedPeriodStartLabel",
        "http://www.xbrl.org/2009/role/negatedTotalLabel",
        "http://www.xbrl.org/2009/role/negatedNetLabel",
        "http://www.xbrl.org/2009/role/negatedTerseLabel",
    }
)

def isStandardRole(role: str | None) -> bool:
    return role in standardRoles


def isTotalRole(role: str | None) -> bool:
    return role in totalRoles


def isNetRole(role: str | None) -> bool:
    return role in netRoles


def isLabelRole(role: str | None) -> bool:
    return role in standardLabelRoles or role == genLabel


def isNumericRole(role: str | None) -> bool:
    return role in numericRoles


dimensionsSpecArcroles = frozenset({
    all,
    notAll,
    hypercubeDimension,
    dimensionDomain,
    domainMember,
    dimensionDefault,
})
standardDimensionArcroles = dimensionsSpecArcroles

baseSpecDefinitionArcroles =  frozenset({
    essenceAlias,
    generalSpecial,
    requiresElement,
    similarTuples,
})

standardDefinitionArcroles = baseSpecDefinitionArcroles | dimensionsSpecArcroles


standardArcroles = baseSpecDefinitionArcroles | {
        "http://www.w3.org/1999/xlink/properties/linkbase",
        "http://www.xbrl.org/2003/arcrole/concept-label",
        "http://www.xbrl.org/2003/arcrole/concept-reference",
        "http://www.xbrl.org/2003/arcrole/fact-footnote",
        "http://www.xbrl.org/2003/arcrole/parent-child",
        "http://www.xbrl.org/2003/arcrole/summation-item",
}


def isStandardArcrole(role: str) -> bool:
    return role in standardArcroles


standardArcroleCyclesAllowed: dict[str, tuple[str, str | None]] = {
    "http://www.xbrl.org/2003/arcrole/concept-label": ("any", None),
    "http://www.xbrl.org/2003/arcrole/concept-reference": ("any", None),
    "http://www.xbrl.org/2003/arcrole/fact-footnote": ("any", None),
    "http://www.xbrl.org/2003/arcrole/parent-child": ("undirected", "xbrl.5.2.4.2"),
    "http://www.xbrl.org/2003/arcrole/summation-item": ("any", "xbrl.5.2.5.2"),
    "http://www.xbrl.org/2003/arcrole/general-special": ("undirected", "xbrl.5.2.6.2.1"),
    "http://www.xbrl.org/2003/arcrole/essence-alias": ("undirected", "xbrl.5.2.6.2.1"),
    "http://www.xbrl.org/2003/arcrole/similar-tuples": ("any", "xbrl.5.2.6.2.3"),
    "http://www.xbrl.org/2003/arcrole/requires-element": ("any", "xbrl.5.2.6.2.4"),
}


def standardArcroleArcElement(arcrole: str) -> str:
    return {
        "http://www.xbrl.org/2003/arcrole/concept-label": "labelArc",
        "http://www.xbrl.org/2003/arcrole/concept-reference": "referenceArc",
        "http://www.xbrl.org/2003/arcrole/fact-footnote": "footnoteArc",
        "http://www.xbrl.org/2003/arcrole/parent-child": "presentationArc",
        "http://www.xbrl.org/2003/arcrole/summation-item": "calculationArc",
        "http://www.xbrl.org/2003/arcrole/general-special": "definitionArc",
        "http://www.xbrl.org/2003/arcrole/essence-alias": "definitionArc",
        "http://www.xbrl.org/2003/arcrole/similar-tuples": "definitionArc",
        "http://www.xbrl.org/2003/arcrole/requires-element": "definitionArc",
    }[arcrole]


def isDefinitionOrXdtArcrole(arcrole: str) -> bool:
    return arcrole in standardDefinitionArcroles


def isStandardResourceOrExtLinkElement(element: ModelObject) -> bool:
    return (
        element.namespaceURI == link
        and element.localName
        in {
            "definitionLink",
            "calculationLink",
            "presentationLink",
            "labelLink",
            "referenceLink",
            "footnoteLink",
            "label",
            "footnote",
            "reference",
        }
        or element.qname == qnIXbrl11Relationship
    )


def isStandardArcElement(element: ModelObject) -> bool:
    return (
        element.namespaceURI == link
        and element.localName
        in {"definitionArc", "calculationArc", "presentationArc", "labelArc", "referenceArc", "footnoteArc"}
        or element.qname == qnIXbrl11Relationship
    )


def isStandardArcInExtLinkElement(element: ModelObject) -> bool:
    return (
        isStandardArcElement(element) and isStandardResourceOrExtLinkElement(cast("ModelObject", element.getparent()))
    ) or element.qname == qnIXbrl11Relationship


standardExtLinkQnames = frozenset({
    qnLinkDefinitionLink,
    qnLinkCalculationLink,
    qnLinkPresentationLink,
    qnLinkLabelLink,
    qnLinkReferenceLink,
    qnLinkFootnoteLink,
})

standardExtLinkQnamesAndResources = frozenset({
    qnLinkDefinitionLink,
    qnLinkCalculationLink,
    qnLinkPresentationLink,
    qnLinkLabelLink,
    qnLinkReferenceLink,
    qnLinkFootnoteLink,
    qnLinkLabel,
    qnLinkFootnote,
    qnLinkReference,
})


def isStandardExtLinkQname(qName: QName) -> bool:
    return qName in standardExtLinkQnamesAndResources


def isStandardArcQname(qName: QName) -> bool:
    return qName in {
        qnLinkDefinitionArc,
        qnLinkCalculationArc,
        qnLinkPresentationArc,
        qnLinkLabelArc,
        qnLinkReferenceArc,
        qnLinkFootnoteArc,
    }


def isDimensionArcrole(arcrole: str) -> bool:
    return arcrole in dimensionsSpecArcroles


consecutiveArcrole: dict[str, str | tuple[str, ...]] = {  # can be list of or single arcrole
    all: (dimensionDomain, hypercubeDimension),
    notAll: (dimensionDomain, hypercubeDimension),
    hypercubeDimension: dimensionDomain,
    dimensionDomain: (domainMember, all, notAll),
    domainMember: (domainMember, all, notAll),
    dimensionDefault: (),
}


tableRenderingArcroles = frozenset({
    # current PWD 2013-05-17
    tableBreakdown,
    tableBreakdownTree,
    tableFilter,
    tableParameter,
    tableDefinitionNodeSubtree,
    tableAspectNodeFilter,
    # current IWD
    tableBreakdownMMDD,
    tableBreakdownTreeMMDD,
    tableFilterMMDD,
    tableParameterMMDD,
    tableDefinitionNodeSubtreeMMDD,
    tableAspectNodeFilterMMDD,
})

def isTableRenderingArcrole(arcrole: str | None) -> bool:
    return arcrole in tableRenderingArcroles


tableIndexingArcroles = frozenset({
    euGroupTable,
})

def isTableIndexingArcrole(arcrole: str | None) -> bool:
    return arcrole in tableIndexingArcroles


formulaArcroles = frozenset({
    "http://xbrl.org/arcrole/2008/assertion-set",
    "http://xbrl.org/arcrole/2008/variable-set",
    "http://xbrl.org/arcrole/2008/variable-set-filter",
    "http://xbrl.org/arcrole/2008/variable-filter",
    "http://xbrl.org/arcrole/2008/boolean-filter",
    "http://xbrl.org/arcrole/2008/variable-set-precondition",
    "http://xbrl.org/arcrole/2008/consistency-assertion-formula",
    "http://xbrl.org/arcrole/2010/function-implementation",
    "http://xbrl.org/arcrole/2010/assertion-satisfied-message",
    "http://xbrl.org/arcrole/2010/assertion-unsatisfied-message",
    "http://xbrl.org/arcrole/PR/2015-11-18/assertion-unsatisfied-severity",
    "http://xbrl.org/arcrole/2010/instance-variable",
    "http://xbrl.org/arcrole/2010/formula-instance",
    "http://xbrl.org/arcrole/2010/function-implementation",
    "http://xbrl.org/arcrole/2010/variables-scope",
})

def isFormulaArcrole(arcrole: str | None) -> bool:
    return arcrole in formulaArcroles


resourceArcroles = frozenset({
    "http://www.xbrl.org/2003/arcrole/concept-label",
    "http://www.xbrl.org/2003/arcrole/concept-reference",
    "http://www.xbrl.org/2003/arcrole/fact-footnote",
    "http://xbrl.org/arcrole/2008/element-label",
    "http://xbrl.org/arcrole/2008/element-reference",
}) | formulaArcroles


def isResourceArcrole(arcrole: str | None) -> bool:
    return arcrole in resourceArcroles


# LRR (https://specifications.xbrl.org/registries/lrr-2.0/index.html)
lrrRoleHrefs = {
    "http://www.xbrl.org/2006/role/restatedLabel": "http://www.xbrl.org/lrr/role/restated-2006-02-21.xsd#restatedLabel",
    "http://xbrl.us/us-gaap/role/label/negated": "http://www.xbrl.org/lrr/role/negated-2008-03-31.xsd#negated",
    "http://xbrl.us/us-gaap/role/label/negatedPeriodEnd": "http://www.xbrl.org/lrr/role/negated-2008-03-31.xsd#negatedPeriodEnd",
    "http://xbrl.us/us-gaap/role/label/negatedPeriodStart": "http://www.xbrl.org/lrr/role/negated-2008-03-31.xsd#negatedPeriodStart",
    "http://xbrl.us/us-gaap/role/label/negatedTotal": "http://www.xbrl.org/lrr/role/negated-2008-03-31.xsd#negatedTotal",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/periodStartNegativeLabel": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RolePeriodStartNegativeLabel",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/periodEndNegativeLabel": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RolePeriodEndNegativeLabel",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/positiveOrNegativeLabel": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RolePositiveOrNegativeLabel",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/periodStartPositiveOrNegativeLabel": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RolePeriodStartPositiveOrNegativeLabel",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/periodEndPositiveOrNegativeLabel": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RolePeriodEndPositiveOrNegativeLabel",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/NotesNumber": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RoleNotesNumber",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/NotesNumberPeriodStart": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RoleNotesNumberPeriodStart",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/NotesNumberPeriodEnd": "http://www.xbrl.org/lrr/role/jpfr-role-2007-11-07.xsd#RoleNotesNumberPeriodEnd",
    "http://www.xbrl.org/2009/role/negatedLabel": "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#negatedLabel",
    "http://www.xbrl.org/2009/role/negatedPeriodEndLabel": "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#negatedPeriodEndLabel",
    "http://www.xbrl.org/2009/role/negatedPeriodStartLabel": "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#negatedPeriodStartLabel",
    "http://www.xbrl.org/2009/role/negatedTotalLabel": "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#negatedTotalLabel",
    "http://www.xbrl.org/2009/role/negatedNetLabel": "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#negatedNetLabel",
    "http://www.xbrl.org/2009/role/negatedTerseLabel": "http://www.xbrl.org/lrr/role/negated-2009-12-16.xsd#negatedTerseLabel",
    "http://www.xbrl.org/2009/role/negativePeriodStartLabel": "http://www.xbrl.org/lrr/role/negative-2009-12-16.xsd#negativePeriodStartLabel",
    "http://www.xbrl.org/2009/role/negativePeriodEndLabel": "http://www.xbrl.org/lrr/role/negative-2009-12-16.xsd#negativePeriodEndLabel",
    "http://www.xbrl.org/2009/role/negativePeriodStartTotalLabel": "http://www.xbrl.org/lrr/role/negative-2009-12-16.xsd#negativePeriodStartTotalLabel",
    "http://www.xbrl.org/2009/role/negativePeriodEndTotalLabel": "http://www.xbrl.org/lrr/role/negative-2009-12-16.xsd#negativePeriodEndTotalLabel",
    "http://www.xbrl.org/2009/role/positivePeriodStartLabel": "http://www.xbrl.org/lrr/role/positive-2009-12-16.xsd#positivePeriodStartLabel",
    "http://www.xbrl.org/2009/role/positivePeriodEndLabel": "http://www.xbrl.org/lrr/role/positive-2009-12-16.xsd#positivePeriodEndLabel",
    "http://www.xbrl.org/2009/role/positivePeriodStartTotalLabel": "http://www.xbrl.org/lrr/role/positive-2009-12-16.xsd#positivePeriodStartTotalLabel",
    "http://www.xbrl.org/2009/role/positivePeriodEndTotalLabel": "http://www.xbrl.org/lrr/role/positive-2009-12-16.xsd#positivePeriodEndTotalLabel",
    "http://www.xbrl.org/2009/role/netLabel": "http://www.xbrl.org/lrr/role/net-2009-12-16.xsd#netLabel",
    "http://www.xbrl.org/2009/role/deprecatedLabel": "http://www.xbrl.org/lrr/role/deprecated-2009-12-16.xsd#deprecatedLabel",
    "http://www.xbrl.org/2009/role/deprecatedDateLabel": "http://www.xbrl.org/lrr/role/deprecated-2009-12-16.xsd#deprecatedDateLabel",
    "http://www.xbrl.org/2009/role/commonPracticeRef": "http://www.xbrl.org/lrr/role/reference-2009-12-16.xsd#commonPracticeRef",
    "http://www.xbrl.org/2009/role/nonauthoritativeLiteratureRef": "http://www.xbrl.org/lrr/role/reference-2009-12-16.xsd#nonauthoritativeLiteratureRef",
    "http://www.xbrl.org/2009/role/recognitionRef": "http://www.xbrl.org/lrr/role/reference-2009-12-16.xsd#recognitionRef",
}
lrrArcroleHrefs = {
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/arcrole/Gross-Net": "http://www.xbrl.org/lrr/arcrole/jpfr-arcrole-2007-11-07.xsd#ArcroleGrossNet",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/arcrole/Gross-Allowance": "http://www.xbrl.org/lrr/arcrole/jpfr-arcrole-2007-11-07.xsd#ArcroleGrossAllowance",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/arcrole/Gross-AccumulatedDepreciation": "http://www.xbrl.org/lrr/arcrole/jpfr-arcrole-2007-11-07.xsd#ArcroleGrossAccumulatedDepreciation",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/arcrole/Gross-AccumulatedImpairmentLoss": "http://www.xbrl.org/lrr/arcrole/jpfr-arcrole-2007-11-07.xsd#ArcroleGrossAccumulatedImpairmentLoss",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/arcrole/Gross-AccumulatedDepreciationAndImpairmentLoss": "http://www.xbrl.org/lrr/arcrole/jpfr-arcrole-2007-11-07.xsd#ArcroleGrossAccumulatedDepreciationAndImpairmentLoss",
    "http://www.xbrl.org/2009/arcrole/fact-explanatoryFact": "http://www.xbrl.org/lrr/arcrole/factExplanatory-2009-12-16.xsd#fact-explanatoryFact",
    "http://www.xbrl.org/2009/arcrole/dep-concept-deprecatedConcept": "http://www.xbrl.org/lrr/arcrole/deprecated-2009-12-16.xsd#dep-concept-deprecatedConcept",
    "http://www.xbrl.org/2009/arcrole/dep-aggregateConcept-deprecatedPartConcept": "http://www.xbrl.org/lrr/arcrole/deprecated-2009-12-16.xsd#dep-aggregateConcept-deprecatedPartConcept",
    "http://www.xbrl.org/2009/arcrole/dep-dimensionallyQualifiedConcept-deprecatedConcept": "http://www.xbrl.org/lrr/arcrole/deprecated-2009-12-16.xsd#dep-dimensionallyQualifiedConcept-deprecatedConcept",
    "http://www.xbrl.org/2009/arcrole/dep-mutuallyExclusiveConcept-deprecatedConcept": "http://www.xbrl.org/lrr/arcrole/deprecated-2009-12-16.xsd#dep-mutuallyExclusiveConcept-deprecatedConcept",
    "http://www.xbrl.org/2009/arcrole/dep-partConcept-deprecatedAggregateConcept": "http://www.xbrl.org/lrr/arcrole/deprecated-2009-12-16.xsd#dep-partConcept-deprecatedAggregateConcept",
    "http://www.xbrl.org/2013/arcrole/parent-child": "http://www.xbrl.org/lrr/arcrole/parent-child-2013-09-19.xsd#parent-child",
    "http://www.esma.europa.eu/xbrl/esef/arcrole/wider-narrower": "http://www.xbrl.org/lrr/arcrole/esma-arcrole-2018-11-21.xsd#wider-narrower",
}
lrrUnapprovedRoles = {  # lrr entries which are not REC or ACK status
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/NotesNumber": "IWD",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/NotesNumberPeriodStart": "IWD",
    "http://info.edinet-fsa.go.jp/jp/fr/gaap/role/NotesNumberPeriodEnd": "IWD",
    # proposed but commented out in lrr
    "http://www.xbrl.org/2013/arcrole/item-enumeration": "PROPOSED",
    # only for test case use
    "http://www.xbrl.org/2005/role/nieRole": "NIE",
}
lrrUnapprovedArcroles = {  # lrr entries which are not REC or ACK status
    # only for test case use
    "http://www.xbrl.org/2005/arcrole/nieRole": "NIE",
}


_DEPRECATIONS = ModuleDeprecations(__name__)
_DEPRECATIONS.add("tuple", formulaTuple, "use XbrlConst.formulaTuple instead.")
_DEPRECATIONS.add("dimStartsWith", "http://xbrl.org/int/dim", "use XbrlConst.isDimensionArcrole() instead.")
_DEPRECATIONS.add("dtrTypesStartsWith", _dtrTypesStartsWith, "use XbrlConst.isDtrTypeNamespace() instead.")


def __getattr__(name: str) -> Any:
    return _DEPRECATIONS.resolve(name)
