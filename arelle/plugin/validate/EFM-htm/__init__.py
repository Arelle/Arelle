'''
See COPYRIGHT.md for copyright information.
'''
import os, io
from lxml.etree import HTMLParser, parse, DTD, _ElementTree, _Comment, _ProcessingInstruction
from regex import compile as re_compile, match as re_match, DOTALL as re_DOTALL
from arelle import ValidateFilingText
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.UrlUtil import isHttpUrl, scheme
from arelle.Version import authorLabel, copyrightLabel
from .Const import edgarAdditionalTags, disallowedElements, disallowedElementAttrs, recognizedElements

def dislosureSystemTypes(disclosureSystem, *args, **kwargs):
    # return ((disclosure system name, variable name), ...)
    return (("EFM", "EFMHTMplugin"),)

def disclosureSystemConfigURL(disclosureSystem, *args, **kwargs):
    return os.path.join(os.path.dirname(__file__), "config.xml")

def validateXbrlStart(val, parameters=None, *args, **kwargs):
    val.validateEFMHTMplugin = val.validateDisclosureSystem and getattr(val.disclosureSystem, "EFMHTMplugin", False)
    if not (val.validateEFMHTMplugin):
        return

def validateXbrlFinally(val, *args, **kwargs):
    if not (val.validateEFMHTMplugin):
        return

    modelXbrl = val.modelXbrl
    allowedExternalHrefPattern = modelXbrl.modelManager.disclosureSystem.allowedExternalHrefPattern
    #efmHtmDTD = None
    #with open(os.path.join(os.path.dirname(__file__), "resources", "efm-htm.dtd")) as fh:
    #    efmHtmDTD = DTD(fh)
    #if efmHtmDTD and not efmHtmDTD.validate( modelXbrl.modelDocument.xmlRootElement ):
    #    for e in efmHtmDTD.error_log.filter_from_errors():
    #        if "declared in the external subset contains white spaces nodes" not in e.message:
    #            modelXbrl.error("html.syntax",
    #                _("HTML error %(error)s"),
    #                error=e.message)
    numHtmlTags = 0
    inBody = False
    for elt in modelXbrl.modelDocument.xmlRootElement.iter():
        if isinstance(elt, (_ElementTree, _Comment, _ProcessingInstruction)):
            continue # comment or other non-parsed element
        eltTag = elt.tag.lower()
        for attrTag, attrValue in elt.items():
            if ((attrTag == "href" and eltTag == "a") or
                (attrTag == "src" and eltTag == "img")):
                if "javascript:" in attrValue:
                    modelXbrl.error("EFM.5.02.02.10.activeContent",
                        _("Element has javascript in '%(attribute)s' for <%(element)s>"),
                        modelObject=elt, attribute=attrTag, element=eltTag)
                elif eltTag == "a" and (not allowedExternalHrefPattern or allowedExternalHrefPattern.match(attrValue)):
                    pass
                elif scheme(attrValue) in ("http", "https", "ftp", "mailto"):
                    modelXbrl.error("EFM.6.05.16.externalReference",
                        _("Element has an invalid external reference in '%(attribute)s' for <%(element)s>"),
                        modelObject=elt, attribute=attrTag, element=eltTag)
                if attrTag == "src":
                    if scheme(attrValue)  == "data":
                        modelXbrl.error("EFM.5.02.02.10.graphicDataUrl",
                            _("Element references a graphics data URL which isn't accepted '%(attribute)s' for <%(element)s>"),
                            modelObject=elt, attribute=attrValue[:32], element=eltTag)
                    elif attrValue.lower()[-4:] not in ('.jpg', '.gif'):
                        modelXbrl.error("EFM.5.02.02.10.graphicFileType",
                            _("Element references a graphics file which isn't .gif or .jpg '%(attribute)s' for <%(element)s>"),
                            modelObject=elt, attribute=attrValue, element=eltTag)
            elif attrTag in disallowedElementAttrs.get(eltTag,()) or attrTag in disallowedElementAttrs["*"]:
                modelXbrl.error("EFM.5.02.02.05.disallowedAttribute",
                    _("Element has disallowed attribute '%(attribute)s' for <%(element)s>"),
                    modelObject=elt, attribute=attrTag, element=eltTag)
            elif attrTag.startswith("xmlns"):
                modelXbrl.error("EFM.5.02.02.05.xmlns",
                    _("Element has disallowed xmlns declaration '%(attribute)s' for <%(element)s>"),
                    modelObject=elt, attribute=attrTag, element=eltTag)
        if eltTag == "html":
            numHtmlTags += 1
            if numHtmlTags > 1:
                modelXbrl.error("EFM.5.02.02.02.htmlTags",
                    _("Document can only have one html tag"),
                    modelObject=elt)
        elif eltTag in ("head", "meta", "isindex", "title"):
            pass # these are allowed
        elif eltTag == "body":
            inBody = True
        elif eltTag == "table":
            if any(a is not None for a in elt.iterancestors("table")):
                modelXbrl.error("EFM.5.02.02.10.nestedTable",
                    _("Element is a disallowed nested <table>."),
                    modelObject=elt)
        elif eltTag in disallowedElements:
            modelXbrl.error("EFM.5.02.02.04.disallowedElement",
                _("Element is disallowed: <%(element)s>"),
                modelObject=elt, element=eltTag)
        elif eltTag not in recognizedElements:
            modelXbrl.error("EFM.5.02.02.03.unrecognizedElement",
                _("Element is not recognized: <%(element)s>"),
                modelObject=elt, element=eltTag)
        elif not inBody:
            modelXbrl.error("EFM.5.02.02.03.bodyTags",
                _("Element is not in a body: <%(element)s>"),
                modelObject=elt, element=eltTag)

def filingStart(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None, *args, **kwargs):
    modelManager = cntlr.modelManager
    if modelManager.validateDisclosureSystem and (getattr(modelManager.disclosureSystem, "EFMHTMplugin", False)):
        pass

def xbrlLoaded(cntlr, options, modelXbrl, entryPoint, *args, **kwargs):
    # cntlr.addToLog("TRACE EFM xbrl loaded")
    modelManager = cntlr.modelManager


def xbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # cntlr.addToLog("TRACE EFM xbrl run")
    modelManager = cntlr.modelManager

def filingValidate(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None, *args, **kwargs):
    # cntlr.addToLog("TRACE EFM xbrl validate")
    modelManager = cntlr.modelManager

def filingEnd(cntlr, options, filesource, entrypointFiles, sourceZipStream=None, responseZipStream=None, *args, **kwargs):
    #cntlr.addToLog("TRACE EFM filing end")
    modelManager = cntlr.modelManager

def isLoadableHtml(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    global lastFilePath, lastFilePathIsHTML
    lastFilePath = filepath
    lastFilePathIsHTML = False
    _ext = os.path.splitext(filepath)[1]
    if _ext.lower() in (".htm", ".html"):
        try:
            file, _encoding = modelXbrl.fileSource.file(filepath, stripDeclaration=False)
            _fileStart = file.read(4096)
            file.close()
            if _fileStart and re_match(r"(?!.*<[?]xml\s).*<html.*>", _fileStart):
                lastFilePathIsHTML = True
        except Exception as err:
            return False
    return lastFilePathIsHTML

def htmlLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if filepath != lastFilePath or not lastFilePathIsHTML:
        return None # not an HTML file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading HTML file: {0}").format(os.path.basename(filepath)))
    # parse html
    try:
        if (modelXbrl.modelManager.validateDisclosureSystem and
            modelXbrl.modelManager.disclosureSystem.validateFileText):
            file, _encoding = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            file, _encoding = modelXbrl.fileSource.file(filepath, stripDeclaration=False)
        _parser = HTMLParser()
        htmlTree = parse(file, _parser, base_url=filepath)
        for error in _parser.error_log:
            if not (error.type_name == "HTML_UNKNOWN_TAG" and
                    error.message.startswith("Tag ") and
                    error.message.lower()[4:].partition(" ")[0] in edgarAdditionalTags):
                modelXbrl.error("html:syntax",
                        _("%(error)s, %(fileName)s, line %(line)s, column %(column)s"),
                        fileName=os.path.basename(mappedUri),
                        error=error.message, line=error.line, column=error.column)
        file.close()
    except Exception as err:
        modelXbrl.error(type(err).__name__,
                _("Unrecoverable error: %(error)s, %(fileName)s"),
                fileName=os.path.basename(mappedUri),
                error=str(err), exc_info=True)
        return None
    if modelXbrl: # pull loader implementation
        modelXbrl.blockDpmDBrecursion = True
        modelXbrl.modelDocument = doc = createModelDocument(
              modelXbrl,
              Type.HTML,
              filepath,
              isEntry=True,
              documentEncoding="utf-8",
              base=filepath)
    else: # API implementation
        modelXbrl = ModelXbrl.create(
            cntlr.modelManager,
            Type.HTML,
            filepath,
            isEntry=True,
            base=filepath)
        doc = modelXbrl.modelDocument
    doc.xmlRootElement = htmlTree.getroot()

    if doc is None:
        return None # not an HTML file
    modelXbrl.loadedFromHTML = True
    return doc


__pluginInfo__ = {
    # Do not use _( ) in pluginInfo itself (it is applied later, after loading
    'name': 'Validate EFM non-XBRL HTM',
    'version': '1.20.3', # SEC EDGAR release 20.3
    'description': '''EFM non-XBRL HTM Validation.''',
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'ModelDocument.IsPullLoadable': isLoadableHtml,
    'ModelDocument.PullLoader': htmlLoader,
    'DisclosureSystem.Types': dislosureSystemTypes,
    'DisclosureSystem.ConfigURL': disclosureSystemConfigURL,
    'Validate.XBRL.Start': validateXbrlStart,
    'Validate.XBRL.Finally': validateXbrlFinally,
    'CntlrCmdLine.Filing.Start': filingStart,
    'CntlrCmdLine.Xbrl.Loaded': xbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': xbrlRun,
    'CntlrCmdLine.Filing.Validate': filingValidate,
    'CntlrCmdLine.Filing.End': filingEnd,
}
