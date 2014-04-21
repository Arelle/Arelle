'''
StreamingExtensions is a plug-in to both GUI menu and command line/web service
that provides an alternative approach to big instance documents without building a DOM, to save
memory footprint.  lxml iterparse is used to parse the big instance.  ModelObjects are specialized by features
for efficiency and to avoid dependency on an underlying DOM.

(Note that this module is based on a parser target, an alternate based on iterparse is under examples/plugin.)

(c) Copyright 2013 Mark V Systems Limited, All rights reserved.
'''

import io, sys, os, time
from decimal import Decimal, InvalidOperation
from lxml import etree
from collections import defaultdict
from arelle import XbrlConst, XmlUtil, XmlValidate, ValidateXbrlDimensions
from arelle.ModelDocument import ModelDocument, Type
from arelle.ModelObject import ModelObject
from arelle.ModelObjectFactory import parser
from arelle.ModelValue import QName
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelUnit
from arelle.Validate import Validate

_streamingExtensionsCheck = True  # check streaming if enabled except for CmdLine, then only when requested
_streamingExtensionsValidate = False
    
class NotInstanceDocumentException(Exception):
    def __init__(self):
        pass

def precedingProcessingInstruction(elt, target):
    pi = elt.getprevious()
    while pi is not None:
        if isinstance(pi, etree._ProcessingInstruction) and pi.target == target:
            return pi
        pi = pi.getprevious()
    return None

def precedingComment(elt):
    c = elt.getprevious()
    comment = ''
    while c is not None:
        if isinstance(c, etree._Comment) and c.text:
            comment = c.text + '\n' + comment
        c = c.getprevious()
    return comment or None

def streamingExtensionsLoader(modelXbrl, mappedUri, filepath, **kwargs):
    # check if big instance and has header with an initial incomplete tree walk (just 2 elements
    if not _streamingExtensionsCheck:
        return None
    
    # track whether modelXbrl has been validated by this streaming extension
    modelXbrl._streamingExtensionValidated = False
        
    def logSyntaxErrors(parsercontext):
        for error in parsercontext.error_log:
            modelXbrl.error("xmlSchema:syntax",
                    _("%(error)s, %(fileName)s, line %(line)s, column %(column)s, %(sourceAction)s source element"),
                    modelObject=modelXbrl, fileName=os.path.basename(filepath), 
                    error=error.message, line=error.line, column=error.column, sourceAction="streaming")
    #### note: written for iterparse of lxml prior to version 3.3, otherwise rewrite to use XmlPullParser ###
    #### note: iterparse wants a binary file, but file is text mode
    _file, = modelXbrl.fileSource.file(filepath, binary=True)
    startedAt = time.time()
    modelXbrl.profileActivity()
    ''' this seems twice as slow as iterparse
    class instInfoTarget():
        def __init__(self, element_factory=None, parser=None):
            self.newTree = True
            self.streamingAspects = None
            self.foundInstance = False
            self.creationSoftwareComment = ''
            self.currentEltTag = "(before xbrli:xbrl)"
            self.numRootFacts = 0
        def start(self, tag, attrib, nsmap=None):
            if self.newTree:
                if tag == "{http://www.xbrl.org/2003/instance}xbrl":
                    self.foundInstance = True
                    self.newTree = False
                else: # break 
                    raise NotInstanceDocumentException()
            elif not tag.startswith("{http://www.xbrl.org/"):
                self.numRootFacts += 1
                if self.numRootFacts % 1000 == 0:
                    modelXbrl.profileActivity("... streaming tree check", minTimeToShow=20.0)
            self.currentEltTag = tag
        def end(self, tag):
            pass
        def data(self, data):
            pass
        def comment(self, text):
            if not self.foundInstance: # accumulate comments before xbrli:xbrl
                self.creationSoftwareComment += ('\n' if self.creationSoftwareComment else '') + text
            elif not self.creationSoftwareComment:
                self.creationSoftwareComment = text # or first comment after xbrli:xbrl
        def pi(self, target, data):
            if target == "xbrl-streamable-instance":
                if self.currentEltTag == "{http://www.xbrl.org/2003/instance}xbrl":
                    self.streamingAspects = dict(etree.PI(target,data).attrib.copy()) # dereference target results
                else:
                    modelXbrl.error("streamingExtensions:headerMisplaced",
                            _("Header is misplaced: %(target)s, must follow xbrli:xbrl element but was found at %(element)s"),
                            modelObject=modelXbrl, target=target, element=self.currentEltTag)
        def close(self):
            if not self.creationSoftwareComment:
                self.creationSoftwareComment = None
            return True
    instInfo = instInfoTarget()
    infoParser = etree.XMLParser(recover=True, huge_tree=True, target=instInfo)
    try:
        etree.parse(_file, parser=infoParser, base_url=filepath)
    except NotInstanceDocumentException:
        pass
    '''
    foundErrors = False
    foundInstance = False
    streamingAspects = None
    creationSoftwareComment = None
    instInfoNumRootFacts = 0
    numElts = 0
    elt = None
    instInfoContext = etree.iterparse(_file, events=("start","end"), huge_tree=True)
    for event, elt in instInfoContext:
        if event == "start":
            if elt.getparent() is not None:
                if elt.getparent().tag == "{http://www.xbrl.org/2003/instance}xbrl":
                    if not foundInstance:
                        foundInstance = True
                        pi = precedingProcessingInstruction(elt, "xbrl-streamable-instance")
                        if pi is None:
                            break
                        else:
                            streamingAspects = dict(pi.attrib.copy())
                            if creationSoftwareComment is None:
                                creationSoftwareComment = precedingComment(elt)
                    if not elt.tag.startswith("{http://www.xbrl.org/"):
                        instInfoNumRootFacts += 1
                        if instInfoNumRootFacts % 1000 == 0:
                            modelXbrl.profileActivity("... streaming tree check", minTimeToShow=20.0)
                elif not foundInstance:       
                    break
            elif elt.tag == "{http://www.xbrl.org/2003/instance}xbrl":
                creationSoftwareComment = precedingComment(elt)
                if precedingProcessingInstruction(elt, "xbrl-streamable-instance") is not None:
                    modelXbrl.error("streamingExtensions:headerMisplaced",
                            _("Header is misplaced: %(error)s, must follow xbrli:xbrl element"),
                            modelObject=elt)
        elif event == "end":
            elt.clear()
            numElts += 1
            if numElts % 1000 == 0 and elt.getparent() is not None:
                while elt.getprevious() is not None and elt.getparent() is not None:
                    del elt.getparent()[0]
    if elt is not None:
        elt.clear()
    
    _file.seek(0,io.SEEK_SET) # allow reparsing
    if not foundInstance or streamingAspects is None:
        del elt
        _file.close()
        return None
    modelXbrl.profileStat(_("streaming tree check"), time.time() - startedAt)
    startedAt = time.time()
    try:
        version = Decimal(streamingAspects.get("version"))
        if int(version) != 1:
            modelXbrl.error("streamingExtensions:unsupportedVersion",
                    _("Streaming version %(version)s, major version number must be 1"),
                    modelObject=elt, version=version)
            foundErrors = True
    except (InvalidOperation, OverflowError):
        modelXbrl.error("streamingExtensions:versionError",
                _("Version %(version)s, number must be 1.n"),
                modelObject=elt, version=streamingAspects.get("version", "(none)"))
        foundErrors = True
    for bufAspect in ("contextBuffer", "unitBuffer", "footnoteBuffer"):
        try:
            bufLimit = Decimal(streamingAspects.get(bufAspect, "INF"))
            if bufLimit < 1 or (bufLimit.is_finite() and bufLimit % 1 != 0):
                raise InvalidOperation
            elif bufAspect == "contextBuffer":
                contextBufferLimit = bufLimit
            elif bufAspect == "unitBuffer":
                unitBufferLimit = bufLimit
            elif bufAspect == "footnoteBuffer":
                footnoteBufferLimit = bufLimit
        except InvalidOperation:
            modelXbrl.error("streamingExtensions:valueError",
                    _("Streaming %(attrib)s %(value)s, number must be a positive integer or INF"),
                    modelObject=elt, attrib=bufAspect, value=streamingAspects.get(bufAspect))
            foundErrors = True
    if _streamingExtensionsValidate:
        incompatibleValidations = []
        _validateDisclosureSystem = modelXbrl.modelManager.validateDisclosureSystem
        _disclosureSystem = modelXbrl.modelManager.disclosureSystem
        if _validateDisclosureSystem and _disclosureSystem.EFM:
            incompatibleValidations.append("EFM")
        if _validateDisclosureSystem and _disclosureSystem.GFM:
            incompatibleValidations.append("GFM")
        if _validateDisclosureSystem and _disclosureSystem.EBA:
            incompatibleValidations.append("EBA")
        if _validateDisclosureSystem and _disclosureSystem.HMRC:
            incompatibleValidations.append("EBA")
        if modelXbrl.modelManager.validateCalcLB:
            incompatibleValidations.append("calculation LB")
        if incompatibleValidations:            
            modelXbrl.error("streamingExtensions:incompatibleValidation",
                    _("Streaming instance validation does not support %(incompatibleValidations)s validation"),
                    modelObject=modelXbrl, incompatibleValidations=', '.join(incompatibleValidations))
            foundErrors = True
    if instInfoContext.error_log:
        foundErrors = True
    logSyntaxErrors(instInfoContext)
    del instInfoContext # dereference
    
    if foundErrors:
        _file.close()
        return None

    _encoding = XmlUtil.encoding(_file.read(512))
    _file.seek(0,io.SEEK_SET) # allow reparsing

    if _streamingExtensionsValidate:
        validator = Validate(modelXbrl)
        instValidator = validator.instValidator

    eltMdlObjs = {}
    contextBuffer = []
    unitBuffer = []
    footnoteBuffer = []
    factBuffer = []
    numFacts = 1
    
    class modelLoaderTarget():
        def __init__(self, element_factory=None, parser=None):
            self.newTree = True
            self.currentMdlObj = None
            self.beforeInstanceStream = True
            self.numRootFacts = 1
        def start(self, tag, attrib, nsmap=None):
            mdlObj = _parser.makeelement(tag, attrib=attrib, nsmap=nsmap)
            mdlObj.sourceline = 1
            if self.newTree:
                self.newTree = False
                self.currentMdlObj = mdlObj
                modelDocument = ModelDocument(modelXbrl, Type.INSTANCE, mappedUri, filepath, mdlObj.getroottree())
                modelXbrl.modelDocument = modelDocument # needed for incremental validation
                mdlObj.init(modelDocument)
                modelDocument.parser = _parser # needed for XmlUtil addChild's makeelement 
                modelDocument.parserLookupName = _parserLookupName
                modelDocument.parserLookupClass = _parserLookupClass
                modelDocument.xmlRootElement = mdlObj
                modelDocument.schemaLocationElements.add(mdlObj)
                modelDocument.documentEncoding = _encoding
                modelDocument._creationSoftwareComment = creationSoftwareComment
                modelXbrl.info("streamingExtensions:streaming",
                               _("Stream processing this instance."),
                               modelObject = modelDocument)    
            else:
                self.currentMdlObj.append(mdlObj)
                self.currentMdlObj = mdlObj
                mdlObj._init()
                ns = mdlObj.namespaceURI
                ln = mdlObj.localName
                if (self.beforeInstanceStream and (
                    (ns == XbrlConst.link and ln not in ("schemaRef", "linkbaseRef")) or
                    (ns == XbrlConst.xbrli and ln in ("context", "unit")) or
                    (ns not in (XbrlConst.link, XbrlConst.xbrli)))):
                    self.beforeInstanceStream = False
                    if _streamingExtensionsValidate:
                        instValidator.validate(modelXbrl, modelXbrl.modelManager.formulaOptions.typedParameters())
                    else: # need default dimensions
                        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
            return mdlObj
        def end(self, tag):
            modelDocument = modelXbrl.modelDocument
            mdlObj = self.currentMdlObj
            parentMdlObj = mdlObj.getparent()
            self.currentMdlObj = parentMdlObj
            ns = mdlObj.namespaceURI
            ln = mdlObj.localName
            if ns == XbrlConst.xbrli:
                if ln == "context":
                    if mdlObj.get("sticky"):
                        del mdlObj.attrib["sticky"]
                        XmlValidate.validate(modelXbrl, mdlObj)
                        modelDocument.contextDiscover(mdlObj)
                    else:
                        if _streamingExtensionsValidate and len(contextBuffer) >= contextBufferLimit:
                            # drop before adding as dropped may have same id as added
                            cntx = contextBuffer.pop(0)
                            dropContext(modelXbrl, cntx)
                            del parentMdlObj[parentMdlObj.index(cntx)]
                            cntx = None
                        XmlValidate.validate(modelXbrl, mdlObj)
                        modelDocument.contextDiscover(mdlObj)
                        if contextBufferLimit.is_finite():
                            contextBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        contextsToCheck = (mdlObj,)
                        instValidator.checkContexts(contextsToCheck)
                        if modelXbrl.hasXDT:
                            instValidator.checkContextsDimensions(contextsToCheck)
                        del contextsToCheck # dereference
                elif ln == "unit":
                    if _streamingExtensionsValidate and len(unitBuffer) >= unitBufferLimit:
                        # drop before additing as dropped may have same id as added
                        unit = unitBuffer.pop(0)
                        dropUnit(modelXbrl, unit)
                        del parentMdlObj[parentMdlObj.index(unit)]
                        unit = None 
                    XmlValidate.validate(modelXbrl, mdlObj)
                    modelDocument.unitDiscover(mdlObj)
                    if unitBufferLimit.is_finite():
                        unitBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        instValidator.checkUnits( (mdlObj,) )
                elif ln == "xbrl": # end of document
                    # check remaining footnote refs
                    for footnoteLink in footnoteBuffer:
                        checkFootnoteHrefs(modelXbrl, footnoteLink)
            elif ns == XbrlConst.link:
                if ln == "footnoteLink":
                    XmlValidate.validate(modelXbrl, mdlObj)
                    footnoteLinks = (mdlObj,)
                    modelDocument.linkbaseDiscover(footnoteLinks, inInstance=True)
                    if footnoteBufferLimit.is_finite():
                        footnoteBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        instValidator.checkLinks(footnoteLinks)
                        if len(footnoteBuffer) > footnoteBufferLimit:
                            # check that hrefObjects for locators were all satisfied
                                # drop before addition as dropped may have same id as added
                            footnoteLink = footnoteBuffer.pop(0)
                            checkFootnoteHrefs(modelXbrl, footnoteLink)
                            dropFootnoteLink(modelXbrl, footnoteLink)
                            del parentMdlObj[parentMdlObj.index(footnoteLink)]
                            footnoteLink = None
                    footnoteLinks = None
                elif ln in ("schemaRef", "linkbaseRef"):
                    modelDocument.discoverHref(mdlObj)
                elif not modelXbrl.skipDTS:
                    if ln in ("roleRef", "arcroleRef"):
                        modelDocument.linkbaseDiscover((mdlObj,), inInstance=True)
            elif parentMdlObj.qname == XbrlConst.qnXbrliXbrl:
                self.numRootFacts += 1
                XmlValidate.validate(modelXbrl, mdlObj)
                modelDocument.factDiscover(mdlObj, modelXbrl.facts)
                if _streamingExtensionsValidate:
                    factsToCheck = (mdlObj,)
                    instValidator.checkFacts(factsToCheck)
                    if modelXbrl.hasXDT:
                        instValidator.checkFactsDimensions(factsToCheck)
                    del factsToCheck
                    dropFact(modelXbrl, mdlObj, modelXbrl.facts)
                    del parentMdlObj[parentMdlObj.index(mdlObj)]
                if self.numRootFacts % 1000 == 0:
                    modelXbrl.profileActivity("... streaming fact {0} of {1} {2:.2f}%".format(self.numRootFacts, instInfoNumRootFacts, 
                                                                                              100.0 * self.numRootFacts / instInfoNumRootFacts), 
                                              minTimeToShow=20.0)
            return mdlObj
        def data(self, data):
            self.currentMdlObj.text = data
        def comment(self, text):
            pass
        def pi(self, target, data):
            pass
        def close(self):
            return None
        
    _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl, filepath, target=modelLoaderTarget())
    etree.parse(_file, parser=_parser, base_url=filepath)
    logSyntaxErrors(_parser)
    _file.close()
    if _streamingExtensionsValidate and validator is not None:
        del instValidator
        validator.close()
        # track that modelXbrl has been validated by this streaming extension
        modelXbrl._streamingExtensionValidated = True
        
    modelXbrl.profileStat(_("streaming complete"), time.time() - startedAt)
    return modelXbrl.modelDocument

def checkFootnoteHrefs(modelXbrl, footnoteLink):
    for locElt in footnoteLink.iterchildren(tag="{http://www.xbrl.org/2003/linkbase}loc"):
        for hrefElt, doc, id in footnoteLink.modelDocument.hrefObjects:
            if locElt == hrefElt and id not in footnoteLink.modelDocument.idObjects:
                modelXbrl.error("streamingExtensions:footnoteId",
                        _("Footnote id %(id)s not matched to fact in buffered region"),
                        modelObject=footnoteLink, id=id)

def dropContext(modelXbrl, cntx):
    del modelXbrl.contexts[cntx.id]
    dropObject(modelXbrl, cntx)
    
def dropUnit(modelXbrl, unit):
    del modelXbrl.units[unit.id]
    dropObject(modelXbrl, unit)
    
def dropFootnoteLink(modelXbrl, footnoteLink):
    for baseSet in modelXbrl.baseSets.values():
        if footnoteLink in baseSet:
            baseSet.remove(footnoteLink)
    dropObject(modelXbrl, footnoteLink)
    
def dropFact(modelXbrl, fact, facts):
    while fact.modelTupleFacts:
        dropFact(modelXbrl, fact.modelTupleFacts[0], fact.modelTupleFacts)
    modelXbrl.factsInInstance.discard(fact)
    facts.remove(fact)
    modelXbrl.modelObjects[fact.objectIndex] = None # objects found by index, can't remove position from list
    fact.modelDocument.modelObjects.remove(fact)
    fact.clear()
    
def dropObject(modelXbrl, mdlObj):
    for childObj in mdlObj.iterchildren():
        dropObject(modelXbrl, childObj)
    if mdlObj.qname == XbrlConst.qnLinkLoc:
        hrefs = mdlObj.modelDocument.hrefObjects
        removedHrefs = [i for i, hrefObj in enumerate(hrefs) if mdlObj == hrefObj[0]]
        for i in removedHrefs:
            del hrefs[i]
    modelXbrl.modelObjects[mdlObj.objectIndex] = None # objects found by index, can't remove position from list
    mdlObj.modelDocument.modelObjects.remove(mdlObj)
    mdlObj.modelDocument.idObjects.pop(mdlObj.id, None)
    mdlObj.clear()

'''
def streamingOptionsExtender(parser):
    parser.add_option("--check-streaming", 
                      action="store_true", 
                      dest="check_streaming", 
                      help=_('Check streamability of instance document."'))
'''

def streamingExtensionsSetup(cntlr, options, **kwargs):
    global _streamingExtensionsCheck, _streamingExtensionsValidate
    # streaming only checked in CmdLine/web server mode if requested
    # _streamingExtensionsCheck = getattr(options, 'check_streaming', False)
    _streamingExtensionsValidate = options.validate

def streamingExtensionsIsValidated(modelXbrl):
    return getattr(modelXbrl, "_streamingExtensionValidated", False)

'''
   Do not use _( ) in pluginInfo itself (it is applied later, after loading
'''

__pluginInfo__ = {
    'name': 'Streaming Extensions Loader',
    'version': '0.9',
    'description': "This plug-in loads big XBRL instances without building a DOM in memory.  "
                    "lxml iterparse parses XBRL directly into an object model without a DOM.  ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2014 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    # take out for now: 'CntlrCmdLine.Options': streamingOptionsExtender,
    'CntlrCmdLine.Utility.Run': streamingExtensionsSetup,
    'ModelDocument.PullLoader': streamingExtensionsLoader,
    'ModelDocument.IsValidated': streamingExtensionsIsValidated,
}
