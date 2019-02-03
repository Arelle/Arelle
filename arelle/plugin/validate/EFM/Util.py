'''
Created on Jul 7, 2018

@author: Mark V Systems Limited
(c) Copyright 2018 Mark V Systems Limited, All rights reserved.
'''
import os, json, re
from collections import defaultdict
from arelle.FileSource import openFileStream, openFileSource, saveFile # only needed if building a cached file
from arelle.ModelValue import qname
from arelle import XbrlConst
from arelle.PythonUtil import attrdict
from .Consts import standardNamespacesPattern, latestTaxonomyDocs

EMPTY_DICT = {}

def conflictClassFromNamespace(namespaceURI):
    match = standardNamespacesPattern.match(namespaceURI or "")
    if match:
        _class = match.group(2) or match.group(5)[:4] # trim ifrs-full to ifrs
        if _class.startswith("ifrs"):
            _class = "ifrs"
        return "{}/{}".format(_class, match.group(3) or match.group(4))
        
def abbreviatedNamespace(namespaceURI):
    match = standardNamespacesPattern.match(namespaceURI or "")
    if match:
        return "{}/{}".format(match.group(2) or match.group(5), match.group(3) or match.group(4))
    
def abbreviatedWildNamespace(namespaceURI):
    match = standardNamespacesPattern.match(namespaceURI or "")
    if match:
        return "{}/*".format(match.group(2) or match.group(5))
    
def loadNonNegativeFacts(modelXbrl):
    _file = openFileStream(modelXbrl.modelManager.cntlr, resourcesFilePath(modelXbrl.modelManager, "signwarnings.json"), 'rt', encoding='utf-8')
    signwarnings = json.load(_file) # {localName: date, ...}
    _file.close()
    concepts = set()
    excludedAxesMembers = defaultdict(set)
    for modelDocument in modelXbrl.urlDocs.values():
        ns = modelDocument.targetNamespace # set up non neg lookup by full NS
        for abbrNs in (abbreviatedNamespace(ns), abbreviatedWildNamespace(ns)):
            for localName in signwarnings["conceptNames"].get(abbrNs, ()):
                concepts.add(qname(ns, localName))
            for localDimName, localMemNames in signwarnings["excludedAxesMembers"].get(abbrNs, EMPTY_DICT).items():
                for localMemName in localMemNames:
                    excludedAxesMembers[qname(ns, localDimName)].add(qname(ns, localMemName) if localMemName != "*" else None)
    return attrdict(concepts=concepts, excludedAxesMembers=excludedAxesMembers)
    
def loadCustomAxesReplacements(modelXbrl): # returns match expression, standard patterns
    _file = openFileStream(modelXbrl.modelManager.cntlr, resourcesFilePath(modelXbrl.modelManager, "axiswarnings.json"), 'rt', encoding='utf-8')
    axiswarnings = json.load(_file) # {localName: date, ...}
    _file.close()
    standardAxes = {}
    matchPattern = []
    for i, (standardAxis, customAxisPattern) in enumerate(axiswarnings.items()):
        if standardAxis not in ("#", "copyright", "description"):
            patternName = "_{}".format(i)
            standardAxes[patternName] = standardAxis
            matchPattern.append("(?P<{}>^{}$)".format(patternName, customAxisPattern))
    return attrdict(standardAxes=standardAxes, 
                    customNamePatterns=re.compile("|".join(matchPattern)))

def loadDeprecatedConceptDates(val, deprecatedConceptDates):  
    for modelDocument in val.modelXbrl.urlDocs.values():
        ns = modelDocument.targetNamespace
        abbrNs = abbreviatedWildNamespace(ns)
        latestTaxonomyDoc = latestTaxonomyDocs.get(abbrNs)
        _fileName = deprecatedConceptDatesFile(val.modelXbrl.modelManager, abbrNs, latestTaxonomyDoc)
        if _fileName:
            _file = openFileStream(val.modelXbrl.modelManager.cntlr, _fileName, 'rt', encoding='utf-8')
            _deprecatedConceptDates = json.load(_file) # {localName: date, ...}
            _file.close()
            for localName, date in _deprecatedConceptDates.items():
                deprecatedConceptDates[qname(ns, localName)] = date
                
def resourcesFilePath(modelManager, fileName):
    # resourcesDir can be in cache dir (production) or in validate/EFM/resources (for development)
    _resourcesDir = os.path.join( os.path.dirname(__file__), "resources") # dev/testing location
    _target = "validate/EFM/resources"
    if not os.path.isabs(_resourcesDir):
        _resourcesDir = os.path.abspath(_resourcesDir)
    if not os.path.exists(_resourcesDir): # production location
        _resourcesDir = os.path.join(modelManager.cntlr.webCache.cacheDir, "resources", "validation", "EFM")
        _target = "web-cache/resources"
    return os.path.join(_resourcesDir, fileName)
                    
def deprecatedConceptDatesFile(modelManager, abbrNs, latestTaxonomyDoc):
    if latestTaxonomyDoc is None:
        return None
    if not abbrNs: # none for an unexpected namespace pattern
        return None
    cntlr = modelManager.cntlr
    _fileName = resourcesFilePath(modelManager, abbrNs.partition("/")[0] + "-deprecated-concepts.json")
    _deprecatedLabelRole = latestTaxonomyDoc["deprecatedLabelRole"]
    _deprecatedDateMatchPattern = latestTaxonomyDoc["deprecationDatePattern"]
    if os.path.exists(_fileName):
        return _fileName
    # load labels and store file name
    modelManager.addToLog(_("loading {} deprecated concepts into {}").format(abbrNs, _fileName), messageCode="info")
    deprecatedConceptDates = {}
    # load without SEC/EFM validation (doc file would not be acceptable)
    priorValidateDisclosureSystem = modelManager.validateDisclosureSystem
    modelManager.validateDisclosureSystem = False
    from arelle import ModelXbrl
    deprecationsInstance = ModelXbrl.load(modelManager, 
          # "http://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-doc-2012-01-31.xml",
          # load from zip (especially after caching) is incredibly faster
          openFileSource(latestTaxonomyDoc["deprecatedLabels"], cntlr), 
          _("built deprecations table in cache"))
    modelManager.validateDisclosureSystem = priorValidateDisclosureSystem
    if deprecationsInstance is None:
        modelManager.addToLog(
            _("%(name)s documentation not loaded"),
            messageCode="arelle:notLoaded", messageArgs={"modelXbrl": val, "name":_abbrNs})
    else:   
        # load deprecations
        for labelRel in deprecationsInstance.relationshipSet(XbrlConst.conceptLabel).modelRelationships:
            modelLabel = labelRel.toModelObject
            conceptName = labelRel.fromModelObject.name
            if modelLabel.role == _deprecatedLabelRole:
                match = _deprecatedDateMatchPattern.match(modelLabel.text)
                if match is not None:
                    date = match.group(1)
                    if date:
                        deprecatedConceptDates[conceptName] = date
        jsonStr = _STR_UNICODE(json.dumps(deprecatedConceptDates, ensure_ascii=False, indent=0)) # might not be unicode in 2.7
        saveFile(cntlr, _fileName, jsonStr)  # 2.7 gets unicode this way
        deprecationsInstance.close()
        del deprecationsInstance # dereference closed modelXbrl
    
def buildDeprecatedConceptDatesFiles(cntlr):
    # will build in subdirectory "resources" if exists, otherwise in cache/resources
    for abbrNs, latestTaxonomyDoc in latestTaxonomyDocs.items():
        deprecatedConceptDatesFile(cntlr.modelManager, abbrNs, latestTaxonomyDoc)