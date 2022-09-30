'''
StreamingExtensions is a plug-in to both GUI menu and command line/web service
that provides an alternative approach to big instance documents without building a DOM, to save
memory footprint.  lxml iterparse is used to parse the big instance.  ModelObjects are specialized by features
for efficiency and to avoid dependency on an underlying DOM.

(Note that this module is based on iterparse, the module under the installation/plugs is much faster.)

See COPYRIGHT.md for copyright information.
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
from arelle.Version import authorLabel, copyrightLabel

_streamingExtensionsValidate = False
_streamingExtensionsCheck = False

def precedingProcessingInstruction(elt, target):
    pi = elt.getprevious()
    while pi is not None:
        if isinstance(pi, etree._ProcessingInstruction) and pi.target == target:
            return pi
        pi = pi.getprevious()
    return None

def streamingExtensionsLoader(modelXbrl, mappedUri, filepath):
    # check if big instance and has header with an initial incomplete tree walk (just 2 elements
    def logSyntaxErrors(parsercontext):
        for error in parsercontext.error_log:
            modelXbrl.error("xmlSchema:syntax",
                    _("%(error)s, %(fileName)s, line %(line)s, column %(column)s, %(sourceAction)s source element"),
                    modelObject=modelDocument, fileName=os.path.basename(filepath),
                    error=error.message, line=error.line, column=error.column, sourceAction="streaming")
    #### note: written for iterparse of lxml prior to version 3.3, otherwise rewrite to use XmlPullParser ###
    #### note: iterparse wants a binary file, but file is text mode
    _file, = modelXbrl.fileSource.file(filepath, binary=True)
    startedAt = time.time()
    modelXbrl.profileActivity()
    parsercontext = etree.iterparse(_file, events=("start","end"), huge_tree=True)
    foundInstance = False
    foundErrors = False
    streamingAspects = None
    numRootFacts1 = 0
    numElts = 0
    elt = None
    for event, elt in parsercontext:
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
                    if not elt.tag.startswith("{http://www.xbrl.org/"):
                        numRootFacts1 += 1
                        if numRootFacts1 % 1000 == 0:
                            modelXbrl.profileActivity("... streaming tree check", minTimeToShow=20.0)
                elif not foundInstance:
                    break
            elif elt.tag == "{http://www.xbrl.org/2003/instance}xbrl" and precedingProcessingInstruction(elt, "xbrl-streamable-instance") is not None:
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
        del elt, parsercontext
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
    if parsercontext.error_log:
        foundErrors = True
    logSyntaxErrors(parsercontext)

    if foundErrors:
        _file.close()
        return None
    parsercontext = etree.iterparse(_file, events=("start","end"), huge_tree=True)
    _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl,filepath)
    eltMdlObjs = {}
    beforeInstanceStream = True
    validator = None
    contextBuffer = []
    unitBuffer = []
    footnoteBuffer = []
    factBuffer = []
    numFacts = numRootFacts2 = 1
    for event, elt in parsercontext:
        if event == "start":
            mdlObj = _parser.makeelement(elt.tag, attrib=elt.attrib, nsmap=elt.nsmap)
            mdlObj.sourceline = elt.sourceline
            eltMdlObjs[elt] = mdlObj
            if elt.getparent() is None:
                modelDocument = ModelDocument(modelXbrl, Type.INSTANCE, mappedUri, filepath, etree.ElementTree(mdlObj))
                modelDocument.xmlRootElement = mdlObj
                modelXbrl.modelDocument = modelDocument # needed for incremental validation
                mdlObj.init(modelDocument)
                modelXbrl.info("streamingExtensions:streaming",
                               _("Stream processing this instance."),
                               modelObject = modelDocument)
            else:
                eltMdlObjs[elt.getparent()].append(mdlObj)
                mdlObj._init()
                ns = mdlObj.namespaceURI
                ln = mdlObj.localName
                if (beforeInstanceStream and (
                    (ns == XbrlConst.link and ln not in ("schemaRef", "linkbaseRef")) or
                    (ns == XbrlConst.xbrli and ln in ("context", "unit")) or
                    (ns not in (XbrlConst.link, XbrlConst.xbrli)))):
                    beforeInstanceStream = False
                    if _streamingExtensionsValidate:
                        validator = Validate(modelXbrl)
                        validator.instValidator.validate(modelXbrl, modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces))
                    else: # need default dimensions
                        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl)
            mdlObj = None # deref

        elif event == "end":
            mdlObj = eltMdlObjs.pop(elt)
            if elt.text: # text available after child nodes processed
                mdlObj.text = elt.text
            ns = mdlObj.namespaceURI
            ln = mdlObj.localName
            parentMdlObj = mdlObj.getparent()
            if ns == XbrlConst.xbrli:
                if ln == "context":
                    if mdlObj.get("sticky"):
                        del mdlObj.attrib["sticky"]
                        modelDocument.contextDiscover(mdlObj)
                    else:
                        if _streamingExtensionsValidate and len(contextBuffer) >= contextBufferLimit:
                            # drop before adding as dropped may have same id as added
                            cntx = contextBuffer.pop(0)
                            dropContext(modelXbrl, cntx)
                            del parentMdlObj[parentMdlObj.index(cntx)]
                            cntx = None
                        modelDocument.contextDiscover(mdlObj)
                        if contextBufferLimit.is_finite():
                            contextBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        contextsToCheck = (mdlObj,)
                        validator.instValidator.checkContexts(contextsToCheck)
                        if modelXbrl.hasXDT:
                            validator.instValidator.checkContextsDimensions(contextsToCheck)
                        del contextsToCheck # dereference
                elif ln == "unit":
                    if _streamingExtensionsValidate and len(unitBuffer) >= unitBufferLimit:
                        # drop before additing as dropped may have same id as added
                        unit = unitBuffer.pop(0)
                        dropUnit(modelXbrl, unit)
                        del parentMdlObj[parentMdlObj.index(unit)]
                        unit = None
                    modelDocument.unitDiscover(mdlObj)
                    if unitBufferLimit.is_finite():
                        unitBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        validator.instValidator.checkUnits( (mdlObj,) )
                elif ln == "xbrl": # end of document
                    # check remaining footnote refs
                    for footnoteLink in footnoteBuffer:
                        checkFootnoteHrefs(modelXbrl, footnoteLink)
                elt.clear()
            elif ns == XbrlConst.link:
                if ln in ("schemaRef", "linkbaseRef"):
                    modelDocument.discoverHref(mdlObj)
                elif ln in ("roleRef", "arcroleRef"):
                    modelDocument.linkbaseDiscover((mdlObj,), inInstance=True)
                elif ln == "footnoteLink":
                    footnoteLinks = (mdlObj,)
                    modelDocument.linkbaseDiscover(footnoteLinks, inInstance=True)
                    if footnoteBufferLimit.is_finite():
                        footnoteBuffer.append(mdlObj)
                    if _streamingExtensionsValidate:
                        validator.instValidator.checkLinks(footnoteLinks)
                        if len(footnoteBuffer) > footnoteBufferLimit:
                            # check that hrefObjects for locators were all satisfied
                                # drop before addition as dropped may have same id as added
                            footnoteLink = footnoteBuffer.pop(0)
                            checkFootnoteHrefs(modelXbrl, footnoteLink)
                            dropFootnoteLink(modelXbrl, footnoteLink)
                            del parentMdlObj[parentMdlObj.index(footnoteLink)]
                            footnoteLink = None
                    footnoteLinks = None
                elt.clear()
            elif parentMdlObj.qname == XbrlConst.qnXbrliXbrl:
                numRootFacts2 += 1
                modelDocument.factDiscover(mdlObj, modelXbrl.facts)
                XmlValidate.validate(modelXbrl, mdlObj)
                if _streamingExtensionsValidate:
                    factsToCheck = (mdlObj,)
                    validator.instValidator.checkFacts(factsToCheck)
                    if modelXbrl.hasXDT:
                        validator.instValidator.checkFactsDimensions(factsToCheck)
                    del factsToCheck
                    dropFact(modelXbrl, mdlObj, modelXbrl.facts)
                    del parentMdlObj[parentMdlObj.index(mdlObj)]
                if numRootFacts2 % 1000 == 0:
                    modelXbrl.profileActivity("... streaming fact {0} of {1} {2:.2f}%".format(numRootFacts2, numRootFacts1, 100.0 * numRootFacts2 / numRootFacts1),
                                              minTimeToShow=20.0)
                # get rid of root element from iterparse's tree
                elt.clear()
                while elt.getprevious() is not None:  # cleans up any prior siblings
                    del elt.getparent()[0]
            mdlObj = None # deref
    logSyntaxErrors(parsercontext)
    del parsercontext
    if validator is not None:
        validator.close()
    _file.close()
    modelXbrl.profileStat(_("streaming complete"), time.time() - startedAt)
    return modelDocument

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

def streamingOptionsExtender(parser):
    parser.add_option("--check-streaming",
                      action="store_true",
                      dest="check_streaming",
                      help=_('Check streamability of instance document."'))

def streamingExtensionsSetup(self, options, **kwargs):
    global _streamingExtensionsCheck, _streamingExtensionsValidate
    _streamingExtensionsCheck = getattr(options, 'check_streaming', False)
    _streamingExtensionsValidate = options.validate
    if options.validate:
        options.validate = False # prevent cmdLine calling validation

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
    'CntlrCmdLine.Options': streamingOptionsExtender,
    'CntlrCmdLine.Utility.Run': streamingExtensionsSetup,
    'ModelDocument.PullLoader': streamingExtensionsLoader,
}
