'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations

import logging
import os
import sys
import traceback
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast, Optional

import regex as re
from collections.abc import Iterable, Iterator

import arelle
from arelle import FileSource, ModelRelationshipSet, XmlUtil, ModelValue, XbrlConst, XmlValidate
from arelle.ErrorManager import ErrorManager
from arelle.Locale import format_string
from arelle.ModelObject import ModelObject
from arelle.ModelValue import dateUnionEqual
from arelle.PluginManager import pluginClassMethods
from arelle.PrototypeInstanceObject import FactPrototype, DimValuePrototype
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
from arelle.XbrlConst import standardLabel
from arelle.XbrlUtil import sEqual

if TYPE_CHECKING:
    from datetime import date, datetime
    from arelle.CntlrWinMain import CntlrWinMain
    from arelle.FileSource import FileSource as FileSourceClass
    from arelle.ModelDocument import ModelDocument as ModelDocumentClass
    from arelle.ModelDtsObject import ModelConcept, ModelType, ModelRoleType
    from arelle.ModelFormulaObject import ModelConsistencyAssertion, ModelCustomFunctionSignature, ModelVariableSet
    from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelUnit, ModelDimensionValue
    from arelle.ModelManager import ModelManager
    from arelle.ModelRelationshipSet import ModelRelationshipSet as ModelRelationshipSetClass
    from arelle.ModelValue import QName
    from arelle.PrototypeDtsObject import LinkPrototype
    from arelle.typing import TypeGetText, LocaleDict
    from arelle.ValidateUtr import UtrEntry

    _: TypeGetText  # Handle gettext
else:
    ModelFact = None
    ModelContext = None


profileStatNumber = 0

AUTO_LOCATE_ELEMENT = '771407c0-1d0c-11e1-be5e-028037ec0200' # singleton meaning choose best location for new element
DEFAULT = sys.intern("default")
NONDEFAULT = sys.intern("non-default")
DEFAULTorNONDEFAULT = sys.intern("default-or-non-default")
_NOT_FOUND = object()


def load(modelManager: ModelManager, url: str | FileSourceClass, nextaction: str | None = None, base: str | None = None, useFileSource: FileSourceClass | None = None, errorCaptureLevel: int | None = None, **kwargs: Any) -> ModelXbrl:
    """Each loaded instance, DTS, testcase, testsuite, versioning report, or RSS feed, is represented by an
    instance of a ModelXbrl object. The ModelXbrl object has a collection of ModelDocument objects, each
    representing an XML document (for now, with SQL whenever its time comes). One of the modelDocuments of
    the ModelXbrl is the entry point (of discovery or of the test suite).

    :param url: may be a filename or FileSource object
    :param nextaction: text to use as status line prompt on conclusion of loading and discovery
    :param base: the base URL if any (such as a versioning report's URL when loading to/from DTS modelXbrl).
    :param useFileSource: for internal use (when an entry point is in a FileSource archive and discovered files expected to also be in the entry point's archive.
   """
    if nextaction is None: nextaction = _("loading")
    modelXbrl = create(modelManager, errorCaptureLevel=errorCaptureLevel)
    if "errors" in kwargs: # pre-load errors, such as from taxonomy package validation
        modelXbrl.errors.extend(cast(str, kwargs.get("errors")))
    supplementalUrls = None
    if useFileSource is not None:
        modelXbrl.fileSource = useFileSource
        modelXbrl.closeFileSource = False
        url = url
    elif isinstance(url,FileSource.FileSource):
        modelXbrl.fileSource = url
        modelXbrl.closeFileSource= True
        if isinstance(modelXbrl.fileSource.url, list): # json list
            url = modelXbrl.fileSource.url[0]
            supplementalUrls = modelXbrl.fileSource.url[1:]
        #elif isinstance(modelXbrl.fileSource.url, dict): # json object
        else:
            url = cast(str, modelXbrl.fileSource.url)
    else:
        modelXbrl.fileSource = FileSource.FileSource(url, modelManager.cntlr)
        modelXbrl.closeFileSource= True
    modelXbrl.modelDocument = None
    if kwargs.get("isLoadable",True): # used for test cases to block taxonomy packages without discoverable contents
        modelXbrl.modelDocument = arelle.ModelDocument.load(modelXbrl, url, base, isEntry=True, **kwargs)
        if supplementalUrls:
            for url in supplementalUrls:
                arelle.ModelDocument.load(modelXbrl, url, base, isEntry=False, isDiscovered=True, **kwargs)
        if hasattr(modelXbrl, "entryLoadingUrl"):
            del modelXbrl.entryLoadingUrl
        loadSchemalocatedSchemas(modelXbrl)

    #from arelle import XmlValidate
    #uncomment for trial use of lxml xml schema validation of entry document
    #XmlValidate.xmlValidate(modelXbrl.modelDocument)
    modelManager.cntlr.webCache.saveUrlCheckTimes()
    for pluginXbrlMethod in pluginClassMethods("ModelXbrl.LoadComplete"):
        pluginXbrlMethod(modelXbrl)
    modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction))
    return modelXbrl

def create(
        modelManager: ModelManager, newDocumentType: int | None = None, url: str | None = None, schemaRefs: str|None = None, createModelDocument: bool = True, isEntry: bool = False,
        errorCaptureLevel: int | None = None, initialXml: str | None = None, initialComment: str | None = None, base: str | None = None, discover: bool = True, xbrliNamespacePrefix: str | None = None
) -> ModelXbrl:
    modelXbrl = ModelXbrl(modelManager, errorCaptureLevel=errorCaptureLevel)
    modelXbrl.locale = modelManager.locale
    if newDocumentType:
        modelXbrl.fileSource = FileSource.FileSource(cast(str, url), modelManager.cntlr)  # url may be an open file handle, use str(url) below
        modelXbrl.closeFileSource= True
        if createModelDocument:
            modelXbrl.modelDocument = arelle.ModelDocument.create(modelXbrl, newDocumentType, str(url), schemaRefs=schemaRefs, isEntry=isEntry, initialXml=initialXml, initialComment=initialComment, base=base, discover=discover, xbrliNamespacePrefix=xbrliNamespacePrefix)
            if isEntry:
                del modelXbrl.entryLoadingUrl
                loadSchemalocatedSchemas(modelXbrl)
    return modelXbrl

def loadSchemalocatedSchemas(modelXbrl: ModelXbrl) -> None:
    if modelXbrl.modelDocument and modelXbrl.modelDocument.type <= arelle.ModelDocument.Type.INLINEXBRLDOCUMENTSET:
        # at this point DTS is fully discovered but schemaLocated xsd's are not yet loaded
        modelDocumentsSchemaLocated: set[ModelDocumentClass] = set()
        # loadSchemalocatedSchemas sometimes adds to modelXbrl.urlDocs
        while True:
            modelDocuments: set[ModelDocumentClass] = set(modelXbrl.urlDocs.values()) - modelDocumentsSchemaLocated
            if not modelDocuments:
                break
            for modelDocument in modelDocuments:
                modelDocument.loadSchemalocatedSchemas()
            modelDocumentsSchemaLocated |= modelDocuments


MatchSubstitutionGroupValueType = TypeVar('MatchSubstitutionGroupValueType', type[ModelObject], bool)


class ModelXbrl:
    """
    .. class:: ModelXbrl(modelManager)

    ModelXbrl objects represent loaded instances and inline XBRL instances and their DTSes, DTSes
    (without instances), versioning reports, testcase indexes, testcase variation documents, and
    other document-centric loadable objects.

    :param modelManager: The controller's modelManager object for the current session or command line process.
    :type modelManager: ModelManager

        .. attribute:: urlDocs

        Dict, by URL, of loaded modelDocuments

        .. attribute:: errorCaptureLevel

        Minimum logging level to capture in errors list (default is INCONSISTENCY)

        .. attribute:: errors

        Captured error codes (at or over minimum error capture logging level) and assertion results, which were sent to logger, via log() methods, used for validation and post-processing

        .. attribute:: logErrorCount, logWarningCoutn, logInfoCount

        Counts of respective error levels processed by modelXbrl logger

        .. attribute:: arcroleTypes

        Dict by arcrole of defining modelObjects

        .. attribute:: roleTypes

        Dict by role of defining modelObjects

        .. attribute:: qnameConcepts

        Dict by qname (QName) of all top level schema elements, regardless of whether discovered or not discoverable (not in DTS)

        .. attribute:: qnameAttributes

        Dict by qname of all top level schema attributes

        .. attribute:: qnameAttributeGroups

        Dict by qname of all top level schema attribute groups

        .. attribute:: qnameTypes

        Dict by qname of all top level and anonymous types

        .. attribute:: baseSets

        Dict of base sets by (arcrole, linkrole, arc qname, link qname), (arcrole, linkrole, *, *), (arcrole, *, *, *), and in addition, collectively for dimensions, formula,  and rendering, as arcroles 'XBRL-dimensions', 'XBRL-formula', and 'Table-rendering'.

        .. attribute:: relationshipSets

        Dict of effective relationship sets indexed same as baseSets (including collective indices), but lazily resolved when requested.

        .. attribute:: qnameDimensionDefaults

        Dict of dimension defaults by qname of dimension

        .. attribute:: facts

        List of top level facts (not nested in tuples), document order

        .. attribute:: factsInInstance

        List of all facts in instance (including nested in tuples), document order

        .. attribute:: contexts

        Dict of contexts by id

        .. attribute:: units

        Dict of units by id

        .. attribute:: modelObjects

        Model objects in loaded order, allowing object access by ordinal index (for situations, such as tkinter, where a reference to an object would create a memory freeing difficulty).

        .. attribute:: qnameParameters

        Dict of formula parameters by their qname

        .. attribute:: modelVariableSets

        Set of variableSets in formula linkbases

        .. attribute:: modelConsistencyAssertions

        Set of modelConsistencyAssertions in formula linkbases

        .. attribute:: modelCustomFunctionSignatures

        Dict of custom function signatures by qname and by qname,arity

        .. attribute:: modelCustomFunctionImplementations

        Dict of custom function implementations by qname

        .. attribute:: views

        List of view objects

        .. attribute:: langs

        Set of langs in use by modelXbrl

        .. attribute:: labelRoles

        Set of label roles in use by modelXbrl's linkbases

        .. attribute:: hasXDT

        True if dimensions discovered

        .. attribute:: hasTableRendering

        True if table rendering discovered

        .. attribute:: hasTableIndexing

        True if table indexing discovered

        .. attribute:: hasFormulae

        True if formulae discovered

        .. attribute:: formulaOutputInstance

        Standard output instance if formulae produce one.

        .. attribute:: hasRendering

        True if rendering tables are discovered

        .. attribute:: Log

        Logger for modelXbrl

    """

    closeFileSource: bool
    dimensionDefaultConcepts: dict[ModelConcept, ModelConcept]
    entryLoadingUrl: str
    fileSource: FileSourceClass
    ixdsDocUrls: list[str]
    ixdsHtmlElements: list[Any]
    isDimensionsValidated: bool
    locale: LocaleDict | None
    modelDocument: ModelDocumentClass | None
    uri: str
    uriDir: str
    targetRelationships: set[ModelObject]
    qnameDimensionContextElement: dict[QName, str]
    _factsByDimQname: dict[QName, dict[QName | str | None, set[ModelFact]]]
    _factsByQname: dict[QName, set[ModelFact]]
    _factsByDatatype: dict[bool | tuple[bool, QName], set[ModelFact]]
    _factsByLocalName: dict[str, set[ModelFact]]
    _factsByPeriodType: dict[str, set[ModelFact]]
    _nonNilFactsInInstance: set[ModelFact]
    _startedProfiledActivity: float
    _startedTimeStat: float
    _qnameUtrUnits: dict[QName, UtrEntry]

    def __init__(self,  modelManager: ModelManager, errorCaptureLevel: int | None = None) -> None:
        self.modelManager = modelManager
        self.skipDTS: bool = modelManager.skipDTS
        self.init(errorCaptureLevel=errorCaptureLevel)

    def init(self, keepViews: bool = False, errorCaptureLevel: int | None = None) -> None:
        self.uuid: str = uuid.uuid1().urn
        self.namespaceDocs: defaultdict[str, list[ModelDocumentClass]] = defaultdict(list)
        self.urlDocs: dict[str, ModelDocumentClass] = {}
        self.urlUnloadableDocs: dict[bool, str] = {}  # if entry is True, entry is blocked and unloadable, False means loadable but warned
        self.errorCaptureLevel: int = (errorCaptureLevel or logging._checkLevel("INCONSISTENCY"))  # type: ignore[attr-defined]
        self.errorManager = ErrorManager(self.modelManager, self.errorCaptureLevel)
        self.arcroleTypes: defaultdict[str, list[ModelRoleType]] = defaultdict(list)
        self.roleTypes: defaultdict[str, list[ModelRoleType]] = defaultdict(list)
        self.qnameConcepts: dict[QName, ModelConcept] = {}  # indexed by qname of element
        self.nameConcepts: defaultdict[str, list[ModelConcept]] = defaultdict(list)  # contains ModelConcepts by name
        self.qnameAttributes: dict[QName, Any] = {}
        self.qnameAttributeGroups: dict[QName, Any] = {}
        self.qnameGroupDefinitions: dict[QName, Any] = {}
        self.qnameTypes: dict[QName, ModelType] = {}  # contains ModelTypes by qname key of type
        self.baseSets: defaultdict[tuple[str, str | None, QName | None, QName | None], list[ModelObject | LinkPrototype]] = defaultdict(list)  # contains ModelLinks for keys arcrole, arcrole#linkrole
        self.relationshipSets: dict[tuple[str] | tuple[tuple[str, ...] | str, tuple[str, ...] | str | None, QName | None, QName | None, bool], ModelRelationshipSetClass] = {}  # contains ModelRelationshipSets by bas set keys
        self.qnameDimensionDefaults: dict[QName, QName] = {}  # contains qname of dimension (index) and default member(value)
        self.facts: list[ModelFact] = []
        self.factsInInstance: set[ModelFact] = set()
        self.undefinedFacts: list[ModelFact] = []  # elements presumed to be facts but not defined
        self.contexts: dict[str, ModelContext] = {}
        self.ixdsUnmappedContexts: dict[str, ModelContext] = {}
        self._contextsInUseMarked = False
        self.units: dict[str, ModelUnit] = {}
        self.ixdsUnmappedUnits: dict[str, ModelUnit] = {}
        self._unitsInUseMarked = False
        self.modelObjects: list[ModelObject] = []
        self.qnameParameters: dict[QName, Any] = {}
        self.modelVariableSets: set[ModelVariableSet] = set()
        self.modelConsistencyAssertions: set[ModelConsistencyAssertion] = set()
        self.modelCustomFunctionSignatures: dict[QName | tuple[QName | None, int], ModelCustomFunctionSignature] = {}
        self.modelCustomFunctionImplementations: set[ModelDocumentClass] = set()
        self.modelRenderingTables: set[Any] = set()
        if not keepViews:
            self.views: list[Any] = []
        self.langs: set[str] = {self.modelManager.defaultLang}
        self.labelroles: set[str] = {standardLabel}
        self.hasXDT: bool = False
        self.hasTableRendering: bool = False
        self.hasTableIndexing: bool = False
        self.hasFormulae: bool = False
        self.loadedFromOIM = False
        self.loadedFromOimErrorCount = 0
        self.formulaOutputInstance: ModelXbrl | None = None
        self.logger: logging.Logger | None = self.modelManager.cntlr.logger
        self.logRefObjectProperties: bool = getattr(self.logger, "logRefObjectProperties", False)
        self.logRefHasPluginAttrs: bool = any(True for m in pluginClassMethods("Logging.Ref.Attributes"))
        self.logRefHasPluginProperties: bool = any(True for m in pluginClassMethods("Logging.Ref.Properties"))
        self.profileStats: dict[str, tuple[int, float, float | int]] = {}
        self.schemaDocsToValidate: set[ModelDocumentClass] = set()
        self.modelXbrl = self  # for consistency in addressing modelXbrl
        self.arelleUnitTests: dict[str, str] = {}  # unit test entries (usually from processing instructions
        for pluginXbrlMethod in pluginClassMethods("ModelXbrl.Init"):
            pluginXbrlMethod(self)

    def close(self) -> None:
        """Closes any views, formula output instances, modelDocument(s), and dereferences all memory used
        """
        if not self.isClosed:
            self.closeViews()
            if self.formulaOutputInstance:
                self.formulaOutputInstance.close()
            if hasattr(self,"fileSource") and self.closeFileSource:
                self.fileSource.close()
            modelDocument = getattr(self,"modelDocument",None)
            urlDocs = getattr(self,"urlDocs",None)
            for relSet in self.relationshipSets.values():
                relSet.clear()
            self.__dict__.clear() # dereference everything before closing document
            if modelDocument:
                modelDocument.close(urlDocs=urlDocs)

    @property
    def isClosed(self) -> bool:
        """
        :returns:  bool -- True if closed (python object has deferenced and deleted all attributes after closing)
        """
        return not bool(self.__dict__)  # closed when dict is empty

    def reload(self,nextaction: str, reloadCache: bool = False) -> None:
        """Reloads all model objects from their original entry point URL, preserving any open views (which are reloaded).

        :param nextAction: status line text string, if any, to show upon completion
        :param reloadCache: True to force clearing and reloading of web cache, if working online.
        """
        self.init(keepViews=True)
        self.modelDocument = arelle.ModelDocument.load(self, self.fileSource.url, isEntry=True, reloadCache=reloadCache)
        self.modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction),5000)
        self.modelManager.reloadViews(self)

    def closeViews(self) -> None:
        """Close views associated with this modelXbrl
        """
        if not self.isClosed:
            for view in range(len(self.views)):
                if len(self.views) > 0:
                    self.views[0].close()

    @property
    def displayUri(self) -> Any:
        if hasattr(self, "ixdsDocUrls"):
            return "IXDS {}".format(", ".join(os.path.basename(url) for url in self.ixdsDocUrls))
        elif hasattr(self, "uri"):
            return self.uri
        else:
            return self.fileSource.url

    def contextsByDocument(self) -> dict[str, list[ModelContext]]:
        contextsByDocument = defaultdict(list)
        for context in self.contexts.values():
            contextsByDocument[context.modelDocument.filepath].append(context)
        contextsByDocument.default_factory = None
        return contextsByDocument

    def entityIdentifiersInDocument(self) -> set[tuple[str, str]]:
        return {context.entityIdentifier for context in self.contexts.values()}

    def relationshipSet(self, arcrole: tuple[str, ...] | str, linkrole: tuple[str, ...] | str | None = None, linkqname: QName | None = None, arcqname: QName | None = None, includeProhibits: bool = False) -> ModelRelationshipSetClass:
        """Returns a relationship set matching specified parameters (only arcrole is required).

        Resolve and determine relationship set.  If a relationship set of the same parameters was previously resolved, it is returned from a cache.

        :param arcrole: Required arcrole, or special collective arcroles 'XBRL-dimensions', 'XBRL-formula', and 'Table-rendering'
        :param linkrole: Linkrole (wild if None)
        :param arcqname: Arc element qname (wild if None)
        :param includeProhibits: True to include prohibiting arc elements as relationships
        """
        key = (arcrole, linkrole, linkqname, arcqname, includeProhibits)
        if key not in self.relationshipSets:
            ModelRelationshipSet.create(self, arcrole, linkrole, linkqname, arcqname, includeProhibits)
        return self.relationshipSets[key]

    def baseSetModelLink(self, linkElement: Any) -> Any:
        for modelLink in self.baseSets[("XBRL-footnotes", None, None, None)]:
            if modelLink == linkElement:
                return modelLink
        return None

    def roleUriTitle(self, roleURI: str) -> str:
        return re.sub(r"(?!^)[A-Z]", r" \g<0>", os.path.basename(roleURI)).title()

    def roleTypeDefinition(self, roleURI: str, lang: str | None = None) -> str:
        modelRoles  = self.roleTypes.get(roleURI, ())
        if modelRoles:
            _roleType: ModelRoleType = modelRoles[0]
            return cast(str, _roleType.genLabel(lang=lang, strip=True) or _roleType.definition or self.roleUriTitle(roleURI))
        return self.roleUriTitle(roleURI)

    def roleTypeName(self, roleURI: str, lang: str | None = None) -> str:
        # authority-specific role type name
        for pluginXbrlMethod in pluginClassMethods("ModelXbrl.RoleTypeName"):
            _roleTypeName = pluginXbrlMethod(self, roleURI, lang)
            if _roleTypeName:
                return cast(str, _roleTypeName)
        return self.roleTypeDefinition(roleURI, lang)

    def matchSubstitutionGroup(self, elementQname: QName, subsGrpMatchTable: dict[QName | None, MatchSubstitutionGroupValueType]) -> MatchSubstitutionGroupValueType | None:
        """Resolve a subsitutionGroup for the elementQname from the match table

        Used by ModelObjectFactory to return Class type for new ModelObject subclass creation, and isInSubstitutionGroup

        :param elementQname: Element/Concept QName to find substitution group
        :param subsGrpMatchTable: Table of substitutions used to determine xml proxy object class for xml elements and substitution group membership
        """
        result = subsGrpMatchTable.get(elementQname, _NOT_FOUND)
        if result is not _NOT_FOUND:
            return cast(MatchSubstitutionGroupValueType, result) # head of substitution group
        elementMdlObj = self.qnameConcepts.get(elementQname)
        if elementMdlObj is not None:
            subsGrpMdlObj = elementMdlObj.substitutionGroup
            while subsGrpMdlObj is not None:
                subsGrpQname = subsGrpMdlObj.qname
                result = subsGrpMatchTable.get(subsGrpQname, _NOT_FOUND)
                if result is not _NOT_FOUND:
                    return cast(MatchSubstitutionGroupValueType, result)
                subsGrpMdlObj = subsGrpMdlObj.substitutionGroup
        return subsGrpMatchTable.get(None)

    def isInSubstitutionGroup(self, elementQname: QName, subsGrpQnames: QName | Iterable[QName] | None) -> bool:
        """Determine if element is in substitution group(s)
        Used by ModelObjectFactory to return Class type for new ModelObject subclass creation, and isInSubstitutionGroup

        :param elementQname: Element/Concept QName to determine if in substitution group(s)
        :param subsGrpQnames: QName or iterable of QNames
        """
        qnames: Iterable[QName | None]
        if isinstance(subsGrpQnames, Iterable):
            qnames = subsGrpQnames
        else:
            qnames = [subsGrpQnames]
        matchingSubstitutionGroup = cast(
            Optional[bool],
            self.matchSubstitutionGroup(elementQname, {qn: (qn is not None) for qn in qnames})
        )
        return matchingSubstitutionGroup is not None and matchingSubstitutionGroup

    def createInstance(self, url: str) -> None:
        """ Creates an instance document for a DTS which didn't have an instance document, such as
        to create a new instance for a DTS which was loaded from a taxonomy or linkbase entry point.

        :param url: File name to save the new instance document
        """
        if self.modelDocument and self.modelDocument.type == arelle.ModelDocument.Type.INSTANCE:
            # entry already is an instance, delete facts etc.
            del self.facts[:]
            self.factsInInstance.clear()
            del self.undefinedFacts[:]
            self.contexts.clear()
            self.units.clear()
            self.modelDocument.idObjects.clear
            del self.modelDocument.hrefObjects[:]
            self.modelDocument.schemaLocationElements.clear()
            self.modelDocument.referencedNamespaces.clear()
            for child in list(self.modelDocument.xmlRootElement):
                if not (isinstance(child, ModelObject) and child.namespaceURI == XbrlConst.link and
                        child.localName.endswith("Ref")): # remove contexts, facts, footnotes
                    self.modelDocument.xmlRootElement.remove(child)
        else:
            priorFileSource = self.fileSource
            self.fileSource = FileSource.FileSource(url, self.modelManager.cntlr)
            if isHttpUrl(self.uri):
                schemaRefUri = self.uri
            else:   # relativize local paths
                schemaRefUri = os.path.relpath(self.uri, os.path.dirname(url))
            self.modelDocument = arelle.ModelDocument.create(self, arelle.ModelDocument.Type.INSTANCE, url, schemaRefs=[schemaRefUri], isEntry=True)
            if priorFileSource:
                priorFileSource.close()
            self.closeFileSource= True
            del self.entryLoadingUrl
        # reload dts views
        if self.views: # runs with GUI
            from arelle import ViewWinDTS
            for view in self.views:
                if isinstance(view, ViewWinDTS.ViewDTS):
                    cast('CntlrWinMain', self.modelManager.cntlr).uiThreadQueue.put((view.view, []))

    def saveInstance(self, **kwargs: Any) -> Any:
        """Saves current instance document file.

        :param overrideFilepath: specify to override saving in instance's modelDocument.filepath
        """
        assert self.modelDocument is not None
        self.modelDocument.save(**kwargs)

    @property
    def prefixedNamespaces(self) -> dict[str, str]:
        """Dict of prefixes for namespaces defined in DTS
        """
        prefixedNamespaces = {}
        for nsDocs in self.namespaceDocs.values():
            for nsDoc in nsDocs:
                ns = nsDoc.targetNamespace
                if ns:
                    prefix = XmlUtil.xmlnsprefix(nsDoc.xmlRootElement, ns)
                    if prefix and prefix not in prefixedNamespaces:
                        prefixedNamespaces[prefix] = ns
        return prefixedNamespaces

    def matchContext(
            self, entityIdentScheme: str, entityIdentValue: str, periodType: str, periodStart: date | datetime, periodEndInstant: date | datetime,
            dims: dict[ModelDimensionValue, QName], segOCCs: ModelObject, scenOCCs: ModelObject
    ) -> ModelContext | None:
        """Finds matching context, by aspects, as in formula usage, if any

        :param entityIdentScheme: Scheme to match
        :param entityIdentValue: Entity identifier value to match
        :param periodType: Period type to match ("instant", "duration", or "forever")
        :param periodStart: Date or dateTime of period start
        :param periodEndInstant: Date or dateTime of period send
        :param dims: Dimensions
        :param segOCCs: Segment non-dimensional nodes
        :param scenOCCs: Scenario non-dimensional nodes
        """
        if dims:
            segAspect, scenAspect = (arelle.ModelFormulaObject.Aspect.NON_XDT_SEGMENT, arelle.ModelFormulaObject.Aspect.NON_XDT_SCENARIO)
        else:
            segAspect, scenAspect = (arelle.ModelFormulaObject.Aspect.COMPLETE_SEGMENT, arelle.ModelFormulaObject.Aspect.COMPLETE_SCENARIO)
        for c in self.contexts.values():
            if (c.entityIdentifier == (entityIdentScheme, entityIdentValue) and
                ((c.isInstantPeriod and periodType == "instant" and dateUnionEqual(c.instantDatetime, periodEndInstant, instantEndDate=True)) or
                 (c.isStartEndPeriod and periodType == "duration" and dateUnionEqual(c.startDatetime, periodStart) and dateUnionEqual(c.endDatetime, periodEndInstant, instantEndDate=True)) or
                 (c.isForeverPeriod and periodType == "forever")) and
                 # dimensions match if dimensional model
                 (dims is None or (
                    (c.qnameDims.keys() == dims.keys()) and
                        all([cDim.isEqualTo(dims[cDimQn]) for cDimQn, cDim in c.qnameDims.items()]))) and
                 # OCCs match for either dimensional or non-dimensional modle
                 all(
                   all([sEqual(self, cOCCs[i], mOCCs[i]) for i in range(len(mOCCs))])  # type: ignore[arg-type]
                     if len(cOCCs) == len(mOCCs) else False
                        for cOCCs,mOCCs in ((c.nonDimValues(segAspect),segOCCs),
                                            (c.nonDimValues(scenAspect),scenOCCs)))
                ):
                    return c
        return None

    def createContext(
            self, entityIdentScheme: str, entityIdentValue: str, periodType: str, periodStart: datetime | date, periodEndInstant: datetime | date, priItem: QName | None,
            dims: dict[int | QName, QName | DimValuePrototype], segOCCs: ModelObject, scenOCCs: ModelObject, afterSibling: ModelObject | str | None = None, beforeSibling: ModelObject | None = None, id: str | None = None
    ) -> ModelObject:
        """Creates a new ModelContext and validates (integrates into modelDocument object model).

        :param entityIdentScheme: Scheme to match
        :param entityIdentValue: Entity identifier value to match
        :param periodType: Period type to match ("instant", "duration", or "forever")
        :param periodStart: Date or dateTime of period start
        :param periodEndInstant: Date or dateTime of period send
        :param dims: Dimensions
        :param segOCCs: Segment non-dimensional nodes
        :param scenOCCs: Scenario non-dimensional nodes
        :param beforeSibling: lxml element in instance to insert new concept before
        :param afterSibling: lxml element in instance to insert new concept after
        :param id: id to assign to new context, if absent an id will be generated
        """
        assert self.modelDocument is not None
        xbrlElt = self.modelDocument.xmlRootElement
        if cast(str, afterSibling) == AUTO_LOCATE_ELEMENT:
            afterSibling = XmlUtil.lastChild(xbrlElt, XbrlConst.xbrli, ("schemaLocation", "roleType", "arcroleType", "context"))
        cntxId = id if id else 'c-{0:02}'.format( len(self.contexts) + 1)
        newCntxElt = cast(ModelContext, XmlUtil.addChild(xbrlElt, XbrlConst.xbrli, "context", attributes=("id", cntxId),
                                      afterSibling=cast(Optional[ModelObject], afterSibling), beforeSibling=beforeSibling))
        entityElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "entity")
        XmlUtil.addChild(entityElt, XbrlConst.xbrli, "identifier",
                            attributes=("scheme", entityIdentScheme),
                            text=entityIdentValue)
        periodElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "period")
        if periodType == "forever":
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "forever")
        elif periodType == "instant":
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "instant",
                             text=XmlUtil.dateunionValue(periodEndInstant, subtractOneDay=True))
        elif periodType == "duration":
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "startDate",
                             text=XmlUtil.dateunionValue(periodStart))
            XmlUtil.addChild(periodElt, XbrlConst.xbrli, "endDate",
                             text=XmlUtil.dateunionValue(periodEndInstant, subtractOneDay=True))
        segmentElt = None
        scenarioElt = None
        if dims: # requires primary item to determin ambiguous concepts
            ''' in theory we have to check full set of dimensions for validity in source or any other
                context element, but for shortcut will see if each dimension is already reported in an
                unambiguous valid contextElement
            '''
            fpDims: dict[int | QName, QName | DimValuePrototype]
            if priItem is not None: # creating concept for a specific fact
                dims[2] = priItem # Aspect.CONCEPT: prototype needs primary item as an aspect
                fp = FactPrototype(self, dims)
                del dims[2] # Aspect.CONCEPT
                # force trying a valid prototype's context Elements
                if not isFactDimensionallyValid(self, fp, setPrototypeContextElements=True):
                    self.info("arelle:info",
                        _("Create context for %(priItem)s, cannot determine valid context elements, no suitable hypercubes"),
                        modelObject=self, priItem=priItem)
                    # fp.context.qnameDims is actually of type dict[QName, DimValuePrototype]
                fpDims = cast(dict[Union[int, 'QName'], Union['QName', DimValuePrototype]], fp.context.qnameDims)
            else:
                fpDims = dims # dims known to be valid (such as for inline extraction)
            for dimQname in sorted(fpDims.keys()):
                dimValue:DimValuePrototype | ModelDimensionValue | QName = fpDims[dimQname]
                if isinstance(dimValue, (DimValuePrototype,arelle.ModelInstanceObject.ModelDimensionValue)):
                    dimMemberQname = dimValue.memberQname  # None if typed dimension
                    contextEltName = dimValue.contextElement
                else: # qname for explicit or node for typed
                    dimMemberQname = None
                    contextEltName = None
                if contextEltName == "segment":
                    if segmentElt is None:
                        segmentElt = XmlUtil.addChild(entityElt, XbrlConst.xbrli, "segment")
                    contextElt = segmentElt
                elif contextEltName == "scenario":
                    if scenarioElt is None:
                        scenarioElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "scenario")
                    contextElt = scenarioElt
                else:
                    self.info("arelleLinfo",  #type: ignore[func-returns-value]
                        _("Create context, %(dimension)s, cannot determine context element, either no all relationship or validation issue"),
                        modelObject=self, dimension=dimQname),
                    continue
                dimAttr = ("dimension", XmlUtil.addQnameValue(xbrlElt, cast('QName', dimQname)))  #Typing thinks dimQname might still be an integer
                if cast('DimValuePrototype | ModelDimensionValue', dimValue).isTyped:  #Typing thinks that this can also be a QName
                    dimElt = XmlUtil.addChild(contextElt, XbrlConst.xbrldi, "xbrldi:typedMember",
                                              attributes=dimAttr)
                    if isinstance(dimValue, (arelle.ModelInstanceObject.ModelDimensionValue, DimValuePrototype)) and dimValue.isTyped:
                        XmlUtil.copyNodes(dimElt, cast(ModelObject, dimValue.typedMember))
                elif dimMemberQname:
                    dimElt = XmlUtil.addChild(contextElt, XbrlConst.xbrldi, "xbrldi:explicitMember",
                                              attributes=dimAttr,
                                              text=XmlUtil.addQnameValue(xbrlElt, dimMemberQname))
        if segOCCs:
            if segmentElt is None:
                segmentElt = XmlUtil.addChild(entityElt, XbrlConst.xbrli, "segment")
            XmlUtil.copyNodes(segmentElt, segOCCs)
        if scenOCCs:
            if scenarioElt is None:
                scenarioElt = XmlUtil.addChild(newCntxElt, XbrlConst.xbrli, "scenario")
            XmlUtil.copyNodes(scenarioElt, scenOCCs)

        XmlValidate.validate(self, newCntxElt)
        self.modelDocument.contextDiscover(newCntxElt)
        if hasattr(self, "_dimensionsInUse"):
            for dim in newCntxElt.qnameDims.values():
                self._dimensionsInUse.add(dim.dimension)
        return newCntxElt

    def matchUnit(self, multiplyBy: list[QName], divideBy: list[QName]) -> ModelUnit | None:
        """Finds matching unit, by measures, as in formula usage, if any

        :param multiplyBy: List of multiply-by measure QNames (or top level measures if no divideBy)
        :param divideBy: List of multiply-by measure QNames (or empty list if no divideBy)
        """
        _multiplyBy = tuple(sorted(multiplyBy))
        _divideBy = tuple(sorted(divideBy))
        for u in self.units.values():
            if u.measures == (_multiplyBy,_divideBy):
                return u
        return None

    def createUnit(self, multiplyBy: list[QName], divideBy: list[QName], afterSibling: ModelObject | None = None, beforeSibling: ModelObject | None = None, id: str | None = None) -> ModelObject:
        """Creates new unit, by measures, as in formula usage, if any

        :param multiplyBy: List of multiply-by measure QNames (or top level measures if no divideBy)
        :param divideBy: List of multiply-by measure QNames (or empty list if no divideBy)
        :param beforeSibling: lxml element in instance to insert new concept before
        :param afterSibling: lxml element in instance to insert new concept after
        :param id: id to assign to new unit, if absent an id will be generated
        """
        assert self.modelDocument is not None
        xbrlElt = self.modelDocument.xmlRootElement
        if afterSibling == cast('ModelObject', AUTO_LOCATE_ELEMENT):
            afterSibling = XmlUtil.lastChild(xbrlElt, XbrlConst.xbrli, ("schemaLocation", "roleType", "arcroleType", "context", "unit"))
        unitId = id if id else 'u-{0:02}'.format( len(self.units) + 1)
        newUnitElt = XmlUtil.addChild(xbrlElt, XbrlConst.xbrli, "unit", attributes=("id", unitId),
                                      afterSibling=afterSibling, beforeSibling=beforeSibling)
        if len(divideBy) == 0:
            for multiply in multiplyBy:
                XmlUtil.addChild(newUnitElt, XbrlConst.xbrli, "measure", text=XmlUtil.addQnameValue(xbrlElt, multiply))
        else:
            divElt = XmlUtil.addChild(newUnitElt, XbrlConst.xbrli, "divide")
            numElt = XmlUtil.addChild(divElt, XbrlConst.xbrli, "unitNumerator")
            denElt = XmlUtil.addChild(divElt, XbrlConst.xbrli, "unitDenominator")
            for multiply in multiplyBy:
                XmlUtil.addChild(numElt, XbrlConst.xbrli, "measure", text=XmlUtil.addQnameValue(xbrlElt, multiply))
            for divide in divideBy:
                XmlUtil.addChild(denElt, XbrlConst.xbrli, "measure", text=XmlUtil.addQnameValue(xbrlElt, divide))
        XmlValidate.validate(self, newUnitElt)
        self.modelDocument.unitDiscover(newUnitElt)
        return newUnitElt

    @property
    def nonNilFactsInInstance(self) -> set[ModelFact]:  # indexed by fact (concept) qname
        """Facts in the instance which are not nil, cached
        """
        try:
            return self._nonNilFactsInInstance
        except AttributeError:
            self._nonNilFactsInInstance = set(f for f in self.factsInInstance if not f.isNil)
            return self._nonNilFactsInInstance

    @property
    def factsByQname(self) -> dict[QName, set[ModelFact]]:  # indexed by fact (concept) qname
        """Facts in the instance indexed by their QName, cached
        """
        try:
            return self._factsByQname
        except AttributeError:
            fbqn: dict[QName, set[ModelFact]]
            self._factsByQname = fbqn = defaultdict(set)
            for f in self.factsInInstance:
                if f.qname is not None:
                    fbqn[f.qname].add(f)
            return fbqn

    @property
    def factsByLocalName(self) -> dict[str, set[ModelFact]]:  # indexed by fact (concept) localName
        """Facts in the instance indexed by their LocalName, cached
        """
        try:
            return self._factsByLocalName
        except AttributeError:
            fbln: dict[str, set[ModelFact]]
            self._factsByLocalName = fbln = defaultdict(set)
            for f in self.factsInInstance:
                if f.qname is not None:
                    fbln[f.qname.localName].add(f)
            return fbln

    def factsByDatatype(self, notStrict: bool, typeQname: QName) -> set[ModelFact] | None:  # indexed by fact (concept) qname
        """Facts in the instance indexed by data type QName, cached as types are requested

        :param notSctrict: if True, fact may be derived
        """
        try:
            return self._factsByDatatype[notStrict, typeQname]
        except AttributeError:
            self._factsByDatatype = {}
            return self.factsByDatatype(notStrict, typeQname)
        except KeyError:
            fbdt: set[ModelFact]
            self._factsByDatatype[notStrict, typeQname] = fbdt = set()
            for f in self.factsInInstance:
                c = f.concept
                if c is not None and (c.typeQname == typeQname or (notStrict and c.type is not None and c.type.isDerivedFrom(typeQname))):
                    fbdt.add(f)
            return fbdt

    def factsByPeriodType(self, periodType: str) -> set[ModelFact]:  # indexed by fact (concept) qname
        """Facts in the instance indexed by periodType, cached

        :param periodType: Period type to match ("instant", "duration", or "forever")
        """
        try:
            return self._factsByPeriodType[periodType]
        except AttributeError:
            fbpt: defaultdict[str, set[ModelFact]]
            self._factsByPeriodType = fbpt = defaultdict(set)
            for f in self.factsInInstance:
                p = f.concept.periodType
                if p:
                    fbpt[p].add(f)
            return self.factsByPeriodType(periodType)
        except KeyError:
            return set()  # no facts for this period type

    def factsByDimMemQname(self, dimQname: QName, memQname: QName | str | None = None) -> set[ModelFact]:  # indexed by fact (concept) qname
        """Facts in the instance indexed by their Dimension  and Member QName, cached
        If Member is None, returns facts that have the dimension (explicit or typed)
        If Member is NONDEFAULT, returns facts that have the dimension (explicit non-default or typed)
        If Member is DEFAULT, returns facts that have the dimension (explicit non-default or typed) defaulted
        """
        try:
            fbdq = self._factsByDimQname[dimQname]
            return fbdq[memQname]
        except AttributeError:
            self._factsByDimQname = {}
            return self.factsByDimMemQname(dimQname, memQname)
        except KeyError:
            self._factsByDimQname[dimQname] = fbdq = defaultdict(set)
            for fact in self.factsInInstance:
                if fact.isItem and fact.context is not None:
                    dimValue = fact.context.dimValue(dimQname)
                    if isinstance(dimValue, ModelValue.QName):  # explicit dimension default value
                        fbdq[None].add(fact) # set of all facts that have default value for dimension
                        if dimQname in self.modelXbrl.qnameDimensionDefaults:
                            fbdq[self.qnameDimensionDefaults[dimQname]].add(fact) # set of facts that have this dim and mem
                            fbdq[DEFAULT].add(fact) # set of all facts that have default value for dimension
                    elif dimValue is not None: # not default
                        fbdq[None].add(fact) # set of all facts that have default value for dimension
                        fbdq[NONDEFAULT].add(fact) # set of all facts that have non-default value for dimension
                        if dimValue.isExplicit:
                            fbdq[dimValue.memberQname].add(fact) # set of facts that have this dim and mem
                        elif dimValue.isTyped:
                            fbdq[dimValue.typedMember.textValue].add(fact) # set of facts that have this dim and mem
                    else: # default typed dimension
                        fbdq[DEFAULT].add(fact)
            return fbdq[memQname]

    @property
    def contextsInUse(self) -> Iterator[ModelContext]:
        if not self._contextsInUseMarked:
            for fact in self.factsInInstance:
                cntx = fact.context
                if cntx is not None:
                    cntx._inUse = True
            self._contextsInUseMarked = True
        return (cntx for cntx in self.contexts.values() if getattr(cntx, "_inUse", False))

    @property
    def unitsInUse(self) -> Iterator[ModelUnit]:
        if not self._unitsInUseMarked:
            for fact in self.factsInInstance:
                unit = fact.unit
                if unit is not None:
                    unit._inUse = True
            self._unitsInUseMarked = True
        return (unit for unit in self.units.values() if getattr(unit, "_inUse", False))

    @property
    def dimensionsInUse(self) -> set[Any]:
        self._dimensionsInUse: set[Any]
        try:
            return cast(set[Any], self._dimensionsInUse)
        except AttributeError:
            self._dimensionsInUse = set(dim.dimension
                                        for cntx in self.contexts.values()  # use contextsInUse?  slower?
                                        for dim in cntx.qnameDims.values())
            return self._dimensionsInUse

    def matchFact(self, otherFact: ModelFact, unmatchedFactsStack: list[ModelFact] | None = None, deemP0inf: bool = False, matchId: bool = False, matchLang: bool = True) -> ModelFact | None:
        """Finds matching fact, by XBRL 2.1 duplicate definition (if tuple), or by
        QName and VEquality (if an item), lang and accuracy equality, as in formula and test case usage

        :param otherFact: Fact to match
        :deemP0inf: boolean for formula validation to deem P0 facts to be VEqual as if they were P=INF
        """
        for fact in self.facts:
            if not matchId or otherFact.id == fact.id:
                if (fact.isTuple):
                    if otherFact.isDuplicateOf(fact, unmatchedFactsStack=unmatchedFactsStack):
                        return fact
                elif (fact.qname == otherFact.qname and fact.isVEqualTo(otherFact, deemP0inf=deemP0inf)):
                    if fact.isFraction:
                        return fact
                    elif fact.isMultiLanguage and matchLang:
                        if fact.xmlLang == otherFact.xmlLang:
                            return fact
                        # else: print('*** lang mismatch extracted "{}" expected "{}" on {} in {}'.format(fact.xmlLang or "", otherFact.xmlLang or "", fact.qname, otherFact.modelDocument.uri))
                    else:
                        if (fact.decimals == otherFact.decimals and
                            fact.precision == otherFact.precision):
                            return fact
        return None

    def createFact(
            self, conceptQname: QName, attributes: tuple[str, str] | tuple[tuple[str, str]] | None = None, text: str | None = None, parent: ModelObject | None = None, afterSibling: ModelObject | None = None,
            beforeSibling:ModelObject | None = None, validate: bool = True
    ) -> ModelFact | ModelObject:
        """Creates new fact, as in formula output instance creation, and validates into object model

        :param conceptQname: QNames of concept
        :param attributes: Tuple of name, value, or tuples of name, value tuples (name,value) or ((name,value)[,(name,value...)]), where name is either QName or clark-notation name string
        :param text: Text content of fact (will be converted to xpath compatible str by FunctionXS.xsString)
        :param parent: lxml element in instance to append as child of
        :param beforeSibling: lxml element in instance to insert new concept before
        :param afterSibling: lxml element in instance to insert new concept after
        :param validate: specify False to block XML Validation (required when constructing a tuple which is invalid until after it's contents are created)
        """
        if parent is None:
            assert self.modelDocument is not None
            parent = self.modelDocument.xmlRootElement
        self.makeelementParentModelObject = parent
        newFact = cast(
            'ModelFact', XmlUtil.addChild(parent, conceptQname, attributes=attributes, text=text,
                                        afterSibling=afterSibling, beforeSibling=beforeSibling)
        )
        if hasattr(self, "_factsByQname"):
            self._factsByQname[newFact.qname].add(newFact)
        if not isinstance(newFact, arelle.ModelInstanceObject.ModelFact):
            return newFact # unable to create fact for this concept OR DTS not loaded for target instance (e.g., inline extraction, summary output)
        del self.makeelementParentModelObject
        if validate:
            XmlValidate.validate(self, newFact)
        assert self.modelDocument is not None
        self.modelDocument.factDiscover(newFact, parentElement=parent)
        # update cached sets
        if not newFact.isNil and hasattr(self, "_nonNilFactsInInstance"):
            self._nonNilFactsInInstance.add(newFact)
        if newFact.concept is not None:
            if hasattr(self, "_factsByDatatype"):
                del self._factsByDatatype # would need to iterate derived type ancestry to populate
            if hasattr(self, "_factsByPeriodType"):
                self._factsByPeriodType[newFact.concept.periodType].add(newFact)
            if hasattr(self, "_factsByDimQname"):
                del self._factsByDimQname
        self.setIsModified()
        return newFact

    def setIsModified(self) -> None:
        """Records that the underlying document has been modified.
        """
        assert self.modelDocument is not None
        self.modelDocument.isModified = True

    def isModified(self) -> bool:
        """Check if the underlying document has been modified.
        """
        md = self.modelDocument
        if md is not None:
            return md.isModified
        else:
            return False

    def modelObject(self, objectId: str | int) -> ModelObject | None:
        """Finds a model object by an ordinal ID which may be buried in a tkinter view id string (e.g., 'somedesignation_ordinalnumber').

        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        """
        if isinstance(objectId, int):
            return self.modelObjects[objectId]
        # assume it is a string with ID in a tokenized representation, like xyz_33
        try:
            return self.modelObjects[int(objectId.rpartition("_")[2])]
        except (IndexError, ValueError):
            return None

    # UI thread viewModelObject
    def viewModelObject(self, objectId: str | int) -> None:
        """Finds model object, if any, and synchronizes any views displaying it to bring the model object into scrollable view region and highlight it
        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        """
        modelObject:ModelObject | str | int = ""
        try:
            if isinstance(objectId, (ModelObject,FactPrototype)):
                modelObject = objectId
            elif isinstance(objectId, str) and objectId.startswith("_"):
                modelObject = cast('ModelObject', self.modelObject(objectId))
            if modelObject is not None:
                for view in self.views:
                    view.viewModelObject(modelObject)
        except (IndexError, ValueError, AttributeError)as err:
            self.modelManager.addToLog(_("Exception viewing properties {0} {1} at {2}").format(
                            modelObject,
                            err, traceback.format_tb(sys.exc_info()[2])))

    # isLoggingEffectiveFor( messageCodes= messageCode= level= )
    def isLoggingEffectiveFor(self, **kwargs: Any) -> bool:  # args can be messageCode(s) and level
        logger = self.logger
        if logger is None:
            return False
        return self.errorManager.isLoggingEffectiveFor(logger, **kwargs)

    def debug(self, codes: str | tuple[str, ...], msg: str, **args: Any) -> None:
        """Same as error(), but as info
        """
        """@messageCatalog=[]"""
        self.log('DEBUG', codes, msg, **args)

    def info(self, codes: str | tuple[str, ...], msg: str, **args: Any) -> None:
        """Same as error(), but as info
        """
        """@messageCatalog=[]"""
        self.log('INFO', codes, msg, **args)

    def warning(self, codes: str | tuple[str, ...], msg: str, **args: Any) -> None:
        """Same as error(), but as warning, and no error code saved for Validate
        """
        """@messageCatalog=[]"""
        self.log('WARNING', codes, msg, **args)

    def log(self, level: str, codes: Any, msg: str, **args: Any) -> None:
        """Same as error(), but level passed in as argument
        """
        if self.logger is None:
            return
        entryLoadingUrl = None
        try:
            entryLoadingUrl = self.entryLoadingUrl
        except AttributeError:
            pass
        self.errorManager.log(
            self.logger,
            level,
            codes,
            msg,
            sourceModelXbrl=self,
            fileSource=self.fileSource,
            entryLoadingUrl=entryLoadingUrl,
            logRefObjectProperties=self.logRefObjectProperties,
            **args
        )

    def error(self, codes: str | tuple[str, ...], msg: str, **args: Any) -> None:
        """Logs a message as info, by code, logging-system message text (using %(name)s named arguments
        to compose string by locale language), resolving model object references (such as qname),
        to prevent non-dereferencable memory usage.  Supports logging system parameters, and
        special parameters modelObject, modelXbrl, or modelDocument, to provide trace
        information to the file, source line, and href (XPath element scheme pointer).
        Supports the logging exc_info argument.

        Args may include a specification of one or more ModelObjects that identify the source of the
        message, as modelObject={single-modelObject, (sequence-of-modelObjects)} or modelXbrl=modelXbrl or
        modelDocument=modelDocument.

        Args must include a named argument for each msg %(namedArg)s replacement.

        :param codes: Message code or tuple/list of message codes
        :param msg: Message text string to be formatted and replaced with named parameters in **args
        :param **args: Named arguments including modelObject, modelXbrl, or modelDocument, named arguments in msg string, and any exc_info argument.
        :param messageCodes: If first parameter codes, above, is dynamically formatted, this is a documentation string of the message codes only used for extraction of the message catalog document (not used in run-time processing).
        """
        """@messageCatalog=[]"""
        self.log('ERROR', codes, msg, **args)

    def exception(self, codes: str | tuple[str, ...], msg: str, **args: str) -> None:
        """Same as error(), but as exception
        """
        """@messageCatalog=[]"""
        self.log('CRITICAL', codes, msg, **args)

    def logProfileStats(self) -> None:
        """Logs profile stats that were collected
        """
        timeTotal = format_string(self.modelManager.locale, _("%.3f secs"), self.profileStats.get("total", (0,0,0))[1])
        timeEFM = format_string(self.modelManager.locale, _("%.3f secs"), self.profileStats.get("validateEFM", (0,0,0))[1])
        self.info("info:profileStats",
                _("Profile statistics \n") +
                ' \n'.join(format_string(self.modelManager.locale, _("%s %.3f secs, %.0fK"), (statName, statValue[1], statValue[2]), grouping=True)
                           for statName, statValue in sorted(self.profileStats.items(), key=lambda item: item[1])) +
                " \n", # put instance reference on fresh line in traces
                modelObject=self.modelXbrl.modelDocument, profileStats=self.profileStats,
                timeTotal=timeTotal, timeEFM=timeEFM)

    def profileStat(self, name: str | None = None, stat: float | None = None) -> None:
        '''
        order 1xx - load, import, setup, etc
        order 2xx - views, 26x - table lb
        3xx diff, other utilities
        5xx validation
        6xx formula
        '''
        if self.modelManager.collectProfileStats:
            import time
            global profileStatNumber
            try:
                if name:
                    thisTime = stat if stat is not None else time.time() - self._startedTimeStat
                    mem = self.modelXbrl.modelManager.cntlr.memoryUsed
                    prevTime = self.profileStats.get(name, (0,0,0))[1]
                    self.profileStats[name] = (profileStatNumber, thisTime + prevTime, mem)
                    profileStatNumber += 1
            except AttributeError:
                pass
            if stat is None:
                self._startedTimeStat = time.time()

    def profileActivity(self, activityCompleted: str | None = None, minTimeToShow: float = 0) -> None:
        """Used to provide interactive GUI messages of long-running processes.

        When the time between last profileActivity and this profileActivity exceeds minTimeToShow, then
        the time is logged (if it is shorter than it is not logged), thus providing feedback of long
        running (and possibly troublesome) processing steps.

        :param activityCompleted: Description of activity completed, or None if call is just to demark starting of a profiled activity.
        :param minTimeToShow: Seconds of elapsed time for activity, if longer then the profile message appears in the log.
        """
        import time
        try:
            if activityCompleted:
                timeTaken = time.time() - self._startedProfiledActivity
                if timeTaken > minTimeToShow:
                    self.info("info:profileActivity",
                            _("%(activity)s %(time)s secs\n"),
                            modelObject=self.modelXbrl.modelDocument, activity=activityCompleted,
                            time=format_string(self.modelManager.locale, "%.3f", timeTaken, grouping=True))
        except AttributeError:
            pass
        self._startedProfiledActivity = time.time()

    def saveDTSpackage(self) -> None:
        """Contributed program to save DTS package as a zip file.  Refactored into a plug-in (and may be removed from main code).
        """
        if self.fileSource.isArchive:
            return
        from zipfile import ZipFile
        import os
        entryFilename = cast(str, self.fileSource.url)
        pkgFilename = entryFilename + ".zip"
        with ZipFile(pkgFilename, 'w') as zip:
            numFiles = 0
            for fileUri in sorted(self.urlDocs.keys()):
                if not isHttpUrl(fileUri):
                    numFiles += 1
                    # this has to be a relative path because the hrefs will break
                    zip.write(fileUri, os.path.basename(fileUri))
        self.info("info",
                  _("DTS of %(entryFile)s has %(numberOfFiles)s files packaged into %(packageOutputFile)s"),
                modelObject=self,
                entryFile=os.path.basename(entryFilename), packageOutputFile=pkgFilename, numberOfFiles=numFiles)

    @property
    def qnameUtrUnits(self) -> dict[QName, UtrEntry]:
        try:
            return self._qnameUtrUnits
        except AttributeError:
            from arelle.ValidateUtr import ValidateUtr
            utrEntries = ValidateUtr(self).utrItemTypeEntries
            qnameUtrUnits = {}
            for unitType, unitMap in utrEntries.items():
                for unitId, unit in unitMap.items():
                    unitQName = unit.qname()
                    if unitQName:
                        qnameUtrUnits[unitQName] = unit
            self._qnameUtrUnits = qnameUtrUnits
            return self._qnameUtrUnits

    @property
    def errors(self) -> list[str | None]:
        return self.errorManager.errors

    @property
    def logCount(self) -> dict[str, int]:
        return self.errorManager.logCount
