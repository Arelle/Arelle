'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from math import (log10, isnan, isinf, fabs, trunc, fmod, floor, pow)
import decimal
try:
    from regex import compile as re_compile
except ImportError:
    from re import compile as re_compile
import hashlib
from arelle import Locale, XbrlConst, XbrlUtil
from arelle.ModelObject import ObjectPropertyViewWrapper
from arelle.PythonUtil import flattenSequence, strTruncate
from arelle.XmlValidate import UNVALIDATED, VALID

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
ZERO_RANGE = (0,0)
EMPTY_SET = set()

def validate(modelXbrl,
             inferDecimals=False, # for XBRL v2.1 semantics, infer decimals (vs precision which was original REC)
             deDuplicate=False,   # for XBRL v2.1 semantics, deduplicate by choosing most accurate value
             xbrl21=True,         # validate calc LB with XBRL v2.1 semantics (default)
             calc11=False):       # validate calc LB with Calculation 1.1 semantics
    ValidateXbrlCalcs(modelXbrl, inferDecimals, deDuplicate, xbrl21, calc11).validate()
    
class ValidateXbrlCalcs:
    def __init__(self, modelXbrl, inferDecimals=False, deDuplicate=False, xbrl21=True, calc11=False):
        self.modelXbrl = modelXbrl
        self.inferDecimals = inferDecimals
        self.deDuplicate = deDuplicate
        self.xbrl21 = xbrl21
        self.calc11 = calc11
        self.mapContext = {}
        self.mapUnit = {}
        self.sumFacts = defaultdict(list)
        self.sumConceptBindKeys = defaultdict(set)
        self.itemFacts = defaultdict(list)
        self.itemConceptBindKeys = defaultdict(set)
        self.duplicateKeyFacts = {}
        self.duplicatedFacts = set()
        self.calc11KeyFacts = defaultdict(list) # calc 11 reported facts by calcKey (concept, ancestor, contextHash, unit)
        self.consistentDupFacts = set() # when deDuplicatig, holds the less-precise of v-equal dups
        self.esAlFacts = defaultdict(list)
        self.esAlConceptBindKeys = defaultdict(set)
        self.conceptsInEssencesAlias = set()
        self.requiresElementFacts = defaultdict(list)
        self.conceptsInRequiresElement = set()
        
    def validate(self):
        if not self.modelXbrl.contexts and not self.modelXbrl.facts:
            return # skip if no contexts or facts

        modelXbrl = self.modelXbrl
        xbrl21 = self.xbrl21
        calc11 = self.calc11
          
        if xbrl21 and not self.inferDecimals: # infering precision is now contrary to XBRL REC section 5.2.5.2
            modelXbrl.info("xbrl.5.2.5.2:inferringPrecision","Validating calculations inferring precision.")
            
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
                                            y1, y2 = self.oimConsistentInterval(_itemFacts)
                                            if y1 is INCONSISTENT:
                                                blockedIntervals.add(itemBindKey)
                                            elif y1 is not NIL_FACT_SET:
                                                x1, x2 = boundIntervals.get(itemBindKey, ZERO_RANGE)
                                                y1 *= w
                                                y2 *= w
                                                boundIntervals[itemBindKey] = (x1 + min(y1,y2), x2 + max(y1,y2))
                                                boundIntervalItems[itemBindKey].extend(_itemFacts)
                            for sumBindKey in boundSumKeys:
                                ancestor, contextHash, unit = sumBindKey
                                factKey = (sumConcept, ancestor, contextHash, unit)
                                if factKey in self.sumFacts:
                                    sumFacts = self.sumFacts[factKey]
                                    for fact in sumFacts:
                                        if not fact.isNil:
                                            if fact in self.duplicatedFacts:
                                                dupBindingKeys.add(sumBindKey)
                                            elif (xbrl21 and sumBindKey in boundSums and sumBindKey not in dupBindingKeys 
                                                  and fact not in self.consistentDupFacts
                                                  and not (len(sumFacts) > 1 and not (self.deDuplicate or not any(inferredDecimals(f) != inferredDecimals(fact) for f in sumFacts)))): # don't bind if sum duplicated without dedup option
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
                                        s1, s2 = self.oimConsistentInterval(sumFacts)
                                        if s1 is not INCONSISTENT and factKey not in blockedIntervals and sumBindKey in boundIntervals:
                                            x1, x2 = boundIntervals[sumBindKey]
                                            if min(s2, x2) < max(s1, x1):
                                                modelXbrl.error("calc11e:inconsistentCalculation",
                                                    _("Calculation inconsistent from %(concept)s in link role %(linkrole)s reported sum %(reportedSum)s computed sum %(computedSum)s context %(contextID)s unit %(unitID)s"),
                                                    modelObject=[fact] + boundIntervalItems[sumBindKey],
                                                    concept=sumConcept.qname, linkrole=ELR, 
                                                    linkroleDefinition=modelXbrl.roleTypeDefinition(ELR),
                                                    reportedSum="[{},{}]".format(s1, s2),
                                                    computedSum="[{},{}]".format(x1, x2), 
                                                    contextID=fact.context.id, unitID=fact.unit.id)
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
            if concept is not None:
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
                    if calcKey in self.duplicateKeyFacts and not f.isNil:
                        fDup = self.duplicateKeyFacts[calcKey]
                        if self.deDuplicate or inferredDecimals(f) == inferredDecimals(fDup): # add lesser precision fact to consistentDupFacts
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
                    elif self.xbrl21 and not f.isNil:
                        self.duplicateKeyFacts[calcKey] = f
                    if self.calc11:
                        self.calc11KeyFacts[calcKey].append(f)
                elif concept.isTuple and not f.isNil:
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

    def oimConsistentInterval(self, fList):
        if any(f.isNil for f in fList):
            if all(f.isNil for f in fList):
                return (NIL_FACT_SET,NIL_FACT_SET)
            _inConsistent = True # provide error message 
        else: # not all have same decimals
            f0 = fList[0]
            _d = inferredDecimals(f0)
            _v = f0.xValue
            _inConsistent = isnan(_v) # NaN is incomparable, always makes dups inconsistent
            decVals = {_d: _v}
            aMax, bMin = rangeValue(_v, _d)
            for f in fList[1:]:
                _d = inferredDecimals(f)
                _v = f.xValue
                if isnan(_v):
                    _inConsistent = True
                    break
                if _d in decVals:
                    _inConsistent |= _v != decVals[_d]
                else:
                    decVals[_d] = _v
                a, b = rangeValue(_v, _d)
                if a > aMax: aMax = a
                if b < bMin: bMin = b
            if not _inConsistent:
                _inConsistent = (bMin < aMax)
        if _inConsistent:
            self.modelXbrl.error("oime:disallowedDuplicateFacts",
                "Calculations check stopped for duplicate fact values %(element)s: %(values)s, %(contextIDs)s.",
                modelObject=fList, element=fList[0].qname, 
                contextIDs=", ".join(sorted(set(f.contextID for f in fList))), 
                values=", ".join(strTruncate(f.value,64) for f in fList))
            return (INCONSISTENT, INCONSISTENT)
        return (aMax, bMin)
        

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
    
def inferredDecimals(fact):
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

def rangeValue(value, decimals=None):
    from arelle.ModelInstanceObject import ModelFact
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], ModelFact):
            return rangeValue(value[0].xValue, inferredDecimals(value[0]))
        # return intersection of fact value ranges
    if isinstance(value, ModelFact):
        return rangeValue(value.xValue, inferredDecimals(value))
    try:
        vDecimal = decimal.Decimal(value)
    except (decimal.InvalidOperation, ValueError): # would have been a schema error reported earlier
        return (NaN, NaN)
    if decimals is not None and decimals != "INF":
        if not isinstance(decimals, (int,float)):
            try:
                decimals = int(decimals)
            except ValueError: # would be a schema error
                decimals = floatNaN
        if not (isinf(decimals) or isnan(decimals)):
            dd = (TEN**(decimal.Decimal(decimals).quantize(ONE,decimal.ROUND_DOWN)*-ONE)) / TWO
            return (vDecimal - dd, vDecimal + dd)
    return (vDecimal, vDecimal)

def insignificantDigits(value, precision=None, decimals=None, scale=None):
    try:
        vDecimal = decimal.Decimal(value)
        if scale:
            iScale = int(scale)
            vDecimal = vDecimal.scaleb(iScale)
        if precision is not None:
            vFloat = float(value)
            if scale:
                vFloat = pow(vFloat, iScale)
    except (decimal.InvalidOperation, ValueError): # would have been a schema error reported earlier
        return None
    if precision is not None:
        if not isinstance(precision, (int,float)):
            if precision == "INF":
                return None
            else:
                try:
                    precision = int(precision)
                except ValueError: # would be a schema error
                    return None
        if isinf(precision) or precision == 0 or isnan(precision) or vFloat == 0: 
            return None
        else:
            vAbs = fabs(vFloat)
            log = log10(vAbs)
            decimals = precision - int(log) - (1 if vAbs >= 1 else 0)
    elif decimals is not None:
        if not isinstance(decimals, (int,float)):
            if decimals == "INF":
                return None
            else:
                try:
                    decimals = int(decimals)
                except ValueError: # would be a schema error
                    return None
        if isinf(decimals) or isnan(decimals):
            return None
    else:
        return None
    if vDecimal.is_normal() and -28 <= decimals <= 28: # prevent exception with excessive quantization digits
        if decimals > 0:
            divisor = ONE.scaleb(-decimals) # fractional scaling doesn't produce scientific notation
        else:  # extra quantize step to prevent scientific notation for decimal number
            divisor = ONE.scaleb(-decimals).quantize(ONE, decimal.ROUND_HALF_UP) # should never round
        insignificantDigits = abs(vDecimal) % divisor
        if insignificantDigits:
            return (vDecimal // divisor * divisor,  # truncated portion of number
                    insignificantDigits)   # nsignificant digits portion of number
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
                    
