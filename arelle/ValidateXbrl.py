'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import regex as re
from typing import Any, cast
from arelle import (XmlUtil, XbrlUtil, XbrlConst,
                ValidateXbrlCalcs, ValidateXbrlDimensions, ValidateXbrlDTS, ValidateFormula, ValidateUtr)
from arelle.ModelDocument import ModelDocument, Type as ModelDocumentType
from arelle import FunctionIxt
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelContext, ModelDimensionValue, ModelInlineFact
from arelle.ModelValue import qname
from arelle.ModelXbrl import ModelXbrl
from arelle.PluginManager import pluginClassMethods
from arelle.ValidateXbrlCalcs import inferredDecimals
from arelle.XbrlConst import (ixbrlAll, dtrNoDecimalsItemTypes, dtrPrefixedContentItemTypes, dtrPrefixedContentTypes,
                              dtrSQNameItemTypes, dtrSQNameTypes,  dtrSQNamesItemTypes, dtrSQNamesTypes)
from arelle.XhtmlValidate import ixMsgCode
from arelle.XmlValidate import VALID
from collections import defaultdict
from arelle.typing import TypeGetText
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelDtsObject import ModelRelationship
from arelle.ModelFormulaObject import ModelCustomFunctionSignature
from arelle.XmlValidateParticles import validateUniqueParticleAttribution
from arelle.ModelDtsObject import ModelLink
from arelle.ModelValue import QName
from lxml.etree import _Element
from arelle.ModelInstanceObject import ModelUnit
from collections.abc import Iterable

_: TypeGetText  # Handle gettext


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

    authority: str | None
    authParam: dict[str, Any]
    consolidated: bool
    domainMembers: set[ModelConcept]
    DTSreferenceResourceIDs: dict[str, Any]
    extensionImportedUrls: set[str]
    genericArcArcroles: set[str]
    hasExtensionCal: bool
    hasExtensionDef: bool
    hasExtensionLbl: bool
    hasExtensionPre: bool
    hasExtensionSchema: bool
    ixdsDocs: list[ModelDocument]
    ixdsFootnotes: dict[str, Any]
    ixdsHeaderCount: int
    ixdsReferences: dict[str, Any]
    ixdsRelationships: list[dict[Any, Any]]
    ixdsRoleRefURIs: dict[Any, Any]
    ixdsArcroleRefURIs: dict[Any, Any]
    unconsolidated: bool
    validateESEFplugin: bool
    priorFormulaOptionsRunIDs: str | None
    primaryItems: set[Any]
    remoteResourceLocElements: set[ModelObject]

    def __init__(self, testModelXbrl: ModelXbrl) -> None:
        self.testModelXbrl = testModelXbrl

    def close(self, reusable: bool = True) -> None:
        if reusable:
            testModelXbrl = self.testModelXbrl
        self.__dict__.clear()   # dereference everything
        if reusable:
            self.testModelXbrl = testModelXbrl

    def validate(self, modelXbrl: ModelXbrl, parameters: dict[Any, Any] | None = None) -> None:
        self.parameters = parameters
        self.precisionPattern = re.compile("^([0-9]+|INF)$")
        self.decimalsPattern = re.compile("^(-?[0-9]+|INF)$")
        self.isoCurrencyPattern = re.compile(r"^[A-Z]{3}$")
        self.modelXbrl: ModelXbrl = modelXbrl
        self.validateDisclosureSystem = modelXbrl.modelManager.validateDisclosureSystem
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        self.validateEFM = self.validateDisclosureSystem and self.disclosureSystem.EFM  # deprecated non-plugin validators
        self.validateGFM = self.validateDisclosureSystem and self.disclosureSystem.GFM
        self.validateEFMorGFM = self.validateDisclosureSystem and self.disclosureSystem.EFMorGFM
        self.validateHMRC = self.validateDisclosureSystem and self.disclosureSystem.HMRC
        self.validateSBRNL = self.validateDisclosureSystem and self.disclosureSystem.SBRNL
        self.validateEFMorGFMorSBRNL = self.validateEFMorGFM or self.validateSBRNL
        self.validateXmlLang = self.validateDisclosureSystem and self.disclosureSystem.xmlLangPattern
        self.validateCalcLB = modelXbrl.modelManager.validateCalcLB
        self.validateInferDecimals = modelXbrl.modelManager.validateInferDecimals
        self.validateDedupCalcs = modelXbrl.modelManager.validateDedupCalcs
        self.validateUTR = (modelXbrl.modelManager.validateUtr or
                            (self.parameters and self.parameters.get(qname("forceUtrValidation",noPrefixIsNoNamespace=True),(None,"false"))[1] == "true") or
                            (self.validateEFM and
                             any((concept.qname.namespaceURI in self.disclosureSystem.standardTaxonomiesDict and concept.modelDocument.inDTS)
                                 for concept in self.modelXbrl.nameConcepts.get("UTR",()))))
        self.validateIXDS = False # set when any inline document found
        self.validateEnum = bool(XbrlConst.enums & modelXbrl.namespaceDocs.keys())

        for pluginXbrlMethod in pluginClassMethods("Validate.XBRL.Start"):
            pluginXbrlMethod(self, parameters)

        # xlink validation
        modelXbrl.profileStat(None)
        modelXbrl.modelManager.showStatus(_("validating links"))
        modelLinks = set()
        self.remoteResourceLocElements = set()
        self.genericArcArcroles = set()
        for baseSetExtLinks in modelXbrl.baseSets.values():
            for baseSetExtLink in baseSetExtLinks:
                modelLinks.add(baseSetExtLink)    # ext links are unique (no dups)
        self.checkLinks(modelLinks)
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
                                      or arcrole.startswith(XbrlConst.formulaStartsWith) \
                                      or (modelXbrl.hasXDT and arcrole.startswith(XbrlConst.dimStartsWith)):
                relsSet = modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname)
            if cyclesAllowed != "any" and \
                   ((XbrlConst.isStandardExtLinkQname(linkqname) and XbrlConst.isStandardArcQname(arcqname)) \
                    or arcrole in self.genericArcArcroles):
                noUndirected = cyclesAllowed == "none"
                fromRelationships = relsSet.fromModelObjects()
                for relFrom, rels in fromRelationships.items():
                    cycleFound = cast(list[ModelRelationship], self.fwdCycle(relsSet, rels, noUndirected, {relFrom}))

                    if cycleFound is not None:
                        pathEndsAt = len(cycleFound)  # consistently find start of path

                        loopedModelObject = cycleFound[1].toModelObject
                        for i, rel in enumerate(cycleFound[2:]):
                            if rel.fromModelObject == loopedModelObject:
                                pathEndsAt = 3 + i # don't report extra path elements before loop
                                break

                        reversed_list = reversed(cycleFound[1:pathEndsAt])
                        path = str(loopedModelObject.qname) + " " + " - ".join(
                            "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, rel.toModelObject.qname)
                            for rel in reversed_list)

                        modelXbrl.error(cast(str, specSect),
                            _("Relationships have a %(cycle)s cycle in arcrole %(arcrole)s \nlink role %(linkrole)s \nlink %(linkname)s, \narc %(arcname)s, \npath %(path)s"),
                            modelObject=cycleFound[1:pathEndsAt], cycle=cycleFound[0], path=path,
                            arcrole=arcrole, linkrole=ELR, linkname=linkqname, arcname=arcqname,
                            messageCodes=("xbrlgene:violatedCyclesConstraint", "xbrl.5.1.4.3:cycles",
                                          # from XbrlCoinst.standardArcroleCyclesAllowed
                                          "xbrl.5.2.4.2", "xbrl.5.2.5.2", "xbrl.5.2.6.2.1", "xbrl.5.2.6.2.1", "xbrl.5.2.6.2.3", "xbrl.5.2.6.2.4"))
                        break

            # check calculation arcs for weight issues (note calc arc is an "any" cycles)
            if arcrole == XbrlConst.summationItem:
                for modelRel in relsSet.modelRelationships:
                    weight = modelRel.weight
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if weight == 0:
                            modelXbrl.error("xbrl.5.2.5.2.1:zeroWeight", # type: ignore[func-returns-value]
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
                                    sourceBalance=fromBalance, targetBalance=toBalance,
                                    messageCodes=("xbrl.5.1.1.2:balanceCalcWeightIllegalNegative", "xbrl.5.1.1.2:balanceCalcWeightIllegalPositive"))
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
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if preferredLabel is not None and isinstance(fromConcept, ModelConcept) and isinstance(toConcept, ModelConcept):
                        label = toConcept.label(preferredLabel=preferredLabel,fallbackToQname=False,strip=True)
                        if label is None:
                            modelXbrl.error("xbrl.5.2.4.2.1:preferredLabelMissing",
                                _("Presentation relationship from %(source)s to %(target)s in link role %(linkrole)s missing preferredLabel %(preferredLabel)s"),
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR,
                                preferredLabel=preferredLabel)
                        elif not label: # empty string
                            modelXbrl.info("arelle:info.preferredLabelEmpty",
                                _("(Info xbrl.5.2.4.2.1) Presentation relationship from %(source)s to %(target)s in link role %(linkrole)s has empty preferredLabel %(preferredLabel)s"),
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR,
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
                                modelXbrl.error("xbrl.5.2.6.2.2:essenceAliasBalance",  # type: ignore[func-returns-value]
                                    _("Essence-alias relationship from %(source)s to %(target)s in link role %(linkrole)s has different balances")).format(
                                    modelObject=modelRel,
                                    source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
            elif modelXbrl.hasXDT and arcrole.startswith(XbrlConst.dimStartsWith):
                ValidateXbrlDimensions.checkBaseSet(self, arcrole, ELR, relsSet)
            elif arcrole in ValidateFormula.arcroleChecks:
                ValidateFormula.checkBaseSet(self, arcrole, ELR, relsSet)
        modelXbrl.isDimensionsValidated = True
        modelXbrl.profileStat(_("validateRelationships"))

        # instance checks
        modelXbrl.modelManager.showStatus(_("validating instance"))
        assert modelXbrl.modelDocument is not None
        if modelXbrl.modelDocument.type in (ModelDocumentType.INSTANCE, ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET):
            self.checkFacts(modelXbrl.facts)
            self.checkContexts(self.modelXbrl.contexts.values())
            self.checkUnits(self.modelXbrl.units.values())

            modelXbrl.profileStat(_("validateInstance"))

            if modelXbrl.hasXDT:
                modelXbrl.modelManager.showStatus(_("validating dimensions"))
                ''' uncomment if using otherFacts in checkFact
                dimCheckableFacts = set(f
                                        for f in modelXbrl.factsInInstance
                                        if f.concept.isItem and f.context is not None)
                while (dimCheckableFacts): # check one and all of its compatible family members
                    f = dimCheckableFacts.pop()
                    ValidateXbrlDimensions.checkFact(self, f, dimCheckableFacts)
                del dimCheckableFacts
                '''
                self.checkFactsDimensions(modelXbrl.facts) # check fact dimensions in document order
                self.checkContextsDimensions(modelXbrl.contexts.values())
                modelXbrl.profileStat(_("validateDimensions"))

        # dimensional validity
        #concepts checks
        modelXbrl.modelManager.showStatus(_("validating concepts"))
        for concept in modelXbrl.qnameConcepts.values():
            conceptType = concept.type
            if (concept.qname is None or
                XbrlConst.isStandardNamespace(concept.qname.namespaceURI) or
                not concept.modelDocument.inDTS):
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
                        if attribute.qname is not None and attribute.qname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
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
            if self.validateEnum and concept.isEnumeration: # either a enum item type or enum set dimension type
                if not concept.enumDomainQname:
                    self.modelXbrl.error(("enum2te:" if concept.instanceOfType(XbrlConst.qnEnumeration2ItemTypes) else "enumte:") +
                                         "MissingDomainError",
                        _("Item %(concept)s enumeration type must specify a domain."),
                        modelObject=concept, concept=concept.qname,
                        messageCodes=("enumte:MissingDomainError", "enum2te:MissingDomainError"))
                elif concept.enumDomain is None or (not concept.enumDomain.isItem) or concept.enumDomain.isHypercubeItem or concept.enumDomain.isDimensionItem:
                    self.modelXbrl.error(("enum2te:" if concept.instanceOfType(XbrlConst.qnEnumeration2ItemTypes) else "enumte:") +
                                         "InvalidDomainError",
                        _("Item %(concept)s enumeration type must be a xbrli:item that is neither a hypercube nor dimension."),
                        modelObject=concept, concept=concept.qname,
                        messageCodes=("enumte:InvalidDomainError", "enum2te:InvalidDomainError"))
                if not concept.enumLinkrole:
                    self.modelXbrl.error(("enum2te:" if concept.instanceOfType(XbrlConst.qnEnumeration2ItemTypes) else "enumte:") +
                                         "MissingLinkRoleError",
                        _("Item %(concept)s enumeration type must specify a linkrole."),
                        modelObject=concept, concept=concept.qname,
                        messageCodes=("enumte:MissingLinkRoleError", "enum2te:MissingLinkRoleError"))
            if modelXbrl.hasXDT:
                ValidateXbrlDimensions.checkConcept(self, concept)
        modelXbrl.profileStat(_("validateConcepts"))

        for pluginXbrlMethod in pluginClassMethods("Validate.XBRL.Finally"):
            pluginXbrlMethod(self)

        modelXbrl.profileStat() # reset after plugins

        modelXbrl.modelManager.showStatus(_("validating DTS"))
        self.DTSreferenceResourceIDs = {}
        checkedModelDocuments: set[ModelDocument] = set()
        assert modelXbrl.modelDocument is not None
        ValidateXbrlDTS.checkDTS(self, modelXbrl.modelDocument, checkedModelDocuments)
        # ARELLE-220: check imported documents that aren't DTS discovered
        for importedModelDocument in (set(modelXbrl.urlDocs.values()) - checkedModelDocuments):
            ValidateXbrlDTS.checkDTS(self, importedModelDocument, checkedModelDocuments)
        del checkedModelDocuments, self.DTSreferenceResourceIDs

        for modelType in modelXbrl.qnameTypes.values():
            validateUniqueParticleAttribution(modelXbrl, modelType.particlesList, modelType)
        modelXbrl.profileStat(_("validateDTS"))

        if self.validateCalcLB:
            modelXbrl.modelManager.showStatus(_("Validating instance calculations"))
            ValidateXbrlCalcs.validate(modelXbrl,
                                       inferDecimals=self.validateInferDecimals,
                                       deDuplicate=self.validateDedupCalcs)
            modelXbrl.profileStat(_("validateCalculations"))

        if self.validateUTR:
            ValidateUtr.validateFacts(modelXbrl)
            modelXbrl.profileStat(_("validateUTR"))

        if self.validateIXDS:
            modelXbrl.modelManager.showStatus(_("Validating inline document set"))
            assert modelXbrl.modelDocument is not None
            _ixNS = modelXbrl.modelDocument.ixNS
            ixdsIdObjects = defaultdict(list)
            for ixdsDoc in self.ixdsDocs:
                for idObject in ixdsDoc.idObjects.values():
                    if idObject.namespaceURI in ixbrlAll or idObject.elementQname in (XbrlConst.qnXbrliContext, XbrlConst.qnXbrliUnit):
                        ixdsIdObjects[idObject.id].append(idObject)
            for _id, objs in ixdsIdObjects.items():
                if len(objs) > 1:
                    idObject = objs[0]
                    modelXbrl.error(ixMsgCode("uniqueIxId", idObject, sect="validation"),
                        _("Inline XBRL id is not unique in the IXDS: %(id)s, for element(s) %(elements)s"),
                        modelObject=objs, id=_id, elements=",".join(sorted(set(str(obj.elementQname) for obj in objs))))
            self.factsWithDeprecatedIxNamespace = []
            factFootnoteRefs = set()
            undefinedFacts = []
            for f in modelXbrl.factsInInstance:
                for footnoteID in f.footnoteRefs:
                    if footnoteID not in self.ixdsFootnotes:
                        modelXbrl.error(ixMsgCode("footnoteRef", f, name="footnote", sect="validation"),
                            _("Inline XBRL fact's footnoteRef not found: %(id)s"),
                            modelObject=f, id=footnoteID)
                    factFootnoteRefs.add(footnoteID)
                if f.concept is None:
                    undefinedFacts.append(f)
                if f.localName in {"fraction", "nonFraction", "nonNumeric"}:
                    if f.context is None:
                        self.modelXbrl.error(ixMsgCode("contextReference", f, sect="validation"),
                            _("Fact %(fact)s is missing a context for contextRef %(context)s"),
                            modelObject=f, fact=f.qname, context=f.contextID)
                if f.localName in {"fraction", "nonFraction"}:
                    if f.unit is None:
                        self.modelXbrl.error(ixMsgCode("unitReference", f, sect="validation"),
                            _("Fact %(fact)s is missing a unit for unitRef %(unit)s"),
                            modelObject=f, fact=f.qname, unit=f.unitID)
                fmt = f.format
                if fmt:
                    if fmt.namespaceURI == FunctionIxt.deprecatedNamespaceURI:
                        self.factsWithDeprecatedIxNamespace.append(f)
            if undefinedFacts:
                self.modelXbrl.error("xbrl:schemaImportMissing",
                        _("Instance facts missing schema concept definition: %(elements)s"),
                        modelObject=undefinedFacts, elements=", ".join(sorted(set(str(f.qname) for f in undefinedFacts))))
            del undefinedFacts # dereference facts
            for _id, objs in self.ixdsFootnotes.items():
                if len(objs) > 1:
                    modelXbrl.error(ixMsgCode("uniqueFootnoteId", ns=_ixNS, name="footnote", sect="validation"),
                        _("Inline XBRL footnote id is not unique in the IXDS: %(id)s"),
                        modelObject=objs, id=_id)
                else:
                    if self.validateGFM:
                        elt = objs[0]
                        id = elt.footnoteID
                        if id and id not in factFootnoteRefs and elt.textValue:
                            self.modelXbrl.error(("EFM.N/A", "GFM:1.10.15"),
                                _("Inline XBRL non-empty footnote %(footnoteID)s is not referenced by any fact"),
                                modelObject=elt, footnoteID=id)
            if not self.ixdsHeaderCount:
                modelXbrl.error(ixMsgCode("headerMissing", ns=_ixNS, name="header", sect="validation"),
                    _("Inline XBRL document set must have at least one ix:header element"),
                    modelObject=modelXbrl)
            if self.factsWithDeprecatedIxNamespace:
                self.modelXbrl.info("arelle:info",
                    _("%(count)s facts have deprecated transformation namespace %(namespace)s"),
                        modelObject=self.factsWithDeprecatedIxNamespace,
                        count=len(self.factsWithDeprecatedIxNamespace),
                        namespace=FunctionIxt.deprecatedNamespaceURI)

            del self.factsWithDeprecatedIxNamespace
            for target, ixReferences in self.ixdsReferences.items():
                targetDefaultNamespace = None
                schemaRefUris = {}
                for i, ixReference in enumerate(ixReferences):
                    defaultNamepace = XmlUtil.xmlns(ixReference, None)
                    if i == 0:
                        targetDefaultNamespace = defaultNamepace
                    elif targetDefaultNamespace != defaultNamepace:
                        modelXbrl.error(ixMsgCode("referenceInconsistentDefaultNamespaces", ns=_ixNS, sect="validation"),
                            _("Inline XBRL document set must have consistent default namespaces for target %(target)s"),
                            modelObject=ixReferences, target=target)
                    for schemaRef in XmlUtil.children(ixReference, XbrlConst.link, "schemaRef"):
                        href = schemaRef.get("{http://www.w3.org/1999/xlink}href")
                        prefix = XmlUtil.xmlnsprefix(schemaRef, href)
                        if href not in schemaRefUris:
                            schemaRefUris[href] = prefix
                        elif schemaRefUris[href] != prefix:
                            modelXbrl.error(ixMsgCode("referenceNamespacePrefixInconsistency", ns=_ixNS, sect="validation"),
                                _("Inline XBRL document set must have consistent prefixes for target %(target)s: %(prefix1)s, %(prefix2)s"),
                                modelObject=ixReferences, target=target, prefix1=schemaRefUris[href], prefix2=prefix)
            for ixRel in self.ixdsRelationships:
                for fromRef in ixRel.get("fromRefs","").split():
                    refs = ixdsIdObjects.get(fromRef)
                    if refs is None or refs[0].namespaceURI not in ixbrlAll or refs[0].localName not in ("fraction", "nonFraction", "nonNumeric", "tuple"):
                        modelXbrl.error(ixMsgCode("relationshipFromRef", ns=_ixNS, name="relationship", sect="validation"),
                            _("Inline XBRL fromRef %(ref)s is not a fraction, ix:nonFraction, ix:nonNumeric or ix:tuple."),
                            modelObject=ixRel, ref=fromRef)
                hasFootnoteToRef = None
                hasToRefMixture = False
                for toRef in ixRel.get("toRefs","").split():
                    refs = ixdsIdObjects.get(toRef)
                    if refs is None or refs[0].namespaceURI not in ixbrlAll or refs[0].localName not in ("footnote", "fraction", "nonFraction", "nonNumeric", "tuple"):
                        modelXbrl.error(ixMsgCode("relationshipToRef", ns=_ixNS, name="relationship", sect="validation"),
                            _("Inline XBRL toRef %(ref)s is not a footnote, fraction, ix:nonFraction, ix:nonNumeric or ix:tuple."),
                            modelObject=ixRel, ref=toRef)
                    elif hasFootnoteToRef is None:
                        hasFootnoteToRef = refs[0].localName == "footnote"
                    elif hasFootnoteToRef != (refs[0].localName == "footnote"):
                        hasToRefMixture = True
                if hasToRefMixture:
                    modelXbrl.error(ixMsgCode("relationshipToRefMix", ns=_ixNS, name="relationship", sect="validation"),
                        _("Inline XBRL fromRef is not only either footnotes, or ix:fraction, ix:nonFraction, ix:nonNumeric or ix:tuple."),
                        modelObject=ixRel)
                if ixRel in modelXbrl.targetRelationships: # XBRL 2.1 role checks for ixRelationships used in target
                    if ixRel.get("linkRole") is not None:
                        ValidateXbrlDTS.checkLinkRole(self, ixRel, XbrlConst.qnLinkFootnoteLink, ixRel.get("linkRole"), "extended", self.ixdsRoleRefURIs)
                    if ixRel.get("arcrole") is not None:
                        ValidateXbrlDTS.checkArcrole(self, ixRel, XbrlConst.qnLinkFootnoteArc, ixRel.get("arcrole"), self.ixdsArcroleRefURIs)


            del ixdsIdObjects
            # tupleRefs already checked during loading
            modelXbrl.profileStat(_("validateInline"))

        if modelXbrl.hasFormulae or modelXbrl.modelRenderingTables:
            ValidateFormula.validate(self,
                                     statusMsg=_("compiling formulae and rendering tables") if (modelXbrl.hasFormulae and modelXbrl.modelRenderingTables)
                                     else (_("compiling formulae") if modelXbrl.hasFormulae
                                           else _("compiling rendering tables")),
                                     # block executing formulas when validating if hasFormula is False (e.g., --formula=none)
                                     compileOnly=modelXbrl.modelRenderingTables and not modelXbrl.hasFormulae)

        for pluginXbrlMethod in pluginClassMethods("Validate.Finally"):
            pluginXbrlMethod(self)

        modelXbrl.modelManager.showStatus(_("ready"), 2000)

    def checkLinks(self, modelLinks: set[ModelLink]) -> None:
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
                            self.modelXbrl.error("xlink:locatorHref",
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
                            self.modelXbrl.error("xlink:dupArcs",
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
                            assert arcrole is not None
                            self.genericArcArcroles.add(arcrole)
                            if arcrole in (XbrlConst.elementLabel, XbrlConst.elementReference):
                                resourceArcTos.append((toLabel, arcrole, arcElt))
                    # values of type (not needed for validating parsers)
                    if xlinkType not in xlinkTypeValues: # ("", "simple", "extended", "locator", "arc", "resource", "title", "none"):
                        self.modelXbrl.error("xlink:type",
                            _("Xlink type %(xlinkType)s invalid in extended link %(linkrole)s"),
                            modelObject=arcElt, linkrole=modelLink.role, xlinkType=xlinkType)
                    # values of actuate (not needed for validating parsers)
                    xlinkActuate = arcElt.get("{http://www.w3.org/1999/xlink}actuate")
                    if xlinkActuate not in xlinkActuateValues: # ("", "onLoad", "onRequest", "other", "none"):
                        self.modelXbrl.error("xlink:actuate",
                            _("Actuate %(xlinkActuate)s invalid in extended link %(linkrole)s"),
                            modelObject=arcElt, linkrole=modelLink.role, xlinkActuate=xlinkActuate)
                    # values of show (not needed for validating parsers)
                    xlinkShow = arcElt.get("{http://www.w3.org/1999/xlink}show")
                    if xlinkShow not in xlinkShowValues: # ("", "new", "replace", "embed", "other", "none"):
                        self.modelXbrl.error("xlink:show",
                            _("Show %(xlinkShow)s invalid in extended link %(linkrole)s"),
                            modelObject=arcElt, linkrole=modelLink.role, xlinkShow=xlinkShow)
            # check from, to of arcs have a resource or loc
            for fromTo, arcElt in fromToArcs.items():
                fromLabel, toLabel = fromTo
                for name, value, sect in (("from", fromLabel, "3.5.3.9.2"),("to",toLabel, "3.5.3.9.3")):
                    if value not in locLabels and value not in resourceLabels:
                        self.modelXbrl.error("xbrl.{0}:arcResource".format(sect),
                            _("Arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s attribute '%(attribute)s' has no matching loc or resource label"),
                            modelObject=arcElt,
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel,
                            attribute=name,
                            messageCodes=("xbrl.3.5.3.9.2:arcResource", "xbrl.3.5.3.9.3:arcResource"))
                if arcElt.localName == "footnoteArc" and arcElt.namespaceURI == XbrlConst.link and \
                   arcElt.get("{http://www.w3.org/1999/xlink}arcrole") == XbrlConst.factFootnote:
                    if fromLabel not in locLabels:
                        self.modelXbrl.error("xbrl.4.11.1.3.1:factFootnoteArcFrom",
                            _("Footnote arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s \"from\" is not a loc"),
                            modelObject=arcElt,
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
                    if not((toLabel in resourceLabels and resourceLabels[toLabel] is not None
                              and resourceLabels[toLabel].qname == XbrlConst.qnLinkFootnote) or
                           (toLabel in locLabels and locLabels[toLabel].dereference() is not None # type: ignore[attr-defined]
                              and locLabels[toLabel].dereference().qname == XbrlConst.qnLinkFootnote)): # type: ignore[attr-defined]
                        self.modelXbrl.error("xbrl.4.11.1.3.1:factFootnoteArcTo",
                            _("Footnote arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s \"to\" is not a footnote resource"),
                            modelObject=arcElt,
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
            # check unprohibited label arcs to remote locs
            for resourceArcTo in resourceArcTos:
                resourceArcToLabel, resourceArcUse, arcElt = resourceArcTo
                if resourceArcToLabel in locLabels:
                    newToLabel = locLabels[resourceArcToLabel]

                    if resourceArcUse == "prohibited":
                        self.remoteResourceLocElements.add(newToLabel)
                    else:
                        self.modelXbrl.error("xbrl.5.2.2.3:labelArcRemoteResource",
                            _("Unprohibited labelArc in extended link %(linkrole)s has illegal remote resource loc labeled %(xlinkLabel)s href %(xlinkHref)s"),
                            modelObject=arcElt,
                            linkrole=modelLink.role,
                            xlinkLabel=resourceArcToLabel,
                            xlinkHref=newToLabel.get("{http://www.w3.org/1999/xlink}href"))
                elif resourceArcToLabel in resourceLabels:
                    toResource = resourceLabels[resourceArcToLabel]
                    if resourceArcUse == XbrlConst.elementLabel:
                        if not self.isGenericLabel(toResource):
                            self.modelXbrl.error("xbrlle.2.1.1:genericLabelTarget",
                                _("Generic label arc in extended link %(linkrole)s to %(xlinkLabel)s must target a generic label"),
                                modelObject=arcElt,
                                linkrole=modelLink.role,
                                xlinkLabel=resourceArcToLabel)
                    elif resourceArcUse == XbrlConst.elementReference:
                        if not self.isGenericReference(toResource):
                            self.modelXbrl.error("xbrlre.2.1.1:genericReferenceTarget",
                                _("Generic reference arc in extended link %(linkrole)s to %(xlinkLabel)s must target a generic reference"),
                                modelObject=arcElt,
                                linkrole=modelLink.role,
                                xlinkLabel=resourceArcToLabel)

    def checkFacts(self, facts: list[ModelInlineFact], inTuple: dict[Any, Any] | None = None) -> None:  # do in document order
        for f in facts:
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
                    self.modelXbrl.error("xbrl.4.6.5:decimals",
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
                    if f.isNil:
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
                            if not denominator.isnumeric() or int(denominator) == 0:
                                self.modelXbrl.error("xbrl.5.1.1:fractionPrecisionDecimals",
                                    _("Fact %(fact)s context %(contextID)s is a fraction with invalid denominator %(denominator)"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID, denominator=denominator)
                    else:
                        assert self.modelXbrl.modelDocument is not None
                        if self.modelXbrl.modelDocument.type not in (ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET):
                            for child in f.iterchildren():
                                if isinstance(child,ModelObject):
                                    self.modelXbrl.error("xbrl.5.1.1:itemMixedContent",
                                        _("Fact %(fact)s context %(contextID)s may not have child elements %(childElementName)s"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, childElementName=child.prefixedName)
                                    break
                        if concept.isNumeric:
                            if not hasPrecision and not hasDecimals:
                                self.modelXbrl.error("xbrl.4.6.3:missingPrecisionDecimals",
                                    _("Fact %(fact)s context %(contextID)s is a numeric concept and must have either precision or decimals"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                            elif f.concept.instanceOfType(dtrNoDecimalsItemTypes) and inferredDecimals(f) > 0:
                                self.modelXbrl.error("dtre:noDecimalsItemType",
                                    _("Fact %(fact)s context %(contextID)s is a may not have inferred decimals value > 0: %(inferredDecimals)s"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID, inferredDecimals=inferredDecimals(f))
                        else:
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.error("xbrl.4.6.3:extraneousPrecisionDecimals",
                                    _("Fact %(fact)s context %(contextID)s is a non-numeric concept and must not have precision or decimals"),
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                            if getattr(f,"xValid", 0) == 4:
                                if f.concept.instanceOfType(dtrSQNameItemTypes):
                                    if not f.nsmap.get(f.xValue.rpartition(":")[0]):
                                        self.modelXbrl.error("dtre:SQNameItemType",
                                            _("Fact %(fact)s context %(contextID)s must have an in-scope prefix: %(value)s"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, value=f.xValue[:200])
                                elif f.concept.instanceOfType(dtrSQNamesItemTypes):
                                    if not all(f.nsmap.get(n.rpartition(":")[0]) for n in f.xValue.split()):
                                        self.modelXbrl.error("dtre:SQNamesItemType",
                                            _("Fact %(fact)s context %(contextID)s must have an in-scope prefix: %(value)s"),
                                            modelObject=f, fact=f.qname, contextID=f.contextID, value=f.xValue[:200])
                                elif f.concept.instanceOfType(dtrPrefixedContentItemTypes):
                                    self.modelXbrl.error("dtre:prefixedContentItemType",
                                        _("Fact %(fact)s context %(contextID)s must not have an unrecognized subtype of dtr:prefixedContentItemType"),
                                        modelObject=f, fact=f.qname, contextID=f.contextID, value=f.xValue[:200])
                        # not a real check
                        #if f.isNumeric and not f.isNil and f.precision :
                        #    try:
                        #        ValidateXbrlCalcs.roundValue(f.value, f.precision, f.decimals)
                        #    except Exception as err:
                        #        self.modelXbrl.error("arelle:info",
                        #            _("Fact %(fact)s value %(value)s context %(contextID)s rounding exception %(error)s"),
                        #            modelObject=f, fact=f.qname, value=f.value, contextID=f.contextID, error = err)
                    if self.validateEnum and concept.isEnumeration and getattr(f,"xValid", 0) == 4 and not f.isNil:
                        qnEnums = f.xValue
                        if not isinstance(qnEnums, list): qnEnums = (qnEnums,)
                        if not all(ValidateXbrlDimensions.enumerationMemberUsable(self, concept, self.modelXbrl.qnameConcepts.get(qnEnum))
                                   for qnEnum in qnEnums):
                            self.modelXbrl.error(
                                ("enum2ie:InvalidEnumerationSetValue" if concept.instanceOfType(XbrlConst.qnEnumerationSetItemTypes)
                                 else "enum2ie:InvalidEnumerationValue") if concept.instanceOfType(XbrlConst.qnEnumeration2ItemTypes)
                                else ("InvalidListFactValue" if concept.instanceOfType(XbrlConst.qnEnumerationListItemTypes)
                                      else "InvalidFactValue"),
                                _("Fact %(fact)s context %(contextID)s enumeration %(value)s is not in the domain of %(concept)s"),
                                modelObject=f, fact=f.qname, contextID=f.contextID, value=f.xValue, concept=f.qname,
                                messageCodes=("enumie:InvalidFactValue", "enumie:InvalidListFactValue",
                                              "enum2ie:InvalidEnumerationValue", "enum2ie:InvalidEnumerationSetValue"))
                        if concept.instanceOfType(XbrlConst.qnEnumerationSetItemTypes) and len(qnEnums) > len(set(qnEnums)):
                            self.modelXbrl.error(("enum2ie:" if concept.instanceOfType(XbrlConst.qnEnumeration2ItemTypes)
                                                  else "enumie:") +
                                                 "RepeatedEnumerationSetValue",
                                _("Fact %(fact)s context %(contextID)s enumeration has non-unique values %(value)s"),
                                modelObject=f, fact=f.qname, contextID=f.contextID, value=f.xValue, concept=f.qname,
                                messageCodes=("enumie:RepeatedEnumerationSetValue", "enum2ie:RepeatedEnumerationSetValue"))
                        if concept.instanceOfType(XbrlConst.qnEnumerationSetItemTypes) and any(
                                qnEnum < qnEnums[i] for i, qnEnum in enumerate(qnEnums[1:])):
                            self.modelXbrl.error("enum2ie:InvalidEnumerationSetOrder",
                                _("Fact %(fact)s context %(contextID)s enumeration is not in lexicographical order %(value)s"),
                                modelObject=f, fact=f.qname, contextID=f.contextID, value=f.xValue, concept=f.qname)

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
                            self.modelXbrl.error("xbrl.4.9:tupleAttribute",
                                _("Fact %(fact)s is a tuple and must not have attribute in this namespace %(attribute)s"),
                                modelObject=f, fact=f.qname, attribute=attrQname)
                else:
                    self.modelXbrl.error("xbrl.4.6:notItemOrTuple",
                        _("Fact %(fact)s must be an item or tuple"),
                        modelObject=f, fact=f.qname)

            if isinstance(f, ModelInlineFact):
                if not inTuple and f.order is not None:
                    self.modelXbrl.error(ixMsgCode("tupleOrder", f, sect="validation"),
                        _("Fact %(fact)s must not have an order (%(order)s) unless in a tuple"),
                        modelObject=f, fact=f.qname, order=f.order)
                if f.isTuple or f.tupleID:
                    if inTuple is None:
                        inTuple = dict()
                    inTuple[f.qname] = f
                    self.checkIxTupleContent(f, inTuple)
            if f.modelTupleFacts:
                self.checkFacts(f.modelTupleFacts, inTuple=inTuple)
            if isinstance(f, ModelInlineFact) and (f.isTuple or f.tupleID):
                assert inTuple is not None
                del inTuple[f.qname]

            # uncomment if anybody uses this
            #for pluginXbrlMethod in pluginClassMethods("Validate.XBRL.Fact"):
            #    pluginXbrlMethod(self, f)

    def checkFactsDimensions(self, facts: list[ModelInlineFact]) -> None: # check fact dimensions in document order
        for f in facts:
            if f.concept is not None and (f.concept.isItem and f.context is not None):
                ValidateXbrlDimensions.checkFact(self, f)
            elif f.modelTupleFacts:
                self.checkFactsDimensions(f.modelTupleFacts)

    def checkIxTupleContent(self, tf: ModelInlineFact, parentTuples: dict[Any, Any]) -> None:
        if tf.isNil:
            if tf.modelTupleFacts:
                self.modelXbrl.error("ix:tupleNilContent",
                    _("Inline XBRL nil tuple has content"),
                    modelObject=[tf] + tf.modelTupleFacts)
        else:
            if not tf.modelTupleFacts:
                self.modelXbrl.error("ix:tupleContent",
                    _("Inline XBRL non-nil tuple requires content: ix:fraction, ix:nonFraction, ix:nonNumeric or ix:tuple"),
                    modelObject=tf)
        tfTarget = tf.get("target")
        prevTupleFact = None
        for f in tf.modelTupleFacts:
            if f.qname in parentTuples:
                self.modelXbrl.error("ix:tupleRecursion",
                    _("Fact %(fact)s is recursively nested in tuple %(tuple)s"),
                    modelObject=(f, parentTuples[f.qname]), fact=f.qname, tuple=tf.qname)
            if f.order is None:
                self.modelXbrl.error("ix:tupleOrder",
                    _("Fact %(fact)s missing an order in tuple %(tuple)s"),
                    modelObject=f, fact=f.qname, tuple=tf.qname)
            if f.get("target") != tfTarget:
                self.modelXbrl.error("ix:tupleItemTarget",
                    _("Fact %(fact)s has different target, %(factTarget)s, than tuple %(tuple)s, %(tupleTarget)s"),
                    modelObject=(tf, f), fact=f.qname, tuple=tf.qname, factTarget=f.get("target"), tupleTarget=tfTarget)
            if prevTupleFact is None:
                prevTupleFact = f
            elif (prevTupleFact.order == f.order and
                  XmlUtil.collapseWhitespace(prevTupleFact.textValue) == XmlUtil.collapseWhitespace(f.textValue)):
                self.modelXbrl.error("ix:tupleContentDuplicate",
                    _("Inline XBRL at order %(order)s has non-matching content %(value)s"),
                    modelObject=(prevTupleFact, f), order=f.order, value=prevTupleFact.textValue.strip())

    def checkContexts(self, contexts: Iterable[ModelContext]) -> None:
        for cntx in contexts:
            if cntx.isStartEndPeriod:
                try: # if no datetime value would have been a schema error at loading time
                    if (cntx.endDatetime is not None and cntx.startDatetime is not None and
                        cntx.endDatetime <= cntx.startDatetime):
                        self.modelXbrl.error("xbrl.4.7.2:periodStartBeforeEnd",
                            _("Context %(contextID)s must have startDate less than endDate"),
                            modelObject=cntx, contextID=cntx.id)
                except (TypeError, ValueError) as err:
                    self.modelXbrl.error("xbrl.4.7.2:contextDateError",
                        _("Context %(contextID)s startDate or endDate: %(error)s"),
                        modelObject=cntx, contextID=cntx.id, error=err)
            elif cntx.isInstantPeriod:
                try:
                    cntx.instantDatetime #parse field
                except ValueError as err:
                    self.modelXbrl.error("xbrl.4.7.2:contextDateError",
                        _("Context %(contextID)s instant date: %(error)s"),
                        modelObject=cntx, contextID=cntx.id, error=err)
            assert cntx.id is not None
            self.segmentScenario(cntx.segment, cntx.id, "segment", "4.7.3.2")
            self.segmentScenario(cntx.scenario, cntx.id, "scenario", "4.7.4")

            for dim in cntx.qnameDims.values():
                if dim.isTyped:
                    typedMember = dim.typedMember
                    if typedMember is not None and typedMember.xValid >= VALID: # typed dimension may be nil or empty
                        modelConcept = self.modelXbrl.qnameConcepts.get(typedMember.qname)
                        if modelConcept is not None:
                            if modelConcept.instanceOfType(dtrSQNameTypes):
                                if not typedMember.nsmap.get(typedMember.xValue.rpartition(":")[0]):
                                    self.modelXbrl.error("dtre:SQNameType",
                                        _("Context %(contextID)s dimension %(dim)s must have an in-scope prefix: %(value)s"),
                                        modelObject=typedMember, dim=typedMember.qname, contextID=cntx.id, value=typedMember.xValue[:200])
                            elif modelConcept.instanceOfType(dtrSQNamesTypes):
                                if not all(typedMember.nsmap.get(n.rpartition(":")[0]) for n in typedMember.xValue.split()):
                                    self.modelXbrl.error("dtre:SQNamesType",
                                        _("Context %(contextID)s dimension %(dim)s must have an in-scope prefix: %(value)s"),
                                        modelObject=typedMember, dim=typedMember.qname, contextID=cntx.id, value=typedMember.xValue[:200])
                            elif modelConcept.instanceOfType(dtrPrefixedContentTypes):
                                self.modelXbrl.error("dtre:prefixedContentType",
                                    _("Context %(contextID)s dimension %(dim)s must not have an unrecognized subtype of dtr:prefixedContentType."),
                                    modelObject=typedMember, dim=typedMember.qname, contextID=cntx.id, value=typedMember.xValue[:200])


    def checkContextsDimensions(self, contexts: Iterable[ModelContext]) -> None:
        for cntx in contexts:
            ValidateXbrlDimensions.checkContext(self,cntx)

    def checkUnits(self, units: Iterable[ModelUnit]) -> None:
        for unit in units:
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

    def fwdCycle(
        self,
        relsSet: ModelRelationshipSet,
        rels: list[ModelRelationship],
        noUndirected: bool,
        fromConcepts: set[ModelConcept | ModelCustomFunctionSignature | ModelInlineFact],
        cycleType: str = "directed",
        revCycleRel: ModelRelationship | None = None,
    ) -> list[str | ModelRelationship] | None:
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

    def revCycle(
        self,
        relsSet: ModelRelationshipSet,
        toConcept: ModelConcept,
        turnbackRel: ModelRelationship,
        fromConcepts: set[ModelConcept | ModelCustomFunctionSignature | ModelInlineFact],
    ) -> list[str | ModelRelationship] | None:
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

    def segmentScenario(
        self,
        element: ModelObject | ModelDimensionValue | None,
        contextId: str,
        name: str,
        sect: str,
        topLevel: bool = True,
    ) -> None:
        if topLevel:
            if element is None:
                return  # nothing to check
        else:
            assert element is not None
            if element.namespaceURI == XbrlConst.xbrli:
                self.modelXbrl.error("xbrl.{0}:{1}XbrliElement".format(sect,name),
                    _("Context %(contextID)s %(contextElement)s cannot have xbrli element %(elementName)s"),
                    modelObject=element, contextID=contextId, contextElement=name, elementName=element.prefixedName,
                    messageCodes=("xbrl.4.7.3.2:segmentXbrliElement", "xbrl.4.7.4:scenarioXbrliElement"))
            else:
                concept = self.modelXbrl.qnameConcepts.get(element.qname)
                if concept is not None and (concept.isItem or concept.isTuple):
                    self.modelXbrl.error("xbrl.{0}:{1}ItemOrTuple".format(sect,name),
                        _("Context %(contextID)s %(contextElement)s cannot have item or tuple element %(elementName)s"),
                        modelObject=element, contextID=contextId, contextElement=name, elementName=element.prefixedName,
                        messageCodes=("xbrl.4.7.3.2:segmentItemOrTuple", "xbrl.4.7.4:scenarioItemOrTuple"))

        hasChild = False
        for child in element.iterchildren():
            if isinstance(child,ModelObject):
                self.segmentScenario(child, contextId, name, sect, topLevel=False)
                hasChild = True
        if topLevel and not hasChild:
            self.modelXbrl.error("xbrl.{0}:{1}Empty".format(sect,name),
                _("Context %(contextID)s %(contextElement)s cannot be empty"),
                modelObject=element, contextID=contextId, contextElement=name,
                messageCodes=("xbrl.4.7.3.2:segmentEmpty", "xbrl.4.7.4:scenarioEmpty"))

    def isGenericObject(self, elt: ModelObject | _Element | None, genQname: QName | None) -> bool:
        # 2022-08-28: note for type ignore: _Element, which is passed by isGenericResource below, has no qname.
        # isGenericResource is currently used in ValidateXbrlDTS. We should revisit this when adding type hints for
        # ValidateXbrlDTS.
        return self.modelXbrl.isInSubstitutionGroup(elt.qname, genQname)  # type: ignore[union-attr]

    def isGenericLink(self, elt: ModelObject) -> bool:
        return self.isGenericObject(elt, XbrlConst.qnGenLink)

    def isGenericArc(self, elt: ModelObject) -> bool:
        return self.isGenericObject(elt, XbrlConst.qnGenArc)

    def isGenericResource(self, elt: ModelObject) -> bool:
        return self.isGenericObject(elt.getparent(), XbrlConst.qnGenLink)

    def isGenericLabel(self, elt: ModelObject) -> bool:
        return self.isGenericObject(elt, XbrlConst.qnGenLabel)

    def isGenericReference(self, elt: ModelObject) -> bool:
        return self.isGenericObject(elt, XbrlConst.qnGenReference)

    def executeCallTest(self, modelXbrl: ModelXbrl, name: str, callTuple: tuple[Any, ...], testTuple: tuple[Any, ...]) -> None:
        self.modelXbrl = modelXbrl
        ValidateFormula.executeCallTest(self, name, callTuple, testTuple)
