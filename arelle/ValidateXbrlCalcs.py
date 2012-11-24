'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from math import (log10, isnan, isinf, fabs, trunc, fmod, floor)
import decimal
import re
from arelle import Locale, XbrlConst, XbrlUtil

numberPattern = re.compile("[-+]?[0]*([1-9]?[0-9]*)([.])?(0*)([1-9]?[0-9]*)?([eE])?([-+]?[0-9]*)?")
ZERO = decimal.Decimal(0)
ONE = decimal.Decimal(1)
NaN = decimal.Decimal("NaN")
floatNaN = float("NaN")
floatINF = float("INF")

def validate(modelXbrl, inferDecimals=False):
    ValidateXbrlCalcs(modelXbrl, inferDecimals).validate()
    
class ValidateXbrlCalcs:
    def __init__(self, modelXbrl, inferDecimals=False):
        self.modelXbrl = modelXbrl
        self.inferDecimals = inferDecimals
        self.mapContext = {}
        self.mapUnit = {}
        self.sumFacts = defaultdict(list)
        self.sumConceptBindKeys = defaultdict(set)
        self.itemFacts = defaultdict(list)
        self.itemConceptBindKeys = defaultdict(set)
        self.duplicateKeyFacts = {}
        self.duplicatedFacts = set()
        self.esAlFacts = defaultdict(list)
        self.esAlConceptBindKeys = defaultdict(set)
        self.conceptsInEssencesAlias = set()
        self.requiresElementFacts = defaultdict(list)
        self.conceptsInRequiresElement = set()
        
    def validate(self):
        if not self.modelXbrl.contexts and not self.modelXbrl.facts:
            return # skip if no contexts or facts
        
        if not self.inferDecimals: # infering precision is now contrary to XBRL REC section 5.2.5.2
            self.modelXbrl.info("xbrl.5.2.5.2:inferringPrecision","Validating calculations inferring precision.")
            
        # identify equal contexts
        self.modelXbrl.profileActivity()
        uniqueContextHashes = {}
        for context in self.modelXbrl.contexts.values():
            h = context.contextDimAwareHash
            if h in uniqueContextHashes:
                if context.isEqualTo(uniqueContextHashes[h]):
                    self.mapContext[context] = uniqueContextHashes[h]
            else:
                uniqueContextHashes[h] = context
        del uniqueContextHashes
        self.modelXbrl.profileActivity("... identify equal contexts", minTimeToShow=1.0)

        # identify equal contexts
        uniqueUnitHashes = {}
        for unit in self.modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    self.mapUnit[unit] = uniqueUnitHashes[h]
            else:
                uniqueUnitHashes[h] = unit
        self.modelXbrl.profileActivity("... identify equal units", minTimeToShow=1.0)
                    
        # identify concepts participating in essence-alias relationships
        # identify calcluation & essence-alias base sets (by key)
        for baseSetKey in self.modelXbrl.baseSets.keys():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if ELR and linkqname and arcqname:
                if arcrole in (XbrlConst.essenceAlias, XbrlConst.requiresElement):
                    conceptsSet = {XbrlConst.essenceAlias:self.conceptsInEssencesAlias,
                                   XbrlConst.requiresElement:self.conceptsInRequiresElement}[arcrole]
                    for modelRel in self.modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname).modelRelationships:
                        for concept in (modelRel.fromModelObject, modelRel.toModelObject):
                            conceptsSet.add(concept)
        self.modelXbrl.profileActivity("... identify requires-element and esseance-aliased concepts", minTimeToShow=1.0)

        self.bindFacts(self.modelXbrl.facts,[self.modelXbrl.modelDocument.xmlRootElement])
        self.modelXbrl.profileActivity("... bind facts", minTimeToShow=1.0)
        
        # identify calcluation & essence-alias base sets (by key)
        for baseSetKey in self.modelXbrl.baseSets.keys():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if ELR and linkqname and arcqname:
                if arcrole in (XbrlConst.summationItem, XbrlConst.essenceAlias, XbrlConst.requiresElement):
                    relsSet = self.modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname)
                    if arcrole == XbrlConst.summationItem:
                        fromRelationships = relsSet.fromModelObjects()
                        for sumConcept, modelRels in fromRelationships.items():
                            sumBindingKeys = self.sumConceptBindKeys[sumConcept]
                            dupBindingKeys = set()
                            boundSumKeys = set()
                            # determine boundSums
                            for modelRel in modelRels:
                                itemBindingKeys = self.itemConceptBindKeys[modelRel.toModelObject]
                                boundSumKeys |= sumBindingKeys & itemBindingKeys
                            # add up rounded items
                            boundSums = defaultdict(decimal.Decimal) # sum of facts meeting factKey
                            boundSummationItems = defaultdict(list) # corresponding fact refs for messages
                            for modelRel in modelRels:
                                weight = modelRel.weightDecimal
                                itemConcept = modelRel.toModelObject
                                for itemBindKey in boundSumKeys:
                                    ancestor, contextHash, unit = itemBindKey
                                    factKey = (itemConcept, ancestor, contextHash, unit)
                                    if factKey in self.itemFacts:
                                        for fact in self.itemFacts[factKey]:
                                            if fact in self.duplicatedFacts:
                                                dupBindingKeys.add(itemBindKey)
                                            else:
                                                boundSums[itemBindKey] += roundFact(fact, self.inferDecimals) * weight
                                                boundSummationItems[itemBindKey].append(fact)
                            for sumBindKey in boundSumKeys:
                                ancestor, contextHash, unit = sumBindKey
                                factKey = (sumConcept, ancestor, contextHash, unit)
                                if factKey in self.sumFacts:
                                    sumFacts = self.sumFacts[factKey]
                                    for fact in sumFacts:
                                        if fact in self.duplicatedFacts:
                                            dupBindingKeys.add(sumBindKey)
                                        elif sumBindKey not in dupBindingKeys:
                                            roundedSum = roundFact(fact, self.inferDecimals)
                                            roundedItemsSum = roundFact(fact, self.inferDecimals, vDecimal=boundSums[sumBindKey])
                                            if roundedItemsSum  != roundFact(fact, self.inferDecimals):
                                                d = inferredDecimals(fact)
                                                if isnan(d) or isinf(d): d = 4
                                                self.modelXbrl.log('INCONSISTENCY', "xbrl.5.2.5.2:calcInconsistency",
                                                    _("Calculation inconsistent from %(concept)s in link role %(linkrole)s reported sum %(reportedSum)s computed sum %(computedSum)s context %(contextID)s unit %(unitID)s"),
                                                    modelObject=[fact] + boundSummationItems[sumBindKey], 
                                                    concept=sumConcept.qname, linkrole=ELR, 
                                                    reportedSum=Locale.format_decimal(self.modelXbrl.locale, roundedSum, 1, max(d,0)),
                                                    computedSum=Locale.format_decimal(self.modelXbrl.locale, roundedItemsSum, 1, max(d,0)), 
                                                    contextID=context.id, unitID=unit.id)
                            boundSummationItems.clear() # dereference facts in list
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
                                                self.modelXbrl.log('INCONSISTENCY', "xbrl.5.2.6.2.2:essenceAliasUnitsInconsistency",
                                                    _("Essence-Alias inconsistent units from %(essenceConcept)s to %(aliasConcept)s in link role %(linkrole)s context %(contextID)s"),
                                                    modelObject=(modelRel, eF, aF), 
                                                    essenceConcept=essenceConcept.qname, aliasConcept=aliasConcept.qname, 
                                                    linkrole=ELR, contextID=context.id)
                                            if not XbrlUtil.vEqual(eF, aF):
                                                self.modelXbrl.log('INCONSISTENCY', "xbrl.5.2.6.2.2:essenceAliasUnitsInconsistency",
                                                    _("Essence-Alias inconsistent value from %(essenceConcept)s to %(aliasConcept)s in link role %(linkrole)s context %(contextID)s"),
                                                    modelObject=(modelRel, eF, aF), 
                                                    essenceConcept=essenceConcept.qname, aliasConcept=aliasConcept.qname, 
                                                    linkrole=ELR, contextID=context.id)
                    elif arcrole == XbrlConst.requiresElement:
                        for modelRel in relsSet.modelRelationships:
                            sourceConcept = modelRel.fromModelObject
                            requiredConcept = modelRel.toModelObject
                            if sourceConcept in self.requiresElementFacts and \
                               not requiredConcept in self.requiresElementFacts:
                                    self.modelXbrl.log('INCONSISTENCY', "xbrl.5.2.6.2.4:requiresElementInconsistency",
                                        _("Requires-Element %(requiringConcept)s missing required fact for %(requiredConcept)s in link role %(linkrole)s"),
                                        modelObject=sourceConcept, 
                                        requiringConcept=sourceConcept.qname, requiredConcept=requiredConcept.qname, 
                                        linkrole=ELR)
        self.modelXbrl.profileActivity("... find inconsistencies", minTimeToShow=1.0)
        self.modelXbrl.profileActivity() # reset
    
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
                        if not f.isNil:
                            self.itemFacts[calcKey].append(f)
                            bindKey = (ancestor, contextHash, unit)
                            self.itemConceptBindKeys[concept].add(bindKey)
                    if not f.isNil:
                        self.sumFacts[calcKey].append(f) # sum only for immediate parent
                        self.sumConceptBindKeys[concept].add(bindKey)
                    # calcKey is the last ancestor added (immediate parent of fact)
                    if calcKey in self.duplicateKeyFacts:
                        self.duplicatedFacts.add(f)
                        self.duplicatedFacts.add(self.duplicateKeyFacts[calcKey])
                    else:
                        self.duplicateKeyFacts[calcKey] = f
                elif concept.isTuple:
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
        else:
            d = int(dStr)
            # defeat binary rounding to nearest even
            #if trunc(fmod(vFloat * (10 ** d),2)) != 0:
            #    vFloat += 10 ** (-d - 1) * (-1.0 if vFloat > 0 else 1.0)
            #vRounded = round(vFloat, d)
            #vRounded = round(vFloat,d)
            vRounded = decimalRound(vDecimal,d,decimal.ROUND_HALF_EVEN)
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
        else:
            p = int(pStr)
        if p == 0:
            vRounded = NaN
        elif vDecimal == 0:
            vRounded = vDecimal
        else:  # round per 4.6.7.1, half-up
            vAbs = vDecimal.copy_abs()
            log = vAbs.log10()
            # defeat rounding to nearest even
            d = p - int(log) - (1 if vAbs >= 1 else 0)
            #if trunc(fmod(vFloat * (10 ** d),2)) != 0:
            #    vFloat += 10 ** (-d - 1) * (1.0 if vFloat > 0 else -1.0)
            #vRounded = round(vFloat, d)
            vRounded = decimalRound(vDecimal,d,decimal.ROUND_HALF_UP)
    return vRounded
    
def decimalRound(x, d, rounding):
    if x.is_normal():
        if d >= 0:
            return x.quantize(ONE.scaleb(-d),rounding)
        else: # quantize only seems to work on fractional part, convert integer to fraction at scaled point    
            return x.scaleb(d).quantize(ONE,rounding).scaleb(-d)
    return x # infinite, NaN, or zero

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
    
def roundValue(value, precision=None, decimals=None):
    try:
        vDecimal = decimal.Decimal(value)
        if precision:
            vFloat = float(value)
    except (decimal.InvalidOperation, ValueError): # would have been a schema error reported earlier
        return NaN
    if precision:
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
    elif decimals:
        if isinf(decimals):
            vRounded = vDecimal
        elif isnan(decimals):
            vRounded = NaN
        else:
            vRounded = decimalRound(vDecimal,decimals,decimal.ROUND_HALF_EVEN)
    else:
        vRounded = vDecimal
    return vRounded

