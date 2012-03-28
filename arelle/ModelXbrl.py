'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import os, sys, traceback, uuid
import logging
from arelle import UrlUtil, XmlUtil, ModelValue, XbrlConst, XmlValidate
from arelle.FileSource import FileNamedStringIO
from arelle.ModelObject import ModelObject
from arelle.Locale import format_string
from arelle.PrototypeInstanceObject import FactPrototype
from arelle.ValidateXbrlDimensions import isFactDimensionallyValid
ModelRelationshipSet = None # dynamic import

AUTO_LOCATE_ELEMENT = '771407c0-1d0c-11e1-be5e-028037ec0200' # singleton meaning choose best location for new element

def load(modelManager, url, nextaction=None, base=None, useFileSource=None):
    if nextaction is None: nextaction = _("loading")
    from arelle import (ModelDocument, FileSource)
    modelXbrl = create(modelManager)
    if useFileSource is not None:
        modelXbrl.fileSource = useFileSource
        modelXbrl.closeFileSource = False
        url = url
    elif isinstance(url,FileSource.FileSource):
        modelXbrl.fileSource = url
        modelXbrl.closeFileSource= True
        url = modelXbrl.fileSource.url
    else:
        modelXbrl.fileSource = FileSource.FileSource(url)
        modelXbrl.closeFileSource= True
    modelXbrl.modelDocument = ModelDocument.load(modelXbrl, url, base, isEntry=True)
    del modelXbrl.entryLoadingUrl
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
        
    #from arelle import XmlValidate
    #uncomment for trial use of lxml xml schema validation of entry document
    #XmlValidate.xmlValidate(modelXbrl.modelDocument)
    modelManager.cntlr.webCache.saveUrlCheckTimes()
    modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction))
    return modelXbrl

def create(modelManager, newDocumentType=None, url=None, schemaRefs=None, createModelDocument=True, isEntry=False):
    from arelle import (ModelDocument, FileSource)
    modelXbrl = ModelXbrl(modelManager)
    modelXbrl.locale = modelManager.locale
    if newDocumentType:
        modelXbrl.fileSource = FileSource.FileSource(url) # url may be an open file handle, use str(url) below
        modelXbrl.closeFileSource= True
        if createModelDocument:
            modelXbrl.modelDocument = ModelDocument.create(modelXbrl, newDocumentType, str(url), schemaRefs=schemaRefs, isEntry=isEntry)
            if isEntry:
                del modelXbrl.entryLoadingUrl
    return modelXbrl
    
class ModelXbrl:
    
    def __init__(self, modelManager):
        self.modelManager = modelManager
        self.init()
        
    def init(self, keepViews=False):
        self.uuid = uuid.uuid1().urn
        self.namespaceDocs = defaultdict(list)
        self.urlDocs = {}
        self.errors = []
        self.logCountErr = 0
        self.logCountWrn = 0
        self.logCountInfo = 0
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
        self.factsInInstance = []
        self.contexts = {}
        self.units = {}
        self.modelObjects = []
        self.qnameParameters = {}
        self.modelVariableSets = set()
        self.modelCustomFunctionSignatures = {}
        self.modelCustomFunctionImplementations = set()
        if not keepViews:
            self.views = []
        self.langs = {self.modelManager.defaultLang}
        from arelle.XbrlConst import standardLabel
        self.labelroles = {standardLabel}
        self.hasXDT = False
        self.hasTableRendering = False
        self.hasFormulae = False
        self.formulaOutputInstance = None
        self.log = logging.getLogger("arelle")
        self.log.setLevel(logging.DEBUG)
        self.modelXbrl = self # for consistency in addressing modelXbrl

    def close(self):
        if not self.isClosed:
            self.closeViews()
            if self.formulaOutputInstance:
                self.formulaOutputInstance.close()
            if hasattr(self,"fileSource") and self.closeFileSource:
                self.fileSource.close()
            modelDocument = self.modelDocument if hasattr(self,"modelDocument") else None
            self.__dict__.clear() # dereference everything before closing document
            if modelDocument:
                modelDocument.close()
            
    @property
    def isClosed(self):
        return not bool(self.__dict__)  # closed when dict is empty
            
    def reload(self,nextaction,reloadCache=False):
        from arelle import ModelDocument
        self.init(keepViews=True)
        self.modelDocument = ModelDocument.load(self, self.fileSource.url, isEntry=True, reloadCache=reloadCache)
        self.modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction),5000)
        self.modelManager.reloadViews(self)
            
    def closeViews(self):
        if not self.isClosed:
            for view in range(len(self.views)):
                if len(self.views) > 0:
                    self.views[0].close()
        
    def relationshipSet(self, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
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
    
    def matchSubstitutionGroup(self, elementQname, subsGrpMatchTable):
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
        return self.matchSubstitutionGroup(elementQname, {
                  qn:(qn is not None) for qn in (subsGrpQnames if hasattr(subsGrpQnames, '__iter__') else (subsGrpQnames,)) + (None,)})
    
    def createInstance(self, url=None):
        from arelle import (ModelDocument, FileSource)
        if self.modelDocument.type == ModelDocument.Type.INSTANCE: # entry already is an instance
            return self.modelDocument # use existing instance entry point
        priorFileSource = self.fileSource
        self.fileSource = FileSource.FileSource(url)
        if self.uri.startswith("http://"):
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
                
    def saveInstance(self):
        with open(self.modelDocument.filepath, "w", encoding='utf-8') as fh:
            XmlUtil.writexml(fh, self.modelDocument.xmlDocument, encoding="utf-8")
    
    def matchContext(self, entityIdentScheme, entityIdentValue, periodType, periodStart, periodEndInstant, dims, segOCCs, scenOCCs):
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
                      afterSibling=None, beforeSibling=None):
        xbrlElt = self.modelDocument.xmlRootElement
        if afterSibling == AUTO_LOCATE_ELEMENT:
            afterSibling = XmlUtil.lastChild(xbrlElt, XbrlConst.xbrli, ("schemaLocation", "roleType", "arcroleType", "context"))
        cntxId = 'c-{0:02n}'.format( len(self.contexts) + 1)
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
            from arelle.PrototypeInstanceObject import FactPrototype, ContextPrototype, DimValuePrototype
            fp = FactPrototype(self, priItem, dims.items())
            # force trying a valid prototype's context Elements
            if not isFactDimensionallyValid(self, fp, setPrototypeContextElements=True):
                self.info("arelleLinfo",
                    _("Create context for %(priItem)s, cannot determine valid context elements, no suitable hypercubes"), 
                    modelObject=self, priItem=priItem)
            fpDims = fp.context.qnameDims
            for dimQname in sorted(fpDims.keys()):
                dimValue = fpDims[dimQname]
                if isinstance(dimValue, DimValuePrototype):
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
                dimConcept = self.qnameConcepts[dimQname]
                dimAttr = ("dimension", XmlUtil.addQnameValue(xbrlElt, dimConcept.qname))
                if dimConcept.isTypedDimension:
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
                
        self.modelDocument.contextDiscover(newCntxElt)
        XmlValidate.validate(self, newCntxElt)
        return newCntxElt
        
        
    def matchUnit(self, multiplyBy, divideBy):
        multiplyBy.sort()
        divideBy.sort()
        for u in self.units.values():
            if u.measures == (multiplyBy,divideBy):
                return u
        return None

    def createUnit(self, multiplyBy, divideBy, afterSibling=None, beforeSibling=None):
        xbrlElt = self.modelDocument.xmlRootElement
        if afterSibling == AUTO_LOCATE_ELEMENT:
            afterSibling = XmlUtil.lastChild(xbrlElt, XbrlConst.xbrli, ("schemaLocation", "roleType", "arcroleType", "context", "unit"))
        unitId = 'u-{0:02n}'.format( len(self.units) + 1)
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
        self.modelDocument.unitDiscover(newUnitElt)
        XmlValidate.validate(self, newUnitElt)
        return newUnitElt
    
    @property
    def nonNilFactsInInstance(self): # indexed by fact (concept) qname
        try:
            return self._nonNilFactsInInstance
        except AttributeError:
            self._nonNilFactsInInstance = [f for f in self.factsInInstance if not f.isNil]
            return self._nonNilFactsInInstance
        
    def qnameFactsInInstance(self, facts): # indexed by fact (concept) qname
        if facts is self.factsInInstance: # may be all facts in inst or just nonNil factsInInst
            try:
                return self._qnameFactsInInstance
            except AttributeError:
                _qname_factsInInstance = defaultdict(list)
                for f in self.factsInInstance:
                    _qname_factsInInstance[f.qname].append(f)
                self._qnameFactsInInstance = _qname_factsInInstance
                return self._qnameFactsInInstance
        elif facts is getattr(self,"_nonNilFactsInInstance",None):
            try:
                return self._qnameNonNilFactsInInstance
            except AttributeError:
                _qname_factsInInstance = defaultdict(list)
                for f in self._nonNilFactsInInstance:
                    _qname_factsInInstance[f.qname].append(f)
                self._qnameNonNilFactsInInstance = _qname_factsInInstance
                return self._qnameNonNilFactsInInstance
        return None

    def matchFact(self, otherFact):
        for fact in self.facts:
            if (fact.isTuple):
                if fact.isDuplicateOf(otherFact):
                    return fact
            elif (fact.qname == otherFact.qname and fact.isVEqualTo(otherFact)):
                if not fact.isNumeric:
                    if fact.xmlLang == otherFact.xmlLang:
                        return fact
                else:
                    if (fact.decimals == otherFact.decimals and
                        fact.precision == otherFact.precision):
                        return fact
        return None
            
    def createFact(self, conceptQname, attributes=None, text=None, parent=None, afterSibling=None, beforeSibling=None):
        if parent is None: parent = self.modelDocument.xmlRootElement
        newFact = XmlUtil.addChild(parent, conceptQname, attributes=attributes, text=text,
                                   afterSibling=afterSibling, beforeSibling=beforeSibling)
        self.modelDocument.factDiscover(newFact, parentElement=parent)
        XmlValidate.validate(self, newFact)
        return newFact    
        
    def modelObject(self, objectId):
        if isinstance(objectId, _INT_TYPES):  # may be long or short in 2.7
            return self.modelObjects[objectId]
        # assume it is a string with ID in a tokenized representation, like xyz_33
        try:
            return self.modelObjects[_INT(objectId.rpartition("_")[2])]
        except ValueError:
            return None
    
    # UI thread viewModelObject
    def viewModelObject(self, objectId):
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

    def logArguments(self, codes, msg, codedArgs):
        # determine logCode
        messageCode = None
        for argCode in codes if isinstance(codes,tuple) else (codes,):
            if (isinstance(argCode, ModelValue.QName) or
                (self.modelManager.disclosureSystem.EFM and argCode.startswith("EFM")) or
                (self.modelManager.disclosureSystem.GFM and argCode.startswith("GFM")) or
                (self.modelManager.disclosureSystem.HMRC and argCode.startswith("HMRC")) or
                (self.modelManager.disclosureSystem.SBRNL and argCode.startswith("SBR.NL")) or
                argCode[0:3] not in ("EFM", "GFM", "HMR", "SBR")):
                messageCode = argCode
                break
        
        # determine message and extra arguments
        fmtArgs = {}
        extras = {"messageCode":messageCode}
        for argName, argValue in codedArgs.items():
            if argName in ("modelObject", "modelXbrl", "modelDocument"):
                try:
                    entryUrl = self.modelDocument.uri
                except AttributeError:
                    entryUrl = self.entryLoadingUrl
                refs = []
                for arg in (argValue if isinstance(argValue, (tuple,list)) else (argValue,)):
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
                        file = UrlUtil.relativeUri(entryUrl, objectUrl)
                        ref = {}
                        if isinstance(arg,ModelObject):
                            ref["href"] = file + "#" + XmlUtil.elementFragmentIdentifier(arg)
                            ref["sourceLine"] = arg.sourceline
                            ref["objectId"] = arg.objectId()
                        else:
                            ref["href"] = file
                        refs.append(ref)
                extras["refs"] = refs
            elif argName == "sourceLine":
                if isinstance(argValue, _INT_TYPES):    # must be sortable with int's in logger
                    extras["sourceLine"] = argValue
            elif argName != "exc_info":
                if isinstance(argValue, (ModelValue.QName, ModelObject, bool, FileNamedStringIO)):
                    fmtArgs[argName] = str(argValue)
                elif isinstance(argValue, _INT_TYPES):
                    # need locale-dependent formatting
                    fmtArgs[argName] = format_string(self.modelManager.locale, '%i', argValue)
                elif isinstance(argValue,float):
                    # need locale-dependent formatting
                    fmtArgs[argName] = format_string(self.modelManager.locale, '%f', argValue)
                else:
                    fmtArgs[argName] = argValue
        if "refs" not in extras:
            try:
                file = os.path.basename(self.modelDocument.uri)
            except AttributeError:
                try:
                    file = os.path.basename(self.entryLoadingUrl)
                except:
                    file = ""
            extras["refs"] = [{"href": file}]
        return (messageCode, 
                (msg, fmtArgs) if fmtArgs else (msg,), 
                extras)

    def info(self, codes, msg, **args):
        messageCode, logArgs, extras = self.logArguments(codes, msg, args)
        if messageCode == "asrtNoLog":
            self.errors.append(args["assertionResults"])
        else:
            self.logCountInfo += 1
            self.log.info(*logArgs, exc_info=args.get("exc_info"), extra=extras)
                    
    def warning(self, codes, msg, **args):
        messageCode, logArgs, extras = self.logArguments(codes, msg, args)
        if messageCode:
            self.logCountWrn += 1
            self.log.warning(*logArgs, exc_info=args.get("exc_info"), extra=extras)
                    
    def error(self, codes, msg, **args):
        messageCode, logArgs, extras = self.logArguments(codes, msg, args)
        if messageCode:
            self.errors.append(messageCode)
            self.logCountErr += 1
            self.log.error(*logArgs, exc_info=args.get("exc_info"), extra=extras)

    def exception(self, codes, msg, **args):
        messageCode, logArgs, extras = self.logArguments(codes, msg, args)
        self.log.exception(*logArgs, exc_info=args.get("exc_info"), extra=extras)
                    
        
    def profileActivity(self, activityCompleted=None, minTimeToShow=0):
        import time
        try:
            if activityCompleted:
                timeTaken = time.time() - self._startedAt
                if timeTaken > minTimeToShow:
                    self.modelManager.addToLog("{0} {1:.2f} secs".format(activityCompleted, timeTaken))
        except AttributeError:
            pass
        self._startedAt = time.time()

    def saveDTSpackage(self): 
        if self.fileSource.isArchive:
            return
        from zipfile import ZipFile 
        import os 
        entryFilename = self.fileSource.url 
        pkgFilename = entryFilename + ".zip" 
        with ZipFile(pkgFilename, 'w') as zip:
            numFiles = 0
            for fileUri in sorted(self.urlDocs.keys()): 
                if not (fileUri.startswith("http://") or fileUri.startswith("https://")): 
                    numFiles += 1
                    # this has to be a relative path because the hrefs will break
                    zip.write(fileUri, os.path.basename(fileUri)) 
        self.info("info",
                  _("DTS of %(entryFile)s has %(numberOfFiles)s files packaged into %(packageOutputFile)s"), 
                modelObject=self,
                entryFile=os.path.basename(entryFilename), packageOutputFile=pkgFilename, numberOfFiles=numFiles)
