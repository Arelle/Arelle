'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
import sys, traceback

def load(modelManager, url, nextaction, base=None):
    from arelle import (ModelDocument, FileSource)
    modelXbrl = create(modelManager)
    if isinstance(url,FileSource.FileSource):
        modelXbrl.fileSource = url
        url = modelXbrl.fileSource.url
    else:
        modelXbrl.fileSource = FileSource.FileSource(url)
    modelXbrl.modelDocument = ModelDocument.load(modelXbrl, url, base, isEntry=True)
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
        modelXbrl.fileSource = FileSource.FileSource(url)
        if createModelDocument:
            modelXbrl.modelDocument = ModelDocument.create(modelXbrl, newDocumentType, url, schemaRefs=schemaRefs, isEntry=isEntry)
    return modelXbrl
    
class ModelXbrl:
    
    def __init__(self, modelManager):
        self.modelManager = modelManager
        self.init()
        
    def init(self, keepViews=False):
        self.namespaceDocs = defaultdict(list)
        self.urlDocs = {}
        self.errors = []
        self.logCountErr = 0
        self.logCountWrn = 0
        self.logCountInfo = 0
        self.arcroleTypes = defaultdict(list)
        self.roleTypes = defaultdict(list)
        self.qnameConcepts = {} # contains ModelConcepts by Py key {ns}}localname of schema elements
        self.qnameAttributes = {}
        self.nameConcepts = defaultdict(list) # contains ModelConcepts by name 
        self.qnameTypes = {} # contains ModelTypes by Py key {ns}localname of type
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
        self.hasEuRendering = False
        self.hasFormulae = False
        self.formulaOutputInstance = None

    def close(self):
        self.closeViews()
        if self.modelDocument:
            self.modelDocument.close([])
        self.modelDocument = None
        self.xbrlManager = None
        self.namespaceDocs = defaultdict(list)
        self.urlDocs = {}
        self.errors = []
        self.logCountErr = 0
        self.logCountWrn = 0
        self.logCountInfo = 0
        self.arcroleTypes = defaultdict(list)
        self.roleTypes = defaultdict(list)
        self.qnameConcepts = {}
        self.qnameAttributes = {}
        self.nameConcepts = defaultdict(list) # contains ModelConcepts by name 
        self.qnameTypes = {}
        self.baseSets = defaultdict(list)
        self.relationshipSets = {}
        self.facts = []
        self.factsInInstance = []
        self.contexts = {}
        self.units = {}
        self.modelObjects = []
        self.qnameParameters = {}
        self.modelParameters = set()
        self.modelVariableSets = set()
        self.modelCustomFunctionSignatures = {}
        self.modelCustomFunctionImplementations = set()
        self.views = []
        self.langs = set()
        self.labelroles = set()
        if hasattr(self,"fileSource"):
            self.fileSource.close()
        self.hasXDT = False
        self.hasFormulae = False
        self.hasEuRendering = False
        if self.formulaOutputInstance:
            self.formulaOutputInstance.close()
            
    def reload(self,nextaction,reloadCache=False):
        from arelle import ModelDocument
        self.init(keepViews=True)
        self.modelDocument = ModelDocument.load(self, self.fileSource.url, isEntry=True, reloadCache=reloadCache)
        self.modelManager.showStatus(_("xbrl loading finished, {0}...").format(nextaction),5000)
        self.modelManager.reloadViews(self)
            
    def closeViews(self):
        for view in range(len(self.views)):
            if len(self.views) > 0:
                self.views[0].close()
        
    def relationshipSet(self, arcrole, linkrole=None, linkqname=None, arcqname=None, includeProhibits=False):
        from arelle import (ModelRelationshipSet)
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
    
    def matchContext(self, scheme, identifier, periodType, start, end, dims, segOCCs, scenOCCs):
        from arelle.ModelFormulaObject import Aspect
        from arelle.ModelValue import dateUnionEqual
        from arelle.XbrlUtil import sEqual
        if dims: segAspect, scenAspect = (Aspect.NON_XDT_SEGMENT, Aspect.NON_XDT_SCENARIO)
        else: segAspect, scenAspect = (Aspect.COMPLETE_SEGMENT, Aspect.COMPLETE_SCENARIO)
        for c in self.contexts.values():
            if (c.entityIdentifier == (scheme, identifier) and
                ((c.isInstantPeriod and periodType == "instant" and dateUnionEqual(c.instantDatetime, end, instantEndDate=True)) or
                 (c.isStartEndPeriod and periodType == "duration" and dateUnionEqual(c.startDatetime, start) and dateUnionEqual(c.endDatetime, end, instantEndDate=True)) or
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
                 
    def matchUnit(self, multiplyBy, divideBy):
        multiplyBy.sort()
        divideBy.sort()
        for u in self.units.values():
            if u.measures == (multiplyBy,divideBy):
                return u
        return None
    
    def matchFact(self, otherFact):
        for fact in self.facts:
            if (fact.qname == otherFact.qname and
                fact.isVEqualTo(otherFact)):
                if not fact.isNumeric:
                    if fact.xmlLang == otherFact.xmlLang:
                        return fact
                else:
                    if (fact.decimals == otherFact.decimals and
                        fact.precision == otherFact.precision):
                        return fact
        return None
            
    def modelObject(self, objectId):
        if isinstance(objectId,int):
            return self.modelObjects[objectId]
        # assume it is a string with ID in a tokenized representation, like xyz_33
        try:
            return self.modelObjects[int(objectId.rpartition("_")[2])]
        except ValueError:
            return None
    
    # UI thread viewModelObject
    def viewModelObject(self, objectId):
        from arelle.ModelObject import ModelObject
        modelObject = ""
        try:
            if isinstance(objectId, ModelObject):
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
        
    def error(self, message, severity=None, *argCodes):
        code = None
        hasRejectedCode = False
        for argCode in argCodes:
            if (isinstance(argCode,dict) or
                (self.modelManager.disclosureSystem.EFM and argCode.startswith("EFM")) or
                (self.modelManager.disclosureSystem.GFM and argCode.startswith("GFM")) or
                (self.modelManager.disclosureSystem.HMRC and argCode.startswith("HMRC")) or
                (self.modelManager.disclosureSystem.SBRNL and argCode.startswith("SBR.NL")) or
                argCode[0:3] not in ("EFM", "GFM", "HMR", "SBR")):
                code = argCode
                break
            else:
                hasRejectedCode = True
        if code is not None:
            if severity in ('wrn','err'):
                self.errors.append(code)
            elif severity in ('asrt','asrtNoLog'):
                self.errors.append(code) # code is dict expression of id and counts successful/not successful
                code = "assertion:trace" # replace with user friendly code for log
            logString = "[{0}] {1}".format(code, message)
        else:
            if hasRejectedCode:
                return # ignore if wrong disclosure system mode
            logString = message
        if severity != 'asrtNoLog':
            self.modelManager.addToLog(logString)
            
        if severity == 'err': self.logCountErr += 1
        elif severity == 'wrn': self.logCountWrn += 1
        elif severity == 'info': self.logCountInfo += 1
