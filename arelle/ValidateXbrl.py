'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re
from arelle import (ModelDocument, XmlUtil, XbrlUtil, XbrlConst, 
                ValidateXbrlCalcs, ValidateXbrlDimensions, ValidateXbrlDTS, ValidateFormula, ValidateUtr)
from arelle import FunctionIxt
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelValue import qname
validateUniqueParticleAttribution = None # dynamic import

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
        
    def close(self, reusable=True):
        if reusable:
            testModelXbrl = self.testModelXbrl
        self.__dict__.clear()   # dereference everything
        if reusable:
            self.testModelXbrl = testModelXbrl
        
    def validate(self, modelXbrl, parameters=None):
        self.parameters = parameters
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
        modelXbrl.profileStat(None)
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
                            modelXbrl.error("xlink:locatorHref",
                                _("Xlink locator %(xlinkLabel)s missing href in extended link %(linkrole)s"),
                                modelObject=arcElt,
                                linkrole=modelLink.role, 
                                xlinkLabel=arcElt.get("{http://www.w3.org/1999/xlink}label")) 
                        locLabels[arcElt.get("{http://www.w3.org/1999/xlink}label")] = arcElt
                    elif xlinkType == "resource":
                        resourceLabels[arcElt.get("{http://www.w3.org/1999/xlink}label")] = arcElt
                    # can be no duplicated arcs between same from and to
                    elif xlinkType == "arc":
                        fromLabel = arcElt.get("{http://www.w3.org/1999/xlink}from")
                        toLabel = arcElt.get("{http://www.w3.org/1999/xlink}to")
                        fromTo = (fromLabel,toLabel)
                        if fromTo in fromToArcs:
                            modelXbrl.error("xlink:dupArcs",
                                _("Duplicate xlink arcs  in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s"),
                                modelObject=arcElt,
                                linkrole=modelLink.role, 
                                xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
                        else:
                            fromToArcs[fromTo] = arcElt
                        if arcElt.namespaceURI == XbrlConst.link:
                            if arcElt.localName in arcNamesTo21Resource: #("labelArc","referenceArc"):
                                resourceArcTos.append((toLabel, arcElt.get("use"), arcElt))
                        elif self.isGenericArc(arcElt):
                            arcrole = arcElt.get("{http://www.w3.org/1999/xlink}arcrole")
                            self.genericArcArcroles.add(arcrole)
                            if arcrole in (XbrlConst.elementLabel, XbrlConst.elementReference):
                                resourceArcTos.append((toLabel, arcrole, arcElt))
                    # values of type (not needed for validating parsers)
                    if xlinkType not in xlinkTypeValues: # ("", "simple", "extended", "locator", "arc", "resource", "title", "none"):
                        modelXbrl.error("xlink:type",
                            _("Xlink type %(xlinkType)s invalid in extended link %(linkrole)s"),
                            modelObject=arcElt, linkrole=modelLink.role, xlinkType=xlinkType)
                    # values of actuate (not needed for validating parsers)
                    xlinkActuate = arcElt.get("{http://www.w3.org/1999/xlink}actuate")
                    if xlinkActuate not in xlinkActuateValues: # ("", "onLoad", "onRequest", "other", "none"):
                        modelXbrl.error("xlink:actuate",
                            _("Actuate %(xlinkActuate)s invalid in extended link %(linkrole)s"),
                            modelObject=arcElt, linkrole=modelLink.role, xlinkActuate=xlinkActuate)
                    # values of show (not needed for validating parsers)
                    xlinkShow = arcElt.get("{http://www.w3.org/1999/xlink}show")
                    if xlinkShow not in xlinkShowValues: # ("", "new", "replace", "embed", "other", "none"):
                        modelXbrl.error("xlink:show",
                            _("Show %(xlinkShow)s invalid in extended link %(linkrole)s"),
                            modelObject=arcElt, linkrole=modelLink.role, xlinkShow=xlinkShow)
            # check from, to of arcs have a resource or loc
            for fromTo, arcElt in fromToArcs.items():
                fromLabel, toLabel in fromTo
                for name, value, sect in (("from", fromLabel, "3.5.3.9.2"),("to",toLabel, "3.5.3.9.3")):
                    if value not in locLabels and value not in resourceLabels:
                        modelXbrl.error("xbrl.{0}:arcResource".format(sect),
                            _("Arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s attribute '%(attribute)s' has no matching loc or resource label"),
                            modelObject=arcElt, 
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel, 
                            attribute=name)
                if arcElt.localName == "footnoteArc" and arcElt.namespaceURI == XbrlConst.link and \
                   arcElt.get("{http://www.w3.org/1999/xlink}arcrole") == XbrlConst.factFootnote:
                    if fromLabel not in locLabels:
                        modelXbrl.error("xbrl.4.11.1.3.1:factFootnoteArcFrom",
                            _("Footnote arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s \"from\" is not a loc"),
                            modelObject=arcElt, 
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
                    if toLabel not in resourceLabels or qname(resourceLabels[toLabel]) != XbrlConst.qnLinkFootnote:
                        modelXbrl.error("xbrl.4.11.1.3.1:factFootnoteArcTo",
                            _("Footnote arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s \"to\" is not a footnote resource"),
                            modelObject=arcElt, 
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
            # check unprohibited label arcs to remote locs
            for resourceArcTo in resourceArcTos:
                resourceArcToLabel, resourceArcUse, arcElt = resourceArcTo
                if resourceArcToLabel in locLabels:
                    toLabel = locLabels[resourceArcToLabel]
                    if resourceArcUse == "prohibited":
                        self.remoteResourceLocElements.add(toLabel)
                    else:
                        modelXbrl.error("xbrl.5.2.2.3:labelArcRemoteResource",
                            _("Unprohibited labelArc in extended link %(linkrole)s has illegal remote resource loc labeled %(xlinkLabel)s href %(xlinkHref)s"),
                            modelObject=arcElt, 
                            linkrole=modelLink.role, 
                            xlinkLabel=resourceArcToLabel,
                            xlinkHref=toLabel.get("{http://www.w3.org/1999/xlink}href"))
                elif resourceArcToLabel in resourceLabels:
                    toResource = resourceLabels[resourceArcToLabel]
                    if resourceArcUse == XbrlConst.elementLabel:
                        if not self.isGenericLabel(toResource):
                            modelXbrl.error("xbrlle.2.1.1:genericLabelTarget",
                                _("Generic label arc in extended link %(linkrole)s to %(xlinkLabel)s must target a generic label"),
                                modelObject=arcElt, 
                                linkrole=modelLink.role, 
                                xlinkLabel=resourceArcToLabel)
                    elif resourceArcUse == XbrlConst.elementReference:
                        if not self.isGenericReference(toResource):
                            modelXbrl.error("xbrlre.2.1.1:genericReferenceTarget",
                                _("Generic reference arc in extended link %(linkrole)s to %(xlinkLabel)s must target a generic reference"),
                                modelObject=arcElt, 
                                linkrole=modelLink.role, 
                                xlinkLabel=resourceArcToLabel)
            resourceArcTos = None # dereference arcs
        modelXbrl.profileStat(_("validateLinks"))

        modelXbrl.dimensionDefaultConcepts = {}
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
                # TODO: table should be in this module, where it is used
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
                    if cycleFound is not None:
                        path = str(relFrom.qname) + " " + " - ".join(
                            "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, rel.toModelObject.qname)
                            for rel in reversed(cycleFound[1:]))
                        modelXbrl.error(specSect,
                            _("Relationships have a %(cycle)s cycle in arcrole %(arcrole)s \nlink role %(linkrole)s \nlink %(linkname)s, \narc %(arcname)s, \npath %(path)s"),
                            modelObject=cycleFound[1:], cycle=cycleFound[0], path=path,
                            arcrole=arcrole, linkrole=ELR, linkname=linkqname, arcname=arcqname), 
                        break
                
            # check calculation arcs for weight issues (note calc arc is an "any" cycles)
            if arcrole == XbrlConst.summationItem:
                for modelRel in relsSet.modelRelationships:
                    weight = modelRel.weight
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if weight == 0:
                            modelXbrl.error("xbrl.5.2.5.2.1:zeroWeight",
                                _("Calculation relationship has zero weight from %(source)s to %(target)s in link role %(linkrole)s"),
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR), 
                        fromBalance = fromConcept.balance
                        toBalance = toConcept.balance
                        if fromBalance and toBalance:
                            if (fromBalance == toBalance and weight < 0) or \
                               (fromBalance != toBalance and weight > 0):
                                modelXbrl.error("xbrl.5.1.1.2:balanceCalcWeightIllegal" +
                                                ("Negative" if weight < 0 else "Positive"),
                                    _("Calculation relationship has illegal weight %(weight)s from %(source)s, %(sourceBalance)s, to %(target)s, %(targetBalance)s, in link role %(linkrole)s (per 5.1.1.2 Table 6)"),
                                    modelObject=modelRel, weight=weight,
                                    source=fromConcept.qname, target=toConcept.qname, linkrole=ELR, 
                                    sourceBalance=fromBalance, targetBalance=toBalance)
                        if not fromConcept.isNumeric or not toConcept.isNumeric:
                            modelXbrl.error("xbrl.5.2.5.2:nonNumericCalc",
                                _("Calculation relationship has illegal concept from %(source)s%(sourceNumericDecorator)s to %(target)s%(targetNumericDecorator)s in link role %(linkrole)s"),
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR, 
                                sourceNumericDecorator="" if fromConcept.isNumeric else _(" (non-numeric)"), 
                                targetNumericDecorator="" if toConcept.isNumeric else _(" (non-numeric)"))
            # check presentation relationships for preferredLabel issues
            elif arcrole == XbrlConst.parentChild:
                for modelRel in relsSet.modelRelationships:
                    preferredLabel = modelRel.preferredLabel
                    toConcept = modelRel.toModelObject
                    if preferredLabel is not None and toConcept is not None and \
                       toConcept.label(preferredLabel=preferredLabel,fallbackToQname=False) is None:
                        modelXbrl.error("xbrl.5.2.4.2.1:preferredLabelMissing",
                            _("Presentation relationship from %(source)s to %(target)s in link role %(linkrole)s missing preferredLabel %(preferredLabel)s"),
                            modelObject=modelRel,
                            source=modelRel.fromModelObject.qname, target=toConcept.qname, linkrole=ELR, 
                            preferredLabel=preferredLabel)
            # check essence-alias relationships
            elif arcrole == XbrlConst.essenceAlias:
                for modelRel in relsSet.modelRelationships:
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if fromConcept.type != toConcept.type or fromConcept.periodType != toConcept.periodType:
                            modelXbrl.error("xbrl.5.2.6.2.2:essenceAliasTypes",
                                _("Essence-alias relationship from %(source)s to %(target)s in link role %(linkrole)s has different types or periodTypes"),
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                        fromBalance = fromConcept.balance
                        toBalance = toConcept.balance
                        if fromBalance and toBalance:
                            if fromBalance and toBalance and fromBalance != toBalance:
                                modelXbrl.error("xbrl.5.2.6.2.2:essenceAliasBalance",
                                    _("Essence-alias relationship from %(source)s to %(target)s in link role %(linkrole)s has different balances")).format(
                                    modelObject=modelRel,
                                    source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
            elif modelXbrl.hasXDT and arcrole.startswith(XbrlConst.dimStartsWith):
                ValidateXbrlDimensions.checkBaseSet(self, arcrole, ELR, relsSet)             
            elif (modelXbrl.hasFormulae or modelXbrl.hasTableRendering) and arcrole.startswith(XbrlConst.formulaStartsWith):
                ValidateFormula.checkBaseSet(self, arcrole, ELR, relsSet)
        modelXbrl.isDimensionsValidated = True
        modelXbrl.profileStat(_("validateRelationships"))
                            
        # instance checks
        modelXbrl.modelManager.showStatus(_("validating instance"))
        self.footnoteRefs = set()
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            factsWithDeprecatedIxNamespace = []
            for f in modelXbrl.facts:
                concept = f.concept
                if concept is not None:
                    if concept.isNumeric:
                        unit = f.unit
                        if f.unitID is None or unit is None:
                            self.modelXbrl.error("xbrl.4.6.2:numericUnit",
                                 _("Fact %(fact)s context %(contextID)s is numeric and must have a unit"),
                                 modelObject=f, fact=f.qname, contextID=f.contextID)
                        else:
                            if concept.isMonetary:
                                measures = unit.measures
                                if not measures or len(measures[0]) != 1 or len(measures[1]) != 0:
                                    self.modelXbrl.error("xbrl.4.8.2:monetaryFactUnit-notSingleMeasure",
                                        _("Fact %(fact)s context %(contextID)s must have a single unit measure which is monetary %(unitID)s"),
                                         modelObject=f, fact=f.qname, contextID=f.contextID, unitID=f.unitID)
                                elif (measures[0][0].namespaceURI != XbrlConst.iso4217 or
                                      not self.isoCurrencyPattern.match(measures[0][0].localName)):
                                    self.modelXbrl.error("xbrl.4.8.2:monetaryFactUnit-notMonetaryMeasure",
                                        _("Fact %(fact)s context %(contextID)s must have a monetary unit measure %(unitID)s"),
                                         modelObject=f, fact=f.qname, contextID=f.contextID, unitID=f.unitID)
                            elif concept.isShares:
                                measures = unit.measures
                                if not measures or len(measures[0]) != 1 or len(measures[1]) != 0:
                                    self.modelXbrl.error("xbrl.4.8.2:sharesFactUnit-notSingleMeasure",
                                        _("Fact %(fact)s context %(contextID)s must have a single xbrli:shares unit %(unitID)s"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, unitID=f.unitID)
                                elif measures[0][0] != XbrlConst.qnXbrliShares:
                                    self.modelXbrl.error("xbrl.4.8.2:sharesFactUnit-notSharesMeasure",
                                        _("Fact %(fact)s context %(contextID)s must have a xbrli:shares unit %(unitID)s"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, unitID=f.unitID)
                    precision = f.precision
                    hasPrecision = precision is not None
                    if hasPrecision and precision != "INF" and not precision.isdigit():
                        self.modelXbrl.error("xbrl.4.6.4:precision",
                            _("Fact %(fact)s context %(contextID)s precision %(precision)s is invalid"),
                            modelObject=f, fact=f.qname, contextID=f.contextID, precision=precision)
                    decimals = f.decimals
                    hasDecimals = decimals is not None
                    if hasPrecision and not self.precisionPattern.match(precision):
                        self.modelXbrl.error("xbrl.4.6.4:precision",
                            _("Fact %(fact)s context %(contextID)s precision %(precision)s is invalid"),
                            modelObject=f, fact=f.qname, contextID=f.contextID, precision=precision)
                    if hasPrecision and hasDecimals:
                        self.modelXbrl.error("xbrl.4.6.3:bothPrecisionAndDecimals",
                            _("Fact %(fact)s context %(contextID)s can not have both precision and decimals"),
                            modelObject=f, fact=f.qname, contextID=f.contextID)
                    if hasDecimals and not self.decimalsPattern.match(decimals):
                        self.modelXbrl.error(_("xbrl.4.6.5:decimals"),
                            _("Fact %(fact)s context %(contextID)s decimals %(decimals)s is invalid"),
                            modelObject=f, fact=f.qname, contextID=f.contextID, decimals=decimals)
                    if concept.isItem:
                        context = f.context
                        if context is None:
                            self.modelXbrl.error("xbrl.4.6.1:itemContextRef",
                                _("Item %(fact)s must have a context"),
                                modelObject=f, fact=f.qname)
                        else:
                            periodType = concept.periodType
                            if (periodType == "instant" and not context.isInstantPeriod) or \
                               (periodType == "duration" and not (context.isStartEndPeriod or context.isForeverPeriod)):
                                self.modelXbrl.error("xbrl.4.7.2:contextPeriodType",
                                    _("Fact %(fact)s context %(contextID)s has period type %(periodType)s conflict with context"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID, periodType=periodType)
                                
                        # check precision and decimals
                        if f.xsiNil == "true":
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.error("xbrl.4.6.3:nilPrecisionDecimals",
                                    _("Fact %(fact)s context %(contextID)s can not be nil and have either precision or decimals"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                        elif concept.isFraction:
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.error("xbrl.4.6.3:fractionPrecisionDecimals",
                                    _("Fact %(fact)s context %(contextID)s is a fraction concept and cannot have either precision or decimals"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                                numerator, denominator = f.fractionValue
                                if not (numerator == "INF" or numerator.isnumeric()):
                                    self.modelXbrl.error("xbrl.5.1.1:fractionPrecisionDecimals",
                                        _("Fact %(fact)s context %(contextID)s is a fraction with invalid numerator %(numerator)s"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, numerator=numerator)
                                if not denominator.isnumeric() or _INT(denominator) == 0:
                                    self.modelXbrl.error("xbrl.5.1.1:fractionPrecisionDecimals",
                                        _("Fact %(fact)s context %(contextID)s is a fraction with invalid denominator %(denominator)")).format(
                                        modelObject=f, fact=f.qname, contextID=f.contextID, denominator=denominator)
                        else:
                            if modelXbrl.modelDocument.type != ModelDocument.Type.INLINEXBRL:
                                for child in f.iterchildren():
                                    if isinstance(child,ModelObject):
                                        self.modelXbrl.error("xbrl.5.1.1:itemMixedContent",
                                            _("Fact %(fact)s context %(contextID)s may not have child elements %(childElementName)s"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, childElementName=child.prefixedName)
                                        break
                            if concept.isNumeric and not hasPrecision and not hasDecimals:
                                self.modelXbrl.error("xbrl.4.6.3:missingPrecisionDecimals",
                                    _("Fact %(fact)s context %(contextID)s is a numeric concept and must have either precision or decimals"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                    elif concept.isTuple:
                        if f.contextID:
                            self.modelXbrl.error("xbrl.4.6.1:tupleContextRef",
                                _("Tuple %(fact)s must not have a context"),
                                modelObject=f, fact=f.qname)
                        if hasPrecision or hasDecimals:
                            self.modelXbrl.error("xbrl.4.6.3:tuplePrecisionDecimals",
                                _("Fact %(fact)s is a tuple and cannot have either precision or decimals"),
                                modelObject=f, fact=f.qname)
                        # custom attributes may be allowed by anyAttribute but not by 2.1
                        for attrQname, attrValue in XbrlUtil.attributes(self.modelXbrl, f):
                            if attrQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
                                self.modelXbrl.error(_("xbrl.4.9:tupleAttribute"),
                                    _("Fact %(fact)s is a tuple and must not have attribute in this namespace %(attribute)s"),
                                    modelObject=f, fact=f.qname, attribute=attrQname), 
                    else:
                        self.modelXbrl.error("xbrl.4.6:notItemOrTuple",
                            _("Fact %(fact)s must be an item or tuple"),
                            modelObject=f, fact=f.qname)
                        
                if isinstance(f, ModelInlineFact):
                    self.footnoteRefs.update(f.footnoteRefs)
                    fmt = f.format
                    if fmt:
                        if fmt.namespaceURI not in FunctionIxt.ixtNamespaceURIs:
                            self.modelXbrl.error("ix.14.2:invalidTransformation",
                                _("Fact %(fact)s has unrecognized transformation namespace %(namespace)s"),
                                modelObject=f, fact=f.qname, namespace=fmt.namespaceURI)
                        elif fmt.localName not in FunctionIxt.ixtFunctions:
                            self.modelXbrl.error("ix.14.2:invalidTransformation",
                                _("Fact %(fact)s has unrecognized transformation name %(name)s"),
                                modelObject=f, fact=f.qname, name=fmt.localName)
                        if fmt.namespaceURI == FunctionIxt.deprecatedNamespaceURI:
                            factsWithDeprecatedIxNamespace.append(f)
                    if f.order is not None: 
                        self.modelXbrl.error("ix.13.1.2:tupleOrder",
                            _("Fact %(fact)s must not have an order (%(order)s) unless in a tuple"),
                            modelObject=f, fact=f.qname, name=fmt.localName, order=f.order)
                    if f.isTuple:
                        self.checkIxTupleContent(f, set())
                        
            if factsWithDeprecatedIxNamespace:
                self.modelXbrl.info("arelle:info",
                    _("%(count)s facts have deprecated transformation namespace %(namespace)s"),
                        modelObject=factsWithDeprecatedIxNamespace,
                        count=len(factsWithDeprecatedIxNamespace), 
                        namespace=FunctionIxt.deprecatedNamespaceURI)

            
            #instance checks
            for cntx in modelXbrl.contexts.values():
                if cntx.isStartEndPeriod:
                    try:
                        if cntx.endDatetime <= cntx.startDatetime:
                            self.modelXbrl.error("xbrl.4.7.2:periodStartBeforeEnd",
                                _("Context %(contextID)s must have startDate less than endDate"),
                                modelObject=cntx, contextID=cntx.id)
                    except (TypeError, ValueError) as err:
                        self.modelXbrl.error("xbrl.4.7.2:contextDateError",
                            _("Context %(contextID) startDate or endDate: %(error)s"),
                            modelObject=cntx, contextID=cntx.id, error=err)
                elif cntx.isInstantPeriod:
                    try:
                        cntx.instantDatetime #parse field
                    except ValueError as err:
                        self.modelXbrl.error("xbrl.4.7.2:contextDateError",
                            _("Context %(contextID)s instant date: %(error)s"),
                            modelObject=cntx, contextID=cntx.id, error=err)
                self.segmentScenario(cntx.segment, cntx.id, "segment", "4.7.3.2")
                self.segmentScenario(cntx.scenario, cntx.id, "scenario", "4.7.4")
                
            for unit in modelXbrl.units.values():
                mulDivMeasures = unit.measures
                if mulDivMeasures:
                    for measures in mulDivMeasures:
                        for measure in measures:
                            if measure.namespaceURI == XbrlConst.xbrli and not \
                                measure in (XbrlConst.qnXbrliPure, XbrlConst.qnXbrliShares):
                                    self.modelXbrl.error("xbrl.4.8.2:measureElement",
                                        _("Unit %(unitID)s illegal measure: %(measure)s"),
                                        modelObject=unit, unitID=unit.id, measure=measure)
                    for numeratorMeasure in mulDivMeasures[0]:
                        if numeratorMeasure in mulDivMeasures[1]:
                            self.modelXbrl.error("xbrl.4.8.4:measureBothNumDenom",
                                _("Unit %(unitID)s numerator measure: %(measure)s also appears as denominator measure"),
                                modelObject=unit, unitID=unit.id, measure=numeratorMeasure)
            modelXbrl.profileStat(_("validateInstance"))

            if modelXbrl.hasXDT:            
                modelXbrl.modelManager.showStatus(_("validating dimensions"))
                for f in modelXbrl.facts:
                    if concept.isItem and f.context is not None:
                        ValidateXbrlDimensions.checkFact(self, f)
                for cntx in modelXbrl.contexts.values():
                    ValidateXbrlDimensions.checkContext(self,cntx)
                modelXbrl.profileStat(_("validateDimensions"))
                    
        # dimensional validity
        #concepts checks
        modelXbrl.modelManager.showStatus(_("validating concepts"))
        for concept in modelXbrl.qnameConcepts.values():
            conceptType = concept.type
            if XbrlConst.isStandardNamespace(concept.qname.namespaceURI) or \
               not concept.modelDocument.inDTS:
                continue
            
            if concept.isTuple:
                # must be global
                if not concept.getparent().localName == "schema":
                    self.modelXbrl.error("xbrl.4.9:tupleGloballyDeclared",
                        _("Tuple %(concept)s must be declared globally"),
                        modelObject=concept, concept=concept.qname)
                if concept.periodType:
                    self.modelXbrl.error("xbrl.4.9:tuplePeriodType",
                        _("Tuple %(concept)s must not have periodType"),
                        modelObject=concept, concept=concept.qname)
                if concept.balance:
                    self.modelXbrl.error("xbrl.4.9:tupleBalance",
                        _("Tuple %(concept)s must not have balance"),
                        modelObject=concept, concept=concept.qname)
                if conceptType is not None:
                    # check attribute declarations
                    for attribute in conceptType.attributes.values():
                        if attribute.qname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
                            self.modelXbrl.error("xbrl.4.9:tupleAttribute",
                                _("Tuple %(concept)s must not have attribute in this namespace %(attribute)s"),
                                modelObject=concept, concept=concept.qname, attribute=attribute.qname)
                    # check for mixed="true" or simple content
                    if XmlUtil.descendantAttr(conceptType, XbrlConst.xsd, ("complexType", "complexContent"), "mixed") == "true":
                        self.modelXbrl.error("xbrl.4.9:tupleMixedContent",
                            _("Tuple %(concept)s must not have mixed content"),
                            modelObject=concept, concept=concept.qname)
                    if XmlUtil.descendant(conceptType, XbrlConst.xsd, "simpleContent"):
                        self.modelXbrl.error("xbrl.4.9:tupleSimpleContent",
                            _("Tuple %(concept)s must not have simple content"),
                            modelObject=concept, concept=concept.qname)
                    # child elements must be item or tuple
                    for elementQname in conceptType.elements:
                        childConcept = self.modelXbrl.qnameConcepts.get(elementQname)
                        if childConcept is None:
                            self.modelXbrl.error("xbrl.4.9:tupleElementUndefined",
                                _("Tuple %(concept)s element %(tupleElement)s not defined"),
                                modelObject=concept, concept=str(concept.qname), tupleElement=elementQname)
                        elif not (childConcept.isItem or childConcept.isTuple or # isItem/isTuple do not include item or tuple itself
                                  childConcept.qname == XbrlConst.qnXbrliItem or # subs group includes item as member
                                  childConcept.qname == XbrlConst.qnXbrliTuple):
                            self.modelXbrl.error("xbrl.4.9:tupleElementItemOrTuple",
                                _("Tuple %(concept)s must not have element %(tupleElement)s not an item or tuple"),
                                modelObject=concept, concept=concept.qname, tupleElement=elementQname)
            elif concept.isItem:
                if concept.periodType not in periodTypeValues: #("instant","duration"):
                    self.modelXbrl.error("xbrl.5.1.1.1:itemPeriodType",
                        _("Item %(concept)s must have a valid periodType"),
                        modelObject=concept, concept=concept.qname)
                if concept.isMonetary:
                    if concept.balance not in balanceValues: #(None, "credit","debit"):
                        self.modelXbrl.error("xbrl.5.1.1.2:itemBalance",
                            _("Item %(concept)s must have a valid balance %(balance)s"),
                            modelObject=concept, concept=concept.qname, balance=concept.balance)
                else:
                    if concept.balance:
                        self.modelXbrl.error("xbrl.5.1.1.2:itemBalance",
                            _("Item %(concept)s may not have a balance"),
                            modelObject=concept, concept=concept.qname)
                if concept.baseXbrliType not in baseXbrliTypes:
                    self.modelXbrl.error("xbrl.5.1.1.3:itemType",
                        _("Item %(concept)s type %(itemType)s invalid"),
                        modelObject=concept, concept=concept.qname, itemType=concept.baseXbrliType)
                if modelXbrl.hasXDT:
                    if concept.isHypercubeItem and not concept.abstract == "true":
                        self.modelXbrl.error("xbrldte:HypercubeElementIsNotAbstractError",
                            _("Hypercube item %(concept)s must be abstract"),
                            modelObject=concept, concept=concept.qname)
                    elif concept.isDimensionItem and not concept.abstract == "true":
                        self.modelXbrl.error("xbrldte:DimensionElementIsNotAbstractError",
                            _("Dimension item %(concept)s must be abstract"),
                            modelObject=concept, concept=concept.qname)
            if modelXbrl.hasXDT:
                ValidateXbrlDimensions.checkConcept(self, concept)
        modelXbrl.profileStat(_("validateConcepts"))
            
        modelXbrl.modelManager.showStatus(_("validating DTS"))
        self.DTSreferenceResourceIDs = {}
        ValidateXbrlDTS.checkDTS(self, modelXbrl.modelDocument, [])
        del self.DTSreferenceResourceIDs
        
        global validateUniqueParticleAttribution
        if validateUniqueParticleAttribution is None:
            from arelle.XmlValidateParticles import validateUniqueParticleAttribution
        for modelType in modelXbrl.qnameTypes.values():
            validateUniqueParticleAttribution(modelXbrl, modelType.particlesList, modelType)
        modelXbrl.profileStat(_("validateDTS"))
        
        if self.validateCalcLB:
            modelXbrl.modelManager.showStatus(_("Validating instance calculations"))
            ValidateXbrlCalcs.validate(modelXbrl, inferDecimals=self.validateInferDecimals)
            modelXbrl.profileStat(_("validateCalculations"))
            
        if (modelXbrl.modelManager.validateUtr or
            (self.parameters and self.parameters.get(qname("forceUtrValidation",noPrefixIsNoNamespace=True),(None,"false"))[1] == "true") or
             #(self.validateEFM and 
             #any((concept.namespaceURI in self.disclosureSystem.standardTaxonomiesDict) 
             #    for concept in self.modelXbrl.nameConcepts.get("UTR",())))):
            (self.validateEFM and any(modelDoc.definesUTR for modelDoc in self.modelXbrl.urlDocs.values()))):
            ValidateUtr.validate(modelXbrl)
            modelXbrl.profileStat(_("validateUTR"))
            
        if modelXbrl.hasFormulae or modelXbrl.modelRenderingTables:
            ValidateFormula.validate(self, 
                                     statusMsg=_("compiling formulae and rendering tables") if (modelXbrl.hasFormulae and modelXbrl.modelRenderingTables)
                                     else (_("compiling formulae") if modelXbrl.hasFormulae
                                           else _("compiling rendering tables")))
            
        modelXbrl.modelManager.showStatus(_("ready"), 2000)
        
    def checkIxTupleContent(self, tf, visited):
        visited.add(tf.qname)
        for f in tf.modelTupleFacts:
            if f.qname in visited:
                self.modelXbrl.error("ix.13.1.2:tupleRecursion",
                    _("Fact %(fact)s is recursively nested in tuple %(tuple)s"),
                    modelObject=f, fact=f.qname, tuple=tf.qname)
            if f.order is None: 
                self.modelXbrl.error("ix.13.1.2:tupleOrder",
                    _("Fact %(fact)s missing an order in tuple %(tuple)s"),
                    modelObject=f, fact=f.qname, tuple=tf.qname)
        visited.discard(tf.qname)
                        
    def fwdCycle(self, relsSet, rels, noUndirected, fromConcepts, cycleType="directed", revCycleRel=None):
        for rel in rels:
            if revCycleRel is not None and rel.isIdenticalTo(revCycleRel):
                continue # don't double back on self in undirected testing
            relTo = rel.toModelObject
            if relTo in fromConcepts: #forms a directed cycle
                return [cycleType,rel]
            fromConcepts.add(relTo)
            nextRels = relsSet.fromModelObject(relTo)
            foundCycle = self.fwdCycle(relsSet, nextRels, noUndirected, fromConcepts)
            if foundCycle is not None:
                foundCycle.append(rel)
                return foundCycle
            fromConcepts.discard(relTo)
            # look for back path in any of the ELRs visited (pass None as ELR)
            if noUndirected:
                foundCycle = self.revCycle(relsSet, relTo, rel, fromConcepts)
                if foundCycle is not None:
                    foundCycle.append(rel)
                    return foundCycle
        return None
    
    def revCycle(self, relsSet, toConcept, turnbackRel, fromConcepts):
        for rel in relsSet.toModelObject(toConcept):
            if not rel.isIdenticalTo(turnbackRel):
                relFrom = rel.fromModelObject
                if relFrom in fromConcepts:
                    return ["undirected",rel]
                fromConcepts.add(relFrom)
                foundCycle = self.revCycle(relsSet, relFrom, turnbackRel, fromConcepts)
                if foundCycle is not None:
                    foundCycle.append(rel)
                    return foundCycle
                fwdRels = relsSet.fromModelObject(relFrom)
                foundCycle = self.fwdCycle(relsSet, fwdRels, True, fromConcepts, cycleType="undirected", revCycleRel=rel)
                if foundCycle is not None:
                    foundCycle.append(rel)
                    return foundCycle
                fromConcepts.discard(relFrom)
        return None
    
    def segmentScenario(self, element, contextId, name, sect, topLevel=True):
        if topLevel:
            if element is None:
                return  # nothing to check
        else:
            if element.namespaceURI == XbrlConst.xbrli:
                self.modelXbrl.error("xbrl.{0}:{1}XbrliElement".format(sect,name),
                    _("Context %(contextID)s %(contextElement)s cannot have xbrli element %(elementName)s"),
                    modelObject=element, contextID=contextId, contextElement=name, elementName=element.prefixedName)
            else:
                concept = self.modelXbrl.qnameConcepts.get(qname(element))
                if concept is not None and (concept.isItem or concept.isTuple):
                    self.modelXbrl.error("xbrl.{0}:{1}ItemOrTuple".format(sect,name),
                        _("Context %(contextID)s %(contextElement)s cannot have item or tuple element %(elementName)s"),
                        modelObject=element, contextID=contextId, contextElement=name, elementName=element.prefixedName)
        hasChild = False
        for child in element.iterchildren():
            if isinstance(child,ModelObject):
                self.segmentScenario(child, contextId, name, sect, topLevel=False)
                hasChild = True
        if topLevel and not hasChild:
            self.modelXbrl.error("xbrl.{0}:{1}Empty".format(sect,name),
                _("Context %(contextID)s %(contextElement)s cannot be empty"),
                modelObject=element, contextID=contextId, contextElement=name)
        
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
                
