'''
Created on Jan 8, 2019

@author: Mark V Systems Limited
(c) Copyright 2019 Mark V Systems Limited, All rights reserved.
'''

import time
from math import isnan, isinf
from collections import defaultdict
from decimal import Decimal
from arelle import Locale
from arelle.PythonUtil import OrderedDefaultDict
from arelle.ValidateXbrlCalcs import ZERO, inferredDecimals, rangeValue
from arelle.XbrlConst import link, xbrli, xl, xlink

calc2YYYY = "http://xbrl.org/WGWD/YYYY-MM-DD/calculation-2.0"
calc2 = {calc2YYYY}
calc2e = "http://xbrl.org/WGWD/YYYY-MM-DD/calculation-2.0/error"
sectionFact = "http://xbrl.org/arcrole/WGWD/YYYY-MM-DD/section-fact"
calc2linkroles = "{http://xbrl.org/WGWD/YYYY-MM-DD/calculation-2.0}linkroles"
summationItem = "http://xbrl.org/arcrole/WGWD/YYYY-MM-DD/summation-item" # calc2 summation-item arc role
balanceChanges = "http://xbrl.org/arcrole/WGWD/YYYY-MM-DD/balance-changes"
aggregationDomain = "http://xbrl.org/arcrole/WGWD/YYYY-MM-DD/aggregation-domain"
calc2Arcroles = (summationItem, balanceChanges, aggregationDomain)

def nominalPeriod(duration): # account for month and year lengths
    if 364 < duration.days <= 366: return 365
    if 28 <= duration.days <= 31: return 31
    return duration.days

def intervalZero():
    return (Decimal(0), Decimal(0))

def intervalValue(fact, dec=None): # value in decimals
    if dec is None:
        dec = inferredDecimals(fact)
    return rangeValue(fact.value, dec)

class ValidateXbrlCalc2:
    def __init__(self, val):
        self.val = val
        self.cntlr = val.modelXbrl.modelManager.cntlr
        self.modelXbrl = val.modelXbrl
        self.standardTaxonomiesDict = val.disclosureSystem.standardTaxonomiesDict
        self.eqCntx = {} # contexts which are OIM-aspect equivalent 
        self.eqUnit = {} # units which are equivalent
        self.sumInitArcrole = self.perBindArcrole = self.aggBindArcrole = None
        self.sumConceptBindKeys = defaultdict(set)
        self.sumBoundFacts = defaultdict(list)
        self.perConceptBindKeys = defaultdict(set)
        self.perBoundFacts = defaultdict(list)
        self.durationPeriodStarts = defaultdict(set)
        self.aggBindKeys = set()
        self.aggBoundFacts = {}

    
    def validate(self):
        modelXbrl = self.modelXbrl
        if not modelXbrl.contexts or not modelXbrl.facts:
            return # skip if no contexts or facts
        
        if not self.val.validateInferDecimals: # infering precision is now contrary to XBRL REC section 5.2.5.2
            modelXbrl.error("calc2e:inferringPrecision","Calc2 requires inferring decimals.")
            return

        startedAt = time.time()
    
        # check balance attributes and weights, same as XBRL 2.1
        for rel in modelXbrl.relationshipSet(calc2Arcroles).modelRelationships:
            weight = rel.weight
            fromConcept = rel.fromModelObject
            toConcept = rel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if rel.arcrole == aggregationDomain:
                    rel.dimension = rel.arcElement.prefixedNameQname(rel.get("dimension"))
                    if rel.dimension is None or not modelXbrl.qnameConcepts[rel.dimension].isDimensionItem:
                        modelXbrl.error("calc2e:invalidAggregationDimension",
                            _("Aggregation-domain relationship has invalid dimension %(dimension)s in link role %(linkrole)s"),
                            modelObject=rel,
                            dimension=rel.get("dimension"), linkrole=ELR)
                    elif fromConcept != toConcept or not fromConcept.isDomainMember:
                        modelXbrl.error("calc2e:invalidAggregationDomain",
                            _("Calculation relationship has invalid domain %(domain)s in link role %(linkrole)s"),
                            modelObject=rel,
                            domain=fromConcept, linkrole=ELR)
                    continue
                if rel.arcrole == balanceChanges:
                    if fromConcept.periodType != "instant" or toConcept.periodType != "duration":
                        modelXbrl.error("calc2e:invalidBalanceChangesPeriodType",
                            _("Balance-changes relationship must have instant source concept and duration target concept in link role %(linkrole)s"),
                            modelObject=rel, linkrole=ELR)
                if weight not in (1, -1):
                    modelXbrl.error("calc2e:invalidWeight",
                        _("Calculation relationship has invalid weight from %(source)s to %(target)s in link role %(linkrole)s"),
                        modelObject=rel,
                        source=fromConcept.qname, target=toConcept.qname, linkrole=ELR) 
                fromBalance = fromConcept.balance
                toBalance = toConcept.balance
                if fromBalance and toBalance:
                    if (fromBalance == toBalance and weight < 0) or \
                       (fromBalance != toBalance and weight > 0):
                        modelXbrl.error("calc2e:balanceCalcWeightIllegal" +
                                        ("Negative" if weight < 0 else "Positive"),
                            _("Calculation relationship has illegal weight %(weight)s from %(source)s, %(sourceBalance)s, to %(target)s, %(targetBalance)s, in link role %(linkrole)s (per 5.1.1.2 Table 6)"),
                            modelObject=rel, weight=weight,
                            source=fromConcept.qname, target=toConcept.qname, linkrole=rel.linkrole, 
                            sourceBalance=fromBalance, targetBalance=toBalance,
                            messageCodes=("calc2e:    ", "calc2:balanceCalcWeightIllegalPositive"))
                if not fromConcept.isNumeric or not toConcept.isNumeric:
                    modelXbrl.error("calc2e:nonNumericCalc",
                        _("Calculation relationship has illegal concept from %(source)s%(sourceNumericDecorator)s to %(target)s%(targetNumericDecorator)s in link role %(linkrole)s"),
                        modelObject=rel,
                        source=fromConcept.qname, target=toConcept.qname, linkrole=rel.linkrole, 
                        sourceNumericDecorator="" if fromConcept.isNumeric else _(" (non-numeric)"), 
                        targetNumericDecorator="" if toConcept.isNumeric else _(" (non-numeric)"))    
                            
        # identify equal contexts
        uniqueCntxHashes = {}
        self.modelXbrl.profileActivity()
        for cntx in modelXbrl.contexts.values():
            h = hash( (cntx.periodHash, cntx.entityIdentifierHash, cntx.dimsHash) ) # OIM-compatible hash
            if h in uniqueCntxHashes:
                if cntx.isEqualTo(uniqueCntxHashes[h]):
                    self.eqCntx[cntx] = uniqueCntxHashes[h]
            else:
                uniqueCntxHashes[h] = cntx
        del uniqueCntxHashes
        self.modelXbrl.profileActivity("... identify aspect equal contexts", minTimeToShow=1.0)
    
        # identify equal units
        uniqueUnitHashes = {}
        for unit in self.modelXbrl.units.values():
            h = unit.hash
            if h in uniqueUnitHashes:
                if unit.isEqualTo(uniqueUnitHashes[h]):
                    self.eqUnit[unit] = uniqueUnitHashes[h]
            else:
                uniqueUnitHashes[h] = unit
        del uniqueUnitHashes
        self.modelXbrl.profileActivity("... identify equal units", minTimeToShow=1.0)
                    
                    
        sectObjs = sorted(set(rel.fromModelObject # only have numerics with context and unit
                              for rel in modelXbrl.relationshipSet(sectionFact).modelRelationships
                              if rel.fromModelObject is not None and rel.fromModelObject.concept is not None),
                          key=lambda s: (s.concept.label(), s.objectIndex))  # sort into document order for consistent error messages
        if not sectObjs:
            self.modelXbrl.error("calc2e:noSections",
                            "Instance contains no sections, nothing to validate.",
                            modelObject=modelXbrl)
    
        # check by section
        factByConceptCntxUnit = OrderedDefaultDict(list)  # sort into document order for consistent error messages
        self.sectionFacts = []
        for sectObj in sectObjs:
            print ("section {}".format(sectObj.concept.label())) 
            self.section = sectObj.concept.label()
            sectLinkRoles = tuple(sectObj.concept.get(calc2linkroles,"").split())
            factByConceptCntxUnit.clear()
            for f in sorted((rel.toModelObject # sort into document order for consistent error messages
                             for rel in modelXbrl.relationshipSet(sectionFact,sectLinkRoles).fromModelObject(sectObj)
                             if rel.toModelObject is not None and # numeric facts with context and unit
                                rel.fromModelObject is not None and
                                rel.toModelObject.concept is not None and
                                rel.toModelObject.context is not None and
                                rel.toModelObject.unit is not None),
                            key=lambda f: f.objectIndex):
                factByConceptCntxUnit[f.qname, self.eqCntx.get(f.context,f.context), self.eqUnit.get(f.unit,f.unit)].append(f)
            for fList in factByConceptCntxUnit.values():
                f0 = fList[0]
                if len(fList) == 1:
                    self.sectionFacts.append(f0)
                else:
                    if any(f.isNil for f in fList):
                        _inConsistent = not all(f.isNil for f in fList)
                    elif all(inferredDecimals(f) == inferredDecimals(f0) for f in fList[1:]): # same decimals
                        v0 = intervalValue(f0)
                        _inConsistent = not all(intervalValue(f) == v0 for f in fList[1:])
                    else: # not all have same decimals
                        d0 = inferredDecimals(f0)
                        aMax, bMin = intervalValue(f0, d0)
                        for f in fList[1:]:
                            df = inferredDecimals(f0)
                            a, b = intervalValue(f, df)
                            if a > aMax: aMax = a
                            if b < bMin: bMin = b
                            if df > d0: # take most accurate fact in section
                                f0 = f
                                d0 = df
                        _inConsistent = (bMin < aMax)
                    if _inConsistent:
                        modelXbrl.error("calc2e:inconsistentDuplicateInSection",
                            "Section %(section)s contained %(fact)s inconsistent in contexts equivalent to %(contextID)s: values %(values)s",
                            modelObject=fList, section=sectObj.concept.label(), fact=f0.qname, contextID=f0.contextID, values=", ".join(strTruncate(f.value, 128) for f in fList))
                    self.sectionFacts.append(f0)
            # sectionFacts now in document order and deduplicated
            print("section {} facts {}".format(sectObj.concept.label(), ", ".join(str(f.qname)+"="+f.value for f in self.sectionFacts)))
            
            # depth-first calc tree
            sectCalc2RelSet = modelXbrl.relationshipSet(calc2Arcroles, sectLinkRoles)
            
            # indexers for section based on calc2 arcrole
            self.sumInit = False
            self.sumConceptBindKeys.clear()
            self.sumBoundFacts.clear()
            self.perInit = False
            self.perConceptBindKeys.clear()
            self.perBoundFacts.clear()
            self.durationPeriodStarts.clear()
            self.aggInit = False
            self.aggBindKeys.clear()
            self.aggBoundFacts.clear()
            

            for rootConcept in sectCalc2RelSet.rootConcepts:
                self.sectTreeRel(rootConcept, 1, sectCalc2RelSet, None, {rootConcept, None})

    # recursive depth-first tree descender, returns sum
    def sectTreeRel(self, parentConcept, n, sectCalc2RelSet, inferredParentValues, visited,
                    dimension=None):
        childRels = sectCalc2RelSet.fromModelObject(parentConcept)
        if childRels:
            visited.add(parentConcept)
            inferredChildValues = {}
            
            # setup summation bind keys for child objects
            sumParentBindKeys = self.sumConceptBindKeys[parentConcept]
            boundSumKeys = set() # these are contributing fact keys, parent may be inferred
            boundSums = defaultdict(intervalZero)
            boundSummationItems = defaultdict(list)
            boundPerKeys = set() 
            boundPers = defaultdict(intervalZero)
            boundDurationItems = defaultdict(list)
            for rel in childRels:
                childConcept = rel.toModelObject
                if childConcept not in visited:
                    if rel.arcrole == summationItem: 
                        if not self.sumInit:
                            self.sumBindFacts()
                        boundSumKeys |= self.sumConceptBindKeys[childConcept]
                    elif rel.arcrole == balanceChanges: 
                        if not self.perInit:
                            self.perBindFacts()
                        boundPerKeys |= self.perConceptBindKeys[childConcept] # these are only duration items
                    elif rel.arcrole == aggregationDomain:
                        dimension = rel.arcElement.prefixedNameQname(rel.get("dimension"))
                        if not self.aggInit: 
                            for dim in set(rel.dimension for rel in sectCalc2RelSet.modelRelationships if rel.arcrole == aggregationDomain):
                                self.aggBindFacts(dim) # bind each referenced dimension's contexts
                            self.aggInit = True
                    
            # depth-first descent calc tree and process item after descent        
            for rel in childRels:
                childConcept = rel.toModelObject
                if childConcept not in visited:
                    # depth-first descent
                    if rel.arcrole == aggregationDomain:
                        dimObj = self.modelXbrl.qnameConcepts[rel.dimension]
                        childRelSet = modelXbrl.relationshipSet(dimensionDomain,rel.get("targetRole")).fromModelObject(dimObj)
                    else:
                        childRelSet = sectCalc2RelSet
                    self.sectTreeRel(childConcept, n+1, childRelSet, inferredChildValues,  visited, dimension)
                    # post-descent summation (allows use of inferred value)
                    if rel.arcrole == summationItem: 
                        weight = rel.weightDecimal
                        for sumKey in boundSumKeys:
                            cntx, unit = sumKey
                            factKey = (childConcept, cntx, unit)
                            if factKey in self.sumBoundFacts:
                                for f in self.sumBoundFacts[factKey]:
                                    a, b = intervalValue(f)
                                    r = boundSums[sumKey]
                                    boundSums[sumKey] = (r[0] + weight * a, r[1] + weight * b)
                                    boundSummationItems[sumKey].append(f)
                            elif factKey in inferredChildValues:
                                a, b = inferredChildValues[factKey]
                                r = boundSums[sumKey]
                                boundSums[sumKey] = (r[0] + weight * a, r[1] + weight * b)
                    elif rel.arcrole == balanceChanges: 
                        weight = rel.weightDecimal
                        for perKey in boundPerKeys:
                            hCntx, unit, start, end = perKey
                            factKey = (childConcept, hCntx, unit, start, end)
                            if factKey in self.perBoundFacts:
                                for f in self.perBoundFacts[factKey]:
                                    a, b = intervalValue(f)
                                    r = boundPers[perKey]
                                    boundPers[perKey] = (r[0] + weight * a, r[1] + weight * b)
                                    boundDurationItems[perKey].append(f)
                            elif factKey in inferredChildValues:
                                a, b = inferredChildValues[factKey]
                                r = boundPers[perKey]
                                boundPers[perKey] = (r[0] + weight * a, r[1] + weight * b)
                    elif rel.arcrole == aggregationDomain:
                        pass
                        
            # process child items bound to this calc subtree
            for sumKey in boundSumKeys:
                cntx, unit = sumKey
                factKey = (parentConcept, cntx, unit)
                ia, ib = boundSums[sumKey]
                if factKey in self.sumBoundFacts:
                    for f in self.sumBoundFacts[factKey]:
                        d = inferredDecimals(f)
                        sa, sb = intervalValue(f, d)
                        if sb < ia or sa > ib:
                            self.modelXbrl.log('INCONSISTENCY', "calc2e:summationInconsistency",
                                _("Summation inconsistent from %(concept)s in section %(section)s reported sum %(reportedSum)s, computed sum %(computedSum)s context %(contextID)s unit %(unitID)s unreportedContributingItems %(unreportedContributors)s"),
                                modelObject=boundSummationItems[sumKey],
                                concept=parentConcept.qname, section=self.section, 
                                reportedSum=self.formatInterval(sa, sb, d),
                                computedSum=self.formatInterval(ia, ib, d), 
                                contextID=f.context.id, unitID=f.unit.id,
                                unreportedContributors=", ".join(str(c.qname) # list the missing/unreported contributors in relationship order
                                                                 for r in childRels
                                                                 for c in (rel.toModelObject,)
                                                                 if r.arcrole == summationItem and c is not None and
                                                                 (c, cntx, unit) not in self.sumBoundFacts)
                                                         or "none")
                elif inferredParentValues is not None: # value was inferred, return to parent level
                    inferredParentValues[factKey] = (ia, ib)
            for perKey in boundPerKeys:
                hCntx, unit, start, end = perKey
                ia, ib = boundPers[perKey]
                endBalA = endBalB = ZERO
                endFactKey = (parentConcept, hCntx, unit, None, end)
                if endFactKey in self.perBoundFacts:
                    for f in self.perBoundFacts[endFactKey]:
                        d = inferredDecimals(f)
                        a, b = intervalValue(f,d)
                        endBalA += a
                        endBalB += b
                    foundStartingFact = False
                    while not foundStartingFact:
                        startFactKey = (parentConcept, hCntx, unit, None, start)
                        if startFactKey in self.perBoundFacts:
                            for f in self.perBoundFacts[startFactKey]:
                                a, b = intervalValue(f)
                                endBalA -= a
                                endBalB -= b
                                foundStartingFact = True
                                break
                        if not foundStartingFact:
                            # infer backing up one period
                            _nomPer = nominalPeriod(end - start)
                            foundEarlierAdjacentPeriodStart = False
                            for _start in self.durationPeriodStarts.get(_nomPer, ()):
                                if nominalPeriod(start - _start) == _nomPer: # it's preceding period
                                    end = start
                                    start = _start
                                    perKey = hCntx, unit, start, end
                                    if perKey in boundPerKeys:
                                        chngs = boundPers[perKey]
                                        ia += chngs[0]
                                        ib += chngs[1]
                                        foundEarlierAdjacentPeriodStart = True
                                        break
                            if not foundEarlierAdjacentPeriodStart:
                                break

                    if endBalB < ia or endBalA > ib:
                        self.modelXbrl.log('INCONSISTENCY', "calc2e:balanceInconsistency",
                            _("Balance inconsistent from %(concept)s in section %(section)s reported sum %(reportedSum)s, computed sum %(computedSum)s context %(contextID)s unit %(unitID)s unreportedContributingItems %(unreportedContributors)s"),
                            modelObject=boundDurationItems[perKey],
                            concept=parentConcept.qname, section=self.section, 
                            reportedSum=self.formatInterval(endBalA, endBalB, d),
                            computedSum=self.formatInterval(ia, ib, d), 
                            contextID=f.context.id, unitID=f.unit.id,
                            unreportedContributors=", ".join(str(c.qname) # list the missing/unreported contributors in relationship order
                                                             for r in childRels
                                                             for c in (rel.toModelObject,)
                                                             if r.arcrole == balanceChanges and c is not None and
                                                             (c, hCntx, unit, start, end) not in self.perBoundFacts)
                                                     or "none")
            visited.remove(parentConcept)
            
    def sumBindFacts(self):
        # bind facts in section for summation-item
        for f in self.sectionFacts:
            concept = f.concept
            if concept.isNumeric and not f.isNil:
                cntx = self.eqCntx.get(f.context,f.context)
                unit = self.eqUnit.get(f.unit,f.unit)
                self.sumConceptBindKeys[concept].add( (cntx,unit) )
                self.sumBoundFacts[concept, cntx, unit].append(f)
        self.sumInit = True
                
    def perBindFacts(self):
        # bind facts in section for domain aggreggation
        for f in self.sectionFacts:
            concept = f.concept
            if concept.isNumeric and not f.isNil:
                cntx = self.eqCntx.get(f.context,f.context)
                if not cntx.isForeverPeriod:
                    hCntx = hash( (cntx.entityIdentifierHash, cntx.dimsHash) )
                    unit = self.eqUnit.get(f.unit,f.unit)
                    self.perConceptBindKeys[concept].add( (hCntx, unit, cntx.startDatetime, cntx.endDatetime) )
                    self.perBoundFacts[concept, hCntx, unit, cntx.startDatetime, cntx.endDatetime].append(f)
                    if cntx.isStartEndPeriod:
                        self.durationPeriodStarts[nominalPeriod(cntx.endDatetime - cntx.startDatetime)].add(cntx.startDatetime)
        self.perInit = True
    
    def aggBindFacts(self, dimQN):
        # bind facts in section for domain aggreggation
        for f in self.sectionFacts:
            concept = f.concept
            if concept.isNumeric and not f.isNil:
                cntx = self.eqCntx.get(f.context,f.context)
                hCntx = dhash( (cntx.periodHash, cntx.entityIdentifierHash, 
                                frozenset(dimObj
                                          for _dimQN, dimObj in cntx.qnameDims.items()
                                          if _dimQN != dimQN)) )
                unit = self.eqUnit.get(f.unit,f.unit)
                memQN = cntx.dimMemberQname(dimension, includeDefaults=True)
                if memQN is not None:
                    self.aggConceptBindKeys[concept, dimQN].add( (hCntx,unit) )
                    self.aggBoundFacts[concept, hCntx, unit, dimQN, memQN].append(f)

    def formatInterval(self, a, b, dec):
        if isnan(dec) or isinf(dec): dec = 4
        if a == b: # not an interval
            return Locale.format_decimal(self.modelXbrl.locale, a, 1, max(dec,0))
        return "[{}, {}]".format( # show as an interval
            Locale.format_decimal(self.modelXbrl.locale, a, 1, max(dec,0)),
            Locale.format_decimal(self.modelXbrl.locale, b, 1, max(dec,0)))
        
            
def checkCalc2(val, *args, **kwargs):
    ValidateXbrlCalc2(val).validate()


   
__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Calc2',
    'version': '0.9',
    'description': '''Calculation 2.0 Validation.''',
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2019 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'Validate.XBRL.Finally': checkCalc2
}
