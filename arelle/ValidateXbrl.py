'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re
from arelle import (ModelDocument, XmlUtil, XbrlUtil, XbrlConst, 
                ValidateXbrlCalcs, ValidateXbrlDimensions, ValidateXbrlDTS, ValidateFormula, ValidateUtr)
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelValue import qname

arcNamesTo21Resource = {"labelArc","referenceArc"}
xlinkTypeValues = {None, "simple", "extended", "locator", "arc", "resource", "title", "none"}
xlinkActuateValues = {None, "onLoad", "onRequest", "other", "none"}
xlinkShowValues = {None, "new", "replace", "embed", "other", "none"}
xlinkLabelAttributes = {"{http://www.w3.org/1999/xlink}label", "{http://www.w3.org/1999/xlink}from", "{http://www.w3.org/1999/xlink}to"}
periodTypeValues = {"instant","duration"}
balanceValues = {None, "credit","debit"}
baseXbrliTypes = {
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
      }

class ValidateXbrl:
    def __init__(self, testModelXbrl):
        self.testModelXbrl = testModelXbrl
        
        # load edgartaxonomies
        
    def validate(self, modelXbrl, parameters=None):
        self.parameters = parameters
        self.NCnamePattern = re.compile("^[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
                                        r"[_\-\." 
                                           "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*$")
        self.precisionPattern = re.compile("^([0-9]+|INF)$")
        self.decimalsPattern = re.compile("^(-?[0-9]+|INF)$")
        self.isoCurrencyPattern = re.compile(r"^[A-Z]{3}$")
        self.modelXbrl = modelXbrl
        self.validateDisclosureSystem = modelXbrl.modelManager.validateDisclosureSystem
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        self.validateEFM = self.validateDisclosureSystem and self.disclosureSystem.EFM
        self.validateGFM = self.validateDisclosureSystem and self.disclosureSystem.GFM
        self.validateEFMorGFM = self.validateDisclosureSystem and self.disclosureSystem.EFMorGFM
        self.validateHMRC = self.validateDisclosureSystem and self.disclosureSystem.HMRC
        self.validateSBRNL = self.validateDisclosureSystem and self.disclosureSystem.SBRNL
        self.validateXmlLang = self.validateDisclosureSystem and self.disclosureSystem.xmlLangPattern
        self.validateCalcLB = modelXbrl.modelManager.validateCalcLB
        self.validateInferDecimals = modelXbrl.modelManager.validateInferDecimals
        
        # xlink validation
        modelXbrl.modelManager.showStatus(_("validating links"))
        modelLinks = set()
        self.remoteResourceLocElements = set()
        self.genericArcArcroles = set()
        for baseSetExtLinks in modelXbrl.baseSets.values():
            for baseSetExtLink in baseSetExtLinks:
                modelLinks.add(baseSetExtLink)    # ext links are unique (no dups)
        for modelLink in modelLinks:
            fromToArcs = {}
            locLabels = {}
            resourceLabels = {}
            resourceArcTos = []
            for arcElt in modelLink.iterchildren():
                if isinstance(arcElt,ModelObject):
                    xlinkType = arcElt.get("{http://www.w3.org/1999/xlink}type")
                    # locator must have an href
                    if xlinkType == "locator":
                        if arcElt.get("{http://www.w3.org/1999/xlink}href") is None:
                            modelXbrl.error(
                                _("Linkbase {0} extended link {1} locator {2} missing href").format(
                                      modelLink.modelDocument.basename,
                                      modelLink.role, 
                                      arcElt.get("{http://www.w3.org/1999/xlink}label")), 
                                "err", "xlink:locatorHref")
                        locLabels[arcElt.get("{http://www.w3.org/1999/xlink}label")] = arcElt
                    elif xlinkType == "resource":
                        resourceLabels[arcElt.get("{http://www.w3.org/1999/xlink}label")] = arcElt
                    # can be no duplicated arcs between same from and to
                    elif xlinkType == "arc":
                        fromLabel = arcElt.get("{http://www.w3.org/1999/xlink}from")
                        toLabel = arcElt.get("{http://www.w3.org/1999/xlink}to")
                        fromTo = (fromLabel,toLabel)
                        if fromTo in fromToArcs:
                            modelXbrl.error(
                                _("Linkbase {0} extended link {1} duplicate arcs from {2} to {3}").format(
                                      modelLink.modelDocument.basename,
                                      modelLink.role, fromLabel, toLabel), 
                                "err", "xlink:dupArcs")
                        else:
                            fromToArcs[fromTo] = arcElt
                        if arcElt.namespaceURI == XbrlConst.link:
                            if arcElt.localName in arcNamesTo21Resource: #("labelArc","referenceArc"):
                                resourceArcTos.append((toLabel, arcElt.get("use")))
                        elif self.isGenericArc(arcElt):
                            arcrole = arcElt.get("{http://www.w3.org/1999/xlink}arcrole")
                            self.genericArcArcroles.add(arcrole)
                            if arcrole in (XbrlConst.elementLabel, XbrlConst.elementReference):
                                resourceArcTos.append((toLabel, arcrole))
                    # values of type (not needed for validating parsers)
                    if xlinkType not in xlinkTypeValues: # ("", "simple", "extended", "locator", "arc", "resource", "title", "none"):
                        modelXbrl.error(
                            _("Linkbase {0} extended link {1} type {2} invalid").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, xlinkType), 
                            "err", "xlink:type")
                    # values of actuate (not needed for validating parsers)
                    xlinkActuate = arcElt.get("{http://www.w3.org/1999/xlink}actuate")
                    if xlinkActuate not in xlinkActuateValues: # ("", "onLoad", "onRequest", "other", "none"):
                        modelXbrl.error(
                            _("Linkbase {0} extended link {1} actuate {2} invalid").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, xlinkActuate), 
                            "err", "xlink:actuate")
                    # values of show (not needed for validating parsers)
                    xlinkShow = arcElt.get("{http://www.w3.org/1999/xlink}show")
                    if xlinkShow not in xlinkShowValues: # ("", "new", "replace", "embed", "other", "none"):
                        modelXbrl.error(
                            _("Linkbase {0} extended link {1} show {2} invalid").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, xlinkShow), 
                            "err", "xlink:show")
                    # values of label, from, to (not needed for validating parsers)
                    for name in xlinkLabelAttributes: # ("label", "from", "to"):
                        value = arcElt.get(name)
                        if value is not None and not self.NCnamePattern.match(value):
                            modelXbrl.error(
                                _("Linkbase {0} extended link {1} element {2} {3} '{4}' not an NCname").format(
                                      modelLink.modelDocument.basename,
                                      modelLink.role, 
                                      arcElt.prefixedName,
                                      name,
                                      value), 
                                "err", "xlink:{0}".format(name) )
            # check from, to of arcs have a resource or loc
            for fromTo, arcElt in fromToArcs.items():
                fromLabel, toLabel in fromTo
                for name, value, sect in (("from", fromLabel, "3.5.3.9.2"),("to",toLabel, "3.5.3.9.3")):
                    if value not in locLabels and value not in resourceLabels:
                        modelXbrl.error(
                            _("Arc in linkbase {0} extended link {1} from {2} to {3} attribute \"{4}\" has no matching loc or resource label").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, fromLabel, toLabel, name), 
                            "err", "xbrl.{0}:arcResource".format(sect))
                if arcElt.localName == "footnoteArc" and arcElt.namespaceURI == XbrlConst.link and \
                   arcElt.get("{http://www.w3.org/1999/xlink}arcrole") == XbrlConst.factFootnote:
                    if fromLabel not in locLabels:
                        modelXbrl.error(
                            _("FootnoteArc in {0} extended link {1} from {2} to {3} \"from\" is not a loc").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, fromLabel, toLabel), 
                            "err", "xbrl.4.11.1.3.1:factFootnoteArcFrom")
                    if toLabel not in resourceLabels or qname(resourceLabels[toLabel]) != XbrlConst.qnLinkFootnote:
                        modelXbrl.error(
                            _("FootnoteArc in {0} extended link {1} from {2} to {3} \"to\" is not a footnote resource").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, fromLabel, toLabel), 
                            "err", "xbrl.4.11.1.3.1:factFootnoteArcTo")
            # check unprohibited label arcs to remote locs
            for resourceArcTo in resourceArcTos:
                resourceArcToLabel, resourceArcUse = resourceArcTo
                if resourceArcToLabel in locLabels:
                    toLabel = locLabels[resourceArcToLabel]
                    if resourceArcUse == "prohibited":
                        self.remoteResourceLocElements.add(toLabel)
                    else:
                        modelXbrl.error(
                            _("Unprohibited labelArc in linkbase {0} extended link {1} has illegal remote resource loc labeled {2} href {3}").format(
                                  modelLink.modelDocument.basename,
                                  modelLink.role, 
                                  resourceArcToLabel, 
                                  toLabel.get("{http://www.w3.org/1999/xlink}href")), 
                            "err", "xbrl.5.2.2.3:labelArcRemoteResource")
                elif resourceArcToLabel in resourceLabels:
                    toResource = resourceLabels[resourceArcToLabel]
                    if resourceArcUse == XbrlConst.elementLabel:
                        if not self.isGenericLabel(toResource):
                            modelXbrl.error(
                                _("Generic label arc in linkbase {0} extended link {1} to {2} must target a generic label").format(
                                      modelLink.modelDocument.basename,
                                      modelLink.role, 
                                      resourceArcToLabel), 
                                "err", "xbrlle.2.1.1:genericLabelTarget")
                    elif resourceArcUse == XbrlConst.elementReference:
                        if not self.isGenericReference(toResource):
                            modelXbrl.error(
                                _("Generic reference arc in linkbase {0} extended link {1} to {2} must target a generic reference").format(
                                      modelLink.modelDocument.basename,
                                      modelLink.role, 
                                      resourceArcToLabel), 
                                "err", "xbrlre.2.1.1:genericReferenceTarget")

        self.dimensionDefaults = {}
        modelXbrl.qnameDimensionDefaults = {}
        modelXbrl.qnameDimensionContextElement = {}
        # check base set cycles, dimensions
        modelXbrl.modelManager.showStatus(_("validating relationship sets"))
        for baseSetKey in modelXbrl.baseSets.keys():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if arcrole.startswith("XBRL-") or ELR is None or \
                linkqname is None or arcqname is None:
                continue
            elif arcrole in XbrlConst.standardArcroleCyclesAllowed:
                cyclesAllowed, specSect = XbrlConst.standardArcroleCyclesAllowed[arcrole]
            elif arcrole in self.modelXbrl.arcroleTypes and len(self.modelXbrl.arcroleTypes[arcrole]) > 0:
                cyclesAllowed = self.modelXbrl.arcroleTypes[arcrole][0].cyclesAllowed
                if arcrole in self.genericArcArcroles:
                    specSect = "xbrlgene:violatedCyclesConstraint"
                else:
                    specSect = "xbrl.5.1.4.3:cycles"
            else:
                cyclesAllowed = "any"
                specSect = None
            if cyclesAllowed != "any" or arcrole in (XbrlConst.summationItem,) \
                                      or arcrole in self.genericArcArcroles  \
                                      or arcrole.startswith(XbrlConst.formulaStartsWith):
                relsSet = modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname)
            if cyclesAllowed != "any" and \
                   (XbrlConst.isStandardExtLinkQname(linkqname) and XbrlConst.isStandardArcQname(arcqname)) \
                   or arcrole in self.genericArcArcroles:
                noUndirected = cyclesAllowed == "none"
                fromRelationships = relsSet.fromModelObjects()
                for relFrom, rels in fromRelationships.items():
                    cycleFound = self.fwdCycle(relsSet, rels, noUndirected, {relFrom})
                    if cycleFound:
                        modelXbrl.error(
                            _("Relationships have a {0} cycle in arcrole {1} link role {2} link {3}, arc {4} starting from {5}").format(
                                  cycleFound, arcrole, ELR, linkqname, arcqname, relFrom.qname), 
                            "err", "{0}".format(specSect))
                        break
                
            # check calculation arcs for weight issues (note calc arc is an "any" cycles)
            if arcrole == XbrlConst.summationItem:
                for modelRel in relsSet.modelRelationships:
                    weight = modelRel.weight
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if weight == 0:
                            modelXbrl.error(
                                _("Calculation relationship has zero weight from {0} to {1} in link role {2}").format(
                                      fromConcept.qname, toConcept.qname, ELR), 
                                "err", "xbrl.5.2.5.2.1:zeroWeight")
                        fromBalance = fromConcept.balance
                        toBalance = toConcept.balance
                        if fromBalance and toBalance:
                            if (fromBalance == toBalance and weight < 0) or \
                               (fromBalance != toBalance and weight > 0):
                                modelXbrl.error(
                                    _("Calculation relationship has illegal weight {0} from {1}, {2}, to {3}, {4} in link role {5} (per 5.1.1.2 Table 6)").format(
                                          weight, fromConcept.qname, fromBalance, toConcept.qname, toBalance, ELR), 
                                    "err", "xbrl.5.1.1.2:balanceCalcWeight")
                        if not fromConcept.isNumeric or not toConcept.isNumeric:
                            modelXbrl.error(
                                _("Calculation relationship has illegal concept from {0}{1} to {2}{3} in link role {4}").format(
                                      fromConcept.qname, "" if fromConcept.isNumeric else " (non-numeric)", 
                                      toConcept.qname, "" if fromConcept.isNumeric else " (non-numeric)", ELR), 
                                "err", "xbrl.5.2.5.2:nonNumericCalc")
            # check presentation relationships for preferredLabel issues
            elif arcrole == XbrlConst.parentChild:
                for modelRel in relsSet.modelRelationships:
                    preferredLabel = modelRel.preferredLabel
                    toConcept = modelRel.toModelObject
                    if preferredLabel is not None and toConcept is not None and \
                       toConcept.label(preferredLabel=preferredLabel,fallbackToQname=False) is None:
                        modelXbrl.error(
                            _("Presentation relationship from {0} to {1} in link role {2} missing preferredLabel {3}").format(
                                  modelRel.fromModelObject.qname,  toConcept.qname, ELR, preferredLabel), 
                            "err", "xbrl.5.2.4.2.1:preferredLabelMissing")
            # check essence-alias relationships
            elif arcrole == XbrlConst.essenceAlias:
                for modelRel in relsSet.modelRelationships:
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if fromConcept.type != toConcept.type or fromConcept.periodType != toConcept.periodType:
                            modelXbrl.error(
                                _("Essence-alias relationship from {0} to {1} in link role {2} has different types or periodTypes").format(
                                      fromConcept.qname, toConcept.qname, ELR), 
                                "err", "xbrl.5.2.6.2.2:essenceAliasTypes")
                        fromBalance = fromConcept.balance
                        toBalance = toConcept.balance
                        if fromBalance and toBalance:
                            if fromBalance and toBalance and fromBalance != toBalance:
                                modelXbrl.error(
                                    _("Essence-alias relationship from {0} to {1} in link role {2} has different balances").format(
                                          fromConcept.qname, toConcept.qname, ELR), 
                                    "err", "xbrl.5.2.6.2.2:essenceAliasBalance")
            elif modelXbrl.hasXDT and arcrole.startswith(XbrlConst.dimStartsWith):
                ValidateXbrlDimensions.checkBaseSet(self, arcrole, ELR, relsSet)             
            elif modelXbrl.hasFormulae and arcrole.startswith(XbrlConst.formulaStartsWith):
                ValidateFormula.checkBaseSet(self, arcrole, ELR, relsSet)
                            
        # instance checks
        modelXbrl.modelManager.showStatus(_("validating instance"))
        self.footnoteRefs = set()
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            for f in modelXbrl.facts:
                concept = f.concept
                if concept is not None:
                    if concept.isNumeric:
                        unit = f.unit
                        if f.unitID is None or unit is None:
                            self.modelXbrl.error(
                                _("Fact {0} context {1} is numeric and must have a unit").format(
                                      modelXbrl.modelDocument.basename,
                                      f.qname, f.contextID), 
                                "err", "xbrl.4.6.2:numericUnit")
                        else:
                            if concept.isMonetary:
                                measures = unit.measures
                                if not measures or len(measures[0]) != 1 or len(measures[1]) != 0 or \
                                    measures[0][0].namespaceURI != XbrlConst.iso4217 or \
                                    not self.isoCurrencyPattern.match(measures[0][0].localName):
                                        self.modelXbrl.error(
                                            _("Fact {0} context {1} must have a monetary unit {2}").format(
                                                  modelXbrl.modelDocument.basename,
                                                  f.qname, f.contextID, f.unitID), 
                                            "err", "xbrl.4.8.2:monetaryFactUnit")
                            elif concept.isShares:
                                measures = unit.measures
                                if not measures or len(measures[0]) != 1 or len(measures[1]) != 0 or \
                                    measures[0][0] != XbrlConst.qnXbrliShares:
                                        self.modelXbrl.error(
                                            _("Fact {0} context {1} must have a xbrli:shares unit {2}").format(
                                                  f.qname, f.contextID, f.unitID), 
                                            "err", "xbrl.4.8.2:sharesFactUnit")
                    precision = f.precision
                    hasPrecision = precision is not None
                    if hasPrecision and precision != "INF" and not precision.isdigit():
                        self.modelXbrl.error(
                            _("Fact {0} context {1} precision {2} is invalid").format(
                                  f.qname, f.contextID, precision), 
                            "err", "xbrl.4.6.4:precision")
                    decimals = f.decimals
                    hasDecimals = decimals is not None
                    if hasPrecision and not self.precisionPattern.match(precision):
                        self.modelXbrl.error(
                            _("Fact {0} context {1} precision {2} is invalid").format(
                                  f.qname, f.contextID, precision), 
                            "err", "xbrl.4.6.4:precision")
                    if hasPrecision and hasDecimals:
                        self.modelXbrl.error(
                            _("Fact {0} context {1} can not have both precision and decimals").format(
                                  f.qname, f.contextID), 
                            "err", "xbrl.4.6.3:bothPrecisionAndDecimals")
                    if hasDecimals and not self.decimalsPattern.match(decimals):
                        self.modelXbrl.error(
                            _("Fact {0} context {1} decimals {2} is invalid").format(
                                  f.qname, f.contextID, decimals), 
                            "err", "xbrl.4.6.5:decimals")
                    if concept.isItem:
                        context = f.context
                        if context is None:
                            self.modelXbrl.error(
                                _("Item {0} must have a context").format(
                                      f.qname), 
                                "err", "xbrl.4.6.1:itemContextRef")
                        else:
                            periodType = concept.periodType
                            if (periodType == "instant" and not context.isInstantPeriod) or \
                               (periodType == "duration" and not (context.isStartEndPeriod or context.isForeverPeriod)):
                                self.modelXbrl.error(
                                    _("Fact {0} context {1} has period type {2} conflict with context").format(
                                          f.qname, f.contextID, periodType), 
                                    "err", "xbrl.4.7.2:contextPeriodType")
                            if modelXbrl.hasXDT:
                                ValidateXbrlDimensions.checkFact(self, f)
                        # check precision and decimals
                        if f.xsiNil == "true":
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.error(
                                    _("Fact {0} context {1} can not be nil and have either precision or decimals").format(
                                          f.qname, f.contextID), 
                                    "err", "xbrl.4.6.3:nilPrecisionDecimals")
                        elif concept.isFraction:
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.error(
                                    _("Fact {0} context {1} is a fraction concept and cannot have either precision or decimals").format(
                                          f.qname, f.contextID), 
                                    "err", "xbrl.4.6.3:fractionPrecisionDecimals")
                                numerator, denominator = f.fractionValue
                                if not (numerator == "INF" or numerator.isnumeric()):
                                    self.modelXbrl.error(
                                        _("Fact {0} context {1} is a fraction with invalid numerator {2}").format(
                                              f.qname, f.contextID, numerator), 
                                        "err", "xbrl.5.1.1:fractionPrecisionDecimals")
                                if not denominator.isnumeric() or int(denominator) == 0:
                                    self.modelXbrl.error(
                                        _("Fact {0} context {1} is a fraction with invalid denominator {2}").format(
                                              f.qname, f.contextID, denominator), 
                                        "err", "xbrl.5.1.1:fractionPrecisionDecimals")
                        else:
                            if modelXbrl.modelDocument.type != ModelDocument.Type.INLINEXBRL:
                                for child in f.iterchildren():
                                    if isinstance(child,ModelObject):
                                        self.modelXbrl.error(
                                            _("Fact {0} context {1} may not have child elements {2}").format(
                                                  f.qname, f.contextID, child.prefixedName), 
                                            "err", "xbrl.5.1.1:itemMixedContent")
                                        break
                            if concept.isNumeric and not hasPrecision and not hasDecimals:
                                self.modelXbrl.error(
                                    _("Fact {0} context {1} is a numeric concept and must have either precision or decimals").format(
                                          f.qname, f.contextID), 
                                    "err", "xbrl.4.6.3:missingPrecisionDecimals")
                    elif concept.isTuple:
                        if f.contextID:
                            self.modelXbrl.error(
                                _("Tuple {0} must not have a context").format(
                                      f.qname), 
                                "err", "xbrl.4.6.1:tupleContextRef")
                        if hasPrecision or hasDecimals:
                            self.modelXbrl.error(
                                _("Fact {0} is a tuple and cannot have either precision or decimals").format(
                                      f.qname), 
                                "err", "xbrl.4.6.3:tuplePrecisionDecimals")
                        # custom attributes may be allowed by anyAttribute but not by 2.1
                        for attrQname, attrValue in XbrlUtil.attributes(self.modelXbrl, f):
                            if attrQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
                                self.modelXbrl.error(
                                    _("Fact {0} is a tuple and must not have attribute in this namespace {1}").format(
                                          f.qname, attrQname), 
                                    "err", "xbrl.4.9:tupleAttribute")

                    
                    else:
                        self.modelXbrl.error(
                            _("Fact {0} must be an item or tuple").format(
                                  f.qname), 
                            "err", "xbrl.4.6:notItemOrTuple")
                        
                if isinstance(f, ModelInlineFact):
                    self.footnoteRefs.update(f.footnoteRefs)
            
            #instance checks
            for cntx in modelXbrl.contexts.values():
                if cntx.isStartEndPeriod:
                    try:
                        if cntx.endDatetime <= cntx.startDatetime:
                            self.modelXbrl.error(
                                _("Context {0} must have startDate less than endDate").format(
                                      cntx.id), 
                                "err", "xbrl.4.7.2:periodStartBeforeEnd")
                    except (TypeError, ValueError) as err:
                        self.modelXbrl.error(
                            _("Context {0} startDate or endDate: {1}").format(
                                  cntx.id, err), 
                            "err", "xbrl.4.7.2:contextDateError")
                elif cntx.isInstantPeriod:
                    try:
                        cntx.instantDatetime #parse field
                    except ValueError as err:
                        self.modelXbrl.error(
                            _("Context {0} instant date: {1}").format(
                                  cntx.id, err), 
                            "err", "xbrl.4.7.2:contextDateError")
                self.segmentScenario(cntx.segment, cntx.id, "segment", "4.7.3.2")
                self.segmentScenario(cntx.scenario, cntx.id, "scenario", "4.7.4")
                if modelXbrl.hasXDT:
                    ValidateXbrlDimensions.checkContext(self,cntx)
                
            for unit in modelXbrl.units.values():
                mulDivMeasures = unit.measures
                if mulDivMeasures:
                    for measures in mulDivMeasures:
                        for measure in measures:
                            if measure.namespaceURI == XbrlConst.xbrli and not \
                                measure in (XbrlConst.qnXbrliPure, XbrlConst.qnXbrliShares):
                                    self.modelXbrl.error(
                                        _("Unit {0} illegal measure: {1}").format(
                                              unit.id, measure), 
                                        "err", "xbrl.4.8.2:measureElement")
                    for numeratorMeasure in mulDivMeasures[0]:
                        if numeratorMeasure in mulDivMeasures[1]:
                            self.modelXbrl.error(
                                _("Unit {0} numerator measure: {1} also appears as denominator measure").format(
                                      unit.id, numeratorMeasure), 
                                "err", "xbrl.4.8.4:measureBothNumDenom")
                    
        #concepts checks
        modelXbrl.modelManager.showStatus(_("validating concepts"))
        for concept in modelXbrl.qnameConcepts.values():
            conceptType = concept.type
            if XbrlConst.isStandardNamespace(concept.namespaceURI) or \
               not concept.modelDocument.inDTS:
                continue
            
            if concept.isTuple:
                # must be global
                if not concept.getparent().localName == "schema":
                    self.modelXbrl.error(
                        _("Tuple {0} must be declared globally").format(
                              concept.qname), 
                        "err", "xbrl.4.9:tupleGloballyDeclared")
                if concept.periodType:
                    self.modelXbrl.error(
                        _("Tuple {0} must not have periodType").format(
                              concept.qname), 
                        "err", "xbrl.4.9:tuplePeriodType")
                if concept.balance:
                    self.modelXbrl.error(
                        _("Tuple {0} must not have balance").format(
                              concept.qname), 
                        "err", "xbrl.4.9:tupleBalance")
                # check attribute declarations
                for attributeQname in conceptType.attributes:
                    if attributeQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
                        self.modelXbrl.error(
                            _("Tuple {0} must not have attribute in this namespace {1}").format(
                                  concept.qname, attributeQname), 
                            "err", "xbrl.4.9:tupleAttribute")
                # check for mixed="true" or simple content
                if XmlUtil.descendantAttr(conceptType, XbrlConst.xsd, ("complexType", "complexContent"), "mixed") == "true":
                    self.modelXbrl.error(
                        _("Tuple {0} must not have mixed content").format(
                              concept.qname), 
                        "err", "xbrl.4.9:tupleMixedContent")
                if XmlUtil.descendant(conceptType, XbrlConst.xsd, "simpleContent"):
                    self.modelXbrl.error(
                        _("Tuple {0} must not have simple content").format(
                              concept.qname), 
                        "err", "xbrl.4.9:tupleSimpleContent")
                # child elements must be item or tuple
                for elementQname in conceptType.elements:
                    childConcept = self.modelXbrl.qnameConcepts.get(elementQname)
                    if childConcept is None:
                        self.modelXbrl.error(
                            _("Tuple {0} element {1} not defined").format(
                                  concept.qname, elementQname), 
                            "err", "xbrl.4.9:tupleElementUndefined")
                    elif not (childConcept.isItem or childConcept.isTuple or # isItem/isTuple do not include item or tuple itself
                              childConcept.qname == XbrlConst.qnXbrliItem or # subs group includes item as member
                              childConcept.qname == XbrlConst.qnXbrliTuple):
                        self.modelXbrl.error(
                            _("Tuple {0} must not have element {1} not an item or tuple").format(
                                  concept.qname, elementQname), 
                            "err", "xbrl.4.9:tupleElementItemOrTuple")
            elif concept.isItem:
                if concept.periodType not in periodTypeValues: #("instant","duration"):
                    self.modelXbrl.error(
                        _("Item {0} must have a valid periodType").format(
                              concept.qname), 
                        "err", "xbrl.5.1.1.1:itemPeriodType")
                if concept.isMonetary:
                    if concept.balance not in balanceValues: #(None, "credit","debit"):
                        self.modelXbrl.error(
                            _("Item {0} must have a valid balance {1}").format(
                                  concept.qname, concept.balance), 
                            "err", "xbrl.5.1.1.2:itemBalance")
                else:
                    if concept.balance:
                        self.modelXbrl.error(
                            _("Item {0} may not have a balance").format(
                                  concept.qname), 
                            "err", "xbrl.5.1.1.2:itemBalance")
                if concept.baseXbrliType not in baseXbrliTypes:
                    self.modelXbrl.error(
                        _("Item {0} type {1} invalid").format(
                              concept.qname, concept.baseXbrliType), 
                        "err", "xbrl.5.1.1.3:itemType")
                if modelXbrl.hasXDT:
                    if concept.isHypercubeItem and not concept.abstract == "true":
                        self.modelXbrl.error(
                            _("Hypercube item {0} must be abstract").format(
                                  concept.qname), 
                            "err", "xbrldte:HypercubeElementIsNotAbstractError")
                    elif concept.isDimensionItem and not concept.abstract == "true":
                        self.modelXbrl.error(
                            _("Dimension item {0} must be abstract").format(
                                  concept.qname), 
                            "err", "xbrldte:DimensionElementIsNotAbstractError")
            if modelXbrl.hasXDT:
                ValidateXbrlDimensions.checkConcept(self, concept)
            
        modelXbrl.modelManager.showStatus(_("validating DTS"))
        self.DTSreferenceResourceIDs = {}
        ValidateXbrlDTS.checkDTS(self, modelXbrl.modelDocument, [])
        del self.DTSreferenceResourceIDs
        
        if self.validateCalcLB:
            modelXbrl.modelManager.showStatus(_("Validating instance calculations"))
            ValidateXbrlCalcs.validate(modelXbrl, inferPrecision=(not self.validateInferDecimals))
            
        if modelXbrl.modelManager.validateUtr:
            ValidateUtr.validate(modelXbrl)
            
        if modelXbrl.hasFormulae:
            ValidateFormula.validate(self)
            
        modelXbrl.modelManager.showStatus(_("ready"), 2000)
        
    def fwdCycle(self, relsSet, rels, noUndirected, fromConcepts, cycleType="directed", revCycleRel=None):
        for rel in rels:
            if revCycleRel is not None and rel.isIdenticalTo(revCycleRel):
                continue # don't double back on self in undirected testing
            relTo = rel.toModelObject
            if relTo in fromConcepts: #forms a directed cycle
                return cycleType
            fromConcepts.add(relTo)
            nextRels = relsSet.fromModelObject(relTo)
            foundCycle = self.fwdCycle(relsSet, nextRels, noUndirected, fromConcepts)
            if foundCycle:
                return foundCycle
            fromConcepts.discard(relTo)
            # look for back path in any of the ELRs visited (pass None as ELR)
            if noUndirected:
                foundCycle = self.revCycle(relsSet, relTo, rel, fromConcepts)
                if foundCycle:
                    return foundCycle
        return None
    
    def revCycle(self, relsSet, toConcept, turnbackRel, fromConcepts):
        for rel in relsSet.toModelObject(toConcept):
            if not rel.isIdenticalTo(turnbackRel):
                relFrom = rel.fromModelObject
                if relFrom in fromConcepts:
                    return "undirected"
                fromConcepts.add(relFrom)
                foundCycle = self.revCycle(relsSet, relFrom, turnbackRel, fromConcepts)
                if foundCycle:
                    return foundCycle
                fwdRels = relsSet.fromModelObject(relFrom)
                foundCycle = self.fwdCycle(relsSet, fwdRels, True, fromConcepts, cycleType="undirected", revCycleRel=rel)
                if foundCycle:
                    return foundCycle
                fromConcepts.discard(relFrom)
        return None
    
    def segmentScenario(self, element, contextId, name, sect, topLevel=True):
        if topLevel:
            if element is None:
                return  # nothing to check
        else:
            if element.namespaceURI == XbrlConst.xbrli:
                self.modelXbrl.error(
                    _("Context {0} {1} cannot have xbrli element {2}").format(
                          contextId, name, element.prefixedName), 
                    "err", "xbrl.{0}:{1}XbrliElement".format(sect,name))
            else:
                concept = self.modelXbrl.qnameConcepts.get(qname(element))
                if concept is not None and (concept.isItem or concept.isTuple):
                    self.modelXbrl.error(
                        _("Context {0} {1} cannot have item or tuple element {2}").format(
                              contextId, name, element.prefixedName), 
                        "err", "xbrl.{0}:{1}ItemOrTuple".format(sect,name))
        hasChild = False
        for child in element.iterchildren():
            if isinstance(child,ModelObject):
                self.segmentScenario(child, contextId, name, sect, topLevel=False)
                hasChild = True
        if topLevel and not hasChild:
            self.modelXbrl.error(
                _("Context {0} {1} cannot be empty").format(
                      contextId, name), 
                "err", "xbrl.{0}:{1}Empty".format(sect,name))
        
    def isGenericObject(self, elt, genQname):
        return self.modelXbrl.isInSubstitutionGroup(qname(elt),genQname)
    
    def isGenericLink(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenLink)
    
    def isGenericArc(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenArc)
    
    def isGenericResource(self, elt):
        return self.isGenericObject(elt.getparent(), XbrlConst.qnGenLink)

    def isGenericLabel(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenLabel)

    def isGenericReference(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenReference)

    def executeCallTest(self, modelXbrl, name, callTuple, testTuple):
        self.modelXbrl = modelXbrl
        ValidateFormula.executeCallTest(self, name, callTuple, testTuple)
                
