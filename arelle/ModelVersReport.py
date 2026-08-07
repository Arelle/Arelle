"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import os
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

import regex as re
from lxml import etree

from arelle import (
    ModelDocument,
    UrlUtil,
    Version,
    XbrlConst,
    XbrlUtil,
    XmlUtil,
    XmlValidate,
)
from arelle.FileSource import FileNamedStringIO
from arelle.ModelDtsObject import ModelConcept, ModelRelationship
from arelle.ModelObject import ModelObject
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import QName, qname
from arelle.ModelVersObject import (
    relateConceptMdlObjs,
    ModelConceptChange,
    ModelAction,
    ModelAssignment,
    ModelNamespaceRename,
    ModelRoleChange,
    ModelConceptUseChange,
    ModelConceptDetailsChange,
    ModelRelationshipSetChange,
    ModelInstanceAspectsChange,
)
from arelle.ModelXbrl import (
    ModelXbrl,
    create as ModelXbrlCreate,
    load as ModelXbrlLoad,
)
from arelle.typing import TypeGetText

_: TypeGetText

relationshipSetArcAttributesExclusion = {
    "{http://www.w3.org/1999/xlink}from",
    "{http://www.w3.org/1999/xlink}to",
    "{http://www.w3.org/1999/xlink}actuate",
    "{http://www.w3.org/1999/xlink}show",
    "{http://www.w3.org/1999/xlink}title",
    "{http://www.w3.org/XML/1998/namespace}lang",
    "{http://www.w3.org/XML/1998/namespace}space",
    "id", "use", "priority", "order"
    }

authoritiesEquivalence = {
    "http://xbrl.iasb.org": "IFRS", "http://xbrl.ifrs.org": "IFRS",
    "http://xbrl.us": "XBRL-US", "http://fasb.org": "XBRL-US", "http://xbrl.sec.gov": "XBRL-US",
    }

dateRemovalPattern = re.compile(r"[/]?(draft-)?(19|20)[0-9][0-9](-[01][0-9](-[0-3][0-9])?)?")
numberRemovalPattern = re.compile(r"[/]?[0-9][0-9\.]*")


class ModelVersReport(ModelDocument.ModelDocument):
    """
    .. class:: ModelVersReport(type=ModelDocument.Type.VERSIONINGREPORT, uri=None, filepath=None, xmlDocument=None)

    ModelVersReport is a specialization of ModelDocument for Versioning Reports.

    (for parameters and inherited attributes, please see ModelDocument)

        .. attribute:: fromDTS

        From DTS (modelXbrl object)

        .. attribute:: toDTS

        To DTS (modelXbrl object)

        .. attribute:: assignments

        Dict by id of ModelAssignment objects

        .. attribute:: actions

        Dict by id of ModelAction objects

        .. attribute:: namespaceRenameFrom

        Dict by fromURI of ModelNamespaceRename objects

        .. attribute:: namespaceRenameTo

        Dict  by toURI of ModelNamespaceRename objects

        .. attribute:: roleChanges

        Dict by uri of ModelRoleChange objects

        .. attribute:: conceptUseChanges

        List of ModelConceptUseChange objects

        .. attribute:: conceptDetailsChanges

        List of ModelConceptDetailsChange objects

        .. attribute:: equivalentConcepts

        Dict by qname of equivalent qname

        .. attribute:: relatedConceptsDefaultDict by qname of list of related concept qnames


        .. attribute:: relationshipSetChanges    List of ModelRelationshipSet objects

        .. attribute:: instanceAspectChanges

        List of ModelInstanceAspectChange objects

        .. attribute:: typedDomainsCorrespond

        Dict by (fromDimConcept,toDimConcept) of bool that is True if corresponding
    """

    def __init__(
        self,
        modelXbrl: ModelXbrl,
        type: int = ModelDocument.Type.VERSIONINGREPORT,
        uri: str = "",
        filepath: str = "",
        xmlDocument: etree._ElementTree[etree._Element] | None = None,
    ) -> None:
        super(ModelVersReport, self).__init__(modelXbrl, type, uri, filepath, xmlDocument)
        self.fromDTS: ModelXbrl | None = None  # type: ignore[assignment]
        self.toDTS: ModelXbrl | None = None  # type: ignore[assignment]
        self.assignments: dict[str, ModelAssignment] = {}
        self.actions: dict[str, ModelAction] = {}
        self.namespaceRenameFrom: dict[str, ModelNamespaceRename] = {}
        self.namespaceRenameFromURI: dict[str, str] = {}
        self.namespaceRenameTo: dict[str, ModelNamespaceRename] = {}
        self.namespaceRenameToURI: dict[str, str] = {}
        self.roleChanges: dict[str, ModelRoleChange] = {}
        self.conceptUseChanges: list[ModelConceptUseChange] = []
        self.conceptDetailsChanges: list[ModelConceptDetailsChange] = []
        self.equivalentConcepts: dict[QName, QName] = {}
        self.relatedConcepts: defaultdict[QName, set[QName]] = defaultdict(set)
        self.relationshipSetChanges: list[ModelRelationshipSetChange] = []
        self.instanceAspectChanges: list[ModelInstanceAspectsChange] = []
        self.typedDomainsCorrespond: dict[tuple[ModelConcept, ModelConcept], bool] = {}

    def close(self, *args: Any, **kwargs: Any) -> None:
        """Closes any views, formula output instances, modelDocument(s), and dereferences all memory used
        """
        super(ModelVersReport, self).close(*args, **kwargs)

    def versioningReportDiscover(self, rootElement: ModelObject) -> None:
        """Initiates discovery of versioning report

        :param rootElement: lxml root element of versioning report
        :type rootElement: xml element node
        """

        XmlValidate.validate(self.modelXbrl, rootElement) # schema validate

        actionRelatedFromMdlObjs: list[ModelConceptChange] = []
        actionRelatedToMdlObjs: list[ModelConceptChange] = []
        modelAction: ModelObject | ModelAction | None = None
        # add self to namespaced document
        self.xmlRootElement = rootElement
        try:
            for modelObject in rootElement.iterdescendants():
                if isinstance(modelObject, ModelObject):
                    ln = modelObject.localName
                    ns = modelObject.namespaceURI
                    if ns == XbrlConst.ver:
                        if ln == "action":
                            relateConceptMdlObjs(self, actionRelatedFromMdlObjs, actionRelatedToMdlObjs)
                            modelAction = modelObject
                            actionRelatedFromMdlObjs = []
                            actionRelatedToMdlObjs = []
                        elif (ln == "fromDTS" or ln == "toDTS") and not getattr(self, ln):
                            schemaRefElts = XmlUtil.children(modelObject, XbrlConst.link, "schemaRef")
                            if schemaRefElts:
                                if len(schemaRefElts) == 1 and schemaRefElts[0].get("{http://www.w3.org/1999/xlink}href") is not None:
                                    DTSmodelXbrl = ModelXbrlLoad(self.modelXbrl.modelManager,
                                          schemaRefElts[0].get("{http://www.w3.org/1999/xlink}href"),  # type: ignore[arg-type]
                                          "loading validation report",
                                          base=self.baseForElement(schemaRefElts[0]))
                                else:   # need multi-schemaRefs DTS
                                    DTSmodelXbrl = ModelXbrlCreate(self.modelXbrl.modelManager,
                                                 newDocumentType=ModelDocument.Type.DTSENTRIES,
                                                 url=self.uri[:-4] + "-" + ln + ".dts", isEntry=True)
                                    DTSdoc = DTSmodelXbrl.modelDocument
                                    DTSdoc.inDTS = True  # type: ignore[union-attr]
                                    for schemaRefElt in schemaRefElts:
                                        if (href := schemaRefElt.get("{http://www.w3.org/1999/xlink}href")) is not None:
                                            doc = ModelDocument.load(DTSmodelXbrl,
                                                                     href,
                                                                     base=self.baseForElement(schemaRefElt))
                                            DTSdoc.referencesDocument[doc] = "import"  # type: ignore[assignment,index,union-attr]  # fake import
                                            doc.inDTS = True  # type: ignore[union-attr]
                                if DTSmodelXbrl is not None:
                                    setattr(self, ln, DTSmodelXbrl)
                        elif ln in ("namespaceRename", "roleChange"):
                            if modelAction is not None:
                                modelAction.events.append(modelObject)  # type: ignore[attr-defined]
                    elif self.fromDTS is None or self.toDTS is None:
                        pass
                    elif ns in (XbrlConst.vercu, XbrlConst.vercb):
                        if ln in ("conceptRename", "conceptAdd", "conceptDelete"):
                            if modelAction is not None:
                                modelAction.events.append(modelObject)  # type: ignore[attr-defined]
                        if ln == "conceptRename":
                            modelObject.setConceptEquivalence()  # type: ignore[attr-defined]
                        elif ln == "conceptDelete":
                            actionRelatedFromMdlObjs.append(modelObject)  # type: ignore[arg-type]
                        elif ln == "conceptAdd":
                            actionRelatedToMdlObjs.append(modelObject)  # type: ignore[arg-type]
                    elif ns in (XbrlConst.vercd, XbrlConst.verce):
                        if ln in {"conceptIDChange", "conceptTypeChange", "conceptSubstitutionGroupChange",
                                  "conceptDefaultChange", "conceptNillableChange",
                                  "conceptAbstractChange", "conceptBlockChange", "conceptFixedChange",
                                  "conceptFinalChange", "conceptPeriodTypeChange", "conceptBalanceChange",
                                  "conceptAttributeAdd", "conceptAttributeDelete", "conceptAttributeChange",
                                  "tupleContentModelChange",
                                  "conceptLabelAdd", "conceptLabelDelete", "conceptLabelChange",
                                  "conceptReferenceAdd", "conceptReferenceDelete", "conceptReferenceChange"}:
                            if modelAction is not None:
                                modelAction.events.append(modelObject)  # type: ignore[attr-defined]
                    elif ns == XbrlConst.verrels:
                        if ln in {"relationshipSetModelChange", "relationshipSetModelAdd", "relationshipSetModelDelete"}:
                            if modelAction is not None:
                                modelAction.events.append(modelObject)  # type: ignore[attr-defined]
                            modelRelationshipSetEvent = modelObject
                        elif ln in ("fromRelationshipSet", "toRelationshipSet"):
                            if modelRelationshipSetEvent is not None:
                                modelRelationshipSet = modelObject
                                if ln == "fromRelationshipSet":
                                    modelRelationshipSetEvent.fromRelationshipSet = modelObject  # type: ignore[attr-defined]
                                else:
                                    modelRelationshipSetEvent.toRelationshipSet = modelObject  # type: ignore[attr-defined]
                                modelObject.modelRelationshipSetEvent = modelRelationshipSetEvent  # type: ignore[attr-defined]
                        elif ln == "relationships":
                            if modelRelationshipSet is not None:
                                modelRelationshipSet.relationships.append(modelObject)  # type: ignore[attr-defined]
                                modelObject.modelRelationshipSet = modelRelationshipSet  # type: ignore[attr-defined]

                    elif ns in (XbrlConst.verdim, XbrlConst.veria):
                        if ln in ("aspectModelChange", "aspectModelAdd", "aspectModelDelete"):
                            if modelAction is not None:
                                modelAction.events.append(modelObject)  # type: ignore[attr-defined]
                            aspectModelEvent = modelObject
                            modelAspects = None
                        elif ln in ("fromAspects", "toAspects"):
                            if aspectModelEvent is not None:
                                modelAspects = modelObject
                                if ln == "fromAspects":
                                    aspectModelEvent.fromAspects = modelObject  # type: ignore[attr-defined]
                                else:
                                    aspectModelEvent.toAspects = modelObject  # type: ignore[attr-defined]
                                modelObject.aspectModelEvent = aspectModelEvent  # type: ignore[attr-defined]
                        elif ln in ("concepts", "explicitDimension", "typedDimension", "segment", "scenario",
                                    "entityIdentifier", "period", "location", "unit"):
                            modelAspect = modelObject
                            if modelAspects is not None:
                                modelAspects.aspects.append(modelObject)  # type: ignore[attr-defined]
                            modelObject.modelAspects = modelAspects  # type: ignore[attr-defined]
                            modelMulDivBy = None
                        elif ln in ("concept", "member"):
                            if modelAspect is not None:
                                modelAspect.relatedConcepts.append(modelObject)  # type: ignore[attr-defined]
                            modelObject.modelAspect = modelAspect  # type: ignore[attr-defined]
                        elif ln in ("startDate", "endDate", "instant", "forever"):
                            if modelAspect is not None:
                                modelAspect.relatedPeriods.append(modelObject)  # type: ignore[attr-defined]
                            modelObject.modelAspect = modelAspect  # type: ignore[attr-defined]
                        elif ln in ("multiplyBy", "divideBy"):
                            if modelAspect is not None:
                                modelAspect.relatedMeasures.append(modelObject)  # type: ignore[attr-defined]
                            modelObject.modelAspect = modelAspect  # type: ignore[attr-defined]
                            modelMulDivBy = modelObject
                        elif ln == "measure":
                            if modelMulDivBy is not None:
                                modelMulDivBy.relatedMeasures.append(modelObject)  # type: ignore[attr-defined]
                                modelObject.modelAspect = modelMulDivBy  # type: ignore[attr-defined]
                            elif modelAspect is not None:
                                modelAspect.relatedMeasures.append(modelObject)  # type: ignore[attr-defined]
                                modelObject.modelAspect = modelAspect  # type: ignore[attr-defined]
            relateConceptMdlObjs(self, actionRelatedFromMdlObjs, actionRelatedToMdlObjs)
            # do linkbaseRef's at end after idObjects all loaded
            for element in rootElement.iterdescendants("{http://www.xbrl.org/2003/linkbase}linkbaseRef"):
                self.schemaLinkbaseRefDiscover(element)
        except (ValueError, LookupError) as err:
            self.modelXbrl.modelManager.addToLog("discovery: {0} error {1}".format(
                        os.path.basename(self.uri),
                        err))

    def entryURIs(self, DTS: ModelXbrl) -> list[str]:
        if DTS.modelDocument:
            if DTS.modelDocument.type == ModelDocument.Type.DTSENTRIES:
                return sorted([mdlDoc.uri for mdlDoc in DTS.modelDocument.referencesDocument.keys()])
            else:
                return [DTS.uri]
        return []

    def diffDTSes(
        self,
        reportOutput: str | FileNamedStringIO,
        fromDTS: ModelXbrl,
        toDTS: ModelXbrl,
        assignment: str = "technical",
        schemaDir: str | None = None,
    ) -> None:
        """Initiates diffing of fromDTS and toDTS, populating the ModelVersReport object, and saving the
        versioning report file).

        :param versReporFile: file name to save the versioning report
        :type versReporFile: str
        :param fromDTS: first modelXbrl's (DTSes) to be diffed
        :type fromDTS: ModelXbrl
        :param toDTS: second modelXbrl's (DTSes) to be diffed
        :type toDTS: ModelXbrl
        :param assignment: 'technical', 'business', etc. for the assignment clause
        :type assignment: str
        :param schemaDir: Directory for determination of relative path for versioning xsd files (versioning-base.xsd, etc).
        :type schemaDir: str
        """
        versReportFile = str(reportOutput)  # may be a FileNamedStringIO, in which case str( ) is the filename
        self.uri = os.path.normpath(versReportFile)
        from arelle import FileSource
        self.modelXbrl.fileSource = FileSource.FileSource(self.uri)
        self.fromDTS = fromDTS
        self.toDTS = toDTS
        assignment = assignment.lower()
        if ":" in assignment:
            categoryType = assignment
        elif assignment.startswith("technical"):
            categoryType = "technicalCategory"
        elif assignment.startswith("business"):
            categoryType = "businessCategory"
        else:
            categoryType = "errataCategory"
        import io
        file = io.StringIO(
            #'<?xml version="1.0" encoding="UTF-8"?>'
            '<nsmap>'  # for lxml expandable namespace purposes
            '<!-- Generated by Arelle(r) version {3} at {4} -->'
            '<report'
            '  xmlns="http://xbrl.org/2013/versioning-base"'
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            '  xmlns:link="http://www.xbrl.org/2003/linkbase"'
            '  xmlns:xlink="http://www.w3.org/1999/xlink"'
            # for generated testcases the schema locations need to be relative to test case directory
            #'  xsi:schemaLocation="'
            #    'http://xbrl.org/2010/versioning-base http://xbrl.org/2010/versioning-base '
            #    'http://xbrl.org/2010/versioning-concept-basic http://xbrl.org/2010/versioning-concept-basic '
            #    'http://xbrl.org/2010/versioning-concept-extended http://xbrl.org/2010/versioning-concept-extended '
            #'"
            '>'
                '<!-- link:linkbaseRef xlink:type="simple"'
                '  xlink:arcrole="http://www.w3.org/1999/xlink/properties/linkbase"'
                '  xlink:title="documentation"'
                '  xlink:href="sample.xml"/ -->'
                '<fromDTS>{0}</fromDTS>'
                '<toDTS>{1}</toDTS>'
                '<assignment id="versioningTask"><{2}/></assignment>'
            '</report></nsmap>'.format(
                "".join(['<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(self.relativeUri(uri))
                           for uri in self.entryURIs(fromDTS)]),
                "".join(['<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(self.relativeUri(uri))
                           for uri in self.entryURIs(toDTS)]),
                categoryType,
                Version.version,
                format(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
             )
        from arelle.ModelObjectFactory import parser
        self.parser, self.parserLookupName, self.parserLookupClass = parser(self.modelXbrl,None)
        self.xmlDocument = etree.parse(file, parser=self.parser, base_url=self.uri)
        file.close()
        self.xmlDocument.getroot().init(self)  # type: ignore[attr-defined]
        for self.reportElement in  self.xmlDocument.iter(tag="{http://xbrl.org/2013/versioning-base}report"):
            self.xmlRootElement = self.reportElement  # type: ignore[assignment]
        self.actionNum = 1

        self.modelXbrl.modelManager.showStatus(_("Comparing namespaces"))
        self.diffNamespaces()
        self.modelXbrl.modelManager.showStatus(_("Comparing roles"))
        self.diffRoles()
        self.modelXbrl.modelManager.showStatus(_("Comparing concepts"))
        self.diffConcepts()
        for arcroleUri in (XbrlConst.parentChild, XbrlConst.summationItem, XbrlConst.essenceAlias, XbrlConst.requiresElement, XbrlConst.generalSpecial):
            self.modelXbrl.modelManager.showStatus(_("Comparing {0} relationships").format(os.path.basename(arcroleUri)))
            self.diffRelationshipSet(arcroleUri)

        self.modelXbrl.modelManager.showStatus(_("Comparing dimension defaults"))
        self.diffDimensionDefaults()

        self.modelXbrl.modelManager.showStatus(_("Comparing explicit dimensions"))
        self.diffDimensions()

        # determine namespaces
        schemaLocations = []
        if schemaDir is not None:
            schemasRelPath = os.path.relpath(schemaDir, os.path.dirname(versReportFile)) + os.sep
            for prefix in self.reportElement.nsmap.values():
                if prefix == XbrlConst.ver:
                    schemaLocations.append(XbrlConst.ver)
                    schemaLocations.append(schemasRelPath + "versioning-base.xsd")
                elif prefix == XbrlConst.vercu:
                    schemaLocations.append(XbrlConst.vercu)
                    schemaLocations.append(schemasRelPath + "versioning-concept-use.xsd")
                elif prefix == XbrlConst.vercd:
                    schemaLocations.append(XbrlConst.vercd)
                    schemaLocations.append(schemasRelPath + "versioning-concept-details.xsd")
                elif prefix == XbrlConst.verrels:
                    schemaLocations.append(XbrlConst.verrels)
                    schemaLocations.append(schemasRelPath + "versioning-relationship-sets.xsd")
                elif prefix == XbrlConst.verdim:
                    schemaLocations.append(XbrlConst.verdim)
                    schemaLocations.append(schemasRelPath + "versioning-dimensions.xsd")
                elif prefix == XbrlConst.veria:
                    schemaLocations.append(XbrlConst.veria)
                    schemaLocations.append(schemasRelPath + "versioning-instance-aspects.xsd")
            self.reportElement.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
                                   " ".join(schemaLocations))

        self.modelXbrl.modelManager.showStatus(_("Checking report file"))
        self.modelXbrl.modelDocument = self # model document is now established
        self.versioningReportDiscover(self.reportElement)  # type: ignore[arg-type]
        self.modelXbrl.modelManager.showStatus(_("Writing report file"))
        if isinstance(reportOutput, FileNamedStringIO):
            fh = reportOutput
        else:
            fh = open(versReportFile, "w", encoding="utf-8")  # type: ignore[assignment]
        XmlUtil.writexml(fh, self.xmlDocument, encoding="utf-8")
        if not isinstance(reportOutput, FileNamedStringIO):
            fh.close()
        self.filepath = versReportFile
        self.modelXbrl.modelManager.showStatus(_("C report file"))
        self.modelXbrl.modelManager.showStatus(_("ready"), 2000)

    def diffNamespaces(self) -> None:
        # build fomr and to lists based on namespaces
        self.namespaceRenameFromURI = {}
        self.namespaceRenameToURI = {}
        fromNSes: set[str] = set()
        toNSes: set[str] = set()
        for fromModelDoc in self.fromDTS.urlDocs.values():  # type: ignore[union-attr]
            if fromModelDoc.type == ModelDocument.Type.SCHEMA:
                fromNSes.add(fromModelDoc.targetNamespace)  # type: ignore[arg-type]
        for toModelDoc in self.toDTS.urlDocs.values():  # type: ignore[union-attr]
            if toModelDoc.type == ModelDocument.Type.SCHEMA:
                toNSes.add(toModelDoc.targetNamespace)  # type: ignore[arg-type]
        self.diffURIs(fromNSes, toNSes,
                      "namespaceRename",
                      (self.rolePathlessDatelessMatchPattern, self.roleNumlessMatchPattern, self.roleNoFromToMatchPattern),
                      self.namespaceRenameFromURI, self.namespaceRenameToURI)

    def diffRoles(self) -> None:
        self.roleChangeFromURI: dict[str, str] = {}
        self.roleChangeToURI: dict[str, str] = {}
        self.diffURIs(set(self.fromDTS.roleTypes.keys()),  # type: ignore[union-attr]
                      set(self.toDTS.roleTypes.keys()),  # type: ignore[union-attr]
                      "roleChange",
                      (self.rolePathlessDatelessMatchPattern, self.roleNumlessMatchPattern, self.roleNoFromToMatchPattern),
                      self.roleChangeFromURI, self.roleChangeToURI)

    def diffURIs(
        self,
        fromURIs: set[str],
        toURIs: set[str],
        eventName: str,
        matchers: Iterable[Callable[[str], str]],
        changeFrom: dict[str, str],
        changeTo: dict[str, str],
    ) -> None:
        # remove common roles from each
        commonRoles = fromURIs & toURIs
        fromURIs -= commonRoles
        toURIs -= commonRoles
        for matcher in matchers:
            # look for roles matching on matcher subpattern
            fromMatchURIs: defaultdict[str, list[str]] = defaultdict(list)
            toMatchURIs: defaultdict[str, list[str]] = defaultdict(list)
            # try to URIs based on numbers in uri path removed (e.g., ignoring dates)
            for matchURIs, origURIs in ((fromMatchURIs, fromURIs), (toMatchURIs, toURIs)):
                for uri in origURIs:
                    matchURIs[matcher(uri)].append(uri)
            for fromMatchURI, fromMatchedURIs in fromMatchURIs.items():
                for toURI in toMatchURIs.get(fromMatchURI, []):
                    for fromURI in fromMatchedURIs:
                        self.createBaseEvent(eventName, fromURI, toURI)
                        changeFrom[fromURI] = toURI
                        changeTo[toURI] = fromURI
                        # removed from consideration by next pass on final path segment
                        fromURIs.discard(fromURI)
                        toURIs.discard(toURI)

    def uriNumlessMatchPattern(self, uri: str) -> str:
        # remove date and numbers from uri (for now, more sophisticated later)
        return "".join((c if str.isalpha(c) or c == "/" else "") for c in uri)

    def roleNumlessMatchPattern(self, role: str) -> str:
        # remove date and numbers from role except last path segment
        basepart, sep, lastpart = role.rpartition("/")
        return "".join((c if str.isalpha(c) or c == "/" else "") for c in basepart) + \
                ((sep + lastpart) if lastpart else "")

    def rolePathlessDatelessMatchPattern(self, role: str) -> str:
        # remove date from path (including / if immediately before date)
        datelessRole = dateRemovalPattern.sub("", role)
        # remove intermediate role path elements between authority and end path segment (after date removal)
        basepart, sep, lastpart = datelessRole.rpartition("/")
        origAuthority = UrlUtil.authority(role)
        matchedAuthority = authoritiesEquivalence.get(origAuthority,origAuthority)
        return matchedAuthority + ((sep + lastpart) if lastpart else "")

    def roleNoFromToMatchPattern(self, role: str) -> str:
        # remove intermediate role path elements between authority and end path segment
        # for roland test case generation
        basepart, sep, lastpart = role.rpartition("/")
        if lastpart.endswith("_to"):
            lastpart = lastpart[:-3]
        elif lastpart.endswith("_from"):
            lastpart = lastpart[:-5]
        return UrlUtil.authority(role) + ((sep + lastpart) if lastpart else "")

    def diffConcepts(self) -> None:
        toConceptsMatched: set[QName] = set()
        vercu = XbrlConst.vercu
        vercd = XbrlConst.vercd
        for fromConceptQname, fromConcept in self.fromDTS.qnameConcepts.items():  # type: ignore[union-attr]
            if not fromConcept.isItem and not fromConcept.isTuple:
                continue
            toConceptQname = self.toDTSqname(fromConceptQname)
            if toConceptQname in self.toDTS.qnameConcepts:  # type: ignore[union-attr]
                toConcept = self.toDTS.qnameConcepts[toConceptQname]  # type: ignore[index,union-attr]
                toConceptsMatched.add(toConceptQname)  # type: ignore[arg-type]
                # compare concepts
                action = None # keep same action for all of same concept's changes
                if fromConcept.id != toConcept.id:
                    action = self.createConceptEvent(vercd, "vercd:conceptIDChange", fromConcept, toConcept, action, fromValue=fromConcept.id, toValue=toConcept.id)
                if fromConcept.substitutionGroupQname != self.fromDTSqname(toConcept.substitutionGroupQname):
                    action = self.createConceptEvent(vercd, "vercd:conceptSubstitutionGroupChange", fromConcept, toConcept, action, fromValue=fromConcept.substitutionGroupQname, toValue=self.toDTSqname(toConcept.substitutionGroupQname))  # type: ignore[arg-type]
                if fromConcept.isItem and toConcept.isItem:
                    if fromConcept.typeQname != self.fromDTSqname(toConcept.typeQname):
                        action = self.createConceptEvent(vercd, "vercd:conceptTypeChange", fromConcept, toConcept, action, fromValue=fromConcept.typeQname, toValue=toConcept.typeQname)  # type: ignore[arg-type]
                if fromConcept.nillable != toConcept.nillable:
                    action = self.createConceptEvent(vercd, "vercd:conceptNillableChange", fromConcept, toConcept, action, fromValue=fromConcept.nillable, toValue=toConcept.nillable)
                if fromConcept.abstract != toConcept.abstract:
                    action = self.createConceptEvent(vercd, "vercd:conceptAbstractChange", fromConcept, toConcept, action, fromValue=fromConcept.abstract, toValue=toConcept.abstract)
                if fromConcept.isItem and toConcept.isItem:
                    if fromConcept.block != toConcept.block:
                        action = self.createConceptEvent(vercd, "vercd:conceptBlockChange", fromConcept, toConcept, action, fromValue=fromConcept.block, toValue=toConcept.block)
                    if fromConcept.default != toConcept.default:
                        action = self.createConceptEvent(vercd, "vercd:conceptDefaultChange", fromConcept, toConcept, action, fromValue=fromConcept.default, toValue=toConcept.default)
                    if fromConcept.fixed != toConcept.fixed:
                        action = self.createConceptEvent(vercd, "vercd:conceptFixedChange", fromConcept, toConcept, action, fromValue=fromConcept.fixed, toValue=toConcept.fixed)
                    if fromConcept.final != toConcept.final:
                        action = self.createConceptEvent(vercd, "vercd:conceptFinalChange", fromConcept, toConcept, action, fromValue=fromConcept.final, toValue=toConcept.final)
                    if fromConcept.periodType != toConcept.periodType:
                        action = self.createConceptEvent(vercd, "vercd:conceptPeriodTypeChange", fromConcept, toConcept, action, fromValue=fromConcept.periodType, toValue=toConcept.periodType)
                    if fromConcept.balance != toConcept.balance:
                        action = self.createConceptEvent(vercd, "vercd:conceptBalanceChange", fromConcept, toConcept, action, fromValue=fromConcept.balance, toValue=toConcept.balance)
                if fromConcept.isTuple and toConcept.isTuple:
                    fromType = fromConcept.type # it is null for xsd:anyType
                    toType = toConcept.type
                    # TBD change to xml comparison with namespaceURI mappings, prefixes ignored
                    if (fromType is not None and toType is not None and
                        not XbrlUtil.nodesCorrespond(self.fromDTS, fromType, toType, self.toDTS)):  # type: ignore[arg-type]
                        action = self.createConceptEvent(vercd, "vercd:tupleContentModelChange", fromConcept, toConcept, action)
                # custom attributes in from Concept
                fromCustAttrs: dict[QName, str] = {}
                toCustAttrs: dict[QName, str] = {}
                for concept, attrs in ((fromConcept, fromCustAttrs), (toConcept, toCustAttrs)):
                    for attrName, attrValue in concept.items():
                        attrQname = qname(attrName)
                        if (attrName not in ("abstract", "block", "default", "final", "fixed", "form", "id", "maxOccurs",
                                             "minOccurs", "name", "nillable", "ref", "substitutionGroup", "type") and
                            attrQname.namespaceURI != XbrlConst.xbrli and
                            attrQname.namespaceURI != XbrlConst.xbrldt):
                            attrs[concept.prefixedNameQname(attrName)] = attrValue  # type: ignore[index]
                for attr in fromCustAttrs.keys():
                    if attr not in toCustAttrs:
                        action = self.createConceptEvent(vercd, "vercd:conceptAttributeDelete", fromConcept, None, action, fromCustomAttribute=attr, fromValue=fromCustAttrs[attr])
                    elif fromCustAttrs[attr] != toCustAttrs[attr]:
                        action = self.createConceptEvent(vercd, "vercd:conceptAttributeChange", fromConcept, toConcept, action, fromCustomAttribute=attr, toCustomAttribute=attr, fromValue=fromCustAttrs[attr], toValue=toCustAttrs[attr])
                for attr in toCustAttrs.keys():
                    if attr not in fromCustAttrs:
                        action = self.createConceptEvent(vercd, "vercd:conceptAttributeAdd", None, toConcept, action, toCustomAttribute=attr, toValue=toCustAttrs[attr])

                # labels, references from each concept
                for event, arcroles in (("vercd:conceptLabel", (XbrlConst.conceptLabel, XbrlConst.elementLabel)),
                                        ("vercd:conceptReference", (XbrlConst.conceptReference, XbrlConst.elementReference))):
                    fromResources: dict[tuple[Any, ...], ModelObject] = {}
                    toResources: dict[tuple[Any, ...], ModelObject] = {}
                    for dts, concept, resources in ((self.fromDTS, fromConcept, fromResources),
                                                    (self.toDTS, toConcept, toResources)):
                        for arcrole in arcroles:
                            resourcesRelationshipSet: ModelRelationshipSet = dts.relationshipSet(arcrole)  # type: ignore[union-attr]
                            if resourcesRelationshipSet:
                                for rel in resourcesRelationshipSet.fromModelObject(concept):
                                    resource = rel.toModelObject
                                    key = ((rel.linkrole, arcrole, resource.role, resource.xmlLang,  # type: ignore[union-attr]
                                           rel.linkQname, rel.qname, resource.qname) +  # type: ignore[union-attr]
                                           XbrlUtil.attributes(dts, rel.arcElement,  # type: ignore[arg-type]
                                                exclusions={XbrlConst.xlink, "use", "priority", "order", "id"}) +
                                           XbrlUtil.attributes(dts, resource,  # type: ignore[arg-type]
                                                exclusions={XbrlConst.xlink}))
                                    resources[key] = resource  # type: ignore[assignment]
                    for key, label in fromResources.items():
                        fromText = XmlUtil.innerText(label)
                        if key not in toResources:
                            action = self.createConceptEvent(vercd, event + "Delete", fromConcept, None, action, fromResource=label, fromResourceText=fromText)
                        else:
                            toLabel = toResources[key]
                            toText = XmlUtil.innerText(toLabel)
                            if not XbrlUtil.sEqual(self.fromDTS, label, toLabel, excludeIDs=XbrlUtil.ALL_IDs_EXCLUDED, dts2=self.toDTS, ns2ns1Tbl=self.namespaceRenameToURI):  # type: ignore[arg-type]
                                action = self.createConceptEvent(vercd, event + "Change", fromConcept, toConcept, action, fromResource=label, toResource=toResources[key], fromResourceText=fromText, toResourceText=toText)
                    for key, label in toResources.items():
                        toText = XmlUtil.innerText(label)
                        if key not in fromResources:
                            action = self.createConceptEvent(vercd, event + "Add", None, toConcept, action, toResource=label, toResourceText=toText)

            else:
                self.createConceptEvent(vercu, "vercu:conceptDelete", fromConcept=fromConcept)
        for toConceptQname, toConcept in self.toDTS.qnameConcepts.items():  # type: ignore[union-attr]
            if ((toConcept.isItem or toConcept.isTuple) and
                 toConceptQname not in toConceptsMatched):
                self.createConceptEvent(vercu, "vercu:conceptAdd", toConcept=toConcept)

    def diffRelationshipSet(self, arcrole: str) -> None:
        # compare ELRs for new/removed
        fromLinkRoleUris: set[str] = set()
        toLinkRoleUris: set[str] = set()
        for dts, linkRoleUris in ((self.fromDTS, fromLinkRoleUris),
                                  (self.toDTS, toLinkRoleUris)):
            for linkroleUri in dts.relationshipSet(arcrole).linkRoleUris:  # type: ignore[union-attr]
                linkRoleUris.add(linkroleUri)
        # removed, added ELRs
        for dts, linkRoleUris, otherRoleUris, roleChanges, e1, e2, isFrom in (
                        (self.fromDTS, fromLinkRoleUris, toLinkRoleUris, self.roleChangeFromURI, "relationshipSetModelDelete", "fromRelationshipSet", True),
                        (self.toDTS, toLinkRoleUris, fromLinkRoleUris, self.roleChangeToURI, "relationshipSetModelAdd", "toRelationshipSet", False)):
            for linkRoleUri in linkRoleUris:
                if not (linkRoleUri in otherRoleUris or linkRoleUri in roleChanges):
                    # fromUri tree is removed
                    relSetEvent = None
                    relationshipSet = dts.relationshipSet(arcrole, linkRoleUri)  # type: ignore[union-attr]
                    for rootConcept in relationshipSet.rootConcepts:
                        if relSetEvent is None:
                            relSetMdlEvent = self.createRelationshipSetEvent(e1)
                            relSetEvent = self.createRelationshipSetEvent(e2, eventParent=relSetMdlEvent)
                        rs = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=linkRoleUri, arcrole=arcrole)
                        self.createRelationshipSetEvent("relationships", eventParent=rs, fromConcept=rootConcept, axis="descendant-or-self", comment="root relationship")
                elif isFrom:  # role in both, compare hierarchies
                    self.relSetAddedEvent: ModelObject | None = None
                    self.relSetDeletedEvent: ModelObject | None = None
                    otherLinkRoleUri = roleChanges[linkRoleUri] if linkRoleUri in roleChanges else linkRoleUri
                    fromRelationshipSet = dts.relationshipSet(arcrole, linkRoleUri)  # type: ignore[union-attr]
                    toRelationshipSet = self.toDTS.relationshipSet(arcrole, otherLinkRoleUri)  # type: ignore[union-attr]
                    fromRoots = fromRelationshipSet.rootConcepts
                    toRoots = toRelationshipSet.rootConcepts
                    for fromRoot in fromRoots:
                        toRootConcept = self.toDTS.qnameConcepts.get(self.toDTSqname(fromRoot.qname))  # type: ignore[arg-type,union-attr]
                        if toRootConcept is not None and toRootConcept not in toRoots: # added qname
                            if self.relSetDeletedEvent is None:
                                relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelDelete")
                                relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                                self.relSetDeletedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=linkRoleUri, arcrole=arcrole)
                            self.createRelationshipSetEvent("relationships", eventParent=self.relSetDeletedEvent, fromConcept=fromRoot, axis="descendant-or-self")
                        else:
                            # check hierarchies
                            self.diffRelationships(fromRoot, toRootConcept, fromRelationshipSet, toRelationshipSet)
                    for toRoot in toRoots:
                        fromRootConcept = self.fromDTS.qnameConcepts.get(self.fromDTSqname(toRoot.qname))  # type: ignore[arg-type,union-attr]
                        if fromRootConcept is not None and fromRootConcept not in fromRoots: # added qname
                            if self.relSetAddedEvent is None:
                                relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelAdd")
                                relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                                self.relSetAddedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toRelationshipSet.linkrole, arcrole=toRelationshipSet.arcrole)
                            self.createRelationshipSetEvent("relationships", eventParent=self.relSetAddedEvent, fromConcept=toRoot, axis="descendant-or-self", comment="root relationship")

    def diffRelationships(
        self,
        fromConcept: ModelObject | None,
        toConcept: ModelObject | None,
        fromRelationshipSet: ModelRelationshipSet,
        toRelationshipSet: ModelRelationshipSet,
    ) -> None:
        fromRels = fromRelationshipSet.fromModelObject(fromConcept)  # type: ignore[arg-type]
        toRels = toRelationshipSet.fromModelObject(toConcept)  # type: ignore[arg-type]
        for i, fromRel in enumerate(fromRels):
            fromTgtConcept = fromRel.toModelObject
            toTgtQname = self.toDTSqname(fromTgtConcept.qname) if fromTgtConcept is not None else None
            toRel = toRels[i] if i < len(toRels) else None
            if toRel is not None and isinstance(toRel.toModelObject, ModelConcept) and toRel.toModelObject.qname == toTgtQname:
                fromRelAttrs = XbrlUtil.attributes(self.modelXbrl, fromRel.arcElement,
                     exclusions=relationshipSetArcAttributesExclusion)
                toRelAttrs = XbrlUtil.attributes(self.modelXbrl, toRel.arcElement,
                     exclusions=relationshipSetArcAttributesExclusion,
                     ns2ns1Tbl=self.namespaceRenameToURI)
                if fromRelAttrs != toRelAttrs:
                    fromAttrsSet = set(fromRelAttrs)
                    toAttrsSet = set(toRelAttrs)
                    relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelChange")
                    relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                    relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=fromRelationshipSet.linkrole, arcrole=fromRelationshipSet.arcrole)
                    self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=fromConcept, toConcept=fromTgtConcept, attrValues=fromAttrsSet-toAttrsSet)  # type: ignore[arg-type]
                    relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                    relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toRelationshipSet.linkrole, arcrole=toRelationshipSet.arcrole)
                    self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=toConcept, toConcept=toRel.toModelObject, attrValues=toAttrsSet-fromAttrsSet)  # type: ignore[arg-type]
                else:
                    self.diffRelationships(fromTgtConcept, toRel.toModelObject, fromRelationshipSet, toRelationshipSet)
            else:
                if self.relSetDeletedEvent is None:
                    relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelDelete")
                    relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                    self.relSetDeletedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=fromRelationshipSet.linkrole, arcrole=fromRelationshipSet.arcrole)
                if toRel is not None:
                    comment = _('corresponding relationship {0} toDTS toName="{1}"').format(i + 1, XmlUtil.addQnameValue(self.reportElement, toRel.toModelObject.qname))  # type: ignore[arg-type,union-attr]
                else:
                    comment = _("toDTS does not have a corresponding relationship at position {0}").format(i + 1)
                self.createRelationshipSetEvent("relationships", eventParent=self.relSetDeletedEvent, fromConcept=fromConcept, toConcept=fromTgtConcept, comment=comment)
        for i, toRel in enumerate(toRels):
            toTgtConcept = toRel.toModelObject
            fromTgtQname = self.fromDTSqname(toTgtConcept.qname) if isinstance(toRel.toModelObject, ModelConcept) else None  # type: ignore[union-attr]
            fromRel = fromRels[i] if i < len(fromRels) else None  # type: ignore[assignment]
            if fromRel is None or not isinstance(fromRel.toModelObject, ModelConcept) or fromRel.toModelObject.qname != fromTgtQname:
                if self.relSetAddedEvent is None:
                    relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelAdd")
                    relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                    self.relSetAddedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toRelationshipSet.linkrole, arcrole=toRelationshipSet.arcrole)
                if fromRel is not None:
                    comment = _('corresponding relationship {0} toDTS toName="{1}"').format(i + 1, XmlUtil.addQnameValue(self.reportElement, fromRel.toModelObject.qname))  # type: ignore[arg-type,union-attr]
                else:
                    comment = _("fromDTS does not have a corresponding relationship at position {0}").format(i + 1)
                self.createRelationshipSetEvent("relationships", eventParent=self.relSetAddedEvent, fromConcept=toConcept, toConcept=toTgtConcept, comment=comment)

    def diffDimensionDefaults(self) -> None:
        # dimension-defaults are global
        fromDimDefaults: dict[QName, QName] = {}
        toDimDefaults: dict[QName, QName] = {}
        for dts, dimDefaults in ((self.fromDTS, fromDimDefaults),
                                  (self.toDTS, toDimDefaults)):
            for rel in dts.relationshipSet(XbrlConst.dimensionDefault).modelRelationships:  # type: ignore[union-attr]
                dimDefaults[rel.fromModelObject.qname] = rel.toModelObject.qname  # type: ignore[union-attr]
        # removed, added defaults
        for dts, dimDefaults, otherDimDefaults, otherDTSqname, e1, e2 in (
                        (self.fromDTS, fromDimDefaults, toDimDefaults, self.toDTSqname, "aspectModelDelete", "fromAspects"),
                        (self.toDTS, toDimDefaults, fromDimDefaults, self.fromDTSqname, "aspectModelAdd", "toAspects")):
            aspectEvent = None
            for fromDimQname, fromDefaultQname in dimDefaults.items():
                otherDTSDimQname = otherDTSqname(fromDimQname)
                otherDTSDefaultQname = otherDTSqname(fromDefaultQname)
                if otherDTSDimQname not in otherDimDefaults or otherDimDefaults[otherDTSDimQname] != otherDTSDefaultQname:
                    # dim default is removed
                    if aspectEvent is None:
                        aspectMdlEvent = self.createInstanceAspectsEvent(e1)
                        aspectEvent = self.createInstanceAspectsEvent(e2, eventParent=aspectMdlEvent)
                    self.createInstanceAspectsEvent("explicitDimension", (("name", fromDimQname),), eventParent=aspectEvent)  # type: ignore[arg-type]

    def diffDimensions(self) -> None:
        # DRS rels by (primary item,linkrole) of the has-hypercube relationship
        fromDRSrels: defaultdict[tuple[QName, str], list[Any]] = defaultdict(list)
        toDRSrels: defaultdict[tuple[QName, str], list[Any]] = defaultdict(list)
        for dts, DRSrels in ((self.fromDTS, fromDRSrels), (self.toDTS, toDRSrels)):
            for hasHcArcrole in (XbrlConst.all, XbrlConst.notAll):
                for DRSrel in dts.relationshipSet(hasHcArcrole).modelRelationships:  # type: ignore[union-attr]
                    if isinstance(DRSrel.fromModelObject, ModelConcept):
                        DRSrels[DRSrel.fromModelObject.qname, DRSrel.linkrole].append(DRSrel)  # type: ignore[index]
        # removed, added pri item dimensions
        for dts, DRSrels, otherDTS, otherDRSrels, otherDTSqname, roleChanges, e1, e2, isFrom in (
                        (self.fromDTS, fromDRSrels, self.toDTS, toDRSrels, self.toDTSqname, self.roleChangeFromURI, "aspectModelDelete", "fromAspects", True),
                        (self.toDTS, toDRSrels, self.fromDTS, fromDRSrels, self.fromDTSqname, self.roleChangeToURI, "aspectModelAdd", "toAspects", False)):
            for DRSkey, priItemDRSrels in DRSrels.items():
                priItemQname, linkrole = DRSkey
                priItemConcept = dts.qnameConcepts.get(priItemQname)  # type: ignore[union-attr]
                otherDTSpriItemQname = otherDTSqname(priItemQname)
                otherDTSpriItemConcept = otherDTS.qnameConcepts.get(otherDTSpriItemQname)  # type: ignore[arg-type,union-attr]
                otherLinkrole = roleChanges[linkrole] if linkrole in roleChanges else linkrole
                otherDTSpriItemDRSrels = otherDRSrels.get((otherDTSpriItemQname, otherLinkrole))  # type: ignore[arg-type]
                # all dimensions in these DRSes are anded together
                if not otherDTSpriItemDRSrels: #every dim for this pri item is added/removed
                    aspectMdlEvent = self.createInstanceAspectsEvent(e1)
                    aspectEvent = self.createInstanceAspectsEvent(e2, eventParent=aspectMdlEvent)
                    priItemInheritRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)  # type: ignore[arg-type,union-attr]
                    relatedConcepts = self.createInstanceAspectsEvent("concepts", eventParent=aspectEvent)
                    priItem = self.createInstanceAspectsEvent("concept", (("name", priItemQname),), eventParent=relatedConcepts)  # type: ignore[arg-type]
                    if priItemInheritRels:
                        self.createInstanceAspectsEvent(
                            "drsNetwork",
                            (("linkrole", linkrole),  # type: ignore[arg-type]
                             ("arcrole", XbrlConst.domainMember),
                             ("axis", "descendant-or-self")),
                            eventParent=priItem,
                        )
                    for dimRel, isNotAll, isClosed in self.DRSdimRels(dts, priItemDRSrels):  # type: ignore[arg-type]
                        dimConcept = dimRel.toModelObject
                        explDim = self.createInstanceAspectsEvent(
                            "typedDimension" if dimConcept.isTypedDimension else "explicitDimension",  # type: ignore[union-attr]
                            (("name", dimConcept.qname),) + ((("excluded", "true"),) if isNotAll else ()),  # type: ignore[arg-type,union-attr]
                            comment=self.typedDomainElementComment(dimConcept),  # type: ignore[arg-type]
                            eventParent=aspectEvent,
                        )
                        for domRel in self.DRSdomRels(dts, dimRel):  # type: ignore[arg-type]
                            domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)  # type: ignore[arg-type,union-attr]
                            member = self.createInstanceAspectsEvent("member", (("name", domRel.toModelObject.qname),), eventParent=explDim)  # type: ignore[arg-type,union-attr]
                            if domHasMemRels:
                                self.createInstanceAspectsEvent("drsNetwork",
                                                                (("linkrole", domRel.linkrole),  # type: ignore[arg-type]
                                                                 ("arcrole", XbrlConst.domainMember),
                                                                 ("axis", "descendant-or-self")),
                                                                eventParent=member)
                elif isFrom: # pri item in both, differences are found
                    # hypercube differences
                    hcDifferences = self.DRShcDiff(dts, priItemDRSrels, otherDTS, otherDTSpriItemDRSrels)  # type: ignore[arg-type]
                    if hcDifferences:
                        relSetMdlEvent = self.createRelationshipSetEvent("relationshipSetModelChange")
                        for fromHcRel, toHcRel, fromAttrsSet, toAttrsSet in hcDifferences:
                            relSetEvent = self.createRelationshipSetEvent("fromRelationshipSet", eventParent=relSetMdlEvent)
                            relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=fromHcRel.linkrole, arcrole=fromHcRel.arcrole)  # type: ignore[union-attr]
                            self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=fromHcRel.fromModelObject, toConcept=fromHcRel.toModelObject, attrValues=fromAttrsSet-toAttrsSet)  # type: ignore[arg-type,union-attr]
                            relSetEvent = self.createRelationshipSetEvent("toRelationshipSet", eventParent=relSetMdlEvent)
                            relSetChangedEvent = self.createRelationshipSetEvent("relationshipSet", eventParent=relSetEvent, linkrole=toHcRel.linkrole, arcrole=toHcRel.arcrole)  # type: ignore[union-attr]
                            self.createRelationshipSetEvent("relationships", eventParent=relSetChangedEvent, fromConcept=toHcRel.toModelObject, toConcept=toHcRel.toModelObject, attrValues=toAttrsSet-fromAttrsSet)  # type: ignore[arg-type,union-attr]
                    priItemDifferences = self.DRSdiff(priItemConcept, linkrole, otherDTSpriItemConcept, otherLinkrole, XbrlConst.domainMember)  # type: ignore[arg-type]
                    if priItemDifferences:
                        for fromRel, toRel, fromAttrSet, toAttrSet in priItemDifferences:
                            if fromRel is not None:
                                if toRel is not None:
                                    e = "aspectModelChange"
                                else:
                                    e = "aspectModelDelete"
                            else:
                                e = "aspectModelAdd"
                            aspectMdlEvent = self.createInstanceAspectsEvent(e)
                            for priQn, rel, attrSet, e in ((priItemQname, fromRel, fromAttrSet-toAttrSet, "fromAspects"),
                                                           (otherDTSpriItemQname, toRel, toAttrSet-fromAttrSet, "toAspects")):
                                if rel is not None:
                                    aspectEvent = self.createInstanceAspectsEvent(e, eventParent=aspectMdlEvent)
                                    priItemInheritRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)  # type: ignore[arg-type,union-attr]
                                    relatedConcepts = self.createInstanceAspectsEvent("concepts", eventParent=aspectEvent)
                                    priItem = self.createInstanceAspectsEvent("concept", (("name", priQn),), eventParent=relatedConcepts)  # type: ignore[arg-type]
                                    if priItemInheritRels:
                                        self.createInstanceAspectsEvent("drsNetwork",
                                                                        (("linkrole", rel.linkrole),  # type: ignore[arg-type]
                                                                         ("arcrole", XbrlConst.domainMember),
                                                                         ("axis", "descendant-or-self")),
                                                                        eventParent=priItem)
                                    for dimRel, isNotAll, isClosed in self.DRSdimRels(dts, priItemDRSrels):  # type: ignore[arg-type]
                                        dimConcept = dimRel.toModelObject
                                        explDim = self.createInstanceAspectsEvent("typedDimension" if dimConcept.isTypedDimension else "explicitDimension",  # type: ignore[union-attr]
                                                                                  (("name",dimConcept.qname),) + ((("excluded", "true"),) if isNotAll else ()),  # type: ignore[arg-type,union-attr]
                                                                                  comment=self.typedDomainElementComment(dimConcept),  # type: ignore[arg-type]
                                                                                  eventParent=aspectEvent)
                                        for domRel in self.DRSdomRels(dts, dimRel):  # type: ignore[arg-type]
                                            domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)  # type: ignore[arg-type,union-attr]
                                            member = self.createInstanceAspectsEvent("member", (("name", domRel.toModelObject.qname),), eventParent=explDim)  # type: ignore[arg-type,union-attr]
                                            if domHasMemRels:
                                                self.createInstanceAspectsEvent("drsNetwork",
                                                                                (("linkrole", rel.linkrole),  # type: ignore[arg-type]
                                                                                 ("arcrole", XbrlConst.domainMember),
                                                                                 ("axis", "descendant-or-self")),
                                                                                eventParent=member)
                    dimsDifferences = self.DRSdimsDiff(dts, priItemDRSrels, otherDTS, otherDTSpriItemDRSrels)  # type: ignore[arg-type]
                    if dimsDifferences:
                        for fromDimRel, toDimRel, isNotAll, mbrDiffs in dimsDifferences:
                            if fromDimRel is not None:
                                if toDimRel is not None:
                                    e = "aspectModelChange"
                                else:
                                    e = "aspectModelDelete"
                            else:
                                e = "aspectModelAdd"
                            aspectMdlEvent = self.createInstanceAspectsEvent(e)
                            for priQn, dimRel, e, isFrom in ((priItemQname, fromDimRel, "fromAspects", True),  # type: ignore[assignment]
                                                             (otherDTSpriItemQname, toDimRel, "toAspects", False)):
                                if dimRel is not None:
                                    aspectEvent = self.createInstanceAspectsEvent(e, eventParent=aspectMdlEvent)
                                    priItemInheritRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)  # type: ignore[arg-type,union-attr]
                                    relatedConcepts = self.createInstanceAspectsEvent("concepts", eventParent=aspectEvent)
                                    priItem = self.createInstanceAspectsEvent("concept", (("name", priQn),), eventParent=relatedConcepts)  # type: ignore[arg-type]
                                    if priItemInheritRels:
                                        self.createInstanceAspectsEvent("drsNetwork",
                                                                        (("linkrole", linkrole),  # type: ignore[arg-type]
                                                                         ("arcrole", XbrlConst.domainMember),
                                                                         ("axis", "descendant-or-self")),
                                                                         eventParent=priItem)
                                    dimConcept = dimRel.toModelObject
                                    explDim = self.createInstanceAspectsEvent("typedDimension" if dimConcept.isTypedDimension else "explicitDimension",  # type: ignore[union-attr]
                                                                              (("name", dimConcept.qname),) +  # type: ignore[arg-type,union-attr]
                                                                              ((("excluded", "true"),) if isNotAll else ()),
                                                                              comment=self.typedDomainElementComment(dimConcept),  # type: ignore[arg-type]
                                                                              eventParent=aspectEvent)
                                    if mbrDiffs:
                                        for fromRel, toRel, fromAttrSet, toAttrSet in mbrDiffs:
                                            if isFrom:
                                                rel = fromRel
                                            else:
                                                rel = toRel
                                            if rel is not None:
                                                domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, rel.linkrole).fromModelObject(rel.toModelObject)  # type: ignore[arg-type,union-attr]
                                                member = self.createInstanceAspectsEvent("member", (("name", rel.toModelObject.qname),), eventParent=explDim)  # type: ignore[arg-type,union-attr]
                                                if domHasMemRels:
                                                    self.createInstanceAspectsEvent("drsNetwork",
                                                                                    (("linkrole", rel.linkrole),  # type: ignore[arg-type]
                                                                                     ("arcrole", XbrlConst.domainMember),
                                                                                     ("axis", "descendant-or-self")),
                                                                                    eventParent=member)
                                    else:
                                        for domRel in self.DRSdomRels(dts, dimRel):  # type: ignore[arg-type]
                                            domHasMemRels = dts.relationshipSet(XbrlConst.domainMember, linkrole).fromModelObject(priItemConcept)  # type: ignore[arg-type,union-attr]
                                            self.createInstanceAspectsEvent("member", (("name", domRel.toModelObject.qname),) +  # type: ignore[arg-type,union-attr]
                                                                                      ((("linkrole", domRel.linkrole),
                                                                                        ("arcrole", XbrlConst.domainMember),
                                                                                        ("axis", "DRS-descendant-or-self")) if domHasMemRels else ()),
                                                                                      eventParent=explDim)

    def DRSdimRels(self, dts: ModelXbrl, priItemDRSrels: list[ModelRelationship]) -> list[tuple[ModelRelationship, bool, bool]]:
        return [(dimRel, hcRel.arcrole == XbrlConst.notAll, hcRel.isClosed)
                for hcRel in priItemDRSrels
                for dimRel in dts.relationshipSet(XbrlConst.hypercubeDimension, hcRel.consecutiveLinkrole).fromModelObject(hcRel.toModelObject)]  # type: ignore[arg-type]

    def DRSdomRels(self, dts: ModelXbrl, dimRel: ModelRelationship) -> list[ModelRelationship]:
        return dts.relationshipSet(XbrlConst.dimensionDomain, dimRel.consecutiveLinkrole).fromModelObject(dimRel.toModelObject)  # type: ignore[arg-type]

    def DRSdiff(
        self,
        fromConcept: ModelObject,
        fromLinkrole: str | None,
        toConcept: ModelObject,
        toLinkrole: str | None,
        arcrole: str,
        diffs: list[tuple[ModelRelationship | None, ModelRelationship | None, set[tuple[tuple[QName, Any], ...]], set[tuple[tuple[QName, Any], ...]]]] | None = None,
    ) -> list[tuple[ModelRelationship | None, ModelRelationship | None, set[tuple[tuple[QName, Any], ...]], set[tuple[tuple[QName, Any], ...]]]]:
        if diffs is None:
            diffs = []
        fromRels = self.fromDTS.relationshipSet(arcrole, fromLinkrole).fromModelObject(fromConcept)  # type: ignore[union-attr]
        toRels = self.toDTS.relationshipSet(arcrole, toLinkrole).fromModelObject(toConcept)  # type: ignore[union-attr]
        if arcrole == XbrlConst.dimensionDomain:
            arcrole = XbrlConst.domainMember  # consec rel set
        for i, fromRel in enumerate(fromRels):
            fromTgtConcept = fromRel.toModelObject
            toTgtQname = self.toDTSqname(fromTgtConcept.qname) if fromTgtConcept is not None else None
            toRel = toRels[i] if i < len(toRels) else None
            if toRel is not None and isinstance(toRel.toModelObject, ModelConcept) and toRel.toModelObject.qname == toTgtQname:
                toTgtConcept = toRel.toModelObject
                fromRelAttrs = XbrlUtil.attributes(self.modelXbrl, fromRel.arcElement,
                     exclusions=relationshipSetArcAttributesExclusion)
                toRelAttrs = XbrlUtil.attributes(self.modelXbrl, toRel.arcElement,
                     exclusions=relationshipSetArcAttributesExclusion,
                     ns2ns1Tbl=self.namespaceRenameToURI)
                if fromRelAttrs != toRelAttrs:
                    diffs.append((fromRel, toRel, set(fromRelAttrs), set(toRelAttrs)))  # type: ignore[arg-type]
                else:
                    self.DRSdiff(fromTgtConcept, fromRel.consecutiveLinkrole,
                                 toTgtConcept, toRel.consecutiveLinkrole,
                                 arcrole, diffs)
            else:
                diffs.append((fromRel, None, set(), set()))
        for i, toRel in enumerate(toRels):
            toTgtConcept = toRel.toModelObject
            fromTgtQname = self.fromDTSqname(toTgtConcept.qname) if isinstance(toRel.toModelObject, ModelConcept) else None
            fromRel = fromRels[i] if i < len(fromRels) else None
            if fromRel is None or not isinstance(fromRel.toModelObject, ModelConcept) or fromRel.toModelObject.qname != fromTgtQname:
                diffs.append((None, toRel, set(), set()))
        return diffs

    def DRShcDiff(
        self,
        fromDTS: ModelXbrl,
        fromPriItemDRSrels: list[ModelRelationship],
        toDTS: ModelXbrl,
        toPriItemDRSrels: list[ModelRelationship],
    ) -> list[tuple[ModelRelationship | None, ModelRelationship | None, set[tuple[tuple[QName, Any], ...]], set[tuple[tuple[QName, Any], ...]]]]:
        fromHcRels: dict[tuple[ModelObject, ModelObject, bool], ModelRelationship] = {}
        toHcRels: dict[tuple[ModelObject, ModelObject, bool], ModelRelationship] = {}
        for dts, priItemDRSrels, hcRels in ((fromDTS, fromPriItemDRSrels, fromHcRels), (toDTS, toPriItemDRSrels, toHcRels)):
            for hcRel in priItemDRSrels:
                hcRels[hcRel.fromModelObject, hcRel.toModelObject, hcRel.arcrole == XbrlConst.notAll] = hcRel  # type: ignore[index]
        diffs: list[tuple[ModelRelationship | None, ModelRelationship | None, set[tuple[tuple[QName, Any], ...]], set[tuple[tuple[QName, Any], ...]]]] = []
        for i, fromHcRelKey in enumerate(fromHcRels.keys()):
            fromPriItemQname, fromHcQname, isNotAll = fromHcRelKey
            toPriItemQname = self.toDTSqname(fromPriItemQname)  # type: ignore[arg-type]
            toHcQname = self.toDTSqname(fromHcQname)  # type: ignore[arg-type]
            try:
                toHcRel = fromHcRels[toPriItemQname, toHcQname, isNotAll]  # type: ignore[index]
                fromHcRel = fromHcRels[fromHcRelKey]
                fromRelAttrs = XbrlUtil.attributes(self.modelXbrl, fromHcRel.arcElement,
                     exclusions=relationshipSetArcAttributesExclusion)
                toRelAttrs = XbrlUtil.attributes(self.modelXbrl, toHcRel.arcElement,
                     exclusions=relationshipSetArcAttributesExclusion,
                     ns2ns1Tbl=self.namespaceRenameToURI)
                if fromRelAttrs != toRelAttrs:
                    diffs.append((fromHcRel, toHcRel, set(fromRelAttrs), set(toRelAttrs)))  # type: ignore[arg-type]
            except KeyError:
                pass # not tracking addition or removal of hypercubes
        return diffs

    def typedDomainIsDifferent(self, fromDimConcept: ModelConcept, toDimConcept: ModelConcept) -> bool:
        try:
            return self.typedDomainsCorrespond[fromDimConcept, toDimConcept]
        except KeyError:
            fromTypedDomain = fromDimConcept.typedDomainElement
            toTypedDomain = toDimConcept.typedDomainElement
            isCorresponding = (fromTypedDomain is not None and toTypedDomain is not None and
                               XbrlUtil.sEqual(self.fromDTS, fromTypedDomain, toTypedDomain,  # type: ignore[arg-type]
                                              excludeIDs=XbrlUtil.ALL_IDs_EXCLUDED, dts2=self.toDTS, ns2ns1Tbl=self.namespaceRenameToURI))
            self.typedDomainsCorrespond[fromDimConcept, toDimConcept] = isCorresponding
            return isCorresponding

    def typedDomainElementComment(self, dimConcept: ModelConcept) -> str | None:
        if dimConcept.isTypedDimension:
            if dimConcept.typedDomainElement is not None:
                return _("typed domain element {0}").format(dimConcept.typedDomainElement.qname)
            else:
                return _("typedDomainRef={0} (element qname cannot be determined)").format(dimConcept.typedDomainRef)
        return None

    def DRSdimsDiff(
        self,
        fromDTS: ModelXbrl,
        fromPriItemDRSrels: list[ModelRelationship],
        toDTS: ModelXbrl,
        toPriItemDRSrels: list[ModelRelationship],
    ) -> list[
            tuple[
                ModelRelationship | None,
                ModelRelationship | None,
                bool,
                list[
                    tuple[
                        ModelRelationship | None,
                        ModelRelationship | None,
                        set[tuple[tuple[QName, Any], ...]],
                        set[tuple[tuple[QName, Any], ...]],
                    ],
                ]
            ]
        ]:
        fromDims: dict[tuple[QName, bool], ModelRelationship] = {}
        toDims: dict[tuple[QName, bool], ModelRelationship] = {}
        for dts, priItemDRSrels, dims in ((fromDTS, fromPriItemDRSrels, fromDims), (toDTS, toPriItemDRSrels, toDims)):
            for dimRel, isNotAll, isClosed in self.DRSdimRels(dts, priItemDRSrels):
                dims[dimRel.toModelObject.qname, isNotAll] = dimRel  # type: ignore[union-attr]
        diffs: list[
            tuple[
                ModelRelationship | None,
                ModelRelationship | None,
                bool,
                list[
                    tuple[
                        ModelRelationship | None,
                        ModelRelationship | None,
                        set[tuple[tuple[QName, Any], ...]],
                        set[tuple[tuple[QName, Any], ...]],
                    ],
                ]
            ]
        ] = []
        for i, fromDimKey in enumerate(fromDims.keys()):
            fromDimQname, fromIsNotAll = fromDimKey
            fromDimRel = fromDims[fromDimKey]
            fromDimConcept = fromDimRel.toModelObject
            toDimQname = self.toDTSqname(fromDimQname)
            toDimRel = toDims.get((toDimQname, fromIsNotAll))  # type: ignore[arg-type]
            if toDimRel is not None:
                toDimConcept = toDimRel.toModelObject
                mbrDiffs = self.DRSdiff(fromDimConcept, fromDimRel.consecutiveLinkrole,  # type: ignore[arg-type]
                                        toDimConcept, toDimRel.consecutiveLinkrole,  # type: ignore[arg-type]
                                        XbrlConst.dimensionDomain)
                dimsCorrespond = True
                if fromDimConcept.isTypedDimension:  # type: ignore[union-attr]
                    if toDimConcept.isExplicitDimension or self.typedDomainIsDifferent(fromDimConcept, toDimConcept):  # type: ignore[arg-type,union-attr]
                        dimsCorrespond = False
                elif toDimConcept.isTypedDimension:  # type: ignore[union-attr]
                    dimsCorrespond = False
                if mbrDiffs or not dimsCorrespond:
                    diffs.append((fromDimRel, toDimRel, fromIsNotAll, mbrDiffs))
            else:
                diffs.append((fromDimRel, None, fromIsNotAll, []))
        for i, toDimKey in enumerate(toDims.keys()):
            toDimQname, toIsNotAll = toDimKey
            toDimRel = toDims[toDimKey]
            fromDimQname = self.fromDTSqname(toDimQname)  # type: ignore[assignment]
            if not fromDimQname or (fromDimQname, toIsNotAll) not in fromDims:
                diffs.append((None, toDimRel, toIsNotAll, []))
        return diffs

    def toDTSqname(self, fromDTSqname: QName | None) -> QName | None:
        if fromDTSqname is not None and fromDTSqname.namespaceURI in self.namespaceRenameFromURI:
            return qname(self.namespaceRenameFromURI[fromDTSqname.namespaceURI],
                         fromDTSqname.localName)
        return fromDTSqname

    def fromDTSqname(self, toDTSqname: QName | None) -> QName | None:
        if toDTSqname and toDTSqname.namespaceURI in self.namespaceRenameToURI:
            return qname(self.namespaceRenameToURI[toDTSqname.namespaceURI],
                         toDTSqname.localName)
        return toDTSqname

    def createAction(self) -> ModelObject:
        action = XmlUtil.addChild(self.reportElement, XbrlConst.ver, "ver:action", (("id", "action{0:05}".format(self.actionNum)),))  # type: ignore[arg-type]
        self.actionNum += 1
        XmlUtil.addChild(action, XbrlConst.ver, "ver:assignmentRef", (("ref","versioningTask"),))
        return action

    def createBaseEvent(self, eventName: str, fromURI: str, toURI: str) -> None:
        event = XmlUtil.addChild(self.createAction(), XbrlConst.ver, eventName)
        XmlUtil.addChild(event, XbrlConst.ver, "ver:fromURI", ("value", fromURI))
        XmlUtil.addChild(event, XbrlConst.ver, "ver:toURI", ("value", toURI))

    def createConceptEvent(
        self,
        eventNS: str,
        eventName: str,
        fromConcept: ModelConcept | None = None,
        toConcept: ModelConcept | None = None,
        action: ModelObject | None = None,
        fromCustomAttribute: QName | None = None,
        toCustomAttribute: QName | None = None,
        fromResource: ModelObject | None = None,
        toResource: ModelObject | None = None,
        fromValue: str | None = None,
        toValue: str | None = None,
        fromResourceText: str | None = None,
        toResourceText: str | None = None,
    ) -> ModelObject:
        if action is None:
            action = self.createAction()
        event = XmlUtil.addChild(action, eventNS, eventName)
        if fromConcept is not None:
            fromQname = XmlUtil.addQnameValue(self.reportElement, fromConcept.qname)  # type: ignore[arg-type]
            XmlUtil.addChild(event, XbrlConst.vercu, "vercu:fromConcept", ("name", fromQname))
        if fromValue is not None:
            XmlUtil.addComment(event, _("from value: {0} ").format(fromValue))
        if fromResource is not None:
            XmlUtil.addChild(event, XbrlConst.vercd, "vercd:fromResource", ("value", self.conceptHref(fromResource)))
            if fromResource.id is None and fromConcept is not None:
                XmlUtil.addComment(event, _("({0} does not have an id attribute)").format(eventName))
            if fromResourceText:
                XmlUtil.addComment(event, fromResourceText)
        if fromCustomAttribute is not None:
            if fromCustomAttribute.namespaceURI:  # has namespace
                attQname = XmlUtil.addQnameValue(self.reportElement, fromCustomAttribute)  # type: ignore[arg-type]
                XmlUtil.addChild(event, XbrlConst.vercd, "vercd:fromCustomAttribute", (("name", attQname),))
            else: # no namespace
                XmlUtil.addChild(event, XbrlConst.vercd, "vercd:fromCustomAttribute", (("name", fromCustomAttribute.localName),))
        if toConcept is not None:
            toQname = XmlUtil.addQnameValue(self.reportElement, toConcept.qname)  # type: ignore[arg-type]
            XmlUtil.addChild(event, XbrlConst.vercu, "vercb:toConcept", ("name", toQname) )
        if toValue is not None:
            XmlUtil.addComment(event, _("to value: {0} ").format(toValue))
        if toResource is not None:
            XmlUtil.addChild(event, XbrlConst.vercd, "vercd:toResource", ("value", self.conceptHref(toResource)))
            if toResource.id is None and toConcept is not None:
                XmlUtil.addComment(event, _("({0} does not have an id attribute)").format(eventName))
            if toResourceText:
                XmlUtil.addComment(event, toResourceText)
        if toCustomAttribute is not None:
            if toCustomAttribute.namespaceURI:  # has namespace
                attQname = XmlUtil.addQnameValue(self.reportElement, toCustomAttribute)  # type: ignore[arg-type]
                XmlUtil.addChild(event, XbrlConst.vercd, "vercd:toCustomAttribute", (("name", attQname),))
            else: # no namespace
                XmlUtil.addChild(event, XbrlConst.vercd, "vercd:toCustomAttribute", (("name", toCustomAttribute.localName),))

        return action

    def conceptHref(self, concept: ModelObject) -> str:
        return self.relativeUri(concept.modelDocument.uri) + "#" + XmlUtil.elementFragmentIdentifier(concept)  # type: ignore[operator]

    def createRelationshipSetEvent(
        self,
        eventName: str,
        linkrole: str | tuple[str, ...] | None = None,
        arcrole: str | tuple[str, ...] | None = None,
        fromConcept: ModelObject | None = None,
        toConcept: ModelObject | None = None,
        axis: str | None = None,
        attrValues: Iterable[str] | None = None,
        comment: str | None = None,
        eventParent: ModelObject | None = None,
    ) -> ModelObject:
        if eventParent is None:
            eventParent = self.createAction()
        eventAttributes: list[tuple[str, str | tuple[str, ...]]] = []
        if linkrole:
            eventAttributes.append(("linkrole", linkrole))
        if arcrole:
            eventAttributes.append(("arcrole", arcrole))
        if fromConcept is not None:
            eventAttributes.append(("fromName", XmlUtil.addQnameValue(self.reportElement, fromConcept.qname)))  # type: ignore[arg-type]
        if toConcept is not None:
            eventAttributes.append(("toName", XmlUtil.addQnameValue(self.reportElement, toConcept.qname)))  # type: ignore[arg-type]
        if axis:
            eventAttributes.append(("axis", axis))
        eventElement = XmlUtil.addChild(eventParent, XbrlConst.verrels, "verrels:" + eventName, attributes=eventAttributes)  # type: ignore[arg-type]
        if comment:
            XmlUtil.addComment(eventParent, " " + comment + " ")
        if attrValues:
            XmlUtil.addComment(eventParent, " " + ", ".join("{0[0]}='{0[1]}'".format(a) for a in sorted(attrValues)) + " ")
        return eventElement

    def createInstanceAspectsEvent(
        self,
        eventName: str,
        eventAttributes: list[tuple[str, str | tuple[str, ...] | QName]] | None = None,
        comment: str | None = None,
        eventParent: ModelObject | None = None,
    ) -> ModelObject:
        if eventParent is None:
            eventParent = self.createAction()
        eventElement = XmlUtil.addChild(
            eventParent,
            XbrlConst.verdim,
            "verdim:" + eventName,
            attributes=tuple(
                (  # type: ignore[misc]
                    name,
                    (
                        XmlUtil.addQnameValue(self.reportElement, val) if isinstance(val, QName) else val  # type: ignore[arg-type]
                    ),
                ) for name, val in eventAttributes
            ) if eventAttributes else None
        )
        if comment is not None:
            XmlUtil.addComment(eventParent, " " + comment + " ")
        return eventElement
