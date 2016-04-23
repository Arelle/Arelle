'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import os, sys, traceback, uuid
import logging
from decimal import Decimal
from arelle import UrlUtil, XmlUtil, ModelValue, XbrlConst, XmlValidate
from arelle.FileSource import FileNamedStringIO
from arelle.ModelObject import ModelObject, ObjectPropertyViewWrapper
from arelle.Locale import format_string
from arelle.PluginManager import pluginClassMethods
from arelle.PrototypeInstanceObject import FactPrototype, DimValuePrototype
from arelle.PythonUtil import flattenSequence
from arelle.UrlUtil import isHttpUrl
from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
ModelRelationshipSet = None # dynamic import
ModelFact = None

profileStatNumber = 0

AUTO_LOCATE_ELEMENT = '771407c0-1d0c-11e1-be5e-028037ec0200' # singleton meaning choose best location for new element
DEFAULT = sys.intern(_STR_8BIT("default"))
NONDEFAULT = sys.intern(_STR_8BIT("non-default"))
DEFAULTorNONDEFAULT = sys.intern(_STR_8BIT("default-or-non-default"))
    

def load(modelManager, url, nextaction=None, base=None, useFileSource=None, errorCaptureLevel=None, **kwargs):
    """Each loaded instance, DTS, testcase, testsuite, versioning report, or RSS feed, is represented by an 
    instance of a ModelXbrl object. The ModelXbrl object has a collection of ModelDocument objects, each 
    representing an XML document (for now, with SQL whenever its time comes). One of the modelDocuments of 
    the ModelXbrl is the entry point (of discovery or of the test suite).
    
    :param url: may be a filename or FileSource object
    :type url: str or FileSource
    :param nextaction: text to use as status line prompt on conclusion of loading and discovery
    :type nextaction: str
    :param base: the base URL if any (such as a versioning report's URL when loading to/from DTS modelXbrl).
    :type base: str
    :param useFileSource: for internal use (when an entry point is in a FileSource archive and discovered files expected to also be in the entry point's archive.
    :type useFileSource: bool
    :returns: ModelXbrl -- a new modelXbrl, performing DTS discovery for instance, inline XBRL, schema, linkbase, and versioning report entry urls
   """
    if nextaction is None: nextaction = _("loading")
    from arelle import (ModelDocument, FileSource)
    modelXbrl = create(modelManager, errorCaptureLevel=errorCaptureLevel)
    if useFileSource is not None:
        modelXbrl.fileSource = useFileSource
        modelXbrl.closeFileSource = False
        url = url
    elif isinstance(url,FileSource.FileSource):
        modelXbrl.fileSource = url
        modelXbrl.closeFileSource= True
        url = modelXbrl.fileSource.url
    else:
        modelXbrl.fileSource = FileSource.FileSource(url, modelManager.cntlr)
        modelXbrl.closeFileSource= True
    modelXbrl.modelDocument = ModelDocument.load(modelXbrl, url, base, isEntry=True, **kwargs)
    del modelXbrl.entryLoadingUrl
    loadSchemalocatedSchemas(modelXbrl)
    
    #from arelle import XmlValidate
    #uncomment for trial use of lxml xml schema validation of entry document
    #XmlValidate.xmlValidate(modelXbrl.modelDocument)
    modelManager.cntlr.webCache.saveUrlCheckTimes()
    modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction))
    return modelXbrl

def create(modelManager, newDocumentType=None, url=None, schemaRefs=None, createModelDocument=True, isEntry=False, errorCaptureLevel=None, initialXml=None, initialComment=None, base=None, discover=True):
    from arelle import (ModelDocument, FileSource)
    modelXbrl = ModelXbrl(modelManager, errorCaptureLevel=errorCaptureLevel)
    modelXbrl.locale = modelManager.locale
    if newDocumentType:
        modelXbrl.fileSource = FileSource.FileSource(url, modelManager.cntlr) # url may be an open file handle, use str(url) below
        modelXbrl.closeFileSource= True
        if createModelDocument:
            modelXbrl.modelDocument = ModelDocument.create(modelXbrl, newDocumentType, str(url), schemaRefs=schemaRefs, isEntry=isEntry, initialXml=initialXml, initialComment=initialComment, base=base, discover=discover)
            if isEntry:
                del modelXbrl.entryLoadingUrl
                loadSchemalocatedSchemas(modelXbrl)
    return modelXbrl
    
def loadSchemalocatedSchemas(modelXbrl):
    from arelle import ModelDocument
    if modelXbrl.modelDocument is not None and modelXbrl.modelDocument.type < ModelDocument.Type.DTSENTRIES:
        # at this point DTS is fully discovered but schemaLocated xsd's are not yet loaded
        modelDocumentsSchemaLocated = set()
        while True: # need this logic because each new pass may add new urlDocs
            modelDocuments = set(modelXbrl.urlDocs.values()) - modelDocumentsSchemaLocated
            if not modelDocuments:
                break
            modelDocument = modelDocuments.pop()
            modelDocumentsSchemaLocated.add(modelDocument)
            modelDocument.loadSchemalocatedSchemas()
        
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
    
    def __init__(self, modelManager, errorCaptureLevel=None):
        self.modelManager = modelManager
        self.skipDTS = modelManager.skipDTS
        self.init(errorCaptureLevel=errorCaptureLevel)
        
    def init(self, keepViews=False, errorCaptureLevel=None):
        self.uuid = uuid.uuid1().urn
        self.namespaceDocs = defaultdict(list)
        self.urlDocs = {}
        self.urlUnloadableDocs = {}  # if entry is True, entry is blocked and unloadable, False means loadable but warned
        self.errorCaptureLevel = (errorCaptureLevel or logging._checkLevel("INCONSISTENCY"))
        self.errors = []
        self.logCount = {}
        self.arcroleTypes = defaultdict(list)
        self.roleTypes = defaultdict(list)
        self.qnameConcepts = {} # indexed by qname of element
        self.nameConcepts = defaultdict(list) # contains ModelConcepts by name 
        self.qnameAttributes = {}
        self.qnameAttributeGroups = {}
        self.qnameGroupDefinitions = {}
        self.qnameTypes = {} # contains ModelTypes by qname key of type
        self.baseSets = defaultdict(list) # contains ModelLinks for keys arcrole, arcrole#linkrole
        self.relationshipSets = {} # contains ModelRelationshipSets by bas set keys
        self.qnameDimensionDefaults = {} # contains qname of dimension (index) and default member(value)
        self.facts = []
        self.factsInInstance = set()
        self.undefinedFacts = [] # elements presumed to be facts but not defined
        self.contexts = {}
        self.units = {}
        self.modelObjects = []
        self.qnameParameters = {}
        self.modelVariableSets = set()
        self.modelCustomFunctionSignatures = {}
        self.modelCustomFunctionImplementations = set()
        self.modelRenderingTables = set()
        if not keepViews:
            self.views = []
        self.langs = {self.modelManager.defaultLang}
        from arelle.XbrlConst import standardLabel
        self.labelroles = {standardLabel}
        self.hasXDT = False
        self.hasTableRendering = False
        self.hasTableIndexing = False
        self.hasFormulae = False
        self.formulaOutputInstance = None
        self.logger = logging.getLogger("arelle")
        self.logRefObjectProperties = getattr(self.logger, "logRefObjectProperties", False)
        self.logRefHasPluginAttrs = any(True for m in pluginClassMethods("Logging.Ref.Attributes"))
        self.logRefHasPluginProperties = any(True for m in pluginClassMethods("Logging.Ref.Properties"))
        self.profileStats = {}
        self.schemaDocsToValidate = set()
        self.modelXbrl = self # for consistency in addressing modelXbrl
        self.arelleUnitTests = {} # unit test entries (usually from processing instructions
        for pluginXbrlMethod in pluginClassMethods("ModelXbrl.Init"):
            pluginXbrlMethod(self)


    def close(self):
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
    def isClosed(self):
        """
        :returns:  bool -- True if closed (python object has deferenced and deleted all attributes after closing)
        """
        return not bool(self.__dict__)  # closed when dict is empty
            
    def reload(self,nextaction,reloadCache=False):
        """Reloads all model objects from their original entry point URL, preserving any open views (which are reloaded).
        
        :param nextAction: status line text string, if any, to show upon completion
        :type nextAction: str
        :param reloadCache: True to force clearing and reloading of web cache, if working online.
        :param reloadCache: bool
        """
        from arelle import ModelDocument
        self.init(keepViews=True)
        self.modelDocument = ModelDocument.load(self, self.fileSource.url, isEntry=True, reloadCache=reloadCache)
        self.modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction),5000)
        self.modelManager.reloadViews(self)
            
    def closeViews(self):
        """Close views associated with this modelXbrl
        """
        if not self.isClosed:
            for view in range(len(self.views)):
                if len(self.views) > 0:
                    self.views[0].close()
        
    def relationshipSet(self, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
        """Returns a relationship set matching specified parameters (only arcrole is required).
        
        Resolve and determine relationship set.  If a relationship set of the same parameters was previously resolved, it is returned from a cache.
        
        :param arcrole: Required arcrole, or special collective arcroles 'XBRL-dimensions', 'XBRL-formula', and 'Table-rendering'
        :type arcrole: str
        :param linkrole: Linkrole (wild if None)
        :type linkrole: str
        :param arcqname: Arc element qname (wild if None)
        :type arcqname: QName
        :param includeProhibits: True to include prohibiting arc elements as relationships
        :type includeProhibits: bool
        :returns: [ModelRelationship] -- Ordered list of effective relationship objects per parameters
        """
        global ModelRelationshipSet
        if ModelRelationshipSet is None:
            from arelle import ModelRelationshipSet
        key = (arcrole, linkrole, linkqname, arcqname, includeProhibits)
        if key not in self.relationshipSets:
            ModelRelationshipSet.create(self, arcrole, linkrole, linkqname, arcqname, includeProhibits)
        return self.relationshipSets[key]
    
    def baseSetModelLink(self, linkElement):
        for modelLink in self.baseSets[("XBRL-footnotes",None,None,None)]:
            if modelLink == linkElement:
                return modelLink
        return None
    
    def roleTypeDefinition(self, roleURI):
        modelRoles = self.roleTypes.get(roleURI, ())
        if modelRoles:
            return modelRoles[0].definition or roleURI
        return roleURI
    
    def roleTypeName(self, roleURI):
        # authority-specific role type name
        for pluginXbrlMethod in pluginClassMethods("ModelXbrl.RoleTypeName"):
            _roleTypeName = pluginXbrlMethod(self, roleURI)
            if _roleTypeName:
                return _roleTypeName
        return self.roleTypeDefinition(roleURI)
    
    def matchSubstitutionGroup(self, elementQname, subsGrpMatchTable):
        """Resolve a subsitutionGroup for the elementQname from the match table
        
        Used by ModelObjectFactory to return Class type for new ModelObject subclass creation, and isInSubstitutionGroup
        
        :param elementQname: Element/Concept QName to find substitution group
        :type elementQname: QName
        :param subsGrpMatchTable: Table of substitutions used to determine xml proxy object class for xml elements and substitution group membership
        :type subsGrpMatchTable: dict
        :returns: object -- value matching subsGrpMatchTable key
        """
        if elementQname in subsGrpMatchTable:
            return subsGrpMatchTable[elementQname] # head of substitution group
        elementMdlObj = self.qnameConcepts.get(elementQname)
        if elementMdlObj is not None:
            subsGrpMdlObj = elementMdlObj.substitutionGroup
            while subsGrpMdlObj is not None:
                subsGrpQname = subsGrpMdlObj.qname
                if subsGrpQname in subsGrpMatchTable:
                    return subsGrpMatchTable[subsGrpQname]
                subsGrpMdlObj = subsGrpMdlObj.substitutionGroup
        return subsGrpMatchTable.get(None)
    
    def isInSubstitutionGroup(self, elementQname, subsGrpQnames):
        """Determine if element is in substitution group(s)
        
        Used by ModelObjectFactory to return Class type for new ModelObject subclass creation, and isInSubstitutionGroup
        
        :param elementQname: Element/Concept QName to determine if in substitution group(s)
        :type elementQname: QName
        :param subsGrpQnames: QName or list of QNames
        :type subsGrpMatchTable: QName or [QName]
        :returns: bool -- True if element is in any substitution group
        """
        return self.matchSubstitutionGroup(elementQname, {
                  qn:(qn is not None) for qn in (subsGrpQnames if hasattr(subsGrpQnames, '__iter__') else (subsGrpQnames,)) + (None,)})
    
    def createInstance(self, url=None):
        """Creates an instance document for a DTS which didn't have an instance document, such as
        to create a new instance for a DTS which was loaded from a taxonomy or linkbase entry point.
        
        :param url: File name to save the new instance document
        :type url: str
        """
        from arelle import (ModelDocument, FileSource)
        if self.modelDocument.type == ModelDocument.Type.INSTANCE: 
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
            self.modelDocument = ModelDocument.create(self, ModelDocument.Type.INSTANCE, url, schemaRefs=[schemaRefUri], isEntry=True)
            if priorFileSource:
                priorFileSource.close()
            self.closeFileSource= True
            del self.entryLoadingUrl
        # reload dts views
        from arelle import ViewWinDTS
        for view in self.views:
            if isinstance(view, ViewWinDTS.ViewDTS):
                self.modelManager.cntlr.uiThreadQueue.put((view.view, []))
                
    def saveInstance(self, **kwargs):
        """Saves current instance document file.
        
        :param overrideFilepath: specify to override saving in instance's modelDocument.filepath
        """
        self.modelDocument.save(**kwargs)
            
    @property    
    def prefixedNamespaces(self):
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
    
    def matchContext(self, entityIdentScheme, entityIdentValue, periodType, periodStart, periodEndInstant, dims, segOCCs, scenOCCs):
        """Finds matching context, by aspects, as in formula usage, if any
        
        :param entityIdentScheme: Scheme to match
        :type entityIdentScheme: str
        :param entityIdentValue: Entity identifier value to match
        :type entityIdentValue: str
        :param periodType: Period type to match ("instant", "duration", or "forever")
        :type periodType: str
        :param periodStart: Date or dateTime of period start
        :type periodStart: ModelValue.DateTime, datetime.date or datetime.datetime
        :param periodEndInstant: Date or dateTime of period send
        :type periodEndInstant: ModelValue.DateTime, datetime.date or datetime.datetime
        :param dims: Dimensions
        :type dims: ModelDimension or QName
        :param segOCCs: Segment non-dimensional nodes
        :type segOCCs: lxml element
        :param scenOCCs: Scenario non-dimensional nodes
        :type scenOCCs: lxml element
        :returns: ModelContext -- Matching context or None
        """
        from arelle.ModelFormulaObject import Aspect
        from arelle.ModelValue import dateUnionEqual
        from arelle.XbrlUtil import sEqual
        if dims: segAspect, scenAspect = (Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO)
        else: segAspect, scenAspect = (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO)
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
                   all([sEqual(self, cOCCs[i], mOCCs[i]) for i in range(len(mOCCs))])
                     if len(cOCCs) == len(mOCCs) else False
                        for cOCCs,mOCCs in ((c.nonDimValues(segAspect),segOCCs),
                                            (c.nonDimValues(scenAspect),scenOCCs)))
                ):
                    return c
        return None
                 
    def createContext(self, entityIdentScheme, entityIdentValue, periodType, periodStart, periodEndInstant, priItem, dims, segOCCs, scenOCCs,
                      afterSibling=None, beforeSibling=None, id=None):
        """Creates a new ModelContext and validates (integrates into modelDocument object model).
        
        :param entityIdentScheme: Scheme to match
        :type entityIdentScheme: str
        :param entityIdentValue: Entity identifier value to match
        :type entityIdentValue: str
        :param periodType: Period type to match ("instant", "duration", or "forever")
        :type periodType: str
        :param periodStart: Date or dateTime of period start
        :type periodStart: ModelValue.DateTime, datetime.date or datetime.datetime
        :param periodEndInstant: Date or dateTime of period send
        :type periodEndInstant: ModelValue.DateTime, datetime.date or datetime.datetime
        :param dims: Dimensions
        :type dims: ModelDimension or QName
        :param segOCCs: Segment non-dimensional nodes
        :type segOCCs: lxml element
        :param scenOCCs: Scenario non-dimensional nodes
        :type scenOCCs: lxml element
        :param beforeSibling: lxml element in instance to insert new concept before
        :type beforeSibling: ModelObject
        :param afterSibling: lxml element in instance to insert new concept after
        :type afterSibling: ModelObject
        :param id: id to assign to new context, if absent an id will be generated
        :type id: str
        :returns: ModelContext -- New model context object
        """
        xbrlElt = self.modelDocument.xmlRootElement
        if afterSibling == AUTO_LOCATE_ELEMENT:
            afterSibling = XmlUtil.lastChild(xbrlElt, XbrlConst.xbrli, ("schemaLocation", "roleType", "arcroleType", "context"))
        cntxId = id if id else 'c-{0:02n}'.format( len(self.contexts) + 1)
        newCntxElt = XmlUtil.addChild(xbrlElt, XbrlConst.xbrli, "context", attributes=("id", cntxId),
                                      afterSibling=afterSibling, beforeSibling=beforeSibling)
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
        from arelle.ModelInstanceObject import ModelDimensionValue
        if dims: # requires primary item to determin ambiguous concepts
            ''' in theory we have to check full set of dimensions for validity in source or any other
                context element, but for shortcut will see if each dimension is already reported in an
                unambiguous valid contextElement
            '''
            if priItem is not None: # creating concept for a specific fact
                dims[2] = priItem # Aspect.CONCEPT: prototype needs primary item as an aspect
                fp = FactPrototype(self, dims)
                del dims[2] # Aspect.CONCEPT
                # force trying a valid prototype's context Elements
                if not isFactDimensionallyValid(self, fp, setPrototypeContextElements=True):
                    self.info("arelle:info",
                        _("Create context for %(priItem)s, cannot determine valid context elements, no suitable hypercubes"), 
                        modelObject=self, priItem=priItem)
                fpDims = fp.context.qnameDims
            else:
                fpDims = dims # dims known to be valid (such as for inline extraction) 
            for dimQname in sorted(fpDims.keys()):
                dimValue = fpDims[dimQname]
                if isinstance(dimValue, (DimValuePrototype,ModelDimensionValue)):
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
                    self.info("arelleLinfo",
                        _("Create context, %(dimension)s, cannot determine context element, either no all relationship or validation issue"), 
                        modelObject=self, dimension=dimQname),
                    continue
                dimAttr = ("dimension", XmlUtil.addQnameValue(xbrlElt, dimQname))
                if dimValue.isTyped:
                    dimElt = XmlUtil.addChild(contextElt, XbrlConst.xbrldi, "xbrldi:typedMember", 
                                              attributes=dimAttr)
                    if isinstance(dimValue, (ModelDimensionValue, DimValuePrototype)) and dimValue.isTyped:
                        XmlUtil.copyNodes(dimElt, dimValue.typedMember) 
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
        return newCntxElt
        
        
    def matchUnit(self, multiplyBy, divideBy):
        """Finds matching unit, by measures, as in formula usage, if any
        
        :param multiplyBy: List of multiply-by measure QNames (or top level measures if no divideBy)
        :type multiplyBy: [QName]
        :param divideBy: List of multiply-by measure QNames (or empty list if no divideBy)
        :type divideBy: [QName]
        :returns: ModelUnit -- Matching unit object or None
        """
        multiplyBy.sort()
        divideBy.sort()
        for u in self.units.values():
            if u.measures == (multiplyBy,divideBy):
                return u
        return None

    def createUnit(self, multiplyBy, divideBy, afterSibling=None, beforeSibling=None, id=None):
        """Creates new unit, by measures, as in formula usage, if any
        
        :param multiplyBy: List of multiply-by measure QNames (or top level measures if no divideBy)
        :type multiplyBy: [QName]
        :param divideBy: List of multiply-by measure QNames (or empty list if no divideBy)
        :type divideBy: [QName]
        :param beforeSibling: lxml element in instance to insert new concept before
        :type beforeSibling: ModelObject
        :param afterSibling: lxml element in instance to insert new concept after
        :type afterSibling: ModelObject
        :param id: id to assign to new unit, if absent an id will be generated
        :type id: str
        :returns: ModelUnit -- New unit object
        """
        xbrlElt = self.modelDocument.xmlRootElement
        if afterSibling == AUTO_LOCATE_ELEMENT:
            afterSibling = XmlUtil.lastChild(xbrlElt, XbrlConst.xbrli, ("schemaLocation", "roleType", "arcroleType", "context", "unit"))
        unitId = id if id else 'u-{0:02n}'.format( len(self.units) + 1)
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
    def nonNilFactsInInstance(self): # indexed by fact (concept) qname
        """Facts in the instance which are not nil, cached
        
        :returns: set -- non-nil facts in instance
        """
        try:
            return self._nonNilFactsInInstance
        except AttributeError:
            self._nonNilFactsInInstance = set(f for f in self.factsInInstance if not f.isNil)
            return self._nonNilFactsInInstance
        
    @property
    def factsByQname(self): # indexed by fact (concept) qname
        """Facts in the instance indexed by their QName, cached
        
        :returns: dict -- indexes are QNames, values are ModelFacts
        """
        try:
            return self._factsByQname
        except AttributeError:
            self._factsByQname = fbqn = defaultdict(set)
            for f in self.factsInInstance: 
                if f.qname is not None:
                    fbqn[f.qname].add(f)
            return fbqn
        
    def factsByDatatype(self, notStrict, typeQname): # indexed by fact (concept) qname
        """Facts in the instance indexed by data type QName, cached as types are requested

        :param notSctrict: if True, fact may be derived
        :type notStrict: bool
        :returns: set -- ModelFacts that have specified type or (if nonStrict) derived from specified type
        """
        try:
            return self._factsByDatatype[notStrict, typeQname]
        except AttributeError:
            self._factsByDatatype = {}
            return self.factsByDatatype(notStrict, typeQname)
        except KeyError:
            self._factsByDatatype[notStrict, typeQname] = fbdt = set()
            for f in self.factsInInstance:
                c = f.concept
                if c.typeQname == typeQname or (notStrict and c.type.isDerivedFrom(typeQname)):
                    fbdt.add(f)
            return fbdt
        
    def factsByPeriodType(self, periodType): # indexed by fact (concept) qname
        """Facts in the instance indexed by periodType, cached

        :param periodType: Period type to match ("instant", "duration", or "forever")
        :type periodType: str
        :returns: set -- ModelFacts that have specified periodType
        """
        try:
            return self._factsByPeriodType[periodType]
        except AttributeError:
            self._factsByPeriodType = fbpt = defaultdict(set)
            for f in self.factsInInstance:
                p = f.concept.periodType
                if p:
                    fbpt[p].add(f)
            return self.factsByPeriodType(periodType)
        except KeyError:
            return set()  # no facts for this period type
        
    def factsByDimMemQname(self, dimQname, memQname=None): # indexed by fact (concept) qname
        """Facts in the instance indexed by their Dimension  and Member QName, cached
        
        :returns: dict -- indexes are (Dimension, Member) and (Dimension) QNames, values are ModelFacts
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
                    else: # default typed dimension
                        fbdq[DEFAULT].add(fact)
            return fbdq[memQname]
        
    def matchFact(self, otherFact, unmatchedFactsStack=None, deemP0inf=False):
        """Finds matching fact, by XBRL 2.1 duplicate definition (if tuple), or by
        QName and VEquality (if an item), lang and accuracy equality, as in formula and test case usage
        
        :param otherFact: Fact to match
        :type otherFact: ModelFact
        :deemP0inf: boolean for formula validation to deem P0 facts to be VEqual as if they were P=INF
        :returns: ModelFact -- Matching fact or None
        """
        for fact in self.facts:
            if (fact.isTuple):
                if otherFact.isDuplicateOf(fact, unmatchedFactsStack=unmatchedFactsStack):
                    return fact
            elif (fact.qname == otherFact.qname and fact.isVEqualTo(otherFact, deemP0inf=deemP0inf)):
                if not fact.isNumeric:
                    if fact.xmlLang == otherFact.xmlLang:
                        return fact
                else:
                    if (fact.decimals == otherFact.decimals and
                        fact.precision == otherFact.precision):
                        return fact
        return None
            
    def createFact(self, conceptQname, attributes=None, text=None, parent=None, afterSibling=None, beforeSibling=None, validate=True):
        """Creates new fact, as in formula output instance creation, and validates into object model
        
        :param conceptQname: QNames of concept
        :type conceptQname: QName
        :param attributes: Tuple of name, value, or tuples of name, value tuples (name,value) or ((name,value)[,(name,value...)]), where name is either QName or clark-notation name string
        :param text: Text content of fact (will be converted to xpath compatible str by FunctionXS.xsString)
        :type text: object
        :param parent: lxml element in instance to append as child of
        :type parent: ModelObject
        :param beforeSibling: lxml element in instance to insert new concept before
        :type beforeSibling: ModelObject
        :param afterSibling: lxml element in instance to insert new concept after
        :type afterSibling: ModelObject
        :param validate: specify False to block XML Validation (required when constructing a tuple which is invalid until after it's contents are created)
        :type validate: boolean
        :returns: ModelFact -- New fact object
        """
        if parent is None: parent = self.modelDocument.xmlRootElement
        self.makeelementParentModelObject = parent
        newFact = XmlUtil.addChild(parent, conceptQname, attributes=attributes, text=text,
                                   afterSibling=afterSibling, beforeSibling=beforeSibling)
        global ModelFact
        if ModelFact is None:
            from arelle.ModelInstanceObject import ModelFact
        if hasattr(self, "_factsByQname"):
            self._factsByQname[newFact.qname].add(newFact)
        if not isinstance(newFact, ModelFact):
            return newFact # unable to create fact for this concept OR DTS not loaded for target instance (e.g., inline extraction, summary output)
        del self.makeelementParentModelObject
        if validate:
            XmlValidate.validate(self, newFact)
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
        
    def setIsModified(self):
        """Records that the underlying document has been modified.
        """
        self.modelDocument.isModified = True

    def isModified(self):
        """Check if the underlying document has been modified.
        """
        md = self.modelDocument
        if md is not None:
            return md.isModified
        else:
            return False

    def modelObject(self, objectId):
        """Finds a model object by an ordinal ID which may be buried in a tkinter view id string (e.g., 'somedesignation_ordinalnumber').
        
        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        :type objectId: str or int
        :returns: ModelObject
        """
        if isinstance(objectId, _INT_TYPES):  # may be long or short in 2.7
            return self.modelObjects[objectId]
        # assume it is a string with ID in a tokenized representation, like xyz_33
        try:
            return self.modelObjects[_INT(objectId.rpartition("_")[2])]
        except (IndexError, ValueError):
            return None
    
    # UI thread viewModelObject
    def viewModelObject(self, objectId):
        """Finds model object, if any, and synchronizes any views displaying it to bring the model object into scrollable view region and highlight it
        :param objectId: string which includes _ordinalNumber, produced by ModelObject.objectId(), or integer object index
        :type objectId: str or int
        """
        modelObject = ""
        try:
            if isinstance(objectId, (ModelObject,FactPrototype)):
                modelObject = objectId
            elif isinstance(objectId, str) and objectId.startswith("_"):
                modelObject = self.modelObject(objectId)
            if modelObject is not None:
                for view in self.views:
                    view.viewModelObject(modelObject)
        except (IndexError, ValueError, AttributeError)as err:
            self.modelManager.addToLog(_("Exception viewing properties {0} {1} at {2}").format(
                            modelObject,
                            err, traceback.format_tb(sys.exc_info()[2])))

    def effectiveMessageCode(self, messageCodes):        
        effectiveMessageCode = None
        _validationType = self.modelManager.disclosureSystem.validationType
        _exclusiveTypesPattern = self.modelManager.disclosureSystem.exclusiveTypesPattern
        
        for argCode in messageCodes if isinstance(messageCodes,tuple) else (messageCodes,):
            if (isinstance(argCode, ModelValue.QName) or
                (_validationType and argCode.startswith(_validationType)) or
                (not _exclusiveTypesPattern or _exclusiveTypesPattern.match(argCode) == None)):
                effectiveMessageCode = argCode
                break
        return effectiveMessageCode

    # isLoggingEffectiveFor( messageCodes= messageCode= level= )
    def isLoggingEffectiveFor(self, **kwargs): # args can be messageCode(s) and level
        logger = self.logger
        if "messageCodes" in kwargs or "messageCode" in kwargs:
            if "messageCodes" in kwargs:
                messageCodes = kwargs["messageCodes"]
            else:
                messageCodes = kwargs["messageCode"]
            messageCode = self.effectiveMessageCode(messageCodes)
            codeEffective = (messageCode and
                             (not logger.messageCodeFilter or logger.messageCodeFilter.match(messageCode))) 
        else:
            codeEffective = True
        if "level" in kwargs and logger.messageLevelFilter:
            levelEffective = logger.messageLevelFilter.match(kwargs["level"].lower())
        else:
            levelEffective = True
        return codeEffective and levelEffective

    def logArguments(self, codes, msg, codedArgs):
        """ Prepares arguments for logger function as per info() below.
        
        If codes includes EFM, GFM, HMRC, or SBR-coded error then the code chosen (if a sequence)
        corresponds to whether EFM, GFM, HMRC, or SBR validation is in effect.
        """
        def propValues(properties):
            # deref objects in properties
            return [(p[0],str(p[1])) if len(p) == 2 else (p[0],str(p[1]),propValues(p[2]))
                    for p in properties if 2 <= len(p) <= 3]
        # determine logCode
        messageCode = self.effectiveMessageCode(codes)
        
        # determine message and extra arguments
        fmtArgs = {}
        extras = {"messageCode":messageCode}
        modelObjectArgs = ()

        for argName, argValue in codedArgs.items():
            if argName in ("modelObject", "modelXbrl", "modelDocument"):
                try:
                    entryUrl = self.modelDocument.uri
                except AttributeError:
                    try:
                        entryUrl = self.entryLoadingUrl
                    except AttributeError:
                        entryUrl = self.fileSource.url
                refs = []
                modelObjectArgs = argValue if isinstance(argValue, (tuple,list,set)) else (argValue,)
                for arg in flattenSequence(modelObjectArgs):
                    if arg is not None:
                        if isinstance(arg, _STR_BASE):
                            objectUrl = arg
                        else:
                            try:
                                objectUrl = arg.modelDocument.uri
                            except AttributeError:
                                try:
                                    objectUrl = self.modelDocument.uri
                                except AttributeError:
                                    objectUrl = self.entryLoadingUrl
                        try:
                            file = UrlUtil.relativeUri(entryUrl, objectUrl)
                        except:
                            file = ""
                        ref = {}
                        if isinstance(arg,(ModelObject, ObjectPropertyViewWrapper)):
                            _arg = arg.modelObject if isinstance(arg, ObjectPropertyViewWrapper) else arg
                            ref["href"] = file + "#" + XmlUtil.elementFragmentIdentifier(_arg)
                            ref["sourceLine"] = _arg.sourceline
                            ref["objectId"] = _arg.objectId()
                            if self.logRefObjectProperties:
                                try:
                                    ref["properties"] = propValues(arg.propertyView)
                                except AttributeError:
                                    pass # is a default properties entry appropriate or needed?
                            if self.logRefHasPluginProperties:
                                refProperties = ref.get("properties", {})
                                for pluginXbrlMethod in pluginClassMethods("Logging.Ref.Properties"):
                                    pluginXbrlMethod(arg, refProperties, codedArgs)
                                if refProperties:
                                    ref["properties"] = refProperties
                        else:
                            ref["href"] = file
                            try:
                                ref["sourceLine"] = arg.sourceline
                            except AttributeError:
                                pass # arg may not have sourceline, ignore if so
                        if self.logRefHasPluginAttrs:
                            refAttributes = {}
                            for pluginXbrlMethod in pluginClassMethods("Logging.Ref.Attributes"):
                                pluginXbrlMethod(arg, refAttributes, codedArgs)
                            if refAttributes:
                                ref["customAttributes"] = refAttributes
                        refs.append(ref)
                extras["refs"] = refs
            elif argName == "sourceFileLine":
                # sourceFileLines is pairs of file and line numbers, e.g., ((file,line),(file2,line2),...)
                ref = {}
                if isinstance(argValue, (tuple,list)):
                    ref["href"] = str(argValue[0])
                    if len(argValue) > 1 and argValue[1]:
                        ref["sourceLine"] = str(argValue[1])
                else:
                    ref["href"] = str(argValue)
                extras["refs"] = [ref]
            elif argName == "sourceFileLines":
                # sourceFileLines is tuple/list of pairs of file and line numbers, e.g., ((file,line),(file2,line2),...)
                refs = []
                for arg in (argValue if isinstance(argValue, (tuple,list)) else (argValue,)):
                    ref = {}
                    if isinstance(arg, (tuple,list)):
                        ref["href"] = str(arg[0])
                        if len(arg) > 1 and arg[1]:
                            ref["sourceLine"] = str(arg[1])
                    else:
                        ref["href"] = str(arg)
                    refs.append(ref)
                extras["refs"] = refs
            elif argName == "sourceLine":
                if isinstance(argValue, _INT_TYPES):    # must be sortable with int's in logger
                    extras["sourceLine"] = argValue
            elif argName not in ("exc_info", "messageCodes"):
                if isinstance(argValue, (ModelValue.QName, ModelObject, bool, FileNamedStringIO,
                                         # might be a set of lxml objects not dereferencable at shutdown 
                                         tuple, list, set)):
                    fmtArgs[argName] = str(argValue)
                elif argValue is None:
                    fmtArgs[argName] = "(none)"
                elif isinstance(argValue, _INT_TYPES):
                    # need locale-dependent formatting
                    fmtArgs[argName] = format_string(self.modelManager.locale, '%i', argValue)
                elif isinstance(argValue,(float,Decimal)):
                    # need locale-dependent formatting
                    fmtArgs[argName] = format_string(self.modelManager.locale, '%f', argValue)
                elif isinstance(argValue, dict):
                    fmtArgs[argName] = argValue
                else:
                    fmtArgs[argName] = str(argValue)

        if "refs" not in extras:
            try:
                file = os.path.basename(self.modelDocument.uri)
            except AttributeError:
                try:
                    file = os.path.basename(self.entryLoadingUrl)
                except:
                    file = ""
            extras["refs"] = [{"href": file}]
        for pluginXbrlMethod in pluginClassMethods("Logging.Message.Parameters"):
            # plug in can rewrite msg string or return msg if not altering msg
            msg = pluginXbrlMethod(messageCode, msg, modelObjectArgs, fmtArgs) or msg
        return (messageCode, 
                (msg, fmtArgs) if fmtArgs else (msg,), 
                extras)

    def debug(self, codes, msg, **args):
        """Same as error(), but as info
        """
        """@messageCatalog=[]"""
        self.log('DEBUG', codes, msg, **args)
                    
    def info(self, codes, msg, **args):
        """Same as error(), but as info
        """
        """@messageCatalog=[]"""
        self.log('INFO', codes, msg, **args)
                    
    def warning(self, codes, msg, **args):
        """Same as error(), but as warning, and no error code saved for Validate
        """
        """@messageCatalog=[]"""
        self.log('WARNING', codes, msg, **args)
                    
    def log(self, level, codes, msg, **args):
        """Same as error(), but level passed in as argument
        """
        logger = self.logger
        messageCode, logArgs, extras = self.logArguments(codes, msg, args)
        if messageCode == "asrtNoLog":
            self.errors.append(args["assertionResults"])
        elif (messageCode and
              (not logger.messageCodeFilter or logger.messageCodeFilter.match(messageCode)) and
              (not logger.messageLevelFilter or logger.messageLevelFilter.match(level.lower()))):
            numericLevel = logging._checkLevel(level)
            self.logCount[numericLevel] = self.logCount.get(numericLevel, 0) + 1
            if numericLevel >= self.errorCaptureLevel:
                self.errors.append(messageCode)
            """@messageCatalog=[]"""
            logger.log(numericLevel, *logArgs, exc_info=args.get("exc_info"), extra=extras)
                    
    def error(self, codes, msg, **args):
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
        :type codes: str or [str]
        :param msg: Message text string to be formatted and replaced with named parameters in **args
        :param **args: Named arguments including modelObject, modelXbrl, or modelDocument, named arguments in msg string, and any exc_info argument.
        :param messageCodes: If first parameter codes, above, is dynamically formatted, this is a documentation string of the message codes only used for extraction of the message catalog document (not used in run-time processing).
        """
        """@messageCatalog=[]"""
        self.log('ERROR', codes, msg, **args)

    def exception(self, codes, msg, **args):
        """Same as error(), but as exception
        """
        """@messageCatalog=[]"""
        self.log('CRITICAL', codes, msg, **args)
        
    def logProfileStats(self):
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
    
    def profileStat(self, name=None, stat=None):
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
        
    def profileActivity(self, activityCompleted=None, minTimeToShow=0):
        """Used to provide interactive GUI messages of long-running processes.
        
        When the time between last profileActivity and this profileActivity exceeds minTimeToShow, then
        the time is logged (if it is shorter than it is not logged), thus providing feedback of long
        running (and possibly troublesome) processing steps.
        
        :param activityCompleted: Description of activity completed, or None if call is just to demark starting of a profiled activity.
        :type activityCompleted: str
        :param minTimeToShow: Seconds of elapsed time for activity, if longer then the profile message appears in the log.
        :type minTimeToShow: seconds
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

    def saveDTSpackage(self):
        """Contributed program to save DTS package as a zip file.  Refactored into a plug-in (and may be removed from main code).
        """ 
        if self.fileSource.isArchive:
            return
        from zipfile import ZipFile 
        import os 
        entryFilename = self.fileSource.url 
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
