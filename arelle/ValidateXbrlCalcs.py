'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from math import (log10, isnan, isinf, fabs, trunc, fmod, floor)
import re
from arelle import (XbrlConst, XbrlUtil)

numberPattern = re.compile("[-]?[0]*([1-9]?[0-9]*)([.])?(0*)([1-9]?[0-9]*)?([eE])?([-]?[0-9]*)?")

def validate(modelXbrl, inferPrecision=True):
    ValidateXbrlCalcs(modelXbrl, inferPrecision).validate()
    
class ValidateXbrlCalcs:
    def __init__(self, modelXbrl, inferPrecision=True):
        self.modelXbrl = modelXbrl
        self.inferPrecision = inferPrecision
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
        self.modelXbrl.info("info","Validating calculations inferring %(inferMode)s",
                            inferMode=_("precision") if self.inferPrecision else _("decimals"))

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
                            boundSums = defaultdict(float)
                            for modelRel in modelRels:
                                weight = modelRel.weight
                                itemConcept = modelRel.toModelObject
                                for itemBindKey in boundSumKeys:
                                    ancestor, context, unit = itemBindKey
                                    factKey = (itemConcept, ancestor, context, unit)
                                    if factKey in self.itemFacts:
                                        for fact in self.itemFacts[factKey]:
                                            if fact in self.duplicatedFacts:
                                                dupBindingKeys.add(itemBindKey)
                                            else:
                                                boundSums[itemBindKey] += self.roundFact(fact) * weight
                            for sumBindKey in boundSumKeys:
                                ancestor, context, unit = sumBindKey
                                factKey = (sumConcept, ancestor, context, unit)
                                if factKey in self.sumFacts:
                                    for fact in self.sumFacts[factKey]:
                                        if fact in self.duplicatedFacts:
                                            dupBindingKeys.add(sumBindKey)
                                        elif sumBindKey not in dupBindingKeys:
                                            roundedSum = self.roundFact(fact)
                                            roundedItemsSum = self.roundFact(fact, vFloat=boundSums[sumBindKey])
                                            if roundedItemsSum  != self.roundFact(fact):
                                                self.modelXbrl.error("xbrl.5.2.5.2:calcInconsistency",
                                                    _("Calculation inconsistent from %(concept)s in link role %(linkrole)s reported sum %(reportedSum)s computed sum %(computedSum)s context %(contextID)s unit %(unitID)s"),
                                                    modelObject=sumConcept, concept=sumConcept.qname, linkrole=ELR, 
                                                    reportedSum=roundedSum, computedSum=roundedItemsSum, 
                                                    contextID=context.id, unitID=unit.id)
                    elif arcrole == XbrlConst.essenceAlias:
                        for modelRel in relsSet.modelRelationships:
                            essenceConcept = modelRel.fromModelObject
                            aliasConcept = modelRel.toModelObject
                            essenceBindingKeys = self.esAlConceptBindKeys[essenceConcept]
                            aliasBindingKeys = self.esAlConceptBindKeys[aliasConcept]
                            for esAlBindKey in essenceBindingKeys & aliasBindingKeys:
                                ancestor, context = esAlBindKey
                                essenceFactsKey = (essenceConcept, ancestor, context)
                                aliasFactsKey = (aliasConcept, ancestor, context)
                                if essenceFactsKey in self.esAlFacts and aliasFactsKey in self.esAlFacts:
                                    for eF in self.esAlFacts[essenceFactsKey]:
                                        for aF in self.esAlFacts[aliasFactsKey]:
                                            essenceUnit = self.mapUnit.get(eF.unit,eF.unit)
                                            aliasUnit = self.mapUnit.get(aF.unit,aF.unit)
                                            if essenceUnit != aliasUnit:
                                                self.modelXbrl.error("xbrl.5.2.6.2.2:essenceAliasUnitsInconsistency",
                                                    _("Essence-Alias inconsistent units from %(essenceConcept)s to %(aliasConcept)s in link role %(linkrole)s context %(contextID)s"),
                                                    modelObject=essenceConcept, 
                                                    essenceConcept=essenceConcept.qname, aliasConcept=aliasConcept.qname, 
                                                    linkrole=ELR, contextID=context.id)
                                            if not XbrlUtil.vEqual(eF, aF):
                                                self.modelXbrl.error("xbrl.5.2.6.2.2:essenceAliasUnitsInconsistency",
                                                    _("Essence-Alias inconsistent value from %(essenceConcept)s to %(aliasConcept)s in link role %(linkrole)s context %(contextID)s"),
                                                    modelObject=essenceConcept, 
                                                    essenceConcept=essenceConcept.qname, aliasConcept=aliasConcept.qname, 
                                                    linkrole=ELR, contextID=context.id)
                    elif arcrole == XbrlConst.requiresElement:
                        for modelRel in relsSet.modelRelationships:
                            sourceConcept = modelRel.fromModelObject
                            requiredConcept = modelRel.toModelObject
                            if sourceConcept in self.requiresElementFacts and \
                               not requiredConcept in self.requiresElementFacts:
                                    self.modelXbrl.error("xbrl.5.2.6.2.4:requiresElementInconsistency",
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
                        unit = self.mapUnit.get(f.unit,f.unit)
                        calcKey = (concept, ancestor, context, unit)
                        if not f.isNil:
                            self.itemFacts[calcKey].append(f)
                            bindKey = (ancestor, context, unit)
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
                    esAlKey = (concept, ancestor, context)
                    self.esAlFacts[esAlKey].append(f)
                    bindKey = (ancestor, context)
                    self.esAlConceptBindKeys[concept].add(bindKey)
                # index facts by their requires element usage
                if concept in self.conceptsInRequiresElement:
                    self.requiresElementFacts[concept].append(f)

    def roundFact(self, fact, vFloat=None):
        if vFloat is None:
            vStr = fact.value
            vFloat = float(vStr)
            vFloatFact = vFloat
        else: #only vFloat is defined, may not need vStr unless inferring precision from decimals
            if isnan(vFloat):
                return vFloat
            vStr = None
            vFloatFact = float(fact.value)
        dStr = fact.decimals
        pStr = fact.precision
        if dStr == "INF" or pStr == "INF":
            vRounded = vFloat
        elif self.inferPrecision:
            if dStr:
                match = numberPattern.match(vStr if vStr else str(vFloat))
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
                vRounded = float("NaN")
            elif vFloat == 0:
                vRounded = 0
            else:
                vAbs = fabs(vFloat)
                log = log10(vAbs)
                # defeat rounding to nearest even
                if trunc(fmod(vFloat,2)) == 0:
                    vFloat += 10 ** (log - p - 1) * (1.0 if vFloat > 0 else -1.0)
                vRounded = round(vFloat, p - int(log) - (1 if vAbs >= 1 else 0))
        else: #infer decimals
            if pStr:
                p = int(pStr)
                if p == 0:
                    vRounded = float("NaN")
                elif vFloat == 0:
                    vRounded = 0
                else:
                    vAbs = fabs(vFloatFact)
                    d = p - int(floor(log10(vAbs))) - 1
                    # defeat rounding to nearest even
                    if trunc(fmod(vFloat,2)) == 0:
                        vFloat += 10 ** (-d - 1) * (1.0 if vFloat > 0 else -1.0)
                    vRounded = round(vFloat, d)
            else:
                d = int(dStr)
                # defeat rounding to nearest even
                if trunc(fmod(vFloat,2)) == 0:
                    vFloat += 10 ** (-d - 1) * (1.0 if vFloat > 0 else -1.0)
                vRounded = round(vFloat, d)
        return vRounded

def inferredPrecision(fact):
    vStr = fact.value
    vFloat = float(vStr)
    dStr = fact.decimals
    pStr = fact.precision
    if dStr == "INF" or pStr == "INF":
        return float("INF")
    try:
        if dStr:
            match = numberPattern.match(vStr if vStr else str(vFloat))
            if match:
                nonZeroInt, period, zeroDec, nonZeroDec, e, exp = match.groups()
                p = (len(nonZeroInt) if nonZeroInt and (len(nonZeroInt)) > 0 else -len(zeroDec)) + \
                    (int(exp) if exp and (len(exp) > 0) else 0) + \
                    (int(dStr))
                if p < 0:
                    p = 0 # "pathological case" 2.1 spec example 13 line 7
            else:
                p = 0
        else:
            return int(pStr)
    except ValueError:
        return float("NaN")
    if p == 0:
        return 0
    elif vFloat == 0:
        return 0
    else:
        return p
    
def inferredDecimals(fact):
    vStr = fact.value
    vFloat = float(vStr)
    dStr = fact.decimals
    pStr = fact.precision
    if dStr == "INF" or pStr == "INF":
        return float("INF")
    try:
        if pStr:
            p = int(pStr)
            if p == 0:
                return float("NaN") # =0 cannot be determined
            if vFloat == 0:
                return float("INF") # =0 cannot be determined
            else:
                vAbs = fabs(vFloat)
                return p - int(floor(log10(vAbs))) - 1
        elif dStr:
            return int(dStr)
    except ValueError:
        pass
    return float("NaN")
    
def roundValue(vFloat, precision=None, decimals=None):
    if precision:
        if isinf(precision):
            vRounded = vFloat
        elif precision == 0:
            vRounded = float("NaN")
        elif vFloat == 0:
            vRounded = 0
        else:
            vAbs = fabs(vFloat)
            log = log10(vAbs)
            # defeat rounding to nearest even
            if trunc(fmod(vFloat,2)) == 0:
                vFloat += 10 ** (log - precision - 1) * (1.0 if vFloat > 0 else -1.0)
            vRounded = round(vFloat, precision - int(log) - (1 if vAbs >= 1 else 0))
    elif decimals:
        vRounded = round(vFloat, decimals)
    else:
        vRounded = vFloat
    return vRounded

