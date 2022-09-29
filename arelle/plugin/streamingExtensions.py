'''
StreamingExtensions is a plug-in to both GUI menu and command line/web service
that provides an alternative approach to big instance documents without building a DOM, to save
memory footprint.  lxml iterparse is used to parse the big instance.  ModelObjects are specialized by features
for efficiency and to avoid dependency on an underlying DOM.

(Note that this module is based on a parser target, an alternate based on iterparse is under examples/plugin.)

See COPYRIGHT.md for copyright information.

Calls these plug-in classes:
   Streaming.BlockingPlugin(modelXbrl):  returns name of plug in blocking streaming if it is being blocked, else None
   Streaming.Start(modelXbrl): notifies that streaming is starting for modelXbrl; simulated modelDocument is established
   Streaming.ValidateFacts(modelXbrl, modelFacts) modelFacts are available for streaming processing
   Streaming.Finish(modelXbrl): notifies that streaming is finished
'''

import io, os, time, sys, re, gc
from decimal import Decimal, InvalidOperation
from lxml import etree
from arelle import XbrlConst, XmlUtil, XmlValidate, ValidateXbrlDimensions
from arelle.ModelDocument import ModelDocument, Type
from arelle.ModelObjectFactory import parser
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelFact
from arelle.PluginManager import pluginClassMethods
from arelle.Validate import Validate
from arelle.Version import authorLabel, copyrightLabel
from arelle.HashUtil import md5hash, Md5Sum

_streamingExtensionsCheck = True  # check streaming if enabled except for CmdLine, then only when requested
_streamingExtensionsValidate = False
_streamingValidatePlugin = False

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

def childProcessingInstruction(elt, target, reversed=False):
    for pi in elt.iterchildren(reversed=reversed):
        if isinstance(pi, etree._ProcessingInstruction):
            if pi.target == target:
                return pi
        else:
            break
    return None

def precedingComment(elt):
    c = elt.getprevious()
    comment = ''
    while c is not None:
        if isinstance(c, etree._Comment) and c.text:
            comment = c.text + '\n' + comment
        c = c.getprevious()
    return comment or None

def streamingExtensionsLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
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
    try:
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
    except etree.XMLSyntaxError as err:
        modelXbrl.error("xmlSchema:syntax",
                _("Unrecoverable error: %(error)s"),
                error=err)
        _file.close()
        return err

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
        if _validateDisclosureSystem and _disclosureSystem.validationType == "EFM":
            incompatibleValidations.append("EFM")
        if _validateDisclosureSystem and _disclosureSystem.validationType == "GFM":
            incompatibleValidations.append("GFM")
        if _validateDisclosureSystem and _disclosureSystem.validationType == "HMRC":
            incompatibleValidations.append("HMRC")
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

    for pluginMethod in pluginClassMethods("Streaming.BlockStreaming"):
        _blockingPluginName = pluginMethod(modelXbrl)
        if _blockingPluginName: # name of blocking plugin is returned
            modelXbrl.error("streamingExtensions:incompatiblePlugIn",
                    _("Streaming instance not supported by plugin %(blockingPlugin)s"),
                    modelObject=modelXbrl, blockingPlugin=_blockingPluginName)
            foundErrors = True

    if foundErrors:
        _file.close()
        return None

    _encoding = XmlUtil.encoding(_file.read(512))
    _file.seek(0,io.SEEK_SET) # allow reparsing

    if _streamingExtensionsValidate:
        validator = Validate(modelXbrl)
        instValidator = validator.instValidator

    contextBuffer = []
    contextsToDrop = []
    unitBuffer = []
    unitsToDrop = []
    footnoteBuffer = []
    footnoteLinksToDrop = []

    _streamingFactsPlugin = any(True for pluginMethod in pluginClassMethods("Streaming.Facts"))
    _streamingValidateFactsPlugin = (_streamingExtensionsValidate and
                                     any(True for pluginMethod in pluginClassMethods("Streaming.ValidateFacts")))

    ''' this is very much slower than iterparse
    class modelLoaderTarget():
        def __init__(self, element_factory=None, parser=None):
            self.newTree = True
            self.currentMdlObj = None
            self.beforeInstanceStream = True
            self.beforeStartStreamingPlugin = True
            self.numRootFacts = 1
            modelXbrl.makeelementParentModelObject = None
            modelXbrl.isStreamingMode = True
            self.factsCheckVersion = None
            self.factsCheckMd5s = Md5Sum()
        def start(self, tag, attrib, nsmap=None):
            modelXbrl.makeelementParentModelObject = self.currentMdlObj # pass parent to makeelement for ModelObjectFactory
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
                        instValidator.validate(modelXbrl, modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces))
                    else: # need default dimensions
                        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
                elif not self.beforeInstanceStream and self.beforeStartStreamingPlugin:
                    for pluginMethod in pluginClassMethods("Streaming.Start"):
                        pluginMethod(modelXbrl)
                    self.beforeStartStreamingPlugin = False
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
                            if _streamingValidateFactsPlugin:
                                contextsToDrop.append(cntx)
                            else:
                                dropContext(modelXbrl, cntx)
                                del parentMdlObj[parentMdlObj.index(cntx)]
                            cntx = None
                        #>>XmlValidate.validate(modelXbrl, mdlObj)
                        #>>modelDocument.contextDiscover(mdlObj)
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
                        # drop before adding as dropped may have same id as added
                        unit = unitBuffer.pop(0)
                        if _streamingValidateFactsPlugin:
                            unitsToDrop.append(unit)
                        else:
                            dropUnit(modelXbrl, unit)
                            del parentMdlObj[parentMdlObj.index(unit)]
                        unit = None
                    #>>XmlValidate.validate(modelXbrl, mdlObj)
                    #>>modelDocument.unitDiscover(mdlObj)
                    if unitBufferLimit.is_finite():
                        unitBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        instValidator.checkUnits( (mdlObj,) )
                elif ln == "xbrl": # end of document
                    # check remaining batched facts if any
                    if _streamingValidateFactsPlugin:
                        # plugin attempts to process batch of all root facts not yet processed (not just current one)
                        # finish any final batch of facts
                        if len(modelXbrl.facts) > 0:
                            factsToCheck = modelXbrl.facts.copy()
                            factsHaveBeenProcessed = True
                            # can block facts deletion if required data not yet available, such as numeric unit for DpmDB
                            for pluginMethod in pluginClassMethods("Streaming.ValidateFacts"):
                                if not pluginMethod(modelXbrl, factsToCheck):
                                    factsHaveBeenProcessed = False
                            if factsHaveBeenProcessed:
                                for fact in factsToCheck:
                                    dropFact(modelXbrl, fact, modelXbrl.facts)
                                    del parentMdlObj[parentMdlObj.index(fact)]
                                for cntx in contextsToDrop:
                                    dropContext(modelXbrl, cntx)
                                    del parentMdlObj[parentMdlObj.index(cntx)]
                                for unit in unitsToDrop:
                                    dropUnit(modelXbrl, unit)
                                    del parentMdlObj[parentMdlObj.index(unit)]
                                for footnoteLink in footnoteLinksToDrop:
                                    dropFootnoteLink(modelXbrl, footnoteLink)
                                    del parentMdlObj[parentMdlObj.index(footnoteLink)]
                                fact = cntx = unit = footnoteLink = None
                                del contextsToDrop[:]
                                del unitsToDrop[:]
                                del footnoteLinksToDrop[:]
                            del factsToCheck
                    # check remaining footnote refs
                    for footnoteLink in footnoteBuffer:
                        checkFootnoteHrefs(modelXbrl, footnoteLink)
                    for pluginMethod in pluginClassMethods("Streaming.Finish"):
                        pluginMethod(modelXbrl)
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
                            if _streamingValidateFactsPlugin:
                                footnoteLinksToDrop.append(footnoteLink)
                            else:
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
                #>>XmlValidate.validate(modelXbrl, mdlObj)
                #>>modelDocument.factDiscover(mdlObj, modelXbrl.facts)
                if self.factsCheckVersion:
                    self.factCheckFact(mdlObj)
                if _streamingExtensionsValidate or _streamingValidateFactsPlugin:
                    factsToCheck = (mdlObj,)  # validate current fact by itself
                    if _streamingExtensionsValidate:
                        instValidator.checkFacts(factsToCheck)
                        if modelXbrl.hasXDT:
                            instValidator.checkFactsDimensions(factsToCheck)
                    if _streamingValidateFactsPlugin:
                        # plugin attempts to process batch of all root facts not yet processed (not just current one)
                        # use batches of 1000 facts
                        if len(modelXbrl.facts) > 1000:
                            factsToCheck = modelXbrl.facts.copy()
                            factsHaveBeenProcessed = True
                            # can block facts deletion if required data not yet available, such as numeric unit for DpmDB
                            for pluginMethod in pluginClassMethods("Streaming.ValidateFacts"):
                                if not pluginMethod(modelXbrl, factsToCheck):
                                    factsHaveBeenProcessed = False
                            if factsHaveBeenProcessed:
                                for fact in factsToCheck:
                                    dropFact(modelXbrl, fact, modelXbrl.facts)
                                    del parentMdlObj[parentMdlObj.index(fact)]
                                for cntx in contextsToDrop:
                                    dropContext(modelXbrl, cntx)
                                    del parentMdlObj[parentMdlObj.index(cntx)]
                                for unit in unitsToDrop:
                                    dropUnit(modelXbrl, unit)
                                    del parentMdlObj[parentMdlObj.index(unit)]
                                for footnoteLink in footnoteLinksToDrop:
                                    dropFootnoteLink(modelXbrl, footnoteLink)
                                    del parentMdlObj[parentMdlObj.index(footnoteLink)]
                                fact = cntx = unit = footnoteLink = None
                                del contextsToDrop[:]
                                del unitsToDrop[:]
                                del footnoteLinksToDrop[:]
                            del factsToCheck # dereference fact or batch of facts
                    else:
                        dropFact(modelXbrl, mdlObj, modelXbrl.facts) # single fact has been processed
                        del parentMdlObj[parentMdlObj.index(mdlObj)]
                if self.numRootFacts % 1000 == 0:
                    pass
                    #modelXbrl.profileActivity("... streaming fact {0} of {1} {2:.2f}%".format(self.numRootFacts, instInfoNumRootFacts,
                    #                                                                          100.0 * self.numRootFacts / instInfoNumRootFacts),
                    #                          minTimeToShow=20.0)
                    gc.collect()
                    sys.stdout.write ("\rAt fact {} of {} mem {}".format(self.numRootFacts, instInfoNumRootFacts, modelXbrl.modelManager.cntlr.memoryUsed))
            return mdlObj
        def data(self, data):
            self.currentMdlObj.text = data
        def comment(self, text):
            pass
        def pi(self, target, data):
            if target == "xbrl-facts-check":
                _match = re.search("([\\w-]+)=[\"']([^\"']+)[\"']", data)
                if _match:
                    _matchGroups = _match.groups()
                    if len(_matchGroups) == 2:
                        if _matchGroups[0] == "version":
                            self.factsCheckVersion = _matchGroups[1]
                        elif _matchGroups[0] == "sum-of-fact-md5s":
                            try:
                                expectedMd5 = Md5Sum(_matchGroups[1])
                                if self.factsCheckMd5s != expectedMd5:
                                    modelXbrl.warning("streamingExtensions:xbrlFactsCheckWarning",
                                            _("XBRL facts sum of md5s expected %(expectedMd5)s not matched to actual sum %(actualMd5Sum)s"),
                                            modelObject=modelXbrl, expectedMd5=expectedMd5, actualMd5Sum=self.factsCheckMd5s)
                                else:
                                    modelXbrl.info("info",
                                            _("Successful XBRL facts sum of md5s."),
                                            modelObject=modelXbrl)
                            except ValueError:
                                modelXbrl.error("streamingExtensions:xbrlFactsCheckError",
                                        _("Invalid sum-of-md5s %(sumOfMd5)s"),
                                        modelObject=modelXbrl, sumOfMd5=_matchGroups[1])
        def close(self):
            del modelXbrl.makeelementParentModelObject
            return None

        def factCheckFact(self, fact):
            self.factsCheckMd5s += fact.md5sum
            for _tupleFact in fact.modelTupleFacts:
                self.factCheckFact(_tupleFact)

    _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl, filepath, target=modelLoaderTarget())
    etree.parse(_file, parser=_parser, base_url=filepath)
    logSyntaxErrors(_parser)
    '''
    # replace modelLoaderTarget with iterparse (as it now supports CustomElementClassLookup)
    streamingParserContext = etree.iterparse(_file, events=("start","end"), huge_tree=True)
    from arelle.ModelObjectFactory import setParserElementClassLookup
    modelXbrl.isStreamingMode = True # must be set before setting element class lookup
    (_parser, _parserLookupName, _parserLookupClass) = setParserElementClassLookup(streamingParserContext, modelXbrl)
    foundInstance = False
    beforeInstanceStream = beforeStartStreamingPlugin = True
    numRootFacts = 0
    factsCheckVersion = None
    def factCheckFact(fact):
        modelDocument._factsCheckMd5s += fact.md5sum
        for _tupleFact in fact.modelTupleFacts:
            factCheckFact(_tupleFact)
    for event, mdlObj in streamingParserContext:
        if event == "start":
            if mdlObj.tag == "{http://www.xbrl.org/2003/instance}xbrl":
                modelDocument = ModelDocument(modelXbrl, Type.INSTANCE, mappedUri, filepath, mdlObj.getroottree())
                modelXbrl.modelDocument = modelDocument # needed for incremental validation
                mdlObj.init(modelDocument)
                modelDocument.parser = _parser # needed for XmlUtil addChild's makeelement
                modelDocument.parserLookupName = _parserLookupName
                modelDocument.parserLookupClass = _parserLookupClass
                modelDocument.xmlRootElement = mdlObj
                modelDocument.schemaLocationElements.add(mdlObj)
                modelDocument.documentEncoding = _encoding
                modelDocument._creationSoftwareComment = precedingComment(mdlObj)
                modelDocument._factsCheckMd5s = Md5Sum()
                modelXbrl.info("streamingExtensions:streaming",
                               _("Stream processing this instance."),
                               modelObject = modelDocument)
            elif mdlObj.getparent() is not None:
                mdlObj._init() # requires discovery as part of start elements
                if mdlObj.getparent().tag == "{http://www.xbrl.org/2003/instance}xbrl":
                    if not foundInstance:
                        foundInstance = True
                        pi = precedingProcessingInstruction(mdlObj, "xbrl-facts-check")
                        if pi is not None:
                            factsCheckVersion = pi.attrib.get("version", None)
                elif not foundInstance:
                    break
                ns = mdlObj.qname.namespaceURI
                ln = mdlObj.qname.localName
                if beforeInstanceStream:
                    if ((ns == XbrlConst.link and ln not in ("schemaRef", "linkbaseRef")) or
                        (ns == XbrlConst.xbrli and ln in ("context", "unit")) or
                        (ns not in (XbrlConst.link, XbrlConst.xbrli))):
                        beforeInstanceStream = False
                        if _streamingExtensionsValidate:
                            instValidator.validate(modelXbrl, modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces))
                        else: # need default dimensions
                            ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
                elif not beforeInstanceStream and beforeStartStreamingPlugin:
                    for pluginMethod in pluginClassMethods("Streaming.Start"):
                        pluginMethod(modelXbrl)
                    beforeStartStreamingPlugin = False
        elif event == "end":
            parentMdlObj = mdlObj.getparent()
            ns = mdlObj.namespaceURI
            ln = mdlObj.localName
            if ns == XbrlConst.xbrli:
                if ln == "context":
                    if mdlObj.get("sticky"):
                        del mdlObj.attrib["sticky"]
                        XmlValidate.validate(modelXbrl, mdlObj)
                        modelDocument.contextDiscover(mdlObj)
                    else:
                        if len(contextBuffer) >= contextBufferLimit:
                            # drop before adding as dropped may have same id as added
                            cntx = contextBuffer.pop(0)
                            if _streamingFactsPlugin or _streamingValidateFactsPlugin:
                                contextsToDrop.append(cntx)
                            else:
                                dropContext(modelXbrl, cntx)
                                #>>del parentMdlObj[parentMdlObj.index(cntx)]
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
                    if len(unitBuffer) >= unitBufferLimit:
                        # drop before additing as dropped may have same id as added
                        unit = unitBuffer.pop(0)
                        if _streamingFactsPlugin or _streamingValidateFactsPlugin:
                            unitsToDrop.append(unit)
                        else:
                            dropUnit(modelXbrl, unit)
                            #>>del parentMdlObj[parentMdlObj.index(unit)]
                        unit = None
                    XmlValidate.validate(modelXbrl, mdlObj)
                    modelDocument.unitDiscover(mdlObj)
                    if unitBufferLimit.is_finite():
                        unitBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        instValidator.checkUnits( (mdlObj,) )
                elif ln == "xbrl": # end of document
                    # check remaining batched facts if any
                    if _streamingFactsPlugin or _streamingValidateFactsPlugin:
                        # plugin attempts to process batch of all root facts not yet processed (not just current one)
                        # finish any final batch of facts
                        if len(modelXbrl.facts) > 0:
                            factsToCheck = modelXbrl.facts.copy()
                            # can block facts deletion if required data not yet available, such as numeric unit for DpmDB
                            if _streamingValidateFactsPlugin:
                                for pluginMethod in pluginClassMethods("Streaming.ValidateFacts"):
                                    pluginMethod(instValidator, factsToCheck)
                            if _streamingFactsPlugin:
                                for pluginMethod in pluginClassMethods("Streaming.Facts"):
                                    pluginMethod(modelXbrl, factsToCheck)
                            for fact in factsToCheck:
                                dropFact(modelXbrl, fact, modelXbrl.facts)
                                #>>del parentMdlObj[parentMdlObj.index(fact)]
                            for cntx in contextsToDrop:
                                dropContext(modelXbrl, cntx)
                                #>>del parentMdlObj[parentMdlObj.index(cntx)]
                            for unit in unitsToDrop:
                                dropUnit(modelXbrl, unit)
                                #>>del parentMdlObj[parentMdlObj.index(unit)]
                            for footnoteLink in footnoteLinksToDrop:
                                dropFootnoteLink(modelXbrl, footnoteLink)
                                #>>del parentMdlObj[parentMdlObj.index(footnoteLink)]
                            fact = cntx = unit = footnoteLink = None
                            del contextsToDrop[:]
                            del unitsToDrop[:]
                            del footnoteLinksToDrop[:]
                            del factsToCheck
                    # check remaining footnote refs
                    for footnoteLink in footnoteBuffer:
                        checkFootnoteHrefs(modelXbrl, footnoteLink)
                    pi = childProcessingInstruction(mdlObj, "xbrl-facts-check", reversed=True)
                    if pi is not None: # attrib is in .text, not attrib, no idea why!!!
                        _match = re.search("([\\w-]+)=[\"']([^\"']+)[\"']", pi.text)
                        if _match:
                            _matchGroups = _match.groups()
                            if len(_matchGroups) == 2:
                                if _matchGroups[0] == "sum-of-fact-md5s":
                                    try:
                                        expectedMd5 = Md5Sum(_matchGroups[1])
                                        if modelDocument._factsCheckMd5s != expectedMd5:
                                            modelXbrl.warning("streamingExtensions:xbrlFactsCheckWarning",
                                                    _("XBRL facts sum of md5s expected %(expectedMd5)s not matched to actual sum %(actualMd5Sum)s"),
                                                    modelObject=modelXbrl, expectedMd5=expectedMd5, actualMd5Sum=modelDocument._factsCheckMd5s)
                                        else:
                                            modelXbrl.info("info",
                                                    _("Successful XBRL facts sum of md5s."),
                                                    modelObject=modelXbrl)
                                    except ValueError:
                                        modelXbrl.error("streamingExtensions:xbrlFactsCheckError",
                                                _("Invalid sum-of-md5s %(sumOfMd5)s"),
                                                modelObject=modelXbrl, sumOfMd5=_matchGroups[1])
                    if _streamingValidateFactsPlugin:
                        for pluginMethod in pluginClassMethods("Streaming.ValidateFinish"):
                            pluginMethod(instValidator)
                    if _streamingFactsPlugin:
                        for pluginMethod in pluginClassMethods("Streaming.Finish"):
                            pluginMethod(modelXbrl)
            elif ns == XbrlConst.link:
                if ln in ("schemaRef", "linkbaseRef"):
                    modelDocument.discoverHref(mdlObj, urlRewritePluginClass="ModelDocument.InstanceSchemaRefRewriter")
                elif ln in ("roleRef", "arcroleRef"):
                    modelDocument.linkbaseDiscover((mdlObj,), inInstance=True)
                elif ln == "footnoteLink":
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
                            if _streamingValidateFactsPlugin:
                                footnoteLinksToDrop.append(footnoteLink)
                            else:
                                dropFootnoteLink(modelXbrl, footnoteLink)
                                #>>del parentMdlObj[parentMdlObj.index(footnoteLink)]
                            footnoteLink = None
                    footnoteLinks = None
            elif parentMdlObj.qname == XbrlConst.qnXbrliXbrl and isinstance(mdlObj, ModelFact):
                numRootFacts += 1
                XmlValidate.validate(modelXbrl, mdlObj)
                modelDocument.factDiscover(mdlObj, modelXbrl.facts)
                if factsCheckVersion:
                    factCheckFact(mdlObj)
                if _streamingExtensionsValidate or _streamingFactsPlugin or _streamingValidateFactsPlugin:
                    factsToCheck = (mdlObj,)  # validate current fact by itself
                    if _streamingExtensionsValidate:
                        instValidator.checkFacts(factsToCheck)
                        if modelXbrl.hasXDT:
                            instValidator.checkFactsDimensions(factsToCheck)
                    if _streamingFactsPlugin or _streamingValidateFactsPlugin:
                        # plugin attempts to process batch of all root facts not yet processed (not just current one)
                        # use batches of 1000 facts
                        if len(modelXbrl.facts) > 1000:
                            factsToCheck = modelXbrl.facts.copy()
                            # can block facts deletion if required data not yet available, such as numeric unit for DpmDB
                            if _streamingValidateFactsPlugin:
                                for pluginMethod in pluginClassMethods("Streaming.ValidateFacts"):
                                    pluginMethod(instValidator, factsToCheck)
                            if _streamingFactsPlugin:
                                for pluginMethod in pluginClassMethods("Streaming.Facts"):
                                    pluginMethod(modelXbrl, factsToCheck)
                            for fact in factsToCheck:
                                dropFact(modelXbrl, fact, modelXbrl.facts)
                                #>>del parentMdlObj[parentMdlObj.index(fact)]
                            for cntx in contextsToDrop:
                                dropContext(modelXbrl, cntx)
                                #>>del parentMdlObj[parentMdlObj.index(cntx)]
                            for unit in unitsToDrop:
                                dropUnit(modelXbrl, unit)
                                #>>del parentMdlObj[parentMdlObj.index(unit)]
                            for footnoteLink in footnoteLinksToDrop:
                                dropFootnoteLink(modelXbrl, footnoteLink)
                                #>>del parentMdlObj[parentMdlObj.index(footnoteLink)]
                            fact = cntx = unit = footnoteLink = None
                            del contextsToDrop[:]
                            del unitsToDrop[:]
                            del footnoteLinksToDrop[:]
                            del factsToCheck # dereference fact or batch of facts
                    else:
                        dropFact(modelXbrl, mdlObj, modelXbrl.facts) # single fact has been processed
                        #>>del parentMdlObj[parentMdlObj.index(mdlObj)]
                if numRootFacts % 1000 == 0:
                    pass
                    #modelXbrl.profileActivity("... streaming fact {0} of {1} {2:.2f}%".format(self.numRootFacts, instInfoNumRootFacts,
                    #                                                                          100.0 * self.numRootFacts / instInfoNumRootFacts),
                    #                          minTimeToShow=20.0)
                    #gc.collect()
                    #sys.stdout.write ("\rAt fact {} of {} mem {}".format(numRootFacts, instInfoNumRootFacts, modelXbrl.modelManager.cntlr.memoryUsed))
    if mdlObj is not None:
        mdlObj.clear()
    del _parser, _parserLookupName, _parserLookupClass

    if _streamingExtensionsValidate and validator is not None:
        _file.close()
        del instValidator
        validator.close()
        # track that modelXbrl has been validated by this streaming extension
        modelXbrl._streamingExtensionValidated = True

    modelXbrl.profileStat(_("streaming complete"), time.time() - startedAt)
    return modelXbrl.modelDocument

def checkFootnoteHrefs(modelXbrl, footnoteLink):
    for locElt in footnoteLink.iterchildren(tag="{http://www.xbrl.org/2003/linkbase}loc"):
        for hrefElt, _doc, _id in footnoteLink.modelDocument.hrefObjects:
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
    if fact.id:
        fact.modelDocument.idObjects.pop(fact.id, None)
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
    if mdlObj.id:
        mdlObj.modelDocument.idObjects.pop(mdlObj.id, None)
    mdlObj.clear()

'''
def streamingOptionsExtender(parser):
    parser.add_option("--check-streaming",
                      action="store_true",
                      dest="check_streaming",
                      help=_('Check streamability of instance document."'))
'''

def streamingExtensionsSetup(cntlr, options, *args, **kwargs):
    global _streamingExtensionsCheck, _streamingExtensionsValidate
    # streaming only checked in CmdLine/web server mode if requested
    # _streamingExtensionsCheck = getattr(options, 'check_streaming', False)
    _streamingExtensionsValidate = options.validate

def streamingExtensionsIsValidated(modelXbrl, *args, **kwargs):
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
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    # take out for now: 'CntlrCmdLine.Options': streamingOptionsExtender,
    'CntlrCmdLine.Utility.Run': streamingExtensionsSetup,
    'ModelDocument.PullLoader': streamingExtensionsLoader,
    'ModelDocument.IsValidated': streamingExtensionsIsValidated,
}
