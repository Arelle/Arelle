"""
See COPYRIGHT.md for copyright information.

## Overview

The Load From OIM plugin is designed to load reports in Arelle from JSON and CSV that adhere to the Open Information
Model (OIM) XBRL Specification. It also offers the option to save a loaded report as an xBRL-XML instance. It is
designed to work seamlessly with the Save Loadable OIM plugin, allowing for efficient data handling in Arelle.

## Key Features

- **Multiple Formats**: Enables loading data from JSON and CSV OIM formats as well as XLSX.
- **Seamless Integration**: Compatible with the Save Loadable OIM plugin for saving and loading reports.
- **GUI and CLI Compatibility**: Available for use in both GUI and CLI modes.
- **Save xBRL-XML Instance**: Optionally save the data as an xBRL-XML instance.

## Usage Instructions

### Command Line Usage

- **Load OIM Report**:
  To load an OIM report, specify the file path to the JSON, CSV, or XLSX file:
  ```bash
  python arelleCmdLine.py --plugins loadFromOIM --file filing-document.json
  ```

- **Save xBRL-XML Instance**:
  Use the `--saveOIMinstance` argument to save an xBRL-XML instance from an OIM report:
  ```bash
  python arelleCmdLine.py --plugins loadFromOIM --file filing-document.json --saveOIMinstance example.xbrl
  ```

### GUI Usage

* **Load OIM Report**:
  1. Using the normal `File` menu `Open File...` dialog, select the CSV, JSON, or XLSX file.
  2. Provide a name for the XBRL-XML instance to save.
"""
from regex import compile as re_compile
from collections import defaultdict
from arelle.ModelDocument import Type
from arelle.ModelDtsObject import ModelResource
from arelle import ModelDocument
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import link, footnote, factFootnote, isStandardRole
from arelle.XmlValidateConst import VALID


precisionZeroPattern = re_compile(r"^\s*0+\s*$")

nonDiscoveringXmlInstanceElements = {qname(link, "roleRef"), qname(link, "arcroleRef")}


def validateFinally(val, *args, **kwargs):
    modelXbrl = val.modelXbrl
    if getattr(modelXbrl, "loadedFromOIM", False):
        if modelXbrl.loadedFromOimErrorCount < len(modelXbrl.errors):
            modelXbrl.error("oime:invalidTaxonomy",
                                _("XBRL validation errors were logged for this instance."),
                                modelObject=modelXbrl)
    else:
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
        unsupportedExtRoleRefs = defaultdict(list) # role/arcrole and footnote relationship objects referencing it
        footnoteELRs = set()
        footnoteArcroles = set()
        roleDefiningDocs = defaultdict(set)
        def docInSchemaRefedDTS(thisdoc, roleTypeDoc, visited=None):
            if visited is None:
                visited = set()
            visited.add(thisdoc)
            for doc, docRef in thisdoc.referencesDocument.items():
                if thisdoc.type != Type.INSTANCE or docRef.referringModelObject.qname not in nonDiscoveringXmlInstanceElements:
                    if doc == roleTypeDoc or (doc not in visited and docInSchemaRefedDTS(doc, roleTypeDoc, visited)):
                        return True
            visited.remove(thisdoc)
            return False
        for rel in footnoteRels.modelRelationships:
            if not isStandardRole(rel.linkrole):
                footnoteELRs.add(rel.linkrole)
            if rel.arcrole != factFootnote:
                footnoteArcroles.add(rel.arcrole)
        for elr in footnoteELRs:
            for roleType in modelXbrl.roleTypes[elr]:
                roleDefiningDocs[elr].add(roleType.modelDocument)
        for arcrole in footnoteArcroles:
            for arcroleType in modelXbrl.arcroleTypes[arcrole]:
                roleDefiningDocs[arcrole].add(arcroleType.modelDocument)
        extRoles = set(role
                      for role, docs in roleDefiningDocs.items()
                      if not any(docInSchemaRefedDTS(modelXbrl.modelDocument, doc) for doc in docs))
        if extRoles:
            modelXbrl.error("xbrlxe:unsupportedExternalRoleRef",
                            _("Role and arcrole definitions MUST be in standard or schemaRef discoverable sources"),
                            modelObject=modelXbrl, roles=", ".join(sorted(extRoles)))

        # todo: multi-document inline instances
        for elt in modelXbrl.modelDocument.xmlRootElement.iter("{http://www.xbrl.org/2003/linkbase}footnote", "{http://www.xbrl.org/2013/inlineXBRL}footnote"):
            if isinstance(elt, ModelResource) and getattr(elt, "xValid", 0) >= VALID:
                if not footnoteRels.toModelObject(elt):
                    modelXbrl.error("xbrlxe:unlinkedFootnoteResource",
                                    _("Unlinked footnote element %(label)s: %(value)s"),
                                    modelObject=elt, label=elt.xlinkLabel, value=elt.xValue[:100])
                if elt.role not in (None, "", footnote):
                    modelXbrl.error("xbrlxe:nonStandardFootnoteResourceRole",
                                    _("Footnotes MUST have standard footnote resource role, %(role)s is disallowed, %(label)s: %(value)s"),
                                    modelObject=elt, role=elt.role, label=elt.xlinkLabel, value=elt.xValue[:100])
        # xml base on anything
        for elt in modelXbrl.modelDocument.xmlRootElement.getroottree().iterfind(".//{*}*[@{http://www.w3.org/XML/1998/namespace}base]"):
            modelXbrl.error("xbrlxe:unsupportedXmlBase",
                            _("Instance MUST NOT contain xml:base attributes: element %(qname)s, xml:base %(base)s"),
                            modelObject=elt, qname=elt.qname if isinstance(elt, ModelObject) else elt.tag,
                            base=elt.get("{http://www.w3.org/XML/1998/namespace}base"))
        # todo: multi-document inline instances
        if modelXbrl.modelDocument.type in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INLINEXBRLDOCUMENTSET):
            for doc in modelXbrl.modelDocument.referencesDocument.keys():
                if doc.type == Type.LINKBASE:
                    val.modelXbrl.error("xbrlxe:unsupportedLinkbaseReference",
                                        _("Linkbase reference not allowed from instance document."),
                                        modelObject=(modelXbrl.modelDocument,doc))

__pluginInfo__ = {
    'name': 'Load From OIM',
    'version': '1.2',
    'description': "This plug-in loads XBRL instance data from OIM (JSON, CSV or Excel) and saves the resulting XBRL Instance.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'Validate.XBRL.Finally': validateFinally
}
