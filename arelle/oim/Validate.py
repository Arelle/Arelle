"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict

import regex as re

from arelle import ModelDocument, XbrlConst
from arelle.ModelDocument import ModelDocument as ModelDocumentClass
from arelle.ModelDtsObject import ModelResource
from arelle.ModelObject import ModelObject
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText
from arelle.XmlValidateConst import VALID

_: TypeGetText

precisionZeroPattern = re.compile(r"^\s*0+\s*$")


def validateOIM(modelXbrl: ModelXbrl) -> None:
    if modelXbrl.loadedFromOIM:
        if modelXbrl.loadedFromOimErrorCount < len(modelXbrl.errors):
            modelXbrl.error("oime:invalidTaxonomy", _("XBRL validation errors were logged for this instance."), modelObject=modelXbrl)
    else:
        modelDocument = modelXbrl.modelDocument
        assert modelDocument is not None
        # validate xBRL-XML instances
        fractionFacts = []
        tupleFacts = []
        precisionZeroFacts = []
        contextsInUse = set()
        for f in modelXbrl.factsInInstance: # facts in document order (no sorting required for messages)
            concept = f.concept
            if concept is not None:
                if concept.isFraction:
                    fractionFacts.append(f)
                elif concept.isTuple:
                    tupleFacts.append(f)
                elif concept.isNumeric:
                    if f.precision is not None and precisionZeroPattern.match(f.precision):
                        precisionZeroFacts.append(f)
            context = f.context
            if context is not None:
                contextsInUse.add(context)
        if fractionFacts:
            modelXbrl.error("xbrlxe:unsupportedFraction", # this pertains only to xBRL-XML validation (JSON and CSV were checked during loading when loadedFromOIM is True)
                            _("Instance has %(count)s facts with fraction facts"),
                            modelObject=fractionFacts, count=len(fractionFacts))
        if tupleFacts:
            modelXbrl.error("xbrlxe:unsupportedTuple",
                            _("Instance has %(count)s tuple facts"),
                            modelObject=tupleFacts, count=len(tupleFacts))
        if precisionZeroFacts:
            modelXbrl.error("xbrlxe:unsupportedZeroPrecisionFact",
                            _("Instance has %(count)s precision zero facts"),
                            modelObject=precisionZeroFacts, count=len(precisionZeroFacts))
        containers = {"segment", "scenario"}
        dimContainers = set(t for c in contextsInUse for t in containers if c.dimValues(t))
        if len(dimContainers) > 1:
            modelXbrl.error("xbrlxe:inconsistentDimensionsContainer",
                            _("All hypercubes within the DTS of a report MUST be defined for use on the same container (either \"segment\" or \"scenario\")"),
                            modelObject=modelXbrl)
        contextsWithNonDimContent = set()
        contextsWithComplexTypedDimensions = set()
        for context in contextsInUse:
            if context.nonDimValues("segment"):
                contextsWithNonDimContent.add(context)
            if context.nonDimValues("scenario"):
                contextsWithNonDimContent.add(context)
            for modelDimension in context.qnameDims.values():
                if modelDimension.isTyped:
                    typedMember = modelDimension.typedMember
                    if isinstance(typedMember, ModelObject):
                        modelConcept = modelXbrl.qnameConcepts.get(typedMember.qname)
                        if modelConcept is not None and modelConcept.type is not None and modelConcept.type.localName == "complexType":
                            contextsWithComplexTypedDimensions.add(context)
        if contextsWithNonDimContent:
            modelXbrl.error("xbrlxe:nonDimensionalSegmentScenarioContent",
                            _("Contexts MUST not contain non-dimensional content: %(contexts)s"),
                            modelObject=contextsWithNonDimContent,
                            contexts=", ".join(sorted(c.id for c in contextsWithNonDimContent)))
        if contextsWithComplexTypedDimensions:
            modelXbrl.error("xbrlxe:unsupportedComplexTypedDimension",  # this pertains only to xBRL-XML validation (JSON and CSV were checked during loading when loadedFromOIM is True)
                            _("Instance has contexts with complex typed dimensions: %(contexts)s"),
                            modelObject=contextsWithComplexTypedDimensions,
                            contexts=", ".join(sorted(c.id for c in contextsWithComplexTypedDimensions)))

        footnoteRels = modelXbrl.relationshipSet("XBRL-footnotes")
        # ext group and link roles
        footnoteELRs = set()
        footnoteArcroles = set()
        roleDefiningDocs = defaultdict(set)
        for rel in footnoteRels.modelRelationships:
            if not XbrlConst.isStandardRole(rel.linkrole):
                footnoteELRs.add(rel.linkrole)
            if rel.arcrole != XbrlConst.factFootnote:
                footnoteArcroles.add(rel.arcrole)
        for elr in footnoteELRs:
            for roleType in modelXbrl.roleTypes[elr]:
                roleDefiningDocs[elr].add(roleType.modelDocument)
        for arcrole in footnoteArcroles:
            for arcroleType in modelXbrl.arcroleTypes[arcrole]:
                roleDefiningDocs[arcrole].add(arcroleType.modelDocument)
        extRoles = set(role
                      for role, docs in roleDefiningDocs.items()
                      if not any(_docInSchemaRefedDTS(modelDocument, doc) for doc in docs))
        if extRoles:
            modelXbrl.error("xbrlxe:unsupportedExternalRoleRef",
                            _("Role and arcrole definitions MUST be in standard or schemaRef discoverable sources"),
                            modelObject=modelXbrl, roles=", ".join(sorted(extRoles)))

        # todo: multi-document inline instances
        for elt in modelDocument.xmlRootElement.iter(XbrlConst.qnLinkFootnote.clarkNotation, XbrlConst.qnIXbrl11Footnote.clarkNotation):
            if isinstance(elt, ModelResource) and getattr(elt, "xValid", 0) >= VALID:
                if not footnoteRels.toModelObject(elt):
                    errorValue = elt.xValue[:100] if isinstance(elt.xValue, str) else elt.xValue
                    modelXbrl.error("xbrlxe:unlinkedFootnoteResource",
                                    _("Unlinked footnote element %(label)s: %(value)s"),
                                    modelObject=elt, label=elt.xlinkLabel, value=errorValue)
                if elt.role not in (None, "", XbrlConst.footnote):
                    errorValue = elt.xValue[:100] if isinstance(elt.xValue, str) else elt.xValue
                    modelXbrl.error("xbrlxe:nonStandardFootnoteResourceRole",
                                    _("Footnotes MUST have standard footnote resource role, %(role)s is disallowed, %(label)s: %(value)s"),
                                    modelObject=elt, role=elt.role, label=elt.xlinkLabel, value=errorValue)
        # xml base on anything
        for elt in modelDocument.xmlRootElement.getroottree().iterfind(".//{*}*[@{http://www.w3.org/XML/1998/namespace}base]"):
            modelXbrl.error("xbrlxe:unsupportedXmlBase",
                            _("Instance MUST NOT contain xml:base attributes: element %(qname)s, xml:base %(base)s"),
                            modelObject=elt, qname=elt.qname if isinstance(elt, ModelObject) else elt.tag,
                            base=elt.get("{http://www.w3.org/XML/1998/namespace}base"))
        # todo: multi-document inline instances
        if modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
            for doc in modelDocument.referencesDocument.keys():
                if doc.type == ModelDocument.Type.LINKBASE:
                    modelXbrl.error("xbrlxe:unsupportedLinkbaseReference",
                                        _("Linkbase reference not allowed from instance document."),
                                        modelObject=(modelXbrl.modelDocument,doc))

def _docInSchemaRefedDTS(
        thisDoc: ModelDocumentClass,
        roleTypeDoc: ModelDocumentClass,
        visited: set[ModelDocumentClass] | None = None) -> bool:
    if visited is None:
        visited = set()
    visited.add(thisDoc)
    nonDiscoveringXmlInstanceElements = {XbrlConst.qnLinkRoleRef, XbrlConst.qnLinkArcroleRef}
    for doc, docRef in thisDoc.referencesDocument.items():
        if thisDoc.type != ModelDocument.Type.INSTANCE or docRef.referringModelObject.qname not in nonDiscoveringXmlInstanceElements:
            if doc == roleTypeDoc or (doc not in visited and _docInSchemaRefedDTS(doc, roleTypeDoc, visited)):
                return True
    visited.remove(thisDoc)
    return False
