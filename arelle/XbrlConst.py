from arelle.ModelValue import qname
import os
try:
    from regex import compile as re_compile
except ImportError:
    from re import compile as re_compile
from arelle.arelle_c import QName, AnyURI

xsd = AnyURI("http://www.w3.org/2001/XMLSchema")
xsSyntheticAnnotation = AnyURI("http://arelle.org/2018/XsSynAnot") # same string length as xsd
hrefXsSyntheticAnnotation = AnyURI("http://arelle.org/2018/XsSyntheticAnnotation.xsd")
hrefXsd = AnyURI("http://www.w3.org/2001/XMLSchema.xsd")
qnXsdSchema = QName(xsd, "xsd", "schema")
qnXsdAppinfo = QName(xsd, "xsd", "appinfo")
qnXsSyntheticAnnotationAppinfo = QName(xsSyntheticAnnotation, "xsd", "appinfo")
qnXsdDefaultType = QName(xsd, "xsd", "anyType")
xsi = AnyURI("http://www.w3.org/2001/XMLSchema-instance")
qnXsiNil = QName(xsi, "xsi", "nil")
builtinAttributes = {qnXsiNil,
                     QName(xsi,"xsi", "type"),
                     QName(xsi,"xsi", "schemaLocation")
                     ,QName(xsi,"xsi", "noNamespaceSchemaLocation")}
xml = AnyURI("http://www.w3.org/XML/1998/namespace")
hrefXml = AnyURI("http://www.w3.org/2001/xml.xsd")
hrefXml = AnyURI("http://www.w3.org/2001/xml.xsd")
qnXmlLang = QName(xml, "xml", "lang")
xbrli = AnyURI("http://www.xbrl.org/2003/instance")
hrefXbrli = AnyURI("http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd")
eurofilingModelNamespace = AnyURI("http://www.eurofiling.info/xbrl/ext/model")
eurofilingModelPrefix = "model"
qnNsmap = qname("nsmap") # artificial parent for insertion of xmlns in saving xml documents
qnXbrliXbrl = QName(xbrli, "xbrli", "xbrl")
qnXbrliItem = QName(xbrli, "xbrli", "item")
qnXbrliNumerator = QName(xbrli, "xbrli", "numerator")
qnXbrliDenominator = QName(xbrli, "xbrli", "denominator")
qnXbrliTuple = QName(xbrli, "xbrli", "tuple")
qnXbrliContext = QName(xbrli, "xbrli", "context")
qnXbrliPeriod = QName(xbrli, "xbrli", "period")
qnXbrliIdentifier = QName(xbrli, "xbrli", "identifier")
qnXbrliUnit = QName(xbrli, "xbrli", "unit")
qnXbrliStringItemType = QName(xbrli, "xbrli", "stringItemType")
qnXbrliMonetaryItemType = QName(xbrli, "xbrli", "monetaryItemType")
qnXbrliDateItemType = QName(xbrli, "xbrli", "dateItemType")
qnXbrliDurationItemType = QName(xbrli, "xbrli", "durationItemType")
qnXbrliBooleanItemType = QName(xbrli, "xbrli", "booleanItemType")
qnXbrliQNameItemType = QName(xbrli, "xbrli", "QNameItemType")
qnXbrliPure = QName(xbrli, "xbrli", "pure")
qnXbrliShares = QName(xbrli, "xbrli", "shares")
qnInvalidMeasure = QName("http://arelle.org", "arelle", "invalidMeasureQName")
qnXbrliDateUnion = QName(xbrli, "xbrli", "dateUnion")
qnDateUnionXsdTypes = [QName(xsd, "xsd", "date"),QName(xsd, "xsd", "dateTime")]
qnXbrliDecimalsUnion = QName(xbrli, "xbrli", "decimalsType")
qnXbrliPrecisionUnion = QName(xbrli, "xbrli", "precisionType")
qnXbrliNonZeroDecimalUnion = QName(xbrli, "xbrli", "nonZeroDecimal")
link = AnyURI("http://www.xbrl.org/2003/linkbase")
hrefLink = AnyURI("http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd")
qnLinkRoleType = QName(link, "link", "roleType")
qnLinkArcroleType = QName(link, "link", "arcroleType")
qnLinkLinkbase = QName(link, "link", "linkbase")
qnLinkLinkbaseRef = QName(link, "link", "linkbaseRef")
qnLinkLoc = QName(link, "link", "loc")
qnLinkLabelLink = QName(link, "link", "labelLink")
qnLinkLabelArc = QName(link, "link", "labelArc")
qnLinkLabel = QName(link, "link", "label")
qnLinkReferenceLink = QName(link, "link", "referenceLink")
qnLinkReferenceArc = QName(link, "link", "referenceArc")
qnLinkReference = QName(link, "link", "reference")
qnLinkPart = QName(link, "link", "part")
qnLinkFootnoteLink = QName(link, "link", "footnoteLink")
qnLinkFootnoteArc = QName(link, "link", "footnoteArc")
qnLinkFootnote = QName(link, "link", "footnote")
qnLinkPresentationLink = QName(link, "link", "presentationLink")
qnLinkPresentationArc = QName(link, "link", "presentationArc")
qnLinkCalculationLink = QName(link, "link", "calculationLink")
qnLinkCalculationArc = QName(link, "link", "calculationArc")
qnLinkDefinitionLink = QName(link, "link", "definitionLink")
qnLinkDefinitionArc = QName(link, "link", "definitionArc")
gen = AnyURI("http://xbrl.org/2008/generic")
qnGenLink = QName(gen, "gen", "link")
qnGenArc = QName(gen, "gen", "arc")
elementReference = AnyURI("http://xbrl.org/arcrole/2008/element-reference")
genReference = AnyURI("http://xbrl.org/2008/reference")
qnGenReference = QName(genReference, None, "reference")
elementLabel = AnyURI("http://xbrl.org/arcrole/2008/element-label")
genLabel = AnyURI("http://xbrl.org/2008/label")
qnGenLabel = QName(genLabel, None, "label")
xbrldt = AnyURI("http://xbrl.org/2005/xbrldt")
qnXbrldtHypercubeItem = QName(xbrldt, "xbrldt", "hypercubeItem")
qnXbrldtDimensionItem = QName(xbrldt, "xbrldt", "dimensionItem")
qnXbrldtContextElement = QName(xbrldt, "xbrldt", "contextElement")
xbrldi = AnyURI("http://xbrl.org/2006/xbrldi")
hrefXbrldi = AnyURI("http://www.xbrl.org/2006/xbrldi-2006.xsd")
qnXbrldiExplicitMember = QName(xbrldi, "xbrldi", "explicitMember")
qnXbrldiTypedMember = QName(xbrldi, "xbrldi", "typedMember")
xlink = AnyURI("http://www.w3.org/1999/xlink")
hrefXlink = AnyURI("http://www.xbrl.org/2003/xlink-2003-12-31.xsd")
xl = AnyURI("http://www.xbrl.org/2003/XLink")
qnXlExtended = QName(xl, "xl", "extended")
qnXlLocator = QName(xl, "xl", "locator")
qnXlResource = QName(xl, "xl", "resource")
qnXlExtendedType = QName(xl, "xl", "extendedType")
qnXlLocatorType = QName(xl, "xl", "locatorType")
qnXlResourceType = QName(xl, "xl", "resourceType")
qnXlArcType = QName(xl, "xl", "arcType")
xhtml = AnyURI("http://www.w3.org/1999/xhtml")
ixbrl = AnyURI("http://www.xbrl.org/2008/inlineXBRL")
ixbrl11 = AnyURI("http://www.xbrl.org/2013/inlineXBRL")
ixbrlAll = {ixbrl, ixbrl11}
hrefIxbrl = AnyURI("http://www.xbrl.org/2008/inlineXBRL/xhtml-inlinexbrl-1_0.xsd")
hrefIxbrlxsd = AnyURI("xhtml-inlinexbrl-1_0.xsd")
hrefIxbrl11 = AnyURI("http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1.xsd")
hrefIxbrl11xsd = AnyURI("xhtml-inlinexbrl-1_1.xsd")
qnIXbrlResources = QName(ixbrl, None, "resources")
qnIXbrlTuple = QName(ixbrl, None, "tuple")
qnIXbrlNonNumeric = QName(ixbrl, None, "nonNumeric")
qnIXbrlNonFraction = QName(ixbrl, None, "nonFraction")
qnIXbrlFraction = QName(ixbrl, None, "fraction")
qnIXbrlNumerator = QName(ixbrl, None, "numerator")
qnIXbrlDenominator = QName(ixbrl, None, "denominator")
qnIXbrlFootnote = QName(ixbrl, None, "footnote")
qnIXbrl11Resources = QName(ixbrl11, None, "resources")
qnIXbrl11Tuple = QName(ixbrl11, None, "tuple")
qnIXbrl11NonNumeric = QName(ixbrl11, None, "nonNumeric")
qnIXbrl11NonFraction = QName(ixbrl11, None, "nonFraction")
qnIXbrl11Fraction = QName(ixbrl11, None, "fraction")
qnIXbrl11Numerator = QName(ixbrl11, None, "numerator")
qnIXbrl11Denominator = QName(ixbrl11, None, "denominator")
qnIXbrl11Footnote = QName(ixbrl11, None, "footnote")
qnIXbrl11Relationship = QName(ixbrl11, None, "relationship")
qnIXbrl11Hidden = QName(ixbrl11, None, "hidden")
ixAttributes = set(qname(n, noPrefixIsNoNamespace=True)
                   for n in ("continuedAt", "escape", "footnoteRefs", "format", "name", "order",  
                             "scale", "sign","target", "tupleRef", "tupleID"))
conceptLabel = AnyURI("http://www.xbrl.org/2003/arcrole/concept-label")
conceptReference = AnyURI("http://www.xbrl.org/2003/arcrole/concept-reference")
footnote = AnyURI("http://www.xbrl.org/2003/role/footnote")
factFootnote = AnyURI("http://www.xbrl.org/2003/arcrole/fact-footnote")
factExplanatoryFact = AnyURI("http://www.xbrl.org/2009/arcrole/fact-explanatoryFact")
parentChild = AnyURI("http://www.xbrl.org/2003/arcrole/parent-child")
summationItem = AnyURI("http://www.xbrl.org/2003/arcrole/summation-item")
essenceAlias = AnyURI("http://www.xbrl.org/2003/arcrole/essence-alias")
similarTuples = AnyURI("http://www.xbrl.org/2003/arcrole/similar-tuples")
requiresElement = AnyURI("http://www.xbrl.org/2003/arcrole/requires-element")
generalSpecial = AnyURI("http://www.xbrl.org/2003/arcrole/general-special")
dimStartsWith = AnyURI("http://xbrl.org/int/dim")
all = AnyURI("http://xbrl.org/int/dim/arcrole/all")
notAll = AnyURI("http://xbrl.org/int/dim/arcrole/notAll")
hypercubeDimension = AnyURI("http://xbrl.org/int/dim/arcrole/hypercube-dimension")
dimensionDomain = AnyURI("http://xbrl.org/int/dim/arcrole/dimension-domain")
domainMember = AnyURI("http://xbrl.org/int/dim/arcrole/domain-member")
dimensionDefault = AnyURI("http://xbrl.org/int/dim/arcrole/dimension-default")
dtrTypesStartsWith = AnyURI("http://www.xbrl.org/dtr/type/")
dtrNumeric = AnyURI("http://www.xbrl.org/dtr/type/numeric")
defaultLinkRole = AnyURI("http://www.xbrl.org/2003/role/link")
defaultGenLinkRole = AnyURI("http://www.xbrl.org/2008/role/link")
iso4217 = AnyURI("http://www.xbrl.org/2003/iso4217")
iso17442 = AnyURI("http://standards.iso.org/iso/17442")
def qnIsoCurrency(token):
    return qname(iso4217, "iso4217:" + token) if token else None
standardLabel = AnyURI("http://www.xbrl.org/2003/role/label")
genStandardLabel = AnyURI("http://www.xbrl.org/2008/role/label")
documentationLabel = AnyURI("http://www.xbrl.org/2003/role/documentation")
genDocumentationLabel = AnyURI("http://www.xbrl.org/2008/role/documentation")
standardReference = AnyURI("http://www.xbrl.org/2003/role/reference")
genStandardReference = AnyURI("http://www.xbrl.org/2010/role/reference")
periodStartLabel = AnyURI("http://www.xbrl.org/2003/role/periodStartLabel")
periodEndLabel = AnyURI("http://www.xbrl.org/2003/role/periodEndLabel")
verboseLabel = AnyURI("http://www.xbrl.org/2003/role/verboseLabel")
terseLabel = AnyURI("http://www.xbrl.org/2003/role/terseLabel")
conceptNameLabelRole = AnyURI("XBRL-concept-name") # fake label role to show concept QName instead of label
xlinkLinkbase = AnyURI("http://www.w3.org/1999/xlink/properties/linkbase")

utr = AnyURI("http://www.xbrl.org/2009/utr")

dtr = AnyURI("http://www.xbrl.org/2009/dtr")
dtrTypesStartsWith = AnyURI("http://www.xbrl.org/dtr/type/")
dtrNumeric = AnyURI("http://www.xbrl.org/dtr/type/numeric")
dtrYMD = AnyURI("http://www.xbrl.org/dtr/type/WGWD/YYYY-MM-DD")

dtrNoDecimalsItemTypes = (QName(dtrYMD, None, "noDecimalsMonetaryItemType"), 
                          QName(dtrYMD, None, "nonNegativeNoDecimalsMonetaryItemType"))
dtrPrefixedContentItemTypes = (QName(dtrYMD, None, "prefixedContentItemType"), )
dtrPrefixedContentTypes = (QName(dtrYMD, None, "prefixedContentType"), )
dtrSQNameItemTypes = (QName(dtrYMD, None, "SQNameItemType"), )
dtrSQNameTypes = (QName(dtrYMD, None, "SQNameType"), )
dtrSQNamesItemTypes = (QName(dtrYMD, None, "SQNamesItemType"), )
dtrSQNamesTypes = (QName(dtrYMD, None, "SQNamesType"), )

wgnStringItemTypeNames = ("stringItemType", "normalizedStringItemType")
dtrNoLangItemTypeNames = ("domainItemType", "noLangTokenItem", "noLangStringItemType")
oimLangItemTypeNames = ("stringItemType", "normalizedStringItemType")

ver10 = AnyURI("http://xbrl.org/2010/versioning-base")
# 2010 names
vercb = AnyURI("http://xbrl.org/2010/versioning-concept-basic")
verce = AnyURI("http://xbrl.org/2010/versioning-concept-extended")
verrels = AnyURI("http://xbrl.org/2010/versioning-relationship-sets")
veria = AnyURI("http://xbrl.org/2010/versioning-instance-aspects")
# 2013 names
ver = AnyURI("http://xbrl.org/2013/versioning-base")
vercu = AnyURI("http://xbrl.org/2013/versioning-concept-use")
vercd = AnyURI("http://xbrl.org/2013/versioning-concept-details")
verdim = AnyURI("http://xbrl.org/2013/versioning-dimensions")
verPrefixNS = {"ver":ver,
               "vercu":vercu,
               "vercd":vercd,
               "verrels":verrels,
               "verdim":verdim,
               }

# extended enumeration spec
enum2014 = AnyURI("http://xbrl.org/2014/extensible-enumerations")
enum2016 = AnyURI("http://xbrl.org/PWD/2016-10-12/extensible-enumerations-1.1")
enumYMD = AnyURI("http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-1.1")
enum2YMD = AnyURI("http://xbrl.org/WGWD/YYYY-MM-DD/extensible-enumerations-2.0")
enum2020 = AnyURI("http://xbrl.org/2020/extensible-enumerations-2.0")
enum2s = {enum2YMD, enum2020}
enums = {enum2014, enum2016, enumYMD} | enum2s
qnEnumerationItemType2014 = QName(enum2014, "enum", "enumerationItemType")
qnEnumerationItemType2020 = QName(enum2020, "enum2", "enumerationItemType")
qnEnumerationItemTypeYYYY = QName(enum2YMD, "enum2", "enumerationItemType")
qnEnumerationSetItemType2020 = QName(enum2020, "enum2", "enumerationSetItemType")
qnEnumerationSetItemTypeYYYY = QName(enum2YMD, "enum2", "enumerationSetItemType")
qnEnumerationSetValDimType2020 = QName(enum2YMD, "enum2", "setValueDimensionType")
qnEnumerationSetValDimTypeYYYY = QName(enum2YMD, "enum2", "setValueDimensionType")
qnEnumerationItemType11YYYY = QName(enumYMD, "enum", "enumerationItemType")
qnEnumerationSetItemType11YYYY = QName(enumYMD, "enum", "enumerationSetItemType")
qnEnumerationListItemType11YYYY = QName(enumYMD, "enum", "enumerationListItemType")
qnEnumerationItemType2016 = QName(enum2016, "enum", "enumerationItemType")
qnEnumerationsItemType2016 = QName(enum2016, "enum", "enumerationsItemType")
qnEnumerationListItemTypes = (qnEnumerationListItemType11YYYY, qnEnumerationSetItemType11YYYY, qnEnumerationsItemType2016)
qnEnumerationSetItemTypes = (qnEnumerationSetItemType11YYYY, qnEnumerationSetItemTypeYYYY)
qnEnumeration2ItemTypes = (qnEnumerationItemType2020, qnEnumerationItemTypeYYYY, qnEnumerationSetItemType2020, qnEnumerationSetItemTypeYYYY)
qnEnumerationItemTypes = (qnEnumerationItemType2014, 
                          qnEnumerationItemType2020, qnEnumerationItemTypeYYYY, qnEnumerationSetItemType2020, qnEnumerationSetItemTypeYYYY, 
                          qnEnumerationItemType11YYYY, qnEnumerationSetItemType11YYYY, qnEnumerationListItemType11YYYY,
                          qnEnumerationItemType2016, qnEnumerationsItemType2016)
qnEnumerationTypes = qnEnumerationItemTypes + (qnEnumerationSetValDimType2020,qnEnumerationSetValDimTypeYYYY)
qnEnumeration2ItemTypes = (qnEnumerationItemType2020, qnEnumerationSetItemType2020)
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
variable = AnyURI("http://xbrl.org/2008/variable")
qnVariableSet = QName(variable, "variable", "variableSet")
qnVariableVariable = QName(variable, "variable", "variable")
qnVariableFilter = QName(variable, "variable", "filter")
qnVariableFilterArc = QName(variable, "variable", "variableFilterArc")
qnParameter = QName(variable, "variable", "parameter")
qnFactVariable = QName(variable, "variable", "factVariable")
qnGeneralVariable = QName(variable, "variable", "generalVariable")
qnPrecondition = QName(variable, "variable", "precondition")
qnEqualityDefinition = QName(variable, "variable", "equalityDefinition")
qnEqualityTestA = QName("http://xbrl.org/2008/variable/aspectTest", "aspectTest", "a")
qnEqualityTestB = QName("http://xbrl.org/2008/variable/aspectTest", "aspectTest", "b")
formula = AnyURI("http://xbrl.org/2008/formula")
tuple = AnyURI("http://xbrl.org/2010/formula/tuple")
qnFormula = QName(formula, "formula", "formula")
qnTuple = QName("http://xbrl.org/2010/formula/tuple", "tuple", "tuple")
qnFormulaUncovered = QName(formula, "formula", "uncovered")
qnFormulaDimensionSAV = QName(formula, "formula", "DimensionSAV") #signal that dimension aspect should use SAV of this dimension
qnFormulaOccEmpty = QName(formula, "formula", "occEmpty") #signal that OCC aspect should omit the SAV values
ca = AnyURI("http://xbrl.org/2008/assertion/consistency")
qnConsistencyAssertion = QName(ca, "ca", "consistencyAssertion")
qnCaAspectMatchedFacts = QName(ca, "ca", "aspect-matched-facts")
qnCaAcceptanceRadius = QName(ca, "ca", "ca:acceptance-radius")
qnCaAbsoluteAcceptanceRadiusExpression = QName(ca, "ca", "absolute-acceptance-radius-expression")
qnCaProportionalAcceptanceRadiusExpression = QName(ca, "ca", "proportional-acceptance-radius-expression")
ea = AnyURI("http://xbrl.org/2008/assertion/existence")
qnExistenceAssertion = QName(ea, "ea", "existenceAssertion")
qnEaTestExpression = qname(ea,'test-expression')
va = AnyURI("http://xbrl.org/2008/assertion/value")
qnValueAssertion = QName(va, "va", "valueAssertion")
qnVaTestExpression = QName(va,"va", 'test-expression')
variable = AnyURI("http://xbrl.org/2008/variable")
formulaStartsWith = AnyURI("http://xbrl.org/arcrole/20")
equalityDefinition = AnyURI("http://xbrl.org/arcrole/2008/equality-definition")
qnEqualityDefinition = QName("http://xbrl.org/2008/variable", "variable", "equalityDefinition")
variableSet = AnyURI("http://xbrl.org/arcrole/2008/variable-set")
variableSetFilter = AnyURI("http://xbrl.org/arcrole/2008/variable-set-filter")
variableFilter = AnyURI("http://xbrl.org/arcrole/2008/variable-filter")
variableSetPrecondition = AnyURI("http://xbrl.org/arcrole/2008/variable-set-precondition")
equalityDefinition = AnyURI("http://xbrl.org/arcrole/2008/equality-definition")
consistencyAssertionFormula = AnyURI("http://xbrl.org/arcrole/2008/consistency-assertion-formula")
consistencyAssertionParameter = AnyURI("http://xbrl.org/arcrole/2008/consistency-assertion-parameter")
validation = AnyURI("http://xbrl.org/2008/validation")
qnAssertion = QName(validation, "validation", "assertion")
qnVariableSetAssertion = QName(validation, "validation", "variableSetAssertion")
qnAssertionSet = QName(validation, "validation", "assertionSet")
assertionSet = AnyURI("http://xbrl.org/arcrole/2008/assertion-set")
assertionUnsatisfiedSeverity = AnyURI("http://xbrl.org/arcrole/2016/assertion-unsatisfied-severity")
qnAssertionSeverityError = QName("http://xbrl.org/2016/assertion-severity", "sev", "error")
qnAssertionSeverityWarning = QName("http://xbrl.org/2016/assertion-severity", "sev", "warning")
qnAssertionSeverityOk = QName("http://xbrl.org/2016/assertion-severity", "sev", "ok")

acf = AnyURI("http://xbrl.org/2010/filter/aspect-cover")
qnAspectCover = QName(acf, "acf", "aspectCover")
bf = AnyURI("http://xbrl.org/2008/filter/boolean")
qnAndFilter = QName(bf, "bf", "andFilter")
qnOrFilter = QName(bf, "bf", "orFilter")
booleanFilter = AnyURI("http://xbrl.org/arcrole/2008/boolean-filter")
cfi = AnyURI("http://xbrl.org/2010/custom-function")
functionImplementation = AnyURI("http://xbrl.org/arcrole/2010/function-implementation")
qnCustomFunctionSignature = QName("http://xbrl.org/2008/variable", "cfi", "function")
qnCustomFunctionImplementation = QName(cfi, "cfi", "implementation")
crf = AnyURI("http://xbrl.org/2010/filter/concept-relation")
qnConceptRelation = QName("http://xbrl.org/2010/filter/concept-relation", "crf", "conceptRelation")
cf = AnyURI("http://xbrl.org/2008/filter/concept")
qnConceptName = QName(cf, "cf", "conceptName")
qnConceptPeriodType = QName(cf, "cf", "conceptPeriodType")
qnConceptBalance = QName(cf, "cf", "conceptBalance")
qnConceptCustomAttribute = QName(cf, "cf", "conceptCustomAttribute")
qnConceptDataType = QName(cf, "cf", "conceptDataType")
qnConceptSubstitutionGroup = QName(cf, "cf", "conceptSubstitutionGroup")
cfcn = AnyURI("http://xbrl.org/2008/conformance/function")
df = AnyURI("http://xbrl.org/2008/filter/dimension")
qnExplicitDimension = QName("http://xbrl.org/2008/filter/dimension", "df", "explicitDimension")
qnTypedDimension = QName("http://xbrl.org/2008/filter/dimension", "df", "typedDimension")
ef = AnyURI("http://xbrl.org/2008/filter/entity")
qnEntityIdentifier = QName("http://xbrl.org/2008/filter/entity", "ef", "identifier")
qnEntitySpecificIdentifier = QName("http://xbrl.org/2008/filter/entity", "ef", "specificIdentifier")
qnEntitySpecificScheme = QName("http://xbrl.org/2008/filter/entity", "ef", "specificScheme")
qnEntityRegexpIdentifier = QName("http://xbrl.org/2008/filter/entity", "ef", "regexpIdentifier")
qnEntityRegexpScheme = QName("http://xbrl.org/2008/filter/entity", "ef", "regexpScheme")
function = AnyURI("http://xbrl.org/2008/function")
fn = AnyURI("http://www.w3.org/2005/xpath-functions")
xfi = AnyURI("http://www.xbrl.org/2008/function/instance")
qnXfiRoot = QName("http://www.xbrl.org/2008/function/instance", "xfi", "root")
xff = AnyURI("http://www.xbrl.org/2010/function/formula")
gf = AnyURI("http://xbrl.org/2008/filter/general")
qnGeneral = QName("http://xbrl.org/2008/filter/general", "gf", "general")
instances = AnyURI("http://xbrl.org/2010/variable/instance")
qnInstance = QName(instances,"instances", "instance")
instanceVariable = AnyURI("http://xbrl.org/arcrole/2010/instance-variable")
formulaInstance = AnyURI("http://xbrl.org/arcrole/2010/formula-instance")
qnStandardInputInstance = qname(instances,"instances:standard-input-instance")
qnStandardOutputInstance = qname(instances,"instances:standard-output-instance")
mf = AnyURI("http://xbrl.org/2008/filter/match")
qnMatchConcept = QName("http://xbrl.org/2008/filter/match", "mf", "matchConcept")
qnMatchDimension = QName("http://xbrl.org/2008/filter/match", "mf", "matchDimension")
qnMatchEntityIdentifier = QName("http://xbrl.org/2008/filter/match", "mf", "matchEntityIdentifier")
qnMatchLocation = QName("http://xbrl.org/2008/filter/match", "mf", "matchLocation")
qnMatchPeriod = QName("http://xbrl.org/2008/filter/match", "mf", "matchPeriod")
qnMatchSegment = QName("http://xbrl.org/2008/filter/match", "mf", "matchSegment")
qnMatchScenario = QName("http://xbrl.org/2008/filter/match", "mf", "matchScenario")
qnMatchNonXDTSegment = QName("http://xbrl.org/2008/filter/match", "mf", "matchNonXDTSegment")
qnMatchNonXDTScenario = QName("http://xbrl.org/2008/filter/match", "mf", "matchNonXDTScenario")
qnMatchUnit = QName("http://xbrl.org/2008/filter/match", "mf", "matchUnit")
msg = AnyURI("http://xbrl.org/2010/message")
qnMessage = QName("http://xbrl.org/2010/message", None, "message")
assertionSatisfiedMessage = AnyURI("http://xbrl.org/arcrole/2010/assertion-satisfied-message")
assertionUnsatisfiedMessage = AnyURI("http://xbrl.org/arcrole/2010/assertion-unsatisfied-message")
standardMessage = AnyURI("http://www.xbrl.org/2010/role/message")
terseMessage = AnyURI("http://www.xbrl.org/2010/role/terseMessage")
verboseMessage = AnyURI("http://www.xbrl.org/2010/role/verboseMessage")
pf = AnyURI("http://xbrl.org/2008/filter/period")
qnPeriod = QName("http://xbrl.org/2008/filter/period", "pf", "period")
qnPeriodStart = QName("http://xbrl.org/2008/filter/period", "pf", "periodStart")
qnPeriodEnd = QName("http://xbrl.org/2008/filter/period", "pf", "periodEnd")
qnPeriodInstant = QName("http://xbrl.org/2008/filter/period", "pf", "periodInstant")
qnForever = QName("http://xbrl.org/2008/filter/period", "pf", "forever")
qnInstantDuration = QName("http://xbrl.org/2008/filter/period", "pf", "instantDuration")
registry = AnyURI("http://xbrl.org/2008/registry")
rf = AnyURI("http://xbrl.org/2008/filter/relative")
qnRelativeFilter = QName("http://xbrl.org/2008/filter/relative", "rf", "relativeFilter")
ssf = AnyURI("http://xbrl.org/2008/filter/segment-scenario")
qnSegmentFilter = QName("http://xbrl.org/2008/filter/segment-scenario", "ssf", "segment")
qnScenarioFilter = QName("http://xbrl.org/2008/filter/segment-scenario", "ssf", "scenario")
tf = AnyURI("http://xbrl.org/2008/filter/tuple")
qnAncestorFilter = QName("http://xbrl.org/2008/filter/tuple", "tf", "ancestorFilter")
qnLocationFilter = QName("http://xbrl.org/2008/filter/tuple", "tf", "locationFilter")
qnParentFilter = QName("http://xbrl.org/2008/filter/tuple", "tf", "parentFilter")
qnSiblingFilter = QName("http://xbrl.org/2008/filter/tuple", "tf", "siblingFilter")
uf = AnyURI("http://xbrl.org/2008/filter/unit")
qnSingleMeasure = QName("http://xbrl.org/2008/filter/unit", "uf", "singleMeasure")
qnGeneralMeasures = QName("http://xbrl.org/2008/filter/unit", "uf", "generalMeasures")
vf = AnyURI("http://xbrl.org/2008/filter/value")
qnNilFilter = QName("http://xbrl.org/2008/filter/value", "vf", "nil")
qnPrecisionFilter = QName("http://xbrl.org/2008/filter/value", "vf", "precision")
xpath2err = AnyURI("http://www.w3.org/2005/xqt-errors")
variablesScope = AnyURI("http://xbrl.org/arcrole/2010/variables-scope")

# 2014-MM-DD current IWD
tableMMDD = AnyURI("http://xbrl.org/PWD/2016-MM-DD/table")
tableModelMMDD = AnyURI("http://xbrl.org/PWD/2016-MM-DD/table/model")
tableBreakdownMMDD = AnyURI("http://xbrl.org/arcrole/PWD/2014-MM-DD/table-breakdown")
tableBreakdownTreeMMDD = AnyURI("http://xbrl.org/arcrole/PWD/2014-MM-DD/breakdown-tree")
tableDefinitionNodeSubtreeMMDD = AnyURI("http://xbrl.org/arcrole/PWD/2014-MM-DD/definition-node-subtree")
tableFilterMMDD = AnyURI("http://xbrl.org/arcrole/PWD/2014-MM-DD/table-filter")
tableAspectNodeFilterMMDD = AnyURI("http://xbrl.org/arcrole/PWD/2014-MM-DD/aspect-node-filter")
tableParameterMMDD = AnyURI("http://xbrl.org/arcrole/PWD/2014-MM-DD/table-parameter")
qnTableTableMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "table")
qnTableBreakdownMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "breakdown")
qnTableRuleNodeMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "ruleNode")
qnTableRuleSetMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "ruleSet")
qnTableDefinitionNodeMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "definitionNode")
qnTableClosedDefinitionNodeMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "closedDefinitionNode")
qnTableConceptRelationshipNodeMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "conceptRelationshipNode")
qnTableDimensionRelationshipNodeMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "dimensionRelationshipNode")
qnTableAspectNodeMMDD = QName("http://xbrl.org/PWD/2016-MM-DD/table", "table", "aspectNode")

# REC
table = AnyURI("http://xbrl.org/2014/table")
tableModel = AnyURI("http://xbrl.org/2014/table/model")
tableBreakdown = AnyURI("http://xbrl.org/arcrole/2014/table-breakdown")
tableBreakdownTree = AnyURI("http://xbrl.org/arcrole/2014/breakdown-tree")
tableDefinitionNodeSubtree = AnyURI("http://xbrl.org/arcrole/2014/definition-node-subtree")
tableFilter = AnyURI("http://xbrl.org/arcrole/2014/table-filter")
tableAspectNodeFilter = AnyURI("http://xbrl.org/arcrole/2014/aspect-node-filter")
tableParameter = AnyURI("http://xbrl.org/arcrole/2014/table-parameter")
qnTableTable = QName("http://xbrl.org/2014/table", "table", "table")
qnTableBreakdown = QName("http://xbrl.org/2014/table", "table", "breakdown")
qnTableRuleNode = QName("http://xbrl.org/2014/table", "table", "ruleNode")
qnTableRuleSet = QName("http://xbrl.org/2014/table", "table", "ruleSet")
qnTableDefinitionNode = QName("http://xbrl.org/2014/table", "table", "definitionNode")
qnTableClosedDefinitionNode = QName("http://xbrl.org/2014/table", "table", "closedDefinitionNode")
qnTableConceptRelationshipNode = QName("http://xbrl.org/2014/table", "table", "conceptRelationshipNode")
qnTableDimensionRelationshipNode = QName("http://xbrl.org/2014/table", "table", "dimensionRelationshipNode")
qnTableAspectNode = QName("http://xbrl.org/2014/table", "table", "aspectNode")

# 2013-MM-DD current CR
'''
table = AnyURI("http://xbrl.org/CR/2013-11-13/table")
tableModel = AnyURI("http://xbrl.org/CR/2013-11-13/table/model")
tableBreakdown = AnyURI("http://xbrl.org/arcrole/CR/2013-11-13/table-breakdown")
tableBreakdownTree = AnyURI("http://xbrl.org/arcrole/CR/2013-11-13/breakdown-tree")
tableDefinitionNodeSubtree = AnyURI("http://xbrl.org/arcrole/CR/2013-11-13/definition-node-subtree")
tableFilter = AnyURI("http://xbrl.org/arcrole/CR/2013-11-13/table-filter")
tableAspectNodeFilter = AnyURI("http://xbrl.org/arcrole/CR/2013-11-13/aspect-node-filter")
tableParameter = AnyURI("http://xbrl.org/arcrole/CR/2013-11-13/table-parameter")
qnTableTable = QName("http://xbrl.org/CR/2013-11-13/table", "table", "table")
qnTableBreakdown = QName("http://xbrl.org/CR/2013-11-13/table", "table", "breakdown")
qnTableRuleNode = QName("http://xbrl.org/CR/2013-11-13/table", "table", "ruleNode")
qnTableRuleSet = QName("http://xbrl.org/CR/2013-11-13/table", "table", "ruleSet")
qnTableDefinitionNode = QName("http://xbrl.org/CR/2013-11-13/table", "table", "definitionNode")
qnTableClosedDefinitionNode = QName("http://xbrl.org/CR/2013-11-13/table", "table", "closedDefinitionNode")
qnTableConceptRelationshipNode = QName("http://xbrl.org/CR/2013-11-13/table", "table", "conceptRelationshipNode")
qnTableDimensionRelationshipNode = QName("http://xbrl.org/CR/2013-11-13/table", "table", "dimensionRelationshipNode")
qnTableAspectNode = QName("http://xbrl.org/CR/2013-11-13/table", "table", "aspectNode")
'''

# prior 2013-08-28 PWD
''' not supported
table = AnyURI("http://xbrl.org/PWD/2013-08-28/table")
tableModel = AnyURI("http://xbrl.org/PWD/2013-08-28/table/model")
tableBreakdown = AnyURI("http://xbrl.org/arcrole/PWD/2013-08-28/table-breakdown")
tableBreakdownTree = AnyURI("http://xbrl.org/arcrole/PWD/2013-08-28/breakdown-tree")
tableDefinitionNodeSubtree = AnyURI("http://xbrl.org/arcrole/PWD/2013-08-28/definition-node-subtree")
tableFilter = AnyURI("http://xbrl.org/arcrole/PWD/2013-08-28/table-filter")
tableAspectNodeFilter = AnyURI("http://xbrl.org/arcrole/PWD/2013-08-28/aspect-node-filter")
tableParameter = AnyURI("http://xbrl.org/arcrole/PWD/2013-08-28/table-parameter")
qnTableTable = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "table")
qnTableBreakdown = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "breakdown")
qnTableRuleNode = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "ruleNode")
qnTableClosedDefinitionNode = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "closedDefinitionNode")
qnTableConceptRelationshipNode = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "conceptRelationshipNode")
qnTableDimensionRelationshipNode = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "dimensionRelationshipNode")
qnTableAspectNode = QName("http://xbrl.org/PWD/2013-08-28/table", "table", "aspectNode")
'''

# prior 2013-05-17 PWD
table201305 = AnyURI("http://xbrl.org/PWD/2013-05-17/table")
tableModel201305 = AnyURI("http://xbrl.org/PWD/2013-05-17/table/model")
tableBreakdown201305 = AnyURI("http://xbrl.org/arcrole/PWD/2013-05-17/table-breakdown")
tableBreakdownTree201305 = AnyURI("http://xbrl.org/arcrole/PWD/2013-05-17/breakdown-tree")
tableDefinitionNodeSubtree201305 = AnyURI("http://xbrl.org/arcrole/PWD/2013-05-17/definition-node-subtree")
tableFilter201305 = AnyURI("http://xbrl.org/arcrole/PWD/2013-05-17/table-filter")
tableAspectNodeFilter201305 = AnyURI("http://xbrl.org/arcrole/PWD/2013-05-17/aspect-node-filter")
qnTableTable201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "table")
qnTableBreakdown201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "breakdown")
qnTableRuleNode201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "ruleNode")
qnTableClosedDefinitionNode201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "closedDefinitionNode")
qnTableConceptRelationshipNode201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "conceptRelationshipNode")
qnTableDimensionRelationshipNode201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "dimensionRelationshipNode")
qnTableAspectNode201305 = QName("http://xbrl.org/PWD/2013-05-17/table", "table", "aspectNode")

# prior 2013-01-16 PWD
table201301 = AnyURI("http://xbrl.org/PWD/2013-01-16/table")
tableBreakdown201301 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/table-breakdown")
tableFilter201301 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/table-filter")
tableDefinitionNodeSubtree201301 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/definition-node-subtree")
tableTupleContent201301 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/tuple-content")
tableDefinitionNodeMessage201301 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/definition-node-message")
tableDefinitionNodeSelectionMessage201301 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/definition-node-selection-message")
qnTableTable201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "table")
qnTableCompositionNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "compositionNode")
qnTableFilterNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "filterNode")
qnTableConceptRelationshipNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "conceptRelationshipNode")
qnTableDimensionRelationshipNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "dimensionRelationshipNode")
qnTableRuleNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "ruleNode")
qnTableClosedDefinitionNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "closedDefinitionNode")
qnTableSelectionNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "selectionNode")
qnTableTupleNode201301 = QName("http://xbrl.org/PWD/2013-01-16/table", "table", "tupleNode")

# Montreal 2011 table linkbase
table2011 = AnyURI("http://xbrl.org/2011/table")
tableAxis2011 = AnyURI("http://xbrl.org/arcrole/2011/table-axis")
tableAxisSubtree2011 = AnyURI("http://xbrl.org/arcrole/2011/axis/axis-subtree")
tableFilter2011 = AnyURI("http://xbrl.org/arcrole/2011/table-filter")
tableFilterNodeFilter2011 = AnyURI("http://xbrl.org/arcrole/2011/filter-node-filter")
tableAxisFilter2011 = AnyURI("http://xbrl.org/arcrole/2011/axis/axis-filter")
tableAxisFilter201205 = AnyURI("http://xbrl.org/arcrole/2011/axis-filter")
tableTupleContent2011 = AnyURI("http://xbrl.org/arcrole/2011/axis/tuple-content")
tableAxisMessage2011 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/axis-message")
tableAxisSelectionMessage2011 = AnyURI("http://xbrl.org/arcrole/PWD/2013-01-16/axis-selection-message")
qnTableTable2011 = QName("http://xbrl.org/2011/table", "table", "table")
qnTableCompositionAxis2011 = QName("http://xbrl.org/2011/table", "table", "compositionAxis")
qnTableFilterAxis2011 = QName("http://xbrl.org/2011/table", "table", "filterAxis")
qnTableConceptRelationshipAxis2011 = QName("http://xbrl.org/2011/table", "table", "conceptRelationshipAxis")
qnTableDimensionRelationshipAxis2011 = QName("http://xbrl.org/2011/table", "table", "dimensionRelationshipAxis")
qnTableRuleAxis2011 = QName("http://xbrl.org/2011/table", "table", "ruleAxis")
qnTablePredefinedAxis2011 = QName("http://xbrl.org/2011/table", "table", "predefinedAxis")
qnTableSelectionAxis2011 = QName("http://xbrl.org/2011/table", "table", "selectionAxis")
qnTableTupleAxis2011 = QName("http://xbrl.org/2011/table", "table", "tupleAxis")

booleanValueTrue = "true"
booleanValueFalse = "false"

# Eurofiling 2010 table linkbase
euRend = AnyURI("http://www.eurofiling.info/2010/rendering")
euTableAxis = AnyURI("http://www.eurofiling.info/arcrole/2010/table-axis")
euAxisMember = AnyURI("http://www.eurofiling.info/arcrole/2010/axis-member")
qnEuTable = QName("http://www.eurofiling.info/2010/rendering", "rendering", "table")
qnEuAxisCoord = QName("http://www.eurofiling.info/2010/rendering", "rendering", "axisCoord")
euGroupTable = AnyURI("http://www.eurofiling.info/xbrl/arcrole/group-table")

# Anchoring (ESEF and allowed by SEC)
widerNarrower = AnyURI("http://www.esma.europa.eu/xbrl/esef/arcrole/wider-narrower")

xdtSchemaErrorNS = AnyURI("http://www.xbrl.org/2005/genericXmlSchemaError")
errMsgPrefixNS = { # err prefixes which are not declared, such as XPath's "err" prefix
    "err": xpath2err,
    "xmlSchema": xdtSchemaErrorNS,
    "utre" : "http://www.xbrl.org/2009/utr/errors",
    }

hrefScheamImports = (
   "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd",
   "http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd",
   "http://www.xbrl.org/2003/xlink-2003-12-31.xsd",
   "http://www.xbrl.org/2008/generic-link.xsd",
   "http://www.w3.org/2001/xml.xsd",
   "http://arelle.org/2018/XsSyntheticAnnotation.xsd"
   )
   

arcroleGroupDetect = "*detect*"

def baseSetArcroleLabel(arcrole): # with sort char in first position
    if arcrole == "XBRL-dimensions": return _("1Dimension")
    if arcrole == "XBRL-formulae": return _("1Formula")
    if arcrole == "XBRL-table-rendering": return _("1Rendering")
    if arcrole == parentChild: return _("1Presentation")
    if arcrole == summationItem: return _("1Calculation")
    if arcrole == widerNarrower: return ("1Anchoring")
    return "2" + os.path.basename(arcrole).title()

def labelroleLabel(role): # with sort char in first position
    if role == standardLabel: return _("1Standard Label")
    elif role == conceptNameLabelRole: return _("0Name")
    return "3" + os.path.basename(role).title()

def isStandardNamespace(namespaceURI):
    return namespaceURI in {xsd, xbrli, link, gen, xbrldt, xbrldi}

standardNamespaceSchemaLocations = {
    xbrli: "http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd",
    link: "http://www.xbrl.org/2003/xbrl-linkbase-2003-12-31.xsd",
    xl: "http://www.xbrl.org/2003/xl-2003-12-31.xsd",
    xlink: "http://www.w3.org/1999/xlink",
    xbrldt: "http://www.xbrl.org/2005/xbrldt-2005.xsd",
    xbrldi: "http://www.xbrl.org/2006/xbrldi-2006.xsd",
    gen: "http://www.xbrl.org/2008/generic-link.xsd",
    genLabel: "http://www.xbrl.org/2008/generic-label.xsd",
    genReference: "http://www.xbrl.org/2008/generic-reference.xsd"
    }

def isNumericXsdType(xsdType):
    return xsdType in {"integer", "positiveInteger", "negativeInteger", "nonNegativeInteger", "nonPositiveInteger",
                       "long", "unsignedLong", "int", "unsignedInt", "short", "unsignedShort",
                       "byte", "unsignedByte", "decimal", "float", "double"}
    
def isIntegerXsdType(xsdType):
    return xsdType in {"integer", "positiveInteger", "negativeInteger", "nonNegativeInteger", "nonPositiveInteger",
                       "long", "unsignedLong", "int", "unsignedInt", "short", "unsignedShort",
                       "byte", "unsignedByte"}
    
standardLabelRoles = {
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
                    "http://www.xbrl.org/2003/role/exampleGuidance"}

standardReferenceRoles = {
                    "http://www.xbrl.org/2003/role/reference",
                    "http://www.xbrl.org/2003/role/definitionRef",
                    "http://www.xbrl.org/2003/role/disclosureRef",
                    "http://www.xbrl.org/2003/role/mandatoryDisclosureRef",
                    "http://www.xbrl.org/2003/role/recommendedDisclosureRef",
                    "http://www.xbrl.org/2003/role/unspecifiedDisclosureRef",
                    "http://www.xbrl.org/2003/role/presentationRef",
                    "http://www.xbrl.org/2003/role/measurementRef",
                    "http://www.xbrl.org/2003/role/commentaryRef",
                    "http://www.xbrl.org/2003/role/exampleRef"}

standardLinkbaseRefRoles = {
                    "http://www.xbrl.org/2003/role/calculationLinkbaseRef",
                    "http://www.xbrl.org/2003/role/definitionLinkbaseRef",
                    "http://www.xbrl.org/2003/role/labelLinkbaseRef",
                    "http://www.xbrl.org/2003/role/presentationLinkbaseRef",
                    "http://www.xbrl.org/2003/role/referenceLinkbaseRef"}

standardRoles = standardLabelRoles | standardReferenceRoles | standardLinkbaseRefRoles | {   
                    "http://www.xbrl.org/2003/role/link",
                    "http://www.xbrl.org/2003/role/footnote"}

def isStandardRole(role):
    return role in standardRoles

def isTotalRole(role):
    return role in {"http://www.xbrl.org/2003/role/totalLabel",
                    "http://xbrl.us/us-gaap/role/label/negatedTotal",
                    "http://www.xbrl.org/2009/role/negatedTotalLabel"}
    
def isNetRole(role):
    return role in {"http://www.xbrl.org/2009/role/netLabel",
                    "http://www.xbrl.org/2009/role/negatedNetLabel"}
    
def isLabelRole(role):
    return role in standardLabelRoles or role == genLabel

def isNumericRole(role):
    return role in {"http://www.xbrl.org/2003/role/totalLabel",
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
                    "http://www.xbrl.org/2009/role/negatedTerseLabel"
                    }
    
def isStandardArcrole(role):
    return role in {"http://www.w3.org/1999/xlink/properties/linkbase",
                    "http://www.xbrl.org/2003/arcrole/concept-label",
                    "http://www.xbrl.org/2003/arcrole/concept-reference",
                    "http://www.xbrl.org/2003/arcrole/fact-footnote",
                    "http://www.xbrl.org/2003/arcrole/parent-child",
                    "http://www.xbrl.org/2003/arcrole/summation-item",
                    "http://www.xbrl.org/2003/arcrole/general-special",
                    "http://www.xbrl.org/2003/arcrole/essence-alias",
                    "http://www.xbrl.org/2003/arcrole/similar-tuples",
                    "http://www.xbrl.org/2003/arcrole/requires-element"}
    
standardArcroleCyclesAllowed = { 
                    "http://www.xbrl.org/2003/arcrole/concept-label":("any", None),
                    "http://www.xbrl.org/2003/arcrole/concept-reference":("any", None),
                    "http://www.xbrl.org/2003/arcrole/fact-footnote":("any",None),
                    "http://www.xbrl.org/2003/arcrole/parent-child":("undirected", "xbrl.5.2.4.2"),
                    "http://www.xbrl.org/2003/arcrole/summation-item":("any", "xbrl.5.2.5.2"),
                    "http://www.xbrl.org/2003/arcrole/general-special":("undirected", "xbrl.5.2.6.2.1"),
                    "http://www.xbrl.org/2003/arcrole/essence-alias":("undirected", "xbrl.5.2.6.2.1"),
                    "http://www.xbrl.org/2003/arcrole/similar-tuples":("any", "xbrl.5.2.6.2.3"),
                    "http://www.xbrl.org/2003/arcrole/requires-element":("any", "xbrl.5.2.6.2.4")}

def standardArcroleArcElement(arcrole):
    return {"http://www.xbrl.org/2003/arcrole/concept-label":"labelArc",
            "http://www.xbrl.org/2003/arcrole/concept-reference":"referenceArc",
            "http://www.xbrl.org/2003/arcrole/fact-footnote":"footnoteArc",
            "http://www.xbrl.org/2003/arcrole/parent-child":"presentationArc",
            "http://www.xbrl.org/2003/arcrole/summation-item":"calculationArc",
            "http://www.xbrl.org/2003/arcrole/general-special":"definitionArc",
            "http://www.xbrl.org/2003/arcrole/essence-alias":"definitionArc",
            "http://www.xbrl.org/2003/arcrole/similar-tuples":"definitionArc",
            "http://www.xbrl.org/2003/arcrole/requires-element":"definitionArc"}[arcrole]
            
def isDefinitionOrXdtArcrole(arcrole):
    return isDimensionArcrole(arcrole) or arcrole in {
            "http://www.xbrl.org/2003/arcrole/general-special",
            "http://www.xbrl.org/2003/arcrole/essence-alias",
            "http://www.xbrl.org/2003/arcrole/similar-tuples",
            "http://www.xbrl.org/2003/arcrole/requires-element"}
            
def isStandardResourceOrExtLinkElement(element):
    return element.namespaceURI == link and element.localName in {
          "definitionLink", "calculationLink", "presentationLink", "labelLink", "referenceLink", "footnoteLink", 
          "label", "footnote", "reference"} or \
          element.qname == qnIXbrl11Relationship
    
def isStandardArcElement(element):
    return element.namespaceURI == link and element.localName in {
          "definitionArc", "calculationArc", "presentationArc", "labelArc", "referenceArc", "footnoteArc"} or \
          element.qname == qnIXbrl11Relationship
        
def isStandardArcInExtLinkElement(element):
    return ((isStandardArcElement(element) and isStandardResourceOrExtLinkElement(element.getparent())) or
            element.qname == qnIXbrl11Relationship)

standardExtLinkQnames = {qnLinkDefinitionLink, 
                         qnLinkCalculationLink, 
                         qnLinkPresentationLink, 
                         qnLinkLabelLink,     
                         qnLinkReferenceLink, 
                         qnLinkFootnoteLink} 

standardExtLinkQnamesAndResources = {qnLinkDefinitionLink, 
                                     qnLinkCalculationLink, 
                                     qnLinkPresentationLink, 
                                     qnLinkLabelLink, 
                                     qnLinkReferenceLink, 
                                     qnLinkFootnoteLink, 
                                     qnLinkLabel, 
                                     qnLinkFootnote, 
                                     qnLinkReference}

def isStandardExtLinkQname(qName):
    return qName in standardExtLinkQnamesAndResources
    
def isStandardArcQname(qName):
    return qName in {qnLinkDefinitionArc,
                     qnLinkCalculationArc,
                     qnLinkPresentationArc,
                     qnLinkLabelArc,
                     qnLinkReferenceArc,
                     qnLinkFootnoteArc}
    
def isDimensionArcrole(arcrole):
    return arcrole.startswith("http://xbrl.org/int/dim/arcrole/")

dimensionArcroles = {all, notAll, hypercubeDimension, dimensionDomain, domainMember, dimensionDefault}

consecutiveArcrole = { # can be list of or single arcrole
    all: (dimensionDomain,hypercubeDimension), notAll: (dimensionDomain,hypercubeDimension),
    hypercubeDimension: dimensionDomain,
    dimensionDomain: (domainMember, all, notAll),
    domainMember: (domainMember, all, notAll),
    dimensionDefault: ()}

tableRenderingArcroles = {# current PWD 2013-05-17
                       tableBreakdown, tableBreakdownTree, tableFilter, tableParameter,
                       tableDefinitionNodeSubtree, tableAspectNodeFilter,
                       # current IWD
                       tableBreakdownMMDD, tableBreakdownTreeMMDD, tableFilterMMDD, tableParameterMMDD,
                       tableDefinitionNodeSubtreeMMDD, tableAspectNodeFilterMMDD, 
                       # Prior PWD, Montreal and 2013-01-16 
                       tableBreakdown201305, tableBreakdownTree201305, tableFilter201305,
                       tableDefinitionNodeSubtree201305, tableAspectNodeFilter201305,
                       
                       tableBreakdown201301, tableFilter201301,
                       tableDefinitionNodeSubtree201301, 
                       tableTupleContent201301, 
                       tableDefinitionNodeMessage201301, tableDefinitionNodeSelectionMessage201301,
                       
                       tableAxis2011, tableFilter2011, 
                       tableAxisSubtree2011, 
                       tableFilterNodeFilter2011, tableAxisFilter2011, tableAxisFilter201205,
                       tableTupleContent201301, tableTupleContent2011,
                       tableAxisSubtree2011, tableAxisFilter2011,
                       # original Eurofiling
                       euTableAxis, euAxisMember,
                       }


tableIndexingArcroles = frozenset((euGroupTable,))
def isTableIndexingArcrole(arcrole):
    return arcrole in tableIndexingArcroles
    
formulaArcroles = {assertionSet,
                       variableSet,
                       equalityDefinition,
                       variableSetFilter,
                       variableFilter,
                       booleanFilter,
                       variableSetPrecondition,
                       consistencyAssertionFormula,
                       consistencyAssertionParameter,
                       functionImplementation,
                       assertionSatisfiedMessage,
                       assertionUnsatisfiedMessage,
                       assertionUnsatisfiedSeverity,
                       instanceVariable,
                       formulaInstance,
                       variablesScope}

def isFormulaArcrole(arcrole):
    return arcrole in formulaArcroles

def isResourceArcrole(arcrole):
    return (arcrole in {"http://www.xbrl.org/2003/arcrole/concept-label",
                        "http://www.xbrl.org/2003/arcrole/concept-reference",
                        "http://www.xbrl.org/2003/arcrole/fact-footnote",
                        "http://xbrl.org/arcrole/2008/element-label",
                        "http://xbrl.org/arcrole/2008/element-reference"}
            or isFormulaArcrole(arcrole))
    
