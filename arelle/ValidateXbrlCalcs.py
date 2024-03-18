'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from collections import defaultdict, OrderedDict
from math import (log10, isnan, isinf, fabs, floor, pow)
import decimal
from typing import TYPE_CHECKING
from regex import compile as re_compile
import hashlib
from arelle import Locale, XbrlConst, XbrlUtil
from arelle.ModelObject import ObjectPropertyViewWrapper
from arelle.PythonUtil import flattenSequence, strTruncate
from arelle.XmlValidateConst import UNVALIDATED, VALID

if TYPE_CHECKING:
    from _decimal import Decimal
    from arelle.ModelInstanceObject import ModelFact
    from arelle.ModelValue import TypeXValue
else:
    ModelFact = None # circular import with ModelInstanceObject


def init(): # prevent circular imports
    global ModelFact
    if ModelFact is None:
        from arelle.ModelInstanceObject import ModelFact

class ValidateCalcsMode:
    NONE = 0                        # no calculations linkbase validation
    XBRL_v2_1_INFER_PRECISION = 1   # pre-2010 spec v2.1 mode
    XBRL_v2_1 = 2                   # post-2010 spec v2.1 mode
    XBRL_v2_1_DEDUPLICATE = 3       # post-2010 spec v2.1 with deduplication
    ROUND_TO_NEAREST = 4            # calculations 1.1 round-to-nearest mode
    TRUNCATION = 5                  # calculations 1.1 truncation mode

    @staticmethod
    def label(enum): # must be dynamic using language choice when selecting enum choice
        if enum == ValidateCalcsMode.NONE:
            return  _("No calculations linkbase checks")
        if enum == ValidateCalcsMode.XBRL_v2_1_INFER_PRECISION:
            return  _("Pre-2010 XBRL 2.1 calculations validation inferring precision")
        if enum == ValidateCalcsMode.XBRL_v2_1:
            return   _("XBRL 2.1 calculations linkbase checks")
        if enum == ValidateCalcsMode.XBRL_v2_1_DEDUPLICATE:
            return  _("XBRL v2.1 calculations linkbase with de-duplication")
        if enum == ValidateCalcsMode.ROUND_TO_NEAREST:
            return  _("Calculations 1.1 round-to-nearest mode")
        if enum == ValidateCalcsMode.TRUNCATION:
            return  _("Calculations 1.1 truncation mode")

    @staticmethod
    def menu(): # must be dynamic class method to map to current language choice
        return OrderedDict((
            (_("No calculation checks"), ValidateCalcsMode.NONE),
            # omit pre-2010 spec v2.1 mode, XBRL_v2_1_INFER_PRECISION
            (_("Calc 1.0 calculations"), ValidateCalcsMode.XBRL_v2_1),
            (_("Calc 1.0 with de-duplication"), ValidateCalcsMode.XBRL_v2_1_DEDUPLICATE),
            (_("Calc 1.1 round-to-nearest mode"), ValidateCalcsMode.ROUND_TO_NEAREST),
            (_("Calc 1.1 truncation mode"), ValidateCalcsMode.TRUNCATION)
        ))


oimXbrlxeBlockingErrorCodes = {
        "xbrlxe:nonDimensionalSegmentScenarioContent",
        "xbrlxe:nonStandardFootnoteResourceRole",
        "xbrlxe:unsupportedTuple",
        "xbrlxe:unexpectedContextContent",
        "xbrlxe:unlinkedFootnoteResource",
        "xbrlxe:unsupportedComplexTypedDimension",
        "xbrlxe:unsupportedExternalRoleRef",
        "xbrlxe:unsupportedFraction",
        "xbrlxe:unsupportedLinkbaseReference",
        "xbrlxe:unsupportedXmlBase",
        "xbrlxe:unsupportedZeroPrecisionFact"
        }
numberPattern = re_compile("[-+]?[0]*([1-9]?[0-9]*)([.])?(0*)([1-9]?[0-9]*)?([eE])?([-+]?[0-9]*)?")
ZERO = decimal.Decimal(0)
ONE = decimal.Decimal(1)
TWO = decimal.Decimal(2)
TEN = decimal.Decimal(10)
NaN = decimal.Decimal("NaN")
floatNaN = float("NaN")
floatINF = float("INF")
INCONSISTENT = "*inconsistent*" # singleton
NIL_FACT_SET = "*nilFactSet*" # singleton
# RANGE values are (lower, upper, incl Lower bound, incl upper bound)
ZERO_RANGE = (0,0,True,True)
EMPTY_SET = set()
def rangeToStr(a, b, inclA, inclB) -> str:
    return {True:"[", False: "("}[inclA] + f"{a}, {b}" + {True:"]", False: ")"}[inclB]

def validate(modelXbrl, validateCalcs) -> None:
    ValidateXbrlCalcs(modelXbrl, validateCalcs).validate()

class ValidateXbrlCalcs:
    def __init__(self, modelXbrl, validateCalcs):
        self.modelXbrl = modelXbrl
        self.inferDecimals = validateCalcs != ValidateCalcsMode.XBRL_v2_1_INFER_PRECISION
        self.deDuplicate = validateCalcs == ValidateCalcsMode.XBRL_v2_1_DEDUPLICATE
        self.xbrl21 = validateCalcs in (ValidateCalcsMode.XBRL_v2_1_INFER_PRECISION, ValidateCalcsMode.XBRL_v2_1, ValidateCalcsMode.XBRL_v2_1_DEDUPLICATE)
        self.calc11 = validateCalcs in (ValidateCalcsMode.ROUND_TO_NEAREST, ValidateCalcsMode.TRUNCATION)
        self.calc11t = validateCalcs == ValidateCalcsMode.TRUNCATION
        self.calc11suffix = "Truncation" if self.calc11t else "Rounding"
        self.mapContext = {}
        self.mapUnit = {}
        self.sumFacts = defaultdict(list)
        self.sumConceptBindKeys = defaultdict(set)
        self.itemFacts = defaultdict(list)
        self.itemConceptBindKeys = defaultdict(set)
        self.duplicateKeyFacts = {}
        self.duplicatedFacts = set()
        self.calc11KeyFacts = defaultdict(list) # calc 11 reported facts by calcKey (concept, ancestor, contextHash, unit)
        self.consistentDupFacts = set() # when deDuplicating, holds the less-precise of v-equal dups
        self.esAlFacts = defaultdict(list)
        self.esAlConceptBindKeys = defaultdict(set)
        self.conceptsInEssencesAlias = set()
        self.requiresElementFacts = defaultdict(list)
        self.conceptsInRequiresElement = set()

    def validate(self):
        # note that calc linkbase checks need to be performed even if no facts in instance (e.g., to detect duplicate relationships)
        modelXbrl = self.modelXbrl
        xbrl21 = self.xbrl21
        calc11 = self.calc11 # round or truncate
        calc11t = self.calc11t # truncate
        sumConceptItemRels = defaultdict(dict) # for calc11 dup sum-item detection

        if xbrl21:
            if not self.modelXbrl.contexts and not self.modelXbrl.facts:
                return # skip if no contexts or facts (note that in calc11 mode the dup relationships test is nonetheless required)
            if not self.inferDecimals: # infering precision is now contrary to XBRL REC section 5.2.5.2
                modelXbrl.info("xbrl.5.2.5.2:inferringPrecision","Validating calculations inferring precision.")
        elif calc11:
            oimErrs = set()
            for i in range(len(modelXbrl.errors) - 1, -1, -1):
                e = modelXbrl.errors[i]
                if e in oimXbrlxeBlockingErrorCodes:
                    del modelXbrl.errors[i] # remove the oim errors from modelXbrl.errors
                oimErrs.add(e)
            if any(e == "xbrlxe:unsupportedTuple" for e in oimErrs):
                # ignore this error and change to warning
                modelXbrl.warning("calc11e:tuplesInReportWarning","Validating of calculations ignores tuples.")
            if any(e in oimXbrlxeBlockingErrorCodes for e in oimErrs if e != "xbrlxe:unsupportedTuple"):
                modelXbrl.warning("calc11e:oimIncompatibleReportWarning","Validating of calculations is skipped due to OIM errors.")
                return;

        # identify equal contexts
        modelXbrl.profileActivity()
        uniqueContextHashes = {}
        for context in modelXbrl.contexts.values():
            h = context.contextDimAwareHash
            if h in uniqueContextHashes:
                if context.isEqualTo(uniqueContextHashes[h]):
                    self.mapContext[context] = uniqueContextHashes[h]
            else:
                uniqueContextHashes[h] = context
        del uniqueContextHashes
        modelXbrl.profileActivity("... identify equal contexts", minTimeToShow=1.0)

        # identify equal units
        uniqueUnitHashes = {}
        for unit in modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    self.mapUnit[unit] = uniqueUnitHashes[h]
            else:
                uniqueUnitHashes[h] = unit
        del uniqueUnitHashes
        modelXbrl.profileActivity("... identify equal units", minTimeToShow=1.0)

        # identify concepts participating in essence-alias relationships
        # identify calcluation & essence-alias base sets (by key)
        if xbrl21:
            for baseSetKey in modelXbrl.baseSets.keys():
                arcrole, ELR, linkqname, arcqname = baseSetKey
                if ELR and linkqname and arcqname:
                    if arcrole in (XbrlConst.essenceAlias, XbrlConst.requiresElement):
                        conceptsSet = {XbrlConst.essenceAlias:self.conceptsInEssencesAlias,
                                       XbrlConst.requiresElement:self.conceptsInRequiresElement}[arcrole]
                        for modelRel in modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname).modelRelationships:
                            for concept in (modelRel.fromModelObject, modelRel.toModelObject):
                                if concept is not None and concept.qname is not None:
                                    conceptsSet.add(concept)
            modelXbrl.profileActivity("... identify requires-element and esseance-aliased concepts", minTimeToShow=1.0)

        self.bindFacts(modelXbrl.facts,[modelXbrl.modelDocument.xmlRootElement])
        modelXbrl.profileActivity("... bind facts", minTimeToShow=1.0)

        allArcroles = flattenSequence(
            ({XbrlConst.summationItem, XbrlConst.essenceAlias, XbrlConst.requiresElement} if xbrl21 else EMPTY_SET) |
            ({XbrlConst.summationItem, XbrlConst.summationItem11} if calc11 else EMPTY_SET))
        summationArcroles = flattenSequence(
            ({XbrlConst.summationItem} if xbrl21 else EMPTY_SET) |
            ({XbrlConst.summationItem, XbrlConst.summationItem11} if calc11 else EMPTY_SET))

        # identify calcluation & essence-alias base sets (by key)
        for baseSetKey in modelXbrl.baseSets.keys():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if ELR and linkqname and arcqname:
                if arcrole in allArcroles:
                    relsSet = modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname)
                    sumConceptItemRels.clear()
                    if arcrole in summationArcroles:
                        fromRelationships = relsSet.fromModelObjects()
                        for sumConcept, modelRels in fromRelationships.items():
                            sumBindingKeys = self.sumConceptBindKeys[sumConcept]
                            dupBindingKeys = set()
                            boundSumKeys = set()
                            # determine boundSums
                            for modelRel in modelRels:
                                itemConcept = modelRel.toModelObject
                                if itemConcept is not None and itemConcept.qname is not None:
                                    itemBindingKeys = self.itemConceptBindKeys[itemConcept]
                                    boundSumKeys |= sumBindingKeys & itemBindingKeys
                                    if calc11:
                                        siRels = sumConceptItemRels[sumConcept]
                                        if itemConcept in siRels:
                                            modelXbrl.error("calc11e:duplicateCalculationRelationships",
                                                _("Duplicate summation-item relationships from total concept %(sumConcept)s to contributing concept %(itemConcept)s in link role %(linkrole)s"),
                                                modelObject=(siRels[itemConcept], modelRel), linkrole=modelRel.linkrole,
                                                sumConcept=sumConcept.qname, itemConcept=itemConcept.qname)
                                        siRels[itemConcept] = modelRel
                                        if not sumConcept.isDecimal or not itemConcept.isDecimal:
                                            modelXbrl.error("calc11e:nonDecimalItemNode",
                                                _("The source and target of a Calculations v1.1 relationship MUST both be decimal concepts: %(sumConcept)s, %(itemConcept)s, link role %(linkrole)s"),
                                                modelObject=(sumConcept, itemConcept, modelRel), linkrole=modelRel.linkrole,
                                                sumConcept=sumConcept.qname, itemConcept=itemConcept.qname)

                            # add up rounded items
                            boundSums = defaultdict(decimal.Decimal) # sum of facts meeting factKey
                            boundIntervals = {} # interval sum of facts meeting factKey
                            blockedIntervals = set() # bind Keys for summations which have an inconsistency
                            boundSummationItems = defaultdict(list) # corresponding fact refs for messages
                            boundIntervalItems = defaultdict(list) # corresponding fact refs for messages
                            for modelRel in modelRels:
                                w = modelRel.weightDecimal
                                itemConcept = modelRel.toModelObject
                                if itemConcept is not None:
                                    for itemBindKey in boundSumKeys:
                                        ancestor, contextHash, unit = itemBindKey
                                        factKey = (itemConcept, ancestor, contextHash, unit)
                                        _itemFacts = self.itemFacts.get(factKey,())
                                        if xbrl21:
                                            for fact in _itemFacts:
                                                if not fact.isNil:
                                                    if fact in self.duplicatedFacts:
                                                        dupBindingKeys.add(itemBindKey)
                                                    elif fact not in self.consistentDupFacts:
                                                        roundedValue = roundFact(fact, self.inferDecimals)
                                                        boundSums[itemBindKey] += roundedValue * w
                                                        boundSummationItems[itemBindKey].append(wrappedFactWithWeight(fact,w,roundedValue))
                                        if calc11 and _itemFacts:
                                            y1, y2, iY1, iY2 = self.consistentFactValueInterval(_itemFacts, calc11t)
                                            if y1 is INCONSISTENT:
                                                blockedIntervals.add(itemBindKey)
                                            elif y1 is not NIL_FACT_SET:
                                                x1, x2, iX1, iX2 = boundIntervals.get(itemBindKey, ZERO_RANGE)
                                                y1 *= w
                                                y2 *= w
                                                if y2 < y1:
                                                    y1, y2 = y2, y1
                                                boundIntervals[itemBindKey] = (x1 + y1, x2 + y2, iX1 and iY1, iX2 and iY2)
                                                boundIntervalItems[itemBindKey].extend(_itemFacts)
                            for sumBindKey in boundSumKeys:
                                ancestor, contextHash, unit = sumBindKey
                                factKey = (sumConcept, ancestor, contextHash, unit)
                                if factKey in self.sumFacts:
                                    sumFacts = self.sumFacts[factKey]
                                    if xbrl21:
                                        for fact in sumFacts:
                                            if not fact.isNil:
                                                if fact in self.duplicatedFacts:
                                                    dupBindingKeys.add(sumBindKey)
                                                elif (sumBindKey in boundSums and sumBindKey not in dupBindingKeys
                                                      and fact not in self.consistentDupFacts
                                                      and not (len(sumFacts) > 1 and not self.deDuplicate)): # don't bind if sum duplicated without dedup option
                                                    roundedSum = roundFact(fact, self.inferDecimals)
                                                    roundedItemsSum = roundFact(fact, self.inferDecimals, vDecimal=boundSums[sumBindKey])
                                                    if roundedItemsSum  != roundFact(fact, self.inferDecimals):
                                                        d = inferredDecimals(fact)
                                                        if isnan(d) or isinf(d): d = 4
                                                        _boundSummationItems = boundSummationItems[sumBindKey]
                                                        unreportedContribingItemQnames = [] # list the missing/unreported contributors in relationship order
                                                        for modelRel in modelRels:
                                                            itemConcept = modelRel.toModelObject
                                                            if (itemConcept is not None and
                                                                (itemConcept, ancestor, contextHash, unit) not in self.itemFacts):
                                                                unreportedContribingItemQnames.append(str(itemConcept.qname))
                                                        modelXbrl.log('INCONSISTENCY', "xbrl.5.2.5.2:calcInconsistency",
                                                            _("Calculation inconsistent from %(concept)s in link role %(linkrole)s reported sum %(reportedSum)s computed sum %(computedSum)s context %(contextID)s unit %(unitID)s unreportedContributingItems %(unreportedContributors)s"),
                                                            modelObject=wrappedSummationAndItems(fact, roundedSum, _boundSummationItems),
                                                            concept=sumConcept.qname, linkrole=ELR,
                                                            linkroleDefinition=modelXbrl.roleTypeDefinition(ELR),
                                                            reportedSum=Locale.format_decimal(modelXbrl.locale, roundedSum, 1, max(d,0)),
                                                            computedSum=Locale.format_decimal(modelXbrl.locale, roundedItemsSum, 1, max(d,0)),
                                                            contextID=fact.context.id, unitID=fact.unit.id,
                                                            unreportedContributors=", ".join(unreportedContribingItemQnames) or "none")
                                                        del unreportedContribingItemQnames[:]
                                    if calc11:
                                        s1, s2, incls1, incls2 = self.consistentFactValueInterval(sumFacts, calc11t)
                                        if s1 is not INCONSISTENT and s1 is not NIL_FACT_SET and sumBindKey not in blockedIntervals and sumBindKey in boundIntervals:
                                            x1, x2, inclx1, inclx2 = boundIntervals[sumBindKey]
                                            a = max(s1, x1)
                                            b = min(s2, x2)
                                            inclA = incls1 | inclx1
                                            inclB = incls2 | inclx2
                                            if (a == b and not (inclA and inclB)) or (a > b):
                                                modelXbrl.log('INCONSISTENCY', "calc11e:inconsistentCalculationUsing" + self.calc11suffix,
                                                    _("Calculation inconsistent from %(concept)s in link role %(linkrole)s reported sum %(reportedSum)s computed sum %(computedSum)s context %(contextID)s unit %(unitID)s"),
                                                    modelObject=sumFacts + boundIntervalItems[sumBindKey],
                                                    concept=sumConcept.qname, linkrole=ELR,
                                                    linkroleDefinition=modelXbrl.roleTypeDefinition(ELR),
                                                    reportedSum=rangeToStr(s1,s2,incls1,incls2),
                                                    computedSum=rangeToStr(x1,x2,inclx1,inclx2),
                                                    contextID=sumFacts[0].context.id, unitID=sumFacts[0].unit.id)
                            boundSummationItems.clear() # dereference facts in list
                            boundIntervalItems.clear()
                    elif arcrole == XbrlConst.essenceAlias:
                        for modelRel in relsSet.modelRelationships:
                            essenceConcept = modelRel.fromModelObject
                            aliasConcept = modelRel.toModelObject
                            essenceBindingKeys = self.esAlConceptBindKeys[essenceConcept]
                            aliasBindingKeys = self.esAlConceptBindKeys[aliasConcept]
                            for esAlBindKey in essenceBindingKeys & aliasBindingKeys:
                                ancestor, contextHash = esAlBindKey
                                essenceFactsKey = (essenceConcept, ancestor, contextHash)
                                aliasFactsKey = (aliasConcept, ancestor, contextHash)
                                if essenceFactsKey in self.esAlFacts and aliasFactsKey in self.esAlFacts:
                                    for eF in self.esAlFacts[essenceFactsKey]:
                                        for aF in self.esAlFacts[aliasFactsKey]:
                                            essenceUnit = self.mapUnit.get(eF.unit,eF.unit)
                                            aliasUnit = self.mapUnit.get(aF.unit,aF.unit)
                                            if essenceUnit != aliasUnit:
                                                modelXbrl.log('INCONSISTENCY', "xbrl.5.2.6.2.2:essenceAliasUnitsInconsistency",
                                                    _("Essence-Alias inconsistent units from %(essenceConcept)s to %(aliasConcept)s in link role %(linkrole)s context %(contextID)s"),
                                                    modelObject=(modelRel, eF, aF),
                                                    essenceConcept=essenceConcept.qname, aliasConcept=aliasConcept.qname,
                                                    linkrole=ELR,
                                                    linkroleDefinition=modelXbrl.roleTypeDefinition(ELR),
                                                    contextID=eF.context.id)
                                            if not XbrlUtil.vEqual(eF, aF):
                                                modelXbrl.log('INCONSISTENCY', "xbrl.5.2.6.2.2:essenceAliasUnitsInconsistency",
                                                    _("Essence-Alias inconsistent value from %(essenceConcept)s to %(aliasConcept)s in link role %(linkrole)s context %(contextID)s"),
                                                    modelObject=(modelRel, eF, aF),
                                                    essenceConcept=essenceConcept.qname, aliasConcept=aliasConcept.qname,
                                                    linkrole=ELR,
                                                    linkroleDefinition=modelXbrl.roleTypeDefinition(ELR),
                                                    contextID=eF.context.id)
                    elif arcrole == XbrlConst.requiresElement:
                        for modelRel in relsSet.modelRelationships:
                            sourceConcept = modelRel.fromModelObject
                            requiredConcept = modelRel.toModelObject
                            if sourceConcept in self.requiresElementFacts and \
                               not requiredConcept in self.requiresElementFacts:
                                    modelXbrl.log('INCONSISTENCY', "xbrl.5.2.6.2.4:requiresElementInconsistency",
                                        _("Requires-Element %(requiringConcept)s missing required fact for %(requiredConcept)s in link role %(linkrole)s"),
                                        modelObject=sourceConcept,
                                        requiringConcept=sourceConcept.qname, requiredConcept=requiredConcept.qname,
                                        linkrole=ELR,
                                        linkroleDefinition=modelXbrl.roleTypeDefinition(ELR))
        modelXbrl.profileActivity("... find inconsistencies", minTimeToShow=1.0)
        modelXbrl.profileActivity() # reset

    def bindFacts(self, facts, ancestors):
        for f in facts:
            concept = f.concept
            if concept is not None and f.xValid >= VALID:
                # index facts by their calc relationship set
                if concept.isNumeric:
                    for ancestor in ancestors:
                        # tbd: uniqify context and unit
                        context = self.mapContext.get(f.context,f.context)
                        # must use nonDimAwareHash to achieve s-equal comparison of contexts
                        contextHash = context.contextNonDimAwareHash if context is not None else hash(None)
                        unit = self.mapUnit.get(f.unit,f.unit)
                        calcKey = (concept, ancestor, contextHash, unit)
                        self.itemFacts[calcKey].append(f)
                        bindKey = (ancestor, contextHash, unit)
                        self.itemConceptBindKeys[concept].add(bindKey)
                    self.sumFacts[calcKey].append(f) # sum only for immediate parent
                    self.sumConceptBindKeys[concept].add(bindKey)
                    # calcKey is the last ancestor added (immediate parent of fact)
                    if self.xbrl21 and not f.isNil:
                        fDup = self.duplicateKeyFacts.setdefault(calcKey, f)
                        if fDup is not f:
                            if self.deDuplicate: # add lesser precision fact to consistentDupFacts
                                if self.inferDecimals:
                                    d = inferredDecimals(f); dDup = inferredDecimals(fDup)
                                    dMin = min((d, dDup)); pMin = None
                                    hasAccuracy = (not isnan(d) and not isnan(dDup))
                                    fIsMorePrecise = (d > dDup)
                                else:
                                    p = inferredPrecision(f); pDup = inferredPrecision(fDup)
                                    dMin = None; pMin = min((p, pDup))
                                    hasAccuracy = (p != 0)
                                    fIsMorePrecise = (p > pDup)
                                if (hasAccuracy and
                                    roundValue(f.value,precision=pMin,decimals=dMin) ==
                                    roundValue(fDup.value,precision=pMin,decimals=dMin)):
                                    # consistent duplicate, f more precise than fDup, replace fDup with f
                                    if fIsMorePrecise: # works for inf and integer mixtures
                                        self.duplicateKeyFacts[calcKey] = f
                                        self.consistentDupFacts.add(fDup)
                                    else: # fDup is more precise or equally precise
                                        self.consistentDupFacts.add(f)
                                else: # invalid accuracy or inconsistent duplicates
                                    self.duplicatedFacts.add(f)
                                    self.duplicatedFacts.add(fDup)
                            else: # add both this fact and matching calcKey'ed fact to duplicatedFacts
                                self.duplicatedFacts.add(f)
                                self.duplicatedFacts.add(fDup)
                    if self.calc11:
                        self.calc11KeyFacts[calcKey].append(f)
                elif concept.isTuple and not f.isNil and not self.calc11:
                    self.bindFacts(f.modelTupleFacts, ancestors + [f])

                # index facts by their essence alias relationship set
                if concept in self.conceptsInEssencesAlias and not f.isNil:
                    ancestor = ancestors[-1]    # only care about direct parent
                    context = self.mapContext.get(f.context,f.context)
                    contextHash = context.contextNonDimAwareHash if context is not None else hash(None)
                    esAlKey = (concept, ancestor, contextHash)
                    self.esAlFacts[esAlKey].append(f)
                    bindKey = (ancestor, contextHash)
                    self.esAlConceptBindKeys[concept].add(bindKey)
                # index facts by their requires element usage
                if concept in self.conceptsInRequiresElement:
                    self.requiresElementFacts[concept].append(f)

    def consistentFactValueInterval(self, fList, truncate=False) -> tuple[decimal.Decimal | str, decimal.Decimal | str, bool, bool]:
        _excessDigitFacts = []
        if any(f.isNil for f in fList):
            if all(f.isNil for f in fList):
                return (NIL_FACT_SET,NIL_FACT_SET,True,True)
            _inConsistent = True # provide error message
        else: # not all have same decimals
            a = b = None
            inclA = inclB = _inConsistent = False
            decVals = {}
            for f in fList:
                _v = f.xValue
                if isnan(_v):
                    if len(fList) > 1:
                        _inConsistent = True
                    break
                _d = inferredDecimals(f)
                if insignificantDigits(_v, decimals=_d):
                    _excessDigitFacts.append(f)
                elif _d in decVals:
                    _inConsistent |= _v != decVals[_d]
                else:
                    decVals[_d] = _v
                    _a, _b, _inclA, _inclB = rangeValue(_v, _d, truncate=truncate)
                    if a is None or _a >= a:
                        a = _a
                        inclA |= _inclA
                    if b is None or _b <= b:
                        b = _b
                        inclB |= _inclB
            _inConsistent = (a == b and not(inclA and inclB)) or (a > b)
        if _excessDigitFacts:
            self.modelXbrl.log('INCONSISTENCY', "calc11e:excessDigits",
                _("Calculations check stopped for excess digits in fact values %(element)s: %(values)s, %(contextIDs)s."),
                modelObject=fList, element=_excessDigitFacts[0].qname,
                contextIDs=", ".join(sorted(set(f.contextID for f in _excessDigitFacts))),
                values=", ".join(strTruncate(f.value,64) for f in _excessDigitFacts))
            return (INCONSISTENT, INCONSISTENT,True,True)
        if _inConsistent:
            self.modelXbrl.log('INCONSISTENCY',
                "calc11e:disallowedDuplicateFactsUsingTruncation" if self.calc11t else "oime:disallowedDuplicateFacts",
                _("Calculations check stopped for duplicate fact values %(element)s: %(values)s, %(contextIDs)s."),
                modelObject=fList, element=fList[0].qname,
                contextIDs=", ".join(sorted(set(f.contextID for f in fList))),
                values=", ".join(strTruncate(f.value,64) for f in fList))
            return (INCONSISTENT, INCONSISTENT,True,True)
        return (a, b, inclA, inclB)

def roundFact(fact, inferDecimals=False, vDecimal=None):
    if vDecimal is None:
        vStr = fact.value
        try:
            vDecimal = decimal.Decimal(vStr)
            vFloatFact = float(vStr)
        except (decimal.InvalidOperation, ValueError): # would have been a schema error reported earlier
            vDecimal = NaN
            vFloatFact = floatNaN
    else: #only vFloat is defined, may not need vStr unless inferring precision from decimals
        if vDecimal.is_nan():
            return vDecimal
        vStr = None
        try:
            vFloatFact = float(fact.value)
        except ValueError:
            vFloatFact = floatNaN
    dStr = fact.decimals
    pStr = fact.precision
    if dStr == "INF" or pStr == "INF":
        vRounded = vDecimal
    elif inferDecimals: #infer decimals, round per 4.6.7.2, e.g., half-down
        if pStr:
            p = int(pStr)
            if p == 0:
                vRounded = NaN
            elif vDecimal == 0:
                vRounded = ZERO
            else:
                vAbs = fabs(vFloatFact)
                d = p - int(floor(log10(vAbs))) - 1
                # defeat binary rounding to nearest even
                #if trunc(fmod(vFloat * (10 ** d),2)) != 0:
                #    vFloat += 10 ** (-d - 1) * (1.0 if vFloat > 0 else -1.0)
                #vRounded = round(vFloat, d)
                vRounded = decimalRound(vDecimal,d,decimal.ROUND_HALF_EVEN)
        elif dStr:
            d = int(dStr)
            # defeat binary rounding to nearest even
            #if trunc(fmod(vFloat * (10 ** d),2)) != 0:
            #    vFloat += 10 ** (-d - 1) * (-1.0 if vFloat > 0 else 1.0)
            #vRounded = round(vFloat, d)
            #vRounded = round(vFloat,d)
            vRounded = decimalRound(vDecimal,d,decimal.ROUND_HALF_EVEN)
        else: # no information available to do rounding (other errors xbrl.4.6.3 error)
            vRounded = vDecimal
    else: # infer precision
        if dStr:
            match = numberPattern.match(vStr if vStr else str(vDecimal))
            if match:
                nonZeroInt, period, zeroDec, nonZeroDec, e, exp = match.groups()
                p = (len(nonZeroInt) if nonZeroInt and (len(nonZeroInt)) > 0 else -len(zeroDec)) + \
                    (int(exp) if exp and (len(exp) > 0) else 0) + \
                    (int(dStr))
            else:
                p = 0
        elif pStr:
            p = int(pStr)
        else: # no rounding information
            p = None
        if p == 0:
            vRounded = NaN
        elif vDecimal == 0:
            vRounded = vDecimal
        elif p is not None:  # round per 4.6.7.1, half-up
            vAbs = vDecimal.copy_abs()
            log = vAbs.log10()
            # defeat rounding to nearest even
            d = p - int(log) - (1 if vAbs >= 1 else 0)
            #if trunc(fmod(vFloat * (10 ** d),2)) != 0:
            #    vFloat += 10 ** (-d - 1) * (1.0 if vFloat > 0 else -1.0)
            #vRounded = round(vFloat, d)
            vRounded = decimalRound(vDecimal,d,decimal.ROUND_HALF_UP)
        else: # no information available to do rounding (other errors xbrl.4.6.3 error)
            vRounded = vDecimal
    return vRounded

def decimalRound(x, d, rounding):
    if x.is_normal() and -28 <= d <= 28: # prevent exception with excessive quantization digits
        if d >= 0:
            return x.quantize(ONE.scaleb(-d),rounding)
        else: # quantize only seems to work on fractional part, convert integer to fraction at scaled point
            return x.scaleb(d).quantize(ONE,rounding) * (TEN ** decimal.Decimal(-d)) # multiply by power of 10 to prevent scaleb scientific notatino
    return x # infinite, NaN, zero, or excessive decimal digits ( > 28 )

def inferredPrecision(fact):
    vStr = fact.value
    dStr = fact.decimals
    pStr = fact.precision
    if dStr == "INF" or pStr == "INF":
        return floatINF
    try:
        vFloat = float(vStr)
        if dStr:
            match = numberPattern.match(vStr if vStr else str(vFloat))
            if match:
                nonZeroInt, period, zeroDec, nonZeroDec, e, exp = match.groups()
                p = (len(nonZeroInt) if nonZeroInt else (-len(zeroDec) if nonZeroDec else 0)) + \
                    (int(exp) if exp else 0) + \
                    (int(dStr))
                if p < 0:
                    p = 0 # "pathological case" 2.1 spec example 13 line 7
            else:
                p = 0
        else:
            return int(pStr)
    except ValueError:
        return floatNaN
    if p == 0:
        return 0
    elif vFloat == 0:
        return 0
    else:
        return p

def inferredDecimals(fact: ModelFact) -> float | int:
    vStr = fact.value
    dStr = fact.decimals
    pStr = fact.precision
    if dStr == "INF" or pStr == "INF":
        return floatINF
    try:
        if pStr:
            p = int(pStr)
            if p == 0:
                return floatNaN # =0 cannot be determined
            vFloat = float(vStr)
            if vFloat == 0:
                return floatINF # =0 cannot be determined
            else:
                vAbs = fabs(vFloat)
                return p - int(floor(log10(vAbs))) - 1
        elif dStr:
            return int(dStr)
    except ValueError:
        pass
    return floatNaN

def roundValue(value, precision=None, decimals=None, scale=None):
    try:
        vDecimal = decimal.Decimal(value)
        if scale:
            iScale = int(scale)
            vDecimal = vDecimal.scaleb(iScale)
        if precision is not None:
            vFloat = float(value)
            if scale:
                vFloat = pow(vFloat, iScale)
    except (decimal.InvalidOperation, ValueError, TypeError): # would have been a schema error reported earlier  None gives Type Error (e.g., xsi:nil)
        return NaN
    if precision is not None:
        if not isinstance(precision, (int,float)):
            if precision == "INF":
                precision = floatINF
            else:
                try:
                    precision = int(precision)
                except ValueError: # would be a schema error
                    precision = floatNaN
        if isinf(precision):
            vRounded = vDecimal
        elif precision == 0 or isnan(precision):
            vRounded = NaN
        elif vFloat == 0:
            vRounded = ZERO
        else:
            vAbs = fabs(vFloat)
            log = log10(vAbs)
            d = precision - int(log) - (1 if vAbs >= 1 else 0)
            vRounded = decimalRound(vDecimal,d,decimal.ROUND_HALF_UP)
    elif decimals is not None:
        if not isinstance(decimals, (int,float)):
            if decimals == "INF":
                decimals = floatINF
            else:
                try:
                    decimals = int(decimals)
                except ValueError: # would be a schema error
                    decimals = floatNaN
        if isinf(decimals):
            vRounded = vDecimal
        elif isnan(decimals):
            vRounded = NaN
        else:
            vRounded = decimalRound(vDecimal,decimals,decimal.ROUND_HALF_EVEN)
    else:
        vRounded = vDecimal
    return vRounded

def rangeValue(value, decimals=None, truncate=False) -> tuple[decimal.Decimal, decimal.Decimal, bool, bool]:
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], ModelFact):
            return rangeValue(value[0].xValue, inferredDecimals(value[0]), truncate=truncate)
        # return intersection of fact value ranges
    if isinstance(value, ModelFact):
        return rangeValue(value.xValue, inferredDecimals(value), truncate=truncate)
    try:
        vDecimal = decimal.Decimal(value)
    except (decimal.InvalidOperation, ValueError): # would have been a schema error reported earlier
        return (NaN, NaN, True, True)
    if decimals is not None and decimals != "INF":
        if not isinstance(decimals, (int,float)):
            try:
                decimals = int(decimals)
            except ValueError: # would be a schema error
                decimals = floatNaN
        if not (isinf(decimals) or isnan(decimals)):
            dd = (TEN**(decimal.Decimal(decimals).quantize(ONE,decimal.ROUND_DOWN)*-ONE))
            if not truncate:
                dd /= TWO
                return (vDecimal - dd, vDecimal + dd, True, True)
            elif vDecimal > 0:
                return (vDecimal, vDecimal + dd, True, False)
            elif vDecimal < 0:
                return (vDecimal - dd, vDecimal, False, True)
            else:
                return (vDecimal - dd, vDecimal + dd, False, False)
    return (vDecimal, vDecimal, True, True)


def insignificantDigits(
        value: TypeXValue,
        decimals: int | float | Decimal | str) -> tuple[Decimal, Decimal] | None:
    # Normalize value
    try:
        valueDecimal = decimal.Decimal(value)
    except (decimal.InvalidOperation, ValueError):  # would have been a schema error reported earlier
        return None
    if not valueDecimal.is_normal():  # prevent exception with excessive quantization digits
        return None
    # Normalize decimals
    if isinstance(decimals, str):
        if decimals == "INF":
            return None
        else:
            try:
                decimals = int(decimals)
            except ValueError:  # would have been a schema error reported earlier
                return None
    if isinf(decimals) or isnan(decimals) or decimals <= -28:  # prevent exception with excessive quantization digits
        return None
    if decimals > 0:
        divisor = ONE.scaleb(-decimals)  # fractional scaling doesn't produce scientific notation
    else:  # extra quantize step to prevent scientific notation for decimal number
        divisor = ONE.scaleb(-decimals).quantize(ONE, decimal.ROUND_HALF_UP) # should never round
    try:
        quotient, insignificant = divmod(valueDecimal, divisor)
    except decimal.InvalidOperation:
        return None
    if insignificant:
        significant = quotient * divisor
        return significant, abs(insignificant)
    return None


def wrappedFactWithWeight(fact, weight, roundedValue):
    return ObjectPropertyViewWrapper(fact, ( ("weight", weight), ("roundedValue", roundedValue)) )

def wrappedSummationAndItems(fact, roundedSum, boundSummationItems):
    # need hash of facts and their values from boundSummationItems
    ''' ARELLE-281, replace: faster python-based hash (replace with hashlib for fewer collisions)
    itemValuesHash = hash( tuple(( hash(b.modelObject.qname), hash(b.extraProperties[1][1]) )
                                 # sort by qname so we don't care about reordering of summation terms
                                 for b in sorted(boundSummationItems,
                                                       key=lambda b: b.modelObject.qname)) )
    sumValueHash = hash( (hash(fact.qname), hash(roundedSum)) )
    '''
    sha256 = hashlib.sha256()
    # items hash: sort by qname so we don't care about reordering of summation terms in linkbase updates
    for b in sorted(boundSummationItems, key=lambda b: b.modelObject.qname):
        sha256.update(b.modelObject.qname.namespaceURI.encode('utf-8','replace')) #qname of erroneous submission may not be utf-8 perfectly encodable
        sha256.update(b.modelObject.qname.localName.encode('utf-8','replace'))
        sha256.update(str(b.extraProperties[1][1]).encode('utf-8','replace'))
    itemValuesHash = sha256.hexdigest()
    # summation value hash
    sha256 = hashlib.sha256()
    sha256.update(fact.qname.namespaceURI.encode('utf-8','replace'))
    sha256.update(fact.qname.localName.encode('utf-8','replace'))
    sha256.update(str(roundedSum).encode('utf-8','replace'))
    sumValueHash = sha256.hexdigest()
    # return list of bound summation followed by bound contributing items
    return [ObjectPropertyViewWrapper(fact,
                                      ( ("sumValueHash", sumValueHash),
                                        ("itemValuesHash", itemValuesHash),
                                        ("roundedSum", roundedSum) ))] + \
            boundSummationItems
