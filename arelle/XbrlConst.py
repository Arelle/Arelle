from arelle.ModelValue import qname
import os

xsd = "http://www.w3.org/2001/XMLSchema"
qnXsdSchema = qname("{http://www.w3.org/2001/XMLSchema}xsd:schema")
qnXsdAppinfo = qname("{http://www.w3.org/2001/XMLSchema}xsd:appinfo")
qnXsdDefaultType = qname("{http://www.w3.org/2001/XMLSchema}xsd:anyType")
xsi = "http://www.w3.org/2001/XMLSchema-instance"
qnXsiNil = qname(xsi,"xsi:nil") # need default prefix in qname
xml = "http://www.w3.org/XML/1998/namespace"
xbrli = "http://www.xbrl.org/2003/instance"
qnXbrliXbrl = qname("{http://www.xbrl.org/2003/instance}xbrli:xbrl")
qnXbrliItem = qname("{http://www.xbrl.org/2003/instance}xbrli:item")
qnXbrliTuple = qname("{http://www.xbrl.org/2003/instance}xbrli:tuple")
qnXbrliContext = qname("{http://www.xbrl.org/2003/instance}xbrli:context")
qnXbrliUnit = qname("{http://www.xbrl.org/2003/instance}xbrli:unit")
qnXbrliStringItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:stringItemType")
qnXbrliMonetaryItemType = qname("{http://www.xbrl.org/2003/instance}xbrli:monetaryItemType")
qnXbrliPure = qname("{http://www.xbrl.org/2003/instance}xbrli:pure")
qnXbrliShares = qname("{http://www.xbrl.org/2003/instance}xbrli:shares")
qnXbrliDateUnion = qname("{http://www.xbrl.org/2003/instance}xbrli:dateUnion")
qnDateUnionXsdTypes = [qname("{http://www.w3.org/2001/XMLSchema}xsd:date"),qname("{http://www.w3.org/2001/XMLSchema}xsd:dateTime")]
qnXbrliDecimalsUnion = qname("{http://www.xbrl.org/2003/instance}xbrli:decimalsType")
qnXbrliPrecisionUnion = qname("{http://www.xbrl.org/2003/instance}xbrli:precisionType")
qnXbrliNonZeroDecimalUnion = qname("{http://www.xbrl.org/2003/instance}xbrli:nonZeroDecimal")
link = "http://www.xbrl.org/2003/linkbase"
qnLinkLoc = qname("{http://www.xbrl.org/2003/linkbase}link:loc")
qnLinkLabelLink = qname("{http://www.xbrl.org/2003/linkbase}link:labelLink")
qnLinkLabelArc = qname("{http://www.xbrl.org/2003/linkbase}link:labelArc")
qnLinkLabel = qname("{http://www.xbrl.org/2003/linkbase}link:label")
qnLinkReferenceLink = qname("{http://www.xbrl.org/2003/linkbase}link:referenceLink")
qnLinkReferenceArc = qname("{http://www.xbrl.org/2003/linkbase}link:referenceArc")
qnLinkReference = qname("{http://www.xbrl.org/2003/linkbase}link:reference")
qnLinkPart = qname("{http://www.xbrl.org/2003/linkbase}link:part")
qnLinkFootnoteLink = qname("{http://www.xbrl.org/2003/linkbase}link:footnoteLink")
qnLinkFootnoteArc = qname("{http://www.xbrl.org/2003/linkbase}link:footnoteArc")
qnLinkFootnote = qname("{http://www.xbrl.org/2003/linkbase}link:footnote")
qnLinkPresentationLink = qname("{http://www.xbrl.org/2003/linkbase}link:presentationLink")
qnLinkPresentationArc = qname("{http://www.xbrl.org/2003/linkbase}link:presentationArc")
qnLinkCalculationLink = qname("{http://www.xbrl.org/2003/linkbase}link:calculationLink")
qnLinkCalculationArc = qname("{http://www.xbrl.org/2003/linkbase}link:calculationArc")
qnLinkDefinitionLink = qname("{http://www.xbrl.org/2003/linkbase}link:definitionLink")
qnLinkDefinitionArc = qname("{http://www.xbrl.org/2003/linkbase}link:definitionArc")
gen = "http://xbrl.org/2008/generic"
qnGenLink = qname("{http://xbrl.org/2008/generic}gen:link")
qnGenArc = qname("{http://xbrl.org/2008/generic}gen:arc")
elementReference = "http://xbrl.org/arcrole/2008/element-reference"
genReference = "http://xbrl.org/2008/reference"
qnGenReference = qname("{http://xbrl.org/2008/reference}reference")
elementLabel = "http://xbrl.org/arcrole/2008/element-label"
genLabel = "http://xbrl.org/2008/label"
qnGenLabel = qname("{http://xbrl.org/2008/label}label")
elementReference = "http://xbrl.org/arcrole/2008/element-reference"
xbrldt = "http://xbrl.org/2005/xbrldt"
qnXbrldtHypercubeItem = qname("{http://xbrl.org/2005/xbrldt}xbrldt:hypercubeItem")
qnXbrldtDimensionItem = qname("{http://xbrl.org/2005/xbrldt}xbrldt:dimensionItem")
xbrldi = "http://xbrl.org/2006/xbrldi"
qnXbrldiExplicitMember = qname("{http://xbrl.org/2006/xbrldi}xbrldi:explicitMember")
qnXbrldiTypedMember = qname("{http://xbrl.org/2006/xbrldi}xbrldi:typedMember")
xlink = "http://www.w3.org/1999/xlink"
xl = "http://www.xbrl.org/2003/XLink"
qnXlExtended = qname("{http://www.xbrl.org/2003/XLink}xl:extended")
qnXlLocator = qname("{http://www.xbrl.org/2003/XLink}xl:locator")
qnXlResource = qname("{http://www.xbrl.org/2003/XLink}xl:resource")
qnXlExtendedType = qname("{http://www.xbrl.org/2003/XLink}xl:extendedType")
qnXlLocatorType = qname("{http://www.xbrl.org/2003/XLink}xl:locatorType")
qnXlResourceType = qname("{http://www.xbrl.org/2003/XLink}xl:resourceType")
xhtml = "http://www.w3.org/1999/xhtml"
ixbrl = "http://www.xbrl.org/2008/inlineXBRL"
qnIXbrlTuple = qname("{http://www.xbrl.org/2008/inlineXBRL}tuple")
qnIXbrlNonNumeric = qname("{http://www.xbrl.org/2008/inlineXBRL}nonNumeric")
qnIXbrlNonFraction = qname("{http://www.xbrl.org/2008/inlineXBRL}nonFraction")
qnIXbrlFraction = qname("{http://www.xbrl.org/2008/inlineXBRL}fraction")
conceptLabel = "http://www.xbrl.org/2003/arcrole/concept-label"
conceptReference = "http://www.xbrl.org/2003/arcrole/concept-reference"
footnote = "http://www.xbrl.org/2003/role/footnote"
factFootnote = "http://www.xbrl.org/2003/arcrole/fact-footnote"
factExplanatoryFact = "http://www.xbrl.org/2009/arcrole/fact-explanatoryFact"
parentChild = "http://www.xbrl.org/2003/arcrole/parent-child"
summationItem = "http://www.xbrl.org/2003/arcrole/summation-item"
essenceAlias = "http://www.xbrl.org/2003/arcrole/essence-alias"
similarTuples = "http://www.xbrl.org/2003/arcrole/similar-tuples"
requiresElement = "http://www.xbrl.org/2003/arcrole/requires-element"
generalSpecial = "http://www.xbrl.org/2003/arcrole/general-special"
dimStartsWith = "http://xbrl.org/int/dim"
all = "http://xbrl.org/int/dim/arcrole/all"
notAll = "http://xbrl.org/int/dim/arcrole/notAll"
hypercubeDimension = "http://xbrl.org/int/dim/arcrole/hypercube-dimension"
dimensionDomain = "http://xbrl.org/int/dim/arcrole/dimension-domain"
domainMember = "http://xbrl.org/int/dim/arcrole/domain-member"
dimensionDefault = "http://xbrl.org/int/dim/arcrole/dimension-default"
dtrTypesStartsWith = "http://www.xbrl.org/dtr/type/"
dtrNumeric = "http://www.xbrl.org/dtr/type/numeric"
defaultLinkRole = "http://www.xbrl.org/2003/role/link"
iso4217 = "http://www.xbrl.org/2003/iso4217"
standardLabel = "http://www.xbrl.org/2003/role/label"
genStandardLabel = "http://www.xbrl.org/2008/role/label"
documentationLabel = "http://www.xbrl.org/2003/role/documentation"
genDocumentationLabel = "http://www.xbrl.org/2008/role/documentation"
standardReference = "http://www.xbrl.org/2003/role/reference"
genStandardReference = "http://www.xbrl.org/2010/role/reference"
periodStartLabel = "http://www.xbrl.org/2003/role/periodStartLabel"
periodEndLabel = "http://www.xbrl.org/2003/role/periodEndLabel"
conceptNameLabelRole = "XBRL-concept-name" # fake label role to show concept QName instead of label
xlinkLinkbase = "http://www.w3.org/1999/xlink/properties/linkbase"

utr = "http://www.xbrl.org/2009/utr"

ver = "http://xbrl.org/2010/versioning-base"
vercb = "http://xbrl.org/2010/versioning-concept-basic"
verce = "http://xbrl.org/2010/versioning-concept-extended"
verrels = "http://xbrl.org/2010/versioning-relationship-sets"
veria = "http://xbrl.org/2010/versioning-instance-aspects"
verPrefixNS = {"ver":ver,
               "vercb":vercb,
               "verce":verce,
               "verrels":verrels,
               "veria":veria}

# formula specs
variable = "http://xbrl.org/2008/variable"
qnVariableSet = qname("{http://xbrl.org/2008/variable}variable:variableSet")
qnVariableVariable = qname("{http://xbrl.org/2008/variable}variable:variable")
qnVariableFilter = qname("{http://xbrl.org/2008/variable}variable:filter")
qnVariableFilterArc = qname("{http://xbrl.org/2008/variable}variable:variableFilterArc")
qnParameter = qname("{http://xbrl.org/2008/variable}variable:parameter")
qnFactVariable = qname("{http://xbrl.org/2008/variable}variable:factVariable")
qnGeneralVariable = qname("{http://xbrl.org/2008/variable}variable:generalVariable")
qnPrecondition = qname("{http://xbrl.org/2008/variable}variable:precondition")
qnEqualityDefinition = qname("{http://xbrl.org/2008/variable}variable:equalityDefinition")
qnEqualityTestA = qname("{http://xbrl.org/2008/variable/aspectTest}aspectTest:a")
qnEqualityTestB = qname("{http://xbrl.org/2008/variable/aspectTest}aspectTest:b")
formula = "http://xbrl.org/2008/formula"
tuple = "http://xbrl.org/2010/formula/tuple"
qnFormula = qname("{http://xbrl.org/2008/formula}formula:formula")
qnTuple = qname("{http://xbrl.org/2010/formula/tuple}tuple:tuple")
qnFormulaUncovered = qname("{http://xbrl.org/2008/formula}formula:uncovered")
qnFormulaDimensionSAV = qname("{http://xbrl.org/2008/formula}DimensionSAV") #signal that dimension aspect should use SAV of this dimension
qnFormulaOccEmpty = qname("{http://xbrl.org/2008/formula}occEmpty") #signal that OCC aspect should omit the SAV values
ca = "http://xbrl.org/2008/assertion/consistency"
qnConsistencyAssertion = qname("{http://xbrl.org/2008/assertion/consistency}ca:consistencyAssertion")
ea = "http://xbrl.org/2008/assertion/existence"
qnExistenceAssertion = qname("{http://xbrl.org/2008/assertion/existence}ea:existenceAssertion")
va = "http://xbrl.org/2008/assertion/value"
qnValueAssertion = qname("{http://xbrl.org/2008/assertion/value}va:valueAssertion")
variable = "http://xbrl.org/2008/variable"
formulaStartsWith = "http://xbrl.org/arcrole/20"
equalityDefinition = "http://xbrl.org/arcrole/2008/equality-definition"
qnEqualityDefinition = qname("{http://xbrl.org/2008/variable}variable:equalityDefinition")
variableSet = "http://xbrl.org/arcrole/2008/variable-set"
variableSetFilter = "http://xbrl.org/arcrole/2008/variable-set-filter"
variableFilter = "http://xbrl.org/arcrole/2008/variable-filter"
variableSetPrecondition = "http://xbrl.org/arcrole/2008/variable-set-precondition"
equalityDefinition = "http://xbrl.org/arcrole/2008/equality-definition"
consistencyAssertionFormula = "http://xbrl.org/arcrole/2008/consistency-assertion-formula"
consistencyAssertionParameter = "http://xbrl.org/arcrole/2008/consistency-assertion-parameter"
validation = "http://xbrl.org/2008/validation"
qnAssertion = qname("{http://xbrl.org/2008/validation}validation:assertion")
qnVariableSetAssertion = qname("{http://xbrl.org/2008/validation}validation:variableSetAssertion")
qnAssertionSet = qname("{http://xbrl.org/2008/validation}validation:assertionSet")
assertionSet = "http://xbrl.org/arcrole/2008/assertion-set"

acf = "http://xbrl.org/2010/filter/aspect-cover"
qnAspectCover = qname("{http://xbrl.org/2010/filter/aspect-cover}acf:aspectCover")
bf = "http://xbrl.org/2008/filter/boolean"
qnAndFilter = qname("{http://xbrl.org/2008/filter/boolean}bf:andFilter")
qnOrFilter = qname("{http://xbrl.org/2008/filter/boolean}bf:orFilter")
booleanFilter = "http://xbrl.org/arcrole/2008/boolean-filter"
cfi = "http://xbrl.org/2010/custom-function"
functionImplementation = "http://xbrl.org/arcrole/2010/function-implementation"
qnCustomFunctionSignature = qname("{http://xbrl.org/2008/variable}cfi:function")
qnCustomFunctionImplementation = qname("{http://xbrl.org/2010/custom-function}cfi:implementation")
crf = "http://xbrl.org/2010/filter/concept-relation"
qnConceptRelation = qname("{http://xbrl.org/2010/filter/concept-relation}crf:conceptRelation")
cf = "http://xbrl.org/2008/filter/concept"
qnConceptName = qname("{http://xbrl.org/2008/filter/concept}cf:conceptName")
qnConceptPeriodType = qname("{http://xbrl.org/2008/filter/concept}cf:conceptPeriodType")
qnConceptBalance = qname("{http://xbrl.org/2008/filter/concept}cf:conceptBalance")
qnConceptCustomAttribute = qname("{http://xbrl.org/2008/filter/concept}cf:conceptCustomAttribute")
qnConceptDataType = qname("{http://xbrl.org/2008/filter/concept}cf:conceptDataType")
qnConceptSubstitutionGroup = qname("{http://xbrl.org/2008/filter/concept}cf:conceptSubstitutionGroup")
cfcn = "http://xbrl.org/2008/conformance/function"
df = "http://xbrl.org/2008/filter/dimension"
qnExplicitDimension = qname("{http://xbrl.org/2008/filter/dimension}df:explicitDimension")
qnTypedDimension = qname("{http://xbrl.org/2008/filter/dimension}df:typedDimension")
ef = "http://xbrl.org/2008/filter/entity"
qnEntityIdentifier = qname("{http://xbrl.org/2008/filter/entity}ef:identifier")
qnEntitySpecificIdentifier = qname("{http://xbrl.org/2008/filter/entity}ef:specificIdentifier")
qnEntitySpecificScheme = qname("{http://xbrl.org/2008/filter/entity}ef:specificScheme")
qnEntityRegexpIdentifier = qname("{http://xbrl.org/2008/filter/entity}ef:regexpIdentifier")
qnEntityRegexpScheme = qname("{http://xbrl.org/2008/filter/entity}ef:regexpScheme")
function = "http://xbrl.org/2008/function"
fn = "http://www.w3.org/2005/xpath-functions"
xfi = "http://www.xbrl.org/2008/function/instance"
qnXfiRoot = qname("{http://www.xbrl.org/2008/function/instance}xfi:root")
xff = "http://www.xbrl.org/2010/function/formula"
gf = "http://xbrl.org/2008/filter/general"
qnGeneral = qname("{http://xbrl.org/2008/filter/general}gf:general")
instances = "http://xbrl.org/2010/variable/instance"
qnInstance = qname(instances,"instances:instance")
instanceVariable = "http://xbrl.org/arcrole/2010/instance-variable"
formulaInstance = "http://xbrl.org/arcrole/2010/formula-instance"
qnStandardInputInstance = qname(instances,"instances:standard-input-instance")
qnStandardOutputInstance = qname(instances,"instances:standard-output-instance")
mf = "http://xbrl.org/2008/filter/match"
qnMatchConcept = qname("{http://xbrl.org/2008/filter/match}mf:matchConcept")
qnMatchDimension = qname("{http://xbrl.org/2008/filter/match}mf:matchDimension")
qnMatchEntityIdentifier = qname("{http://xbrl.org/2008/filter/match}mf:matchEntityIdentifier")
qnMatchLocation = qname("{http://xbrl.org/2008/filter/match}mf:matchLocation")
qnMatchPeriod = qname("{http://xbrl.org/2008/filter/match}mf:matchPeriod")
qnMatchSegment = qname("{http://xbrl.org/2008/filter/match}mf:matchSegment")
qnMatchScenario = qname("{http://xbrl.org/2008/filter/match}mf:matchScenario")
qnMatchNonXDTSegment = qname("{http://xbrl.org/2008/filter/match}mf:matchNonXDTSegment")
qnMatchNonXDTScenario = qname("{http://xbrl.org/2008/filter/match}mf:matchNonXDTScenario")
qnMatchUnit = qname("{http://xbrl.org/2008/filter/match}mf:matchUnit")
msg = "http://xbrl.org/2010/message"
qnMessage = qname("{http://xbrl.org/2010/message}message")
assertionSatisfiedMessage = "http://xbrl.org/arcrole/2010/assertion-satisfied-message"
assertionUnsatisfiedMessage = "http://xbrl.org/arcrole/2010/assertion-unsatisfied-message"
standardMessage = "http://www.xbrl.org/2010/role/message"
terseMessage = "http://www.xbrl.org/2010/role/terseMessage"
verboseMessage = "http://www.xbrl.org/2010/role/verboseMessage"
pf = "http://xbrl.org/2008/filter/period"
qnPeriod = qname("{http://xbrl.org/2008/filter/period}pf:period")
qnPeriodStart = qname("{http://xbrl.org/2008/filter/period}pf:periodStart")
qnPeriodEnd = qname("{http://xbrl.org/2008/filter/period}pf:periodEnd")
qnPeriodInstant = qname("{http://xbrl.org/2008/filter/period}pf:periodInstant")
qnForever = qname("{http://xbrl.org/2008/filter/period}pf:forever")
qnInstantDuration = qname("{http://xbrl.org/2008/filter/period}pf:instantDuration")
registry = "http://xbrl.org/2008/registry"
rf = "http://xbrl.org/2008/filter/relative"
qnRelativeFilter = qname("{http://xbrl.org/2008/filter/relative}rf:relativeFilter")
ssf = "http://xbrl.org/2008/filter/segment-scenario"
qnSegmentFilter = qname("{http://xbrl.org/2008/filter/segment-scenario}ssf:segment")
qnScenarioFilter = qname("{http://xbrl.org/2008/filter/segment-scenario}ssf:scenario")
tf = "http://xbrl.org/2008/filter/tuple"
qnAncestorFilter = qname("{http://xbrl.org/2008/filter/tuple}tf:ancestorFilter")
qnLocationFilter = qname("{http://xbrl.org/2008/filter/tuple}tf:locationFilter")
qnParentFilter = qname("{http://xbrl.org/2008/filter/tuple}tf:parentFilter")
qnSiblingFilter = qname("{http://xbrl.org/2008/filter/tuple}tf:siblingFilter")
uf = "http://xbrl.org/2008/filter/unit"
qnSingleMeasure = qname("{http://xbrl.org/2008/filter/unit}uf:singleMeasure")
qnGeneralMeasures = qname("{http://xbrl.org/2008/filter/unit}uf:generalMeasures")
vf = "http://xbrl.org/2008/filter/value"
qnNilFilter = qname("{http://xbrl.org/2008/filter/value}vf:nil")
qnPrecisionFilter = qname("{http://xbrl.org/2008/filter/value}vf:precision")
xpath2err = "http://www.w3.org/2005/xqt-errors"
variablesScope = "http://xbrl.org/arcrole/2010/variables-scope"

# 2010 table linkbase
euRend = "http://www.eurofiling.info/2010/rendering"
euTableAxis = "http://www.eurofiling.info/arcrole/2010/table-axis"
euAxisMember = "http://www.eurofiling.info/arcrole/2010/axis-member"
qnEuTable = qname("{http://www.eurofiling.info/2010/rendering}rendering:table")
qnEuAxisCoord = qname("{http://www.eurofiling.info/2010/rendering}rendering:axisCoord")
# 2011 table linkbase
table = "http://xbrl.org/2011/table"
tableAxis = "http://xbrl.org/arcrole/2011/table-axis"
tableFilter = "http://xbrl.org/arcrole/2011/table-filter"
tableAxisSubtree = "http://xbrl.org/arcrole/2011/axis-subtree"
tableAxisFilter = "http://xbrl.org/arcrole/2011/axis-filter"
tableTupleContent = "http://xbrl.org/arcrole/2011/axis/tuple-content"
qnTableTable = qname("{http://xbrl.org/2011/table}table:table")
qnTableCompositionAxis = qname("{http://xbrl.org/2011/table}table:compositionAxis")
qnTableFilterAxis = qname("{http://xbrl.org/2011/table}table:filterAxis")
qnTableConceptRelationshipAxis = qname("{http://xbrl.org/2011/table}table:conceptRelationshipAxis")
qnTableDimensionRelationshipAxis = qname("{http://xbrl.org/2011/table}table:dimensionRelationshipAxis")
qnTableRuleAxis = qname("{http://xbrl.org/2011/table}table:ruleAxis")
qnTablePredefinedAxis = qname("{http://xbrl.org/2011/table}table:predefinedAxis")
qnTableSelectionAxis = qname("{http://xbrl.org/2011/table}table:selectionAxis")
qnTableTupleAxis = qname("{http://xbrl.org/2011/table}table:tupleAxis")

xdtSchemaErrorNS = "http://www.xbrl.org/2005/genericXmlSchemaError"
errMsgPrefixNS = {
    "err": xpath2err,
    "xbrldte": "http://xbrl.org/2005/xbrldt/errors",
    "xbrldie": "http://xbrl.org/2005/xbrldi/errors",
    "xbrlfe": "http://xbrl.org/2008/formula/error",
    "xbrlmsge": "http://xbrl.org/2010/message/error",
    "xbrlvarinste": "http://xbrl.org/2010/variable/instance/error",
    "xbrlve": "http://xbrl.org/2008/variable/error",
    "xbrlcae": "http://xbrl.org/2008/assertion/consistency/error",
    "xbrleae": "http://xbrl.org/2008/assertion/existence/error",
    "xbrldfe": "http://xbrl.org/2008/filter/dimension/error",  
    "xffe": "http://www.xbrl.org/2010/function/formula/error",
    "xfie": "http://www.xbrl.org/2008/function/instance/error",
    "vere": "http://xbrl.org/2010/versioning-base/error",
    "vercbe": "http://xbrl.org/2010/versioning-concept-basic/error",
    "vercee" :"http://xbrl.org/2010/versioning-concept-extended/error",
    "verrelse": "http://xbrl.org/2010/versioning-relationship-sets/error",
    "veriae": "http://xbrl.org/2010/versioning-instance-aspects/error",
    "xbrlacfe": "http://xbrl.org/2010/filter/aspect-cover/error",
    "xbrlcfie": "http://xbrl.org/2010/custom-function/error",
    "xbrlmfe": "http://xbrl.org/2008/filter/match/error",
    "xbrlvarscopee": "http://xbrl.org/2010/variable/variables-scope/error",
    }

def baseSetArcroleLabel(arcrole): # with sort char in first position
    if arcrole == "XBRL-dimensions": return _("1Dimension")
    if arcrole == "XBRL-formulae": return _("1Formula")
    if arcrole == "Table-rendering": return _("1Rendering")
    if arcrole == parentChild: return _("1Presentation")
    if arcrole == summationItem: return _("1Calculation")
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
    
def isStandardRole(role):
    return role in {"http://www.xbrl.org/2003/role/label",
                    "http://www.xbrl.org/2003/role/terseLabel",
                    "http://www.xbrl.org/2003/role/verboseLabel",
                    "http://www.xbrl.org/2003/role/link",
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
                    "http://www.xbrl.org/2003/role/calculationLinkbaseRef",
                    "http://www.xbrl.org/2003/role/definitionLinkbaseRef",
                    "http://www.xbrl.org/2003/role/labelLinkbaseRef",
                    "http://www.xbrl.org/2003/role/presentationLinkbaseRef",
                    "http://www.xbrl.org/2003/role/referenceLinkbaseRef",
                    "http://www.xbrl.org/2003/role/footnote"}

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
    return element.namespaceURI == link and element.localName in (
          "definitionLink", "calculationLink", "presentationLink", "labelLink", "referenceLink", "footnoteLink", 
          "label", "footnote", "reference")
    
def isStandardArcElement(element):
    return element.namespaceURI == link and element.localName in (
          "definitionArc", "calculationArc", "presentationArc", "labelArc", "referenceArc", "footnoteArc")
        
def isStandardArcInExtLinkElement(element):
    return isStandardArcElement(element) and isStandardResourceOrExtLinkElement(element.getparent())

standardExtLinkQnames = {qname("{http://www.xbrl.org/2003/linkbase}definitionLink"), 
                         qname("{http://www.xbrl.org/2003/linkbase}calculationLink"), 
                         qname("{http://www.xbrl.org/2003/linkbase}presentationLink"), 
                         qname("{http://www.xbrl.org/2003/linkbase}labelLink"),     
                         qname("{http://www.xbrl.org/2003/linkbase}referenceLink"), 
                         qname("{http://www.xbrl.org/2003/linkbase}footnoteLink")} 

standardExtLinkQnamesAndResources = {qname("{http://www.xbrl.org/2003/linkbase}definitionLink"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}calculationLink"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}presentationLink"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}labelLink"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}referenceLink"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}footnoteLink"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}label"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}footnote"), 
                                     qname("{http://www.xbrl.org/2003/linkbase}reference")}

def isStandardExtLinkQname(qName):
    return qName in standardExtLinkQnamesAndResources
    
def isStandardArcQname(qName):
    return qName in {
          qname("{http://www.xbrl.org/2003/linkbase}definitionArc"), 
          qname("{http://www.xbrl.org/2003/linkbase}calculationArc"), 
          qname("{http://www.xbrl.org/2003/linkbase}presentationArc"), 
          qname("{http://www.xbrl.org/2003/linkbase}labelArc"),
          qname("{http://www.xbrl.org/2003/linkbase}referenceArc"), 
          qname("{http://www.xbrl.org/2003/linkbase}footnoteArc")}
    
def isDimensionArcrole(arcrole):
    return arcrole.startswith("http://xbrl.org/int/dim/arcrole/")

def isTableRenderingArcrole(arcrole):
    return arcrole in (euTableAxis, euAxisMember, 
                       tableAxis, tableFilter, tableAxisSubtree, tableAxisFilter, tableTupleContent)
   
def isFormulaArcrole(arcrole):
    return arcrole in {"http://xbrl.org/arcrole/2008/assertion-set",
                       "http://xbrl.org/arcrole/2008/variable-set",
                       "http://xbrl.org/arcrole/2008/variable-set-filter",
                       "http://xbrl.org/arcrole/2008/variable-filter",
                       "http://xbrl.org/arcrole/2008/boolean-filter",
                       "http://xbrl.org/arcrole/2008/variable-set-precondition",
                       "http://xbrl.org/arcrole/2008/consistency-assertion-formula",
                       "http://xbrl.org/arcrole/2010/function-implementation",
                       "http://xbrl.org/arcrole/2010/assertion-satisfied-message",
                       "http://xbrl.org/arcrole/2010/assertion-unsatisfied-message",
                       "http://xbrl.org/arcrole/2010/instance-variable",
                       "http://xbrl.org/arcrole/2010/formula-instance",
                       "http://xbrl.org/arcrole/2010/function-implementation",
                       "http://xbrl.org/arcrole/2010/variables-scope"}
