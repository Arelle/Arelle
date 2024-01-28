'''
See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import os, io
from collections import defaultdict
from typing import Any
from lxml import etree
from xml.sax import SAXParseException
from arelle import (PackageManager, XbrlConst, XmlUtil, UrlUtil, ValidateFilingText,
                    XhtmlValidate, XmlValidateSchema, FunctionIxt)
from arelle.FileSource import FileSource
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.ModelDtsObject import ModelLink
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObjectFactory import parser
from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype, ArcPrototype, DocumentPrototype, PrototypeElementTree
from arelle.PluginManager import pluginClassMethods
from arelle.PythonUtil import OrderedDefaultDict, normalizeSpace
from arelle.XhtmlValidate import ixMsgCode
from arelle.XmlValidateConst import VALID
from arelle.XmlValidate import validate as xmlValidate, lxmlSchemaValidate
from arelle.ModelTestcaseObject import ModelTestcaseVariation

creationSoftwareNames = None

def load(modelXbrl, uri, base=None, referringElement=None, isEntry=False, isDiscovered=False, isIncluded=None, isSupplemental=False, namespace=None, reloadCache=False, **kwargs) -> ModelDocument | None:
    """Returns a new modelDocument, performing DTS discovery for instance, inline XBRL, schema,
    linkbase, and versioning report entry urls.

    :param uri: Identification of file to load by string filename or by a FileSource object with a selected content file.
    :type uri: str or FileSource
    :param referringElement: Source element causing discovery or loading of this document, such as an import or xlink:href
    :type referringElement: ModelObject
    :param isEntry: True for an entry document
    :type isEntry: bool
    :param isDiscovered: True if this document is discovered by XBRL rules, otherwise False (such as when schemaLocation and xmlns were the cause of loading the schema)
    :type isDiscovered: bool
    :param isIncluded: True if this document is the target of an xs:include
    :type isIncluded: bool
    :param isSupplemental: True if this is processed for link relationships even if neither isEntry or isDiscovered, such as when adding additional language or documentation linkbases
    :type isIncluded: bool
    :param namespace: The schema namespace of this document, if known and applicable
    :type isSupplemental: True if this document is supplemental (not discovered or in DTS but adds labels or instance facts)
    :type namespace: str
    :param reloadCache: True if desired to reload the web cache for any web-referenced files.
    :type reloadCache: bool
    :param checkModifiedTime: True if desired to check modifed time of web cached entry point (ahead of usual time stamp checks).
    :type checkModifiedTime: bool
    """

    if referringElement is None: # used for error messages
        referringElement = modelXbrl
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
    modelDocument = modelXbrl.urlDocs.get(normalizedUri)
    if modelDocument:
        return modelDocument
    elif modelXbrl.urlUnloadableDocs.get(normalizedUri):  # only return None if in this list and marked True (really not loadable)
        return None
    elif not normalizedUri:
        modelXbrl.error("FileNotLoadable",
                _("File name absent, document can not be loaded."),
                modelObject=referringElement, fileName=normalizedUri)
        return None

    if isEntry:
        modelXbrl.entryLoadingUrl = normalizedUri   # for error logging during loading
        modelXbrl.uri = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    if modelXbrl.modelManager.validateDisclosureSystem and \
       not normalizedUri.startswith(modelXbrl.uriDir) and \
       not modelXbrl.modelManager.disclosureSystem.hrefValid(normalizedUri):
        blocked = modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences
        if normalizedUri not in modelXbrl.urlUnloadableDocs:
            # HMRC note, HMRC.blockedFile should be in this list if hmrc-taxonomies.xml is maintained an dup to date
            modelXbrl.error(("EFM.6.22.00", "GFM.1.1.3", "SBR.NL.2.1.0.06" if normalizedUri.startswith("http") else "SBR.NL.2.2.0.17"),
                    _("Prohibited file for filings %(blockedIndicator)s: %(url)s"),
                    edgarCode="cp-2200-Prohibited-Href-Or-Schema-Location",
                    modelObject=referringElement, url=normalizedUri,
                    blockedIndicator=_(" blocked") if blocked else "",
                    messageCodes=("EFM.6.22.00", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
            #modelXbrl.debug("EFM.6.22.02", "traceback %(traceback)s",
            #                modeObject=referringElement, traceback=traceback.format_stack())
            modelXbrl.urlUnloadableDocs[normalizedUri] = blocked
        if blocked:
            return None

    if modelXbrl.modelManager.skipLoading and modelXbrl.modelManager.skipLoading.match(normalizedUri):
        return None

    if modelXbrl.fileSource.isMappedUrl(normalizedUri):
        mappedUri = modelXbrl.fileSource.mappedUrl(normalizedUri)
    elif PackageManager.isMappedUrl(normalizedUri):
        mappedUri = PackageManager.mappedUrl(normalizedUri)
    else:
        mappedUri = modelXbrl.modelManager.disclosureSystem.mappedUrl(normalizedUri)

    if isEntry:
        modelXbrl.entryLoadingUrl = mappedUri   # for error loggiong during loading

    # don't try reloading if not loadable

    if modelXbrl.fileSource.isInArchive(mappedUri):
        filepath = mappedUri
    else:
        filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUri, reload=reloadCache, checkModifiedTime=kwargs.get("checkModifiedTime",False))
        if filepath:
            uri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(filepath)
    if filepath is None: # error such as HTTPerror is already logged
        if modelXbrl.modelManager.abortOnMajorError and (isEntry or isDiscovered):
            modelXbrl.error("FileNotLoadable",
                    _("File can not be loaded: %(fileName)s \nLoading terminated."),
                    modelObject=referringElement, fileName=mappedUri)
            raise LoadingException()
        if normalizedUri not in modelXbrl.urlUnloadableDocs:
            if "referringElementUrl" in kwargs:
                modelXbrl.error("FileNotLoadable",
                        _("File can not be loaded: %(fileName)s, referenced from %(referencingFileName)s"),
                        modelObject=referringElement, fileName=normalizedUri, referencingFileName=kwargs["referringElementUrl"])
            else:
                modelXbrl.error("FileNotLoadable",
                        _("File can not be loaded: %(fileName)s"),
                        modelObject=referringElement, fileName=normalizedUri)
            modelXbrl.urlUnloadableDocs[normalizedUri] = True # always blocked if not loadable on this error
        return None

    isPullLoadable = any(pluginMethod(modelXbrl, mappedUri, normalizedUri, filepath, isEntry=isEntry, namespace=namespace, **kwargs)
                         for pluginMethod in pluginClassMethods("ModelDocument.IsPullLoadable"))

    if not isPullLoadable and os.path.splitext(filepath)[1] in (".xlsx", ".xls", ".csv", ".json"):
        modelXbrl.error("FileNotLoadable",
                _("File can not be loaded, requires loadFromExcel or loadFromOIM plug-in: %(fileName)s"),
                modelObject=referringElement, fileName=normalizedUri)
        return None


    # load XML and determine type of model document
    modelXbrl.modelManager.showStatus(_("parsing {0}").format(uri))
    file = None
    try:
        for pluginMethod in pluginClassMethods("ModelDocument.PullLoader"):
            # assumes not possible to check file in string format or not all available at once
            modelDocument = pluginMethod(modelXbrl, normalizedUri, filepath, isEntry=isEntry, namespace=namespace, **kwargs)
            if isinstance(modelDocument, Exception):
                return None
            if modelDocument is not None:
                return modelDocument
        if (modelXbrl.modelManager.validateDisclosureSystem and (
            (isEntry and modelXbrl.modelManager.disclosureSystem.validateEntryText) or
            (modelXbrl.modelManager.disclosureSystem.validateFileText and
             not normalizedUri in modelXbrl.modelManager.disclosureSystem.standardTaxonomiesDict))):
            file, _encoding = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            file, _encoding = modelXbrl.fileSource.file(filepath, stripDeclaration=True)
        xmlDocument = None
        isPluginParserDocument = False
        for pluginMethod in pluginClassMethods("ModelDocument.CustomLoader"):
            modelDocument = pluginMethod(modelXbrl, file, mappedUri, filepath)
            if modelDocument is not None:
                file.close()
                return modelDocument
        _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl,normalizedUri)
        xmlDocument = etree.parse(file,parser=_parser,base_url=filepath)
        for error in _parser.error_log:
            modelXbrl.error("xmlSchema:syntax",
                    _("%(error)s, %(fileName)s, line %(line)s, column %(column)s"),
                    modelObject=(referringElement, os.path.basename(uri)),
                    fileName=os.path.basename(uri),
                    error=error.message, line=error.line, column=error.column)
        file.close()
    except (EnvironmentError, KeyError, UnicodeDecodeError) as err:  # missing zip file raises KeyError
        if file:
            file.close()
        # retry in case of well known schema locations
        if not isIncluded and namespace and namespace in XbrlConst.standardNamespaceSchemaLocations and uri != XbrlConst.standardNamespaceSchemaLocations[namespace]:
            return load(modelXbrl, XbrlConst.standardNamespaceSchemaLocations[namespace],
                        base, referringElement, isEntry, isDiscovered, isIncluded, namespace, reloadCache)
        if modelXbrl.modelManager.abortOnMajorError and (isEntry or isDiscovered):
            modelXbrl.error("IOerror",
                _("%(fileName)s: file error: %(error)s \nLoading terminated."),
                modelObject=referringElement, fileName=os.path.basename(uri), error=str(err))
            raise LoadingException()
        #import traceback
        #print("traceback {}".format(traceback.format_tb(sys.exc_info()[2])))
        modelXbrl.error("IOerror",
                _("%(fileName)s: file error: %(error)s"),
                modelObject=referringElement, fileName=os.path.basename(uri), error=str(err))
        modelXbrl.urlUnloadableDocs[normalizedUri] = True  # not loadable due to IO issue
        return None
    except (etree.LxmlError, etree.XMLSyntaxError,
            SAXParseException,
            ValueError) as err:  # ValueError raised on bad format of qnames, xmlns'es, or parameters
        if file:
            file.close()
        if not isEntry and str(err) == "Start tag expected, '<' not found, line 1, column 1":
            return ModelDocument(modelXbrl, Type.UnknownNonXML, normalizedUri, filepath, None)
        else:
            modelXbrl.error("xmlSchema:syntax",
                    _("Unrecoverable error: %(error)s, %(fileName)s"),
                    modelObject=(referringElement, os.path.basename(uri)), fileName=os.path.basename(uri),
                    error=str(err), exc_info=True)
            modelXbrl.urlUnloadableDocs[normalizedUri] = True  # not loadable due to parser issues
            return None
    except XmlUtil.XmlDeclarationLocationException as err:
        modelXbrl.error("xmlSyntax:xmlDeclarationError",
                _("XML file syntax error: %(error)s, %(fileName)s"),
                modelObject=(referringElement, os.path.basename(uri)), fileName=os.path.basename(uri), error=str(err))
        return None
    except Exception as err:
        if len(err.args) >= 2 and err.args[0] == "rpe:unsupportedFileExtension":
            modelXbrl.error(err.args[0],
                _("Unsupported file extension for zip contents: %(fileName)s"),
                modelObject=referringElement, fileName=os.path.basename(uri))
        else:
            modelXbrl.error(type(err).__name__,
                    _("Unrecoverable error: %(error)s, %(fileName)s"),
                    modelObject=referringElement, fileName=os.path.basename(uri),
                    error=str(err), exc_info=True)
        modelXbrl.urlUnloadableDocs[normalizedUri] = True  # not loadable due to exception issue
        return None

    # identify document
    #modelXbrl.modelManager.addToLog("discovery: {0}".format(
    #            os.path.basename(uri)))
    modelXbrl.modelManager.showStatus(_("loading {0}").format(uri))
    modelDocument = None

    rootNode = xmlDocument.getroot()
    if rootNode is not None:
        ln = rootNode.localName
        ns = rootNode.namespaceURI

        # type classification
        _type = None
        _class = ModelDocument
        if ns == XbrlConst.xsd and ln == "schema":
            _type = Type.SCHEMA
            if not isEntry and not isIncluded:
                # check if already loaded under a different url
                targetNamespace = rootNode.get("targetNamespace")
                if targetNamespace and modelXbrl.namespaceDocs.get(targetNamespace):
                    otherModelDoc = modelXbrl.namespaceDocs[targetNamespace][0]
                    if otherModelDoc.basename == os.path.basename(uri):
                        if os.path.normpath(otherModelDoc.uri) != os.path.normpath(uri): # tolerate \ vs / or ../ differences
                            modelXbrl.urlDocs[uri] = otherModelDoc
                            modelXbrl.warning("info:duplicatedSchema",
                                    _("Schema file with same targetNamespace %(targetNamespace)s loaded from %(fileName)s and %(otherFileName)s"),
                                    modelObject=referringElement, targetNamespace=targetNamespace, fileName=uri, otherFileName=otherModelDoc.uri)
                        return otherModelDoc
        elif (isEntry or isDiscovered or isSupplemental) and ns == XbrlConst.link:
            if ln == "linkbase":
                _type = Type.LINKBASE
            elif ln == "xbrl":
                _type = Type.INSTANCE
            else:
                _type = Type.UnknownXML
        elif isEntry and ns == XbrlConst.xbrli:
            if ln == "xbrl":
                _type = Type.INSTANCE
            else:
                _type = Type.UnknownXML
        elif ns == XbrlConst.xhtml and \
             (ln == "html" or ln == "xhtml"):
            _type = Type.UnknownXML
            if (# not a valid test: XbrlConst.ixbrlAll & set(rootNode.nsmap.values()) or
                any(e is not None for e in rootNode.iter(*XbrlConst.ixbrlTags))):
                _type = Type.INLINEXBRL
        elif ln == "report" and ns == XbrlConst.ver:
            _type = Type.VERSIONINGREPORT
            from arelle.ModelVersReport import ModelVersReport
            _class = ModelVersReport
        elif ln in ("testcases", "documentation", "testSuite", "registries"):
            _type = Type.TESTCASESINDEX
        elif ln in ("testcase", "testSet"):
            _type = Type.TESTCASE
        elif ln == "registry" and ns == XbrlConst.registry:
            _type = Type.REGISTRY
        elif ln == "test-suite" and ns == "http://www.w3.org/2005/02/query-test-XQTSCatalog":
            _type = Type.XPATHTESTSUITE
        elif ln == "rss":
            _type = Type.RSSFEED
            from arelle.ModelRssObject import ModelRssObject
            _class = ModelRssObject
        elif ln == "ptvl":
            _type = Type.ARCSINFOSET
        elif ln == "facts":
            _type = Type.FACTDIMSINFOSET
        elif (# not a valid test: XbrlConst.ixbrlAll & set(rootNode.nsmap.values()) or
              any(e is not None for e in rootNode.iter(*XbrlConst.ixbrlTags))):
            # any xml document can be an inline document, only html and xhtml are found above
            _type = Type.INLINEXBRL
        else:
            for pluginMethod in pluginClassMethods("ModelDocument.IdentifyType"):
                _identifiedType = pluginMethod(modelXbrl, rootNode, filepath)
                if _identifiedType is not None:
                    _type, _class, rootNode = _identifiedType
                    break
            if _type is None:
                _type = Type.UnknownXML

                nestedInline = None
                for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}html"):
                    nestedInline = htmlElt
                    break
                if nestedInline is None:
                    for htmlElt in rootNode.iter(tag="{http://www.w3.org/1999/xhtml}xhtml"):
                        nestedInline = htmlElt
                        break
                if nestedInline is not None:
                    if (# not a valid test: XbrlConst.ixbrl in nestedInline.nsmap.values() or
                        any(e is not None for e in rootNode.iter(*XbrlConst.ixbrlTags))):
                        _type = Type.INLINEXBRL
                        rootNode = nestedInline

        modelDocument = _class(modelXbrl, _type, normalizedUri, filepath, xmlDocument)
        rootNode.init(modelDocument)
        modelDocument.parser = _parser # needed for XmlUtil addChild's makeelement
        modelDocument.parserLookupName = _parserLookupName
        modelDocument.parserLookupClass = _parserLookupClass
        modelDocument.xmlRootElement = modelDocument.targetXbrlRootElement = rootNode
        modelDocument.schemaLocationElements.add(rootNode)
        modelDocument.documentEncoding = _encoding

        if isEntry or isDiscovered:
            modelDocument.inDTS = True

        # discovery (parsing)
        if any(pluginMethod(modelDocument)
               for pluginMethod in pluginClassMethods("ModelDocument.Discover")):
            pass # discovery was performed by plug-in, we're done
        elif _type == Type.SCHEMA:
            modelDocument.schemaDiscover(rootNode, isIncluded, isSupplemental, namespace)
        elif _type == Type.LINKBASE:
            modelDocument.linkbaseDiscover(rootNode)
        elif _type == Type.INSTANCE:
            modelDocument.instanceDiscover(rootNode)
        elif _type == Type.INLINEXBRL:
            try:
                modelDocument.inlineXbrlDiscover(rootNode)
            except RecursionError as err:
                schemaErrorCount = modelXbrl.errors.count("xmlSchema:syntax")
                if schemaErrorCount > 100: # arbitrary count, in case of tons of unclosed or mismatched xhtml start-end elements
                    modelXbrl.error("html:unprocessable",
                        _("%(element)s error, unable to process html syntax due to %(schemaErrorCount)s schema syntax errors"),
                        modelObject=rootNode, element=rootNode.localName.title(), schemaErrorCount=schemaErrorCount)
                else:
                    modelXbrl.error("html:validationException",
                        _("%(element)s error %(error)s, unable to process html."),
                        modelObject=rootNode, element=rootNode.localName.title(), error=type(err).__name__)
                return None # rootNode is not processed further to find any facts because there could be many recursion errors
        elif _type == Type.VERSIONINGREPORT:
            modelDocument.versioningReportDiscover(rootNode)
        elif _type == Type.TESTCASESINDEX:
            modelDocument.testcasesIndexDiscover(xmlDocument, modelXbrl.modelManager.validateTestcaseSchema)
        elif _type == Type.TESTCASE:
            modelDocument.testcaseDiscover(rootNode, modelXbrl.modelManager.validateTestcaseSchema)
        elif _type == Type.REGISTRY:
            modelDocument.registryDiscover(rootNode)
        elif _type == Type.XPATHTESTSUITE:
            modelDocument.xPathTestSuiteDiscover(rootNode)
        elif _type == Type.VERSIONINGREPORT:
            modelDocument.versioningReportDiscover(rootNode)
        elif _type == Type.RSSFEED:
            modelDocument.rssFeedDiscover(rootNode)

        if isEntry or _type == Type.INLINEXBRL: # inline doc set members may not be entry but may have processing instructions
            for pi in modelDocument.processingInstructions:
                if pi.target == "arelle-unit-test":
                    modelXbrl.arelleUnitTests[pi.get("location")] = pi.get("action")
        if isEntry:
            while modelXbrl.schemaDocsToValidate:
                doc = modelXbrl.schemaDocsToValidate.pop()
                XmlValidateSchema.validate(doc, doc.xmlRootElement, doc.targetNamespace) # validate schema elements
            if hasattr(modelXbrl, "ixdsHtmlElements"):
                inlineIxdsDiscover(modelXbrl, modelDocument) # compile cross-document IXDS references
                for doc in modelDocument.referencesDocument.keys():
                    for referencedDoc in doc.referencesDocument.keys():
                        if referencedDoc.type == Type.SCHEMA:
                            modelDocument.targetDocumentSchemaRefs.add(doc.relativeUri(referencedDoc.uri))

        if isEntry or isSupplemental:
            # re-order base set keys for entry point or supplemental linkbase addition
            modelXbrl.baseSets = OrderedDefaultDict( # order by linkRole, arcRole of key
                modelXbrl.baseSets.default_factory,
                sorted(modelXbrl.baseSets.items(), key=lambda i: (i[0][0] or "",i[0][1] or "")))

    return modelDocument

def loadSchemalocatedSchema(modelXbrl, element, relativeUrl, namespace, baseUrl):
    if namespace == XbrlConst.xhtml: # block loading xhtml as a schema (e.g., inline which is xsd validated instead)
        return None
    #importSchemaLocation = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(relativeUrl, baseUrl)
    #doc = load(modelXbrl, relativeUrl, isIncluded=False, isDiscovered=False, namespace=namespace, referringElement=element, referringElementUrl=baseUrl)
    doc = load(modelXbrl, relativeUrl, isIncluded=False, isDiscovered=False, namespace=namespace, referringElement=element, base=baseUrl)
    if doc:
        if doc.targetNamespace != namespace:
            modelXbrl.error("xmlSchema1.4.2.3:refSchemaNamespace",
                _("SchemaLocation of %(fileName)s expected namespace %(namespace)s found targetNamespace %(targetNamespace)s"),
                modelObject=element, fileName=baseUrl,
                namespace=namespace, targetNamespace=doc.targetNamespace)
        else:
            doc.inDTS = False
    return doc

def create(modelXbrl, type, uri, schemaRefs=None, isEntry=False, initialXml=None, initialComment=None, base=None, discover=True, documentEncoding="utf-8", xbrliNamespacePrefix=None) -> ModelDocument:
    """Returns a new modelDocument, created from scratch, with any necessary header elements

    (such as the schema, instance, or RSS feed top level elements)
    :param type: type of model document (value of ModelDocument.Types, an integer)
    :type type: Types
    :param schemaRefs: list of URLs when creating an empty INSTANCE, to use to discover (load) the needed DTS modelDocument objects.
    :type schemaRefs: [str]
    :param isEntry is True when creating an entry (e.g., instance)
    :type isEntry: bool
    :param initialXml is initial xml content for xml documents
    :type isEntry: str
    """
    normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(uri, base)
    if isEntry:
        modelXbrl.uri = normalizedUri
        modelXbrl.entryLoadingUrl = normalizedUri
        modelXbrl.uriDir = os.path.dirname(normalizedUri)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.uriDir = os.path.dirname(modelXbrl.uriDir)
    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri, filenameOnly=True)
    if initialComment:
        initialComment = "<!--" + initialComment + "-->"
    # XML document has nsmap root element to replace nsmap as new xmlns entries are required
    if initialXml and type in (Type.INSTANCE, Type.SCHEMA, Type.LINKBASE, Type.RSSFEED, Type.TESTCASE):
        Xml = '<nsmap>{}{}</nsmap>'.format(initialComment or '', initialXml or '')
    elif type == Type.INSTANCE:
        # modelXbrl.uriDir = os.path.dirname(normalizedUri)
        if xbrliNamespacePrefix is not None:
            xbrli_instance_namespace = f'<{xbrliNamespacePrefix}:xbrl xmlns:{xbrliNamespacePrefix}="http://www.xbrl.org/2003/instance"'
        else:
            xbrli_instance_namespace = '<xbrl xmlns="http://www.xbrl.org/2003/instance"'
        Xml = ('<nsmap>{}'
               '{}'
               ' xmlns:link="http://www.xbrl.org/2003/linkbase"'
               ' xmlns:xlink="http://www.w3.org/1999/xlink">').format(initialComment, xbrli_instance_namespace)
        if schemaRefs:
            for schemaRef in schemaRefs:
                Xml += '<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(schemaRef.replace("\\","/"))
        if xbrliNamespacePrefix is not None:
            Xml += f'</{xbrliNamespacePrefix}:xbrl></nsmap>'
        else:
            Xml += '</xbrl></nsmap>'
    elif type == Type.SCHEMA:
        Xml = ('<nsmap>{}<schema xmlns="http://www.w3.org/2001/XMLSchema" /></nsmap>').format(initialComment)
    elif type == Type.RSSFEED:
        Xml = '<nsmap><rss version="2.0" /></nsmap>'
    elif type in (Type.DTSENTRIES, Type.HTML):
        Xml = None
    else:
        type = Type.UnknownXML
        Xml = '<nsmap>{0}</nsmap>'.format(initialXml or '')
    if Xml:
        import io
        file = io.StringIO(Xml)
        _parser, _parserLookupName, _parserLookupClass = parser(modelXbrl,normalizedUri)
        xmlDocument = etree.parse(file,parser=_parser,base_url=filepath)
        file.close()
    else:
        xmlDocument = None
    if type == Type.RSSFEED:
        from arelle.ModelRssObject import ModelRssObject
        modelDocument = ModelRssObject(modelXbrl, type, uri, filepath, xmlDocument)
    else:
        modelDocument = ModelDocument(modelXbrl, type, normalizedUri, filepath, xmlDocument)
    if Xml:
        modelDocument.parser = _parser # needed for XmlUtil addChild's makeelement
        modelDocument.parserLookupName = _parserLookupName
        modelDocument.parserLookupClass = _parserLookupClass
        modelDocument.documentEncoding = documentEncoding
        rootNode = xmlDocument.getroot()
        rootNode.init(modelDocument)
        if xmlDocument:
            for semanticRoot in rootNode.iterchildren():
                if isinstance(semanticRoot, ModelObject):
                    modelDocument.xmlRootElement = modelDocument.targetXbrlRootElement = semanticRoot
                    break
        # init subtree
        for elt in xmlDocument.iter():
            if isinstance(elt, ModelObject):
                elt.init(modelDocument)
    else:
        xmlDocument = None
    if type == Type.INSTANCE and discover:
        modelDocument.instanceDiscover(modelDocument.xmlRootElement)
    elif type == Type.RSSFEED and discover:
        modelDocument.rssFeedDiscover(modelDocument.xmlRootElement)
    elif type == Type.SCHEMA:
        modelDocument.targetNamespace = None
        modelDocument.isQualifiedElementFormDefault = False
        modelDocument.isQualifiedAttributeFormDefault = False
    modelDocument.definesUTR = False
    return modelDocument

class Type:
    """
    .. class:: Type

    Static class of Enumerated type representing modelDocument type
    """
    UnknownXML=0
    UnknownNonXML=1
    UnknownTypes=1  # to test if any unknown type, use <= Type.UnknownTypes
    firstXBRLtype=2  # first filetype that is XBRL and can hold a linkbase, etc inside it
    SCHEMA=2
    LINKBASE=3
    INSTANCE=4
    INLINEXBRL=5
    lastXBRLtype=5  # first filetype that is XBRL and can hold a linkbase, etc inside it
    DTSENTRIES=6  # multiple schema/linkbase Refs composing a DTS but not from an instance document
    INLINEXBRLDOCUMENTSET=7
    VERSIONINGREPORT=8
    TESTCASESINDEX=9
    TESTCASE=10
    REGISTRY=11
    REGISTRYTESTCASE=12
    XPATHTESTSUITE=13
    RSSFEED=14
    ARCSINFOSET=15
    FACTDIMSINFOSET=16
    HTML=17

    TESTCASETYPES = (TESTCASESINDEX, TESTCASE, REGISTRY, REGISTRYTESTCASE, XPATHTESTSUITE)

    typeName = ("unknown XML",
                "unknown non-XML",
                "schema",
                "linkbase",
                "instance",
                "inline XBRL instance",
                "entry point set",
                "inline XBRL document set",
                "versioning report",
                "testcases index",
                "testcase",
                "registry",
                "registry testcase",
                "xpath test suite",
                "RSS feed",
                "arcs infoset",
                "fact dimensions infoset",
                "html non-XBRL")

    @staticmethod
    def identify(filesource: FileSource, filepath: str) -> int:
        _type = Type.UnknownNonXML
        _file, = filesource.file(filepath, stripDeclaration=True, binary=True)
        try:
            _rootElt = True
            _maybeHtml = False
            for _event, elt in etree.iterparse(_file, events=("start",), recover=True, huge_tree=True):
                if _rootElt:
                    _rootElt = False
                    _type = {"testcases": Type.TESTCASESINDEX,
                             "documentation": Type.TESTCASESINDEX,
                             "testSuite": Type.TESTCASESINDEX,
                             "registries": Type.TESTCASESINDEX,
                             "testcase": Type.TESTCASE,
                             "testSet": Type.TESTCASE,
                             "rss": Type.RSSFEED
                        }.get(etree.QName(elt).localname)
                    if _type:
                        break
                    _type = {"{http://www.xbrl.org/2003/instance}xbrl": Type.INSTANCE,
                             "{http://www.xbrl.org/2003/linkbase}linkbase": Type.LINKBASE,
                             "{http://www.w3.org/2001/XMLSchema}schema": Type.SCHEMA,
                             "{http://xbrl.org/2008/registry}registry": Type.REGISTRY
                             }.get(elt.tag, Type.UnknownXML)
                    if _type == Type.UnknownXML and elt.tag.endswith("html"):
                        _maybeHtml = True
                    else:
                        break # stop parsing
                if XbrlConst.ixbrlTagPattern.match(elt.tag):
                    _type = Type.INLINEXBRL
                    break
            if _type == Type.UnknownXML and _maybeHtml:
                _type = Type.HTML
        except Exception as err:
            if not _rootElt: # if _rootElt is false then a root element was found and it's some kind of xml
                _type = Type.UnknownXML
                if filesource.cntlr:
                    filesource.cntlr.addToLog("%(error)s",
                                              messageCode="arelle:fileIdentificationError",
                                              messageArgs={"error":err}, file=filepath)
        _file.close()
        return _type

# schema elements which end the include/import scah
schemaBottom = {"element", "attribute", "notation", "simpleType", "complexType", "group", "attributeGroup"}
fractionParts = {"{http://www.xbrl.org/2003/instance}numerator",
                 "{http://www.xbrl.org/2003/instance}denominator"}



class ModelDocument:
    """
    .. class:: ModelDocment(modelXbrl, type, uri, filepath, xmlDocument)

    The modelDocument performs discovery and initialization when loading documents.
    For instances, schema and linkbase references are resolved, as well as non-DTS schema locations needed
    to ensure PSVI-validated XML elements in the instance document (for formula processing).
    For DTSes, schema includes and imports are resolved, linkbase references discovered, and
    concepts made accessible by qname by the modelXbrl and ID at the modelDocument scope.
    Testcase documents (and their indexing files) are loaded as modelDocument objects.

    Specialized modelDocuments are the versioning report, which must discover from and to DTSes,
    and an RSS feed, which has a unique XML structure.

    :param modelXbrl: The ModelXbrl (DTS) object owning this modelDocument.
    :type modelXbrl: ModelXbrl
    :param uri:  The document's source entry URI (such as web site URL)
    :type uri: str
    :param filepath:  The file path of the source for the document (local file or web cache file name)
    :type filepath: str
    :param xmlDocument: lxml parsed xml document tree model of lxml proxy objects
    :type xmlDocument: lxml document

        .. attribute:: modelDocument

        Self (provided for consistency with modelObjects)

        .. attribute:: modelXbrl

        The owning modelXbrl

        .. attribute:: type

        The enumerated document type

        .. attribute:: uri

        Uri as discovered

        .. attribute:: filepath

        File path as loaded (e.g., from web cache on local drive)

        .. attribute:: basename

        Python basename (last segment of file path)

        .. attribute:: xmlDocument

        The lxml tree model of xml proxies

        .. attribute:: targetNamespace

        Target namespace (if a schema)

        .. attribute:: objectIndex

        Position in lxml objects table, for use as a surrogate

        .. attribute:: referencesDocument

        Dict of referenced documents, key is the modelDocument, value is why loaded (import, include, href)

        .. attribute:: idObjects

        Dict by id of modelObjects in document

        .. attribute:: hrefObjects

        List of (modelObject, modelDocument, id) for each xlink:href

        .. attribute:: schemaLocationElements

        Set of modelObject elements that have xsi:schemaLocations

        .. attribute:: referencedNamespaces

        Set of referenced namespaces (by import, discovery, etc)

        .. attribute:: inDTS

        Qualifies as a discovered schema per XBRL 2.1
    """

    # The document encoding. The XML declaration is stripped from the document
    # before lxml parses the document making the lxml DocInfo encoding unreliable.
    documentEncoding: str
    xmlRootElement: Any
    targetXbrlRootElement: ModelObject

    def __init__(self, modelXbrl, type, uri, filepath, xmlDocument):
        self.modelXbrl = modelXbrl
        self.skipDTS = modelXbrl.skipDTS
        self.type = type
        self.uri = uri
        self.filepath = filepath
        self.xmlDocument = self.targetXbrlElementTree = xmlDocument
        self.targetNamespace = None
        modelXbrl.urlDocs[uri] = self
        self.objectIndex = len(modelXbrl.modelObjects)
        modelXbrl.modelObjects.append(self)
        self.referencesDocument = {}
        self.idObjects = {}  # by id
        self.hrefObjects = []
        self.schemaLocationElements = set()
        self.referencedNamespaces = set()
        self.targetDocumentSchemaRefs = set()
        self.inDTS = False
        self.definesUTR = False
        self.isModified = False


    def objectId(self,refId=""):
        return "_{0}_{1}".format(refId, self.objectIndex)

    # qname of root element of the document so modelDocument can be treated uniformly as modelObject
    @property
    def qname(self):
        try:
            return self._xmlRootElementQname
        except AttributeError:
            self._xmlRootElementQname = qname(self.xmlRootElement)
            return self._xmlRootElementQname

    def relativeUri(self, uri): # return uri relative to this modelDocument uri
        return UrlUtil.relativeUri(self.uri, uri)

    @property
    def modelDocument(self):
        return self # for compatibility with modelObject and modelXbrl

    @property
    def displayUri(self):
        if self.type == Type.INLINEXBRLDOCUMENTSET:
            ixdsDocBaseNames = [ixDoc.basename
                                for ixDoc in self.referencesDocument.keys()
                                if ixDoc.type == Type.INLINEXBRL]
            if len(ixdsDocBaseNames) > 2: # linit to 3 basenames in IXDS
                ixdsDocBaseNames = ixdsDocBaseNames[0:2] + ["..."]
            return "IXDS {}".format(", ".join(ixdsDocBaseNames))
        else:
            return self.uri

    @property
    def basename(self):
        return os.path.basename(self.filepath)

    @property
    def filepathdir(self):
        return os.path.dirname(self.filepath)

    @property
    def propertyView(self):
        return (("type", self.gettype()),
                ("uri", self.uri)) + \
                (("fromDTS", self.fromDTS.uri),
                 ("toDTS", self.toDTS.uri)
                 ) if self.type == Type.VERSIONINGREPORT else ()

    def __repr__(self):
        return ("{0}[{1}]{2})".format(self.__class__.__name__, self.objectId(),self.propertyView))

    def setTitle(self, cntlr):
        try:
            cntlr.parent.wm_title(_("arelle - {0}").format(self.basename))
        except AttributeError:
            pass

    def setTitleInBackground(self):
        try:
            cntlr = self.modelXbrl.modelManager.cntlr
            uiThreadQueue = cntlr.uiThreadQueue
            uiThreadQueue.put((self.setTitle, [cntlr]))
        except AttributeError:
            pass

    def updateFileHistoryIfNeeded(self):
        myCntlr = self.modelXbrl.modelManager.cntlr
        updateFileHistory = getattr(myCntlr, 'updateFileHistory', None)
        if updateFileHistory:
            try:
                cntlr = self.modelXbrl.modelManager.cntlr
                uiThreadQueue = cntlr.uiThreadQueue
                uiThreadQueue.put((updateFileHistory, [self.filepath, False]))
            except AttributeError:
                pass

    def save(self, overrideFilepath=None, outputZip=None, outputFile=None, updateFileHistory=True, encoding="utf-8", **kwargs) -> None:
        """Saves current document file.

        :param overrideFilepath: specify to override saving in instance's modelDocument.filepath
        """
        if outputFile:
            fh = outputFile
        elif outputZip:
            fh = io.StringIO();
        else:
            fh = open( (overrideFilepath or self.filepath), "w", encoding='utf-8')
        XmlUtil.writexml(fh, self.xmlDocument, encoding=encoding, **kwargs)
        if outputZip:
            fh.seek(0)
            outputZip.writestr(os.path.basename(overrideFilepath or self.filepath),fh.read())
        if outputFile is None:
            fh.close()
        if overrideFilepath:
            self.filepath = overrideFilepath
            self.setTitleInBackground()
        if updateFileHistory:
            self.updateFileHistoryIfNeeded()
        self.isModified = False

    def close(self, visited=None, urlDocs=None) -> None:
        try:
            if self.modelXbrl is not None:
                self.modelXbrl = None
        except:
            pass
        if visited is None: visited = []
        visited.append(self)
        # note that self.modelXbrl has been closed/dereferenced already, do not use in plug in
        for pluginMethod in pluginClassMethods("ModelDocument.CustomCloser"):
            pluginMethod(self)
        try:
            for referencedDocument, modelDocumentReference in self.referencesDocument.items():
                if referencedDocument not in visited:
                    referencedDocument.close(visited=visited,urlDocs=urlDocs)
                modelDocumentReference.__dict__.clear() # dereference its contents
            self.referencesDocument.clear()
            if self.type == Type.VERSIONINGREPORT:
                if self.fromDTS:
                    self.fromDTS.close()
                if self.toDTS:
                    self.toDTS.close()
            urlDocs.pop(self.uri,None)
            xmlDocument = self.xmlDocument
            dummyRootElement = self.parser.makeelement("{http://dummy}dummy") # may fail for streaming
            for modelObject in self.xmlRootElement.iter():
                modelObject.__dict__.clear() # clear python variables of modelObjects (not lxml)
            self.xmlRootElement.clear() # clear entire lxml subtree
            self.parserLookupName.__dict__.clear()
            self.parserLookupClass.__dict__.clear()
            self.__dict__.clear() # dereference everything before clearing xml tree
            if dummyRootElement is not None:
                xmlDocument._setroot(dummyRootElement)
            del dummyRootElement
        except AttributeError:
            pass    # maybe already cloased
        if len(visited) == 1:  # outer call
            while urlDocs:
                urlDocs.popitem()[1].close(visited=visited,urlDocs=urlDocs)
        visited.remove(self)

    def gettype(self):
        try:
            return Type.typeName[self.type]
        except AttributeError:
            return "unknown"

    @property
    def creationSoftwareComment(self):
        try:
            return self._creationSoftwareComment
        except AttributeError:
            # first try for comments before root element
            initialComment = ''
            node = self.xmlRootElement
            while node.getprevious() is not None:
                node = node.getprevious()
                if isinstance(node, etree._Comment):
                    initialComment = node.text + '\n' + initialComment
            if initialComment:
                self._creationSoftwareComment = initialComment
            else:
                self._creationSoftwareComment = None
                for i, node in enumerate(self.xmlDocument.iter()):
                    if isinstance(node, etree._Comment):
                        self._creationSoftwareComment = node.text
                    if i > 10:  # give up, no heading comment
                        break
            return self._creationSoftwareComment

    @property
    def creationSoftware(self):
        global creationSoftwareNames
        if creationSoftwareNames is None:
            import json
            import regex as re
            creationSoftwareNames = []
            try:
                with io.open(os.path.join(self.modelXbrl.modelManager.cntlr.configDir, "creationSoftwareNames.json"),
                             'rt', encoding='utf-8') as f:
                    for key, pattern in json.load(f):
                        if key != "_description_":
                            creationSoftwareNames.append( (key, re.compile(pattern, re.IGNORECASE)) )
            except Exception as ex:
                self.modelXbrl.error("arelle:creationSoftwareNamesTable",
                                     _("Error loading creation software names table %(error)s"),
                                     modelObject=self, error=ex)
        creationSoftwareComment = self.creationSoftwareComment
        if not creationSoftwareComment:
            return "None"
        for productKey, productNamePattern in creationSoftwareNames:
            if productNamePattern.search(creationSoftwareComment):
                return productKey
        return creationSoftwareComment # "Other"

    @property
    def processingInstructions(self):
        try:
            return self._processingInstructions
        except AttributeError:
            self._processingInstructions = []
            node = self.xmlRootElement
            while node.getprevious() is not None:
                node = node.getprevious()
                if isinstance(node, etree._ProcessingInstruction):
                    self._processingInstructions.append(node)
            return self._processingInstructions

    def schemaDiscover(self, rootElement, isIncluded, isSupplemental, namespace):
        targetNamespace = rootElement.get("targetNamespace")
        if targetNamespace:
            self.targetNamespace = targetNamespace
            self.referencedNamespaces.add(targetNamespace)
            self.modelXbrl.namespaceDocs[targetNamespace].append(self)
            if namespace and targetNamespace != namespace:
                self.modelXbrl.error("xmlSchema1.4.2.3:refSchemaNamespace",
                    _("Discovery of %(fileName)s expected namespace %(namespace)s found targetNamespace %(targetNamespace)s"),
                    modelObject=rootElement, fileName=self.basename,
                    namespace=namespace, targetNamespace=targetNamespace)
            if (self.modelXbrl.modelManager.validateDisclosureSystem and
                self.modelXbrl.modelManager.disclosureSystem.disallowedHrefOfNamespace(self.uri, targetNamespace)):
                    self.modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if self.uri.startswith("http") else "SBR.NL.2.2.0.17"),
                            _("Namespace: %(namespace)s disallowed schemaLocation %(schemaLocation)s"),
                            modelObject=rootElement, namespace=targetNamespace, schemaLocation=self.uri, url=self.uri,
                            messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
            self.noTargetNamespace = False
        else:
            if isIncluded == True and namespace:
                self.targetNamespace = namespace
                self.modelXbrl.namespaceDocs[targetNamespace].append(self)
            self.noTargetNamespace = True
        if targetNamespace == XbrlConst.xbrldt:
            # BUG: should not set this if obtained from schemaLocation instead of import (but may be later imported)
            self.modelXbrl.hasXDT = True
        self.isQualifiedElementFormDefault = rootElement.get("elementFormDefault") == "qualified"
        self.isQualifiedAttributeFormDefault = rootElement.get("attributeFormDefault") == "qualified"
        # self.definesUTR = any(ns == XbrlConst.utr for ns in rootElement.nsmap.values())
        try:
            self.schemaDiscoverChildElements(rootElement, isSupplemental)
        except (ValueError, LookupError) as err:
            self.filesource.cntlr.addToLog("error during schema discovery: %(error)s",
                                           messageCode="arelle:discoveryError",
                                           messageArgs={"error":err}, file=self.basename)
        if not isIncluded:
            if targetNamespace:
                nsDocs = self.modelXbrl.namespaceDocs
                if targetNamespace in nsDocs and nsDocs[targetNamespace].index(self) == 0:
                    for doc in nsDocs[targetNamespace]: # includes self and included documents of this namespace
                        self.modelXbrl.schemaDocsToValidate.add(doc) # validate after all schemas are loaded
            else:  # no target namespace, no includes to worry about order of validation
                self.modelXbrl.schemaDocsToValidate.add(self) # validate schema elements


    def schemaDiscoverChildElements(self, parentModelObject, isSupplemental=False):
        # find roleTypes, elements, and linkbases
        # must find import/include before processing linkbases or elements
        for modelObject in parentModelObject.iterchildren():
            if isinstance(modelObject,ModelObject):
                ln = modelObject.localName
                ns = modelObject.namespaceURI
                if modelObject.namespaceURI == XbrlConst.xsd and ln in {"import", "include", "redefine"}:
                    if parentModelObject.qname == XbrlConst.qnXsdSchema:
                        self.importDiscover(modelObject)
                    else:
                        self.modelXbrl.error("schema.compositionElement",
                            _("Schema element %(element)s must be parented by xs:schema."),
                            modelObject=modelObject, element=ln)
                elif ns == XbrlConst.link and (self.inDTS or isSupplemental):
                    _mislocated = not XmlUtil.elementTagnamesPath(parentModelObject).endswith("{http://www.w3.org/2001/XMLSchema}schema/{http://www.w3.org/2001/XMLSchema}annotation/{http://www.w3.org/2001/XMLSchema}appinfo")
                    if ln == "roleType":
                        if _mislocated:
                            self.modelXbrl.error("xbrl.5.1.3.roleTypeLocation",
                                _("Schema file link:roleType may only be located at path //xs:schema/xs:annotation/xs:appinfo but was found at %(elementPath)s"),
                                modelObject=modelObject, elementPath=self.xmlDocument.getpath(parentModelObject))
                        self.modelXbrl.roleTypes[modelObject.roleURI].append(modelObject)
                    elif ln == "arcroleType":
                        if _mislocated:
                            self.modelXbrl.error("xbrl.5.1.4.arcroleTypeLocation",
                                _("Schema file link:arcroleType may only be located at path //xs:schema/xs:annotation/xs:appinfo but was found at %(elementPath)s"),
                                modelObject=modelObject, elementPath=self.xmlDocument.getpath(parentModelObject))
                        self.modelXbrl.arcroleTypes[modelObject.arcroleURI].append(modelObject)
                    elif ln == "linkbaseRef":
                        if _mislocated:
                            self.modelXbrl.error("xbrl.5.1.2.LinkbaseRefLocation",
                                _("Schema file link:linkbaseRef may only be located at path //xs:schema/xs:annotation/xs:appinfo but was found at %(elementPath)s"),
                                modelObject=modelObject, elementPath=self.xmlDocument.getpath(parentModelObject))
                        self.schemaLinkbaseRefDiscover(modelObject)
                    elif ln == "linkbase":
                        if _mislocated:
                            self.modelXbrl.error("xbrl.5.2.linkbaseLocation",
                                _("Schema file link:linkbase may only be located at path //xs:schema/xs:annotation/xs:appinfo but was found at %(elementPath)s"),
                                modelObject=modelObject, elementPath=self.xmlDocument.getpath(parentModelObject))
                        self.linkbaseDiscover(modelObject)
                else: # recurse to children
                    self.schemaDiscoverChildElements(modelObject, isSupplemental)


    def baseForElement(self, element):
        base = ""
        baseElt = element
        while baseElt is not None:
            baseAttr = baseElt.get("{http://www.w3.org/XML/1998/namespace}base")
            if baseAttr:
                if self.modelXbrl.modelManager.validateDisclosureSystem:
                    self.modelXbrl.error(("EFM.6.03.11", "GFM.1.1.7", "EBA.2.1", "EIOPA.2.1"),
                        _("Prohibited base attribute: %(attribute)s"),
                        edgarCode="du-0311-Xml-Base-Used",
                        modelObject=element, attribute=baseAttr, element=element.qname)
                else:
                    ''' HF 2019-09-29: believe this is wrong
                    if baseAttr.startswith("/"):
                        base = baseAttr
                    else:
                        base = baseAttr + base
                    '''
                    base = baseAttr + base
                    if base.startswith("/"):
                        break # break because it is now absolute
            baseElt = baseElt.getparent()
        if base: # neither None nor ''
            if base.startswith('http://') or os.path.isabs(base):
                return base
            else:
                return os.path.dirname(self.uri) + "/" + base
        return self.uri

    def importDiscover(self, element):
        schemaLocation = element.get("schemaLocation")
        if element.localName in ("include", "redefine"): # add redefine, loads but type definitons of redefine not processed yet (See below)
            importNamespace = self.targetNamespace
            isIncluded = True
        else:
            importNamespace = element.get("namespace")
            isIncluded = False
        if importNamespace and schemaLocation:
            importElementBase = self.baseForElement(element)
            importSchemaLocation = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(schemaLocation, importElementBase)
            if (self.modelXbrl.modelManager.validateDisclosureSystem and
                    self.modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences and
                    self.modelXbrl.modelManager.disclosureSystem.disallowedHrefOfNamespace(importSchemaLocation, importNamespace)):
                self.modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if importSchemaLocation.startswith("http") else "SBR.NL.2.2.0.17"),
                        _("Namespace: %(namespace)s disallowed schemaLocation blocked %(schemaLocation)s"),
                        modelObject=element, namespace=importNamespace, schemaLocation=importSchemaLocation, url=importSchemaLocation,
                        messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
                return
            doc = None
            importSchemaLocationBasename = os.path.basename(importNamespace)
            # is there an exact match for importNamespace and uri?
            for otherDoc in self.modelXbrl.namespaceDocs[importNamespace]:
                doc = otherDoc
                if otherDoc.uri == importSchemaLocation:
                    break
                elif isIncluded:
                    doc = None  # don't allow matching namespace lookup on include (NS is already loaded!)
                elif doc.basename != importSchemaLocationBasename:
                    doc = None  # different file (may have imported a file now being included)
            # if no uri match, doc will be some other that matched targetNamespace
            if doc is not None:
                if self.inDTS and not doc.inDTS:
                    doc.inDTS = True    # now known to be discovered
                    doc.schemaDiscoverChildElements(doc.xmlRootElement)
            else:
                doc = load(self.modelXbrl, schemaLocation, base=importElementBase, isDiscovered=self.inDTS,
                           isIncluded=isIncluded, namespace=importNamespace, referringElement=element)
            if doc is not None:
                self.addDocumentReference(doc, element.localName, element) #import or include
                self.referencedNamespaces.add(importNamespace)

            # future note: for redefine, if doc was just loaded, process redefine type definitions

    def schemalocateElementNamespace(self, element):
        if isinstance(element,ModelObject):
            eltNamespace = element.namespaceURI
            if eltNamespace not in self.modelXbrl.namespaceDocs and eltNamespace not in self.referencedNamespaces:
                schemaLocationElement = XmlUtil.schemaLocation(element, eltNamespace, returnElement=True)
                if schemaLocationElement is not None:
                    self.schemaLocationElements.add(schemaLocationElement)
                    self.referencedNamespaces.add(eltNamespace)

    def loadSchemalocatedSchemas(self) -> None:
        # schemaLocation requires loaded schemas for validation
        if self.skipDTS:
            return
        for elt in self.schemaLocationElements:
            schemaLocation = elt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
            if schemaLocation:
                ns = None
                for entry in schemaLocation.split():
                    if ns is None:
                        ns = entry
                    else:
                        if self.type == Type.INLINEXBRL and ns == XbrlConst.xhtml:
                            pass # skip schema validation of inline XBRL
                        elif ns not in self.modelXbrl.namespaceDocs:
                            loadSchemalocatedSchema(self.modelXbrl, elt, entry, ns, self.baseForElement(elt))
                        ns = None

    def schemaLinkbaseRefsDiscover(self, tree):
        for refln in ("{http://www.xbrl.org/2003/linkbase}schemaRef", "{http://www.xbrl.org/2003/linkbase}linkbaseRef"):
            for element in tree.iterdescendants(tag=refln):
                if isinstance(element,ModelObject):
                    self.schemaLinkbaseRefDiscover(element)
        # schemaLocate xbrldi if there is an xbrldi element
        for element in tree.iterdescendants("{http://xbrl.org/2006/xbrldi}*"):
            loadSchemalocatedSchema(self.modelXbrl, element, "http://www.xbrl.org/2006/xbrldi-2006.xsd", "http://xbrl.org/2006/xbrldi", self.baseForElement(element))
            break

    def schemaLinkbaseRefDiscover(self, element):
        return self.discoverHref(element, urlRewritePluginClass="ModelDocument.InstanceSchemaRefRewriter")

    def linkbasesDiscover(self, tree):
        for linkbaseElement in tree.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(linkbaseElement,ModelObject):
                self.linkbaseDiscover(self, linkbaseElement)

    def linkbaseDiscover(self, linkbaseElement, inInstance=False):
        # sequence linkbase elements for elementPointer efficiency
        lbElementSequence = 0
        for lbElement in linkbaseElement:
            if isinstance(lbElement,ModelObject):
                lbElementSequence += 1
                lbElement._elementSequence = lbElementSequence
                lbLn = lbElement.localName
                lbNs = lbElement.namespaceURI
                if lbNs == XbrlConst.link:
                    if lbLn == "roleRef" or lbLn == "arcroleRef":
                        href = self.discoverHref(lbElement)
                        if href is None:
                            self.modelXbrl.error("xmlSchema:requiredAttribute",
                                    _("Linkbase reference for %(linkbaseRefElement)s href attribute missing or malformed"),
                                    modelObject=lbElement, linkbaseRefElement=lbLn)
                        continue
                if lbElement.get("{http://www.w3.org/1999/xlink}type") == "extended":
                    if isinstance(lbElement, ModelLink):
                        self.schemalocateElementNamespace(lbElement)
                        arcrolesFound = set()
                        dimensionArcFound = False
                        formulaArcFound = False
                        tableRenderingArcFound = False
                        linkQn = qname(lbElement)
                        linkrole = lbElement.get("{http://www.w3.org/1999/xlink}role")
                        isStandardExtLink = XbrlConst.isStandardResourceOrExtLinkElement(lbElement)
                        if inInstance:
                            #index footnote links even if no arc children
                            baseSetKeys = (("XBRL-footnotes",None,None,None),
                                           ("XBRL-footnotes",linkrole,None,None))
                            for baseSetKey in baseSetKeys:
                                self.modelXbrl.baseSets[baseSetKey].append(lbElement)
                        linkElementSequence = 0
                        for linkElement in lbElement.iterchildren():
                            if isinstance(linkElement,ModelObject):
                                linkElementSequence += 1
                                linkElement._elementSequence = linkElementSequence
                                self.schemalocateElementNamespace(linkElement)
                                xlinkType = linkElement.get("{http://www.w3.org/1999/xlink}type")
                                modelResource = None
                                if xlinkType == "locator":
                                    nonDTS = linkElement.namespaceURI != XbrlConst.link or linkElement.localName != "loc"
                                    # only link:loc elements are discovered or processed
                                    href = self.discoverHref(linkElement, nonDTS=nonDTS)
                                    if href is None:
                                        if isStandardExtLink:
                                            self.modelXbrl.error("xmlSchema:requiredAttribute",
                                                    _('Locator href attribute "%(href)s" missing or malformed in standard extended link'),
                                                    modelObject=linkElement, href=linkElement.get("{http://www.w3.org/1999/xlink}href"))
                                        else:
                                            self.modelXbrl.warning("arelle:hrefWarning",
                                                    _('Locator href attribute "%(href)s" missing or malformed in non-standard extended link'),
                                                    modelObject=linkElement, href=linkElement.get("{http://www.w3.org/1999/xlink}href"))
                                    else:
                                        linkElement.modelHref = href
                                        modelResource = linkElement
                                elif xlinkType == "arc":
                                    arcQn = qname(linkElement)
                                    arcrole = linkElement.get("{http://www.w3.org/1999/xlink}arcrole")
                                    if arcrole not in arcrolesFound:
                                        if linkrole == "":
                                            linkrole = XbrlConst.defaultLinkRole
                                        #index by both arcrole and linkrole#arcrole and dimensionsions if applicable
                                        baseSetKeys = [(arcrole, linkrole, linkQn, arcQn)]
                                        baseSetKeys.append((arcrole, linkrole, None, None))
                                        baseSetKeys.append((arcrole, None, None, None))
                                        if XbrlConst.isDimensionArcrole(arcrole) and not dimensionArcFound:
                                            baseSetKeys.append(("XBRL-dimensions", None, None, None))
                                            baseSetKeys.append(("XBRL-dimensions", linkrole, None, None))
                                            dimensionArcFound = True
                                        if XbrlConst.isFormulaArcrole(arcrole) and not formulaArcFound:
                                            baseSetKeys.append(("XBRL-formulae", None, None, None))
                                            baseSetKeys.append(("XBRL-formulae", linkrole, None, None))
                                            formulaArcFound = True
                                        if XbrlConst.isTableRenderingArcrole(arcrole) and not tableRenderingArcFound:
                                            baseSetKeys.append(("Table-rendering", None, None, None))
                                            baseSetKeys.append(("Table-rendering", linkrole, None, None))
                                            tableRenderingArcFound = True
                                            self.modelXbrl.hasTableRendering = True
                                        if XbrlConst.isTableIndexingArcrole(arcrole):
                                            self.modelXbrl.hasTableIndexing = True
                                        for baseSetKey in baseSetKeys:
                                            self.modelXbrl.baseSets[baseSetKey].append(lbElement)
                                        arcrolesFound.add(arcrole)
                                elif xlinkType == "resource":
                                    # create resource and make accessible by id for document
                                    modelResource = linkElement
                                    for resourceElt in linkElement.iter(): # check resource element schemaLocations
                                        self.schemalocateElementNamespace(resourceElt)
                                if modelResource is not None:
                                    lbElement.labeledResources[linkElement.get("{http://www.w3.org/1999/xlink}label")] \
                                        .append(modelResource)
                    else:
                        self.modelXbrl.error("xbrl:schemaDefinitionMissing",
                                _("Linkbase extended link %(element)s missing schema definition"),
                                modelObject=lbElement, element=lbElement.prefixedName)

    def discoverHref(self, element, nonDTS=False, urlRewritePluginClass=None):
        href = element.get("{http://www.w3.org/1999/xlink}href")
        if href:
            url, id = UrlUtil.splitDecodeFragment(href)
            if url == "":
                doc = self
            else:
                # href discovery only can happein within a DTS
                if self.skipDTS: # no discovery
                    _newDoc = DocumentPrototype
                else:
                    _newDoc = load
                if urlRewritePluginClass:
                    for pluginMethod in pluginClassMethods(urlRewritePluginClass):
                        url = pluginMethod(self, url)
                doc = _newDoc(self.modelXbrl, url, isDiscovered=not nonDTS, base=self.baseForElement(element), referringElement=element)
                if not nonDTS and doc is not None:
                    if doc not in self.referencesDocument:
                        if not doc.inDTS and doc.type > Type.UnknownTypes:    # non-XBRL document is not in DTS
                            doc.inDTS = True    # now known to be discovered
                            if doc.type == Type.SCHEMA and not self.skipDTS: # schema coming newly into DTS
                                doc.schemaDiscoverChildElements(doc.xmlRootElement)
                    self.addDocumentReference(doc, "href", element)
            href = (element, doc, id if len(id) > 0 else None)
            if doc is not None:  # if none, an error would have already been reported, don't multiply report it
                self.hrefObjects.append(href)
            return href
        return None

    def instanceDiscover(self, xbrlElement):
        self.schemaLinkbaseRefsDiscover(xbrlElement)
        if not self.skipDTS:
            self.linkbaseDiscover(xbrlElement,inInstance=True) # for role/arcroleRefs and footnoteLinks
        xmlValidate(self.modelXbrl, xbrlElement) # validate instance elements (xValid may be UNKNOWN if skipDTS)
        self.instanceContentsDiscover(xbrlElement)

    def instanceContentsDiscover(self,xbrlElement):
        nextUndefinedFact = len(self.modelXbrl.undefinedFacts)
        instElementSequence = 0
        for instElement in xbrlElement.iterchildren():
            if isinstance(instElement,ModelObject):
                instElementSequence += 1
                instElement._elementSequence = instElementSequence
                ln = instElement.localName
                ns = instElement.namespaceURI
                if ns == XbrlConst.xbrli:
                    if ln == "context":
                        self.contextDiscover(instElement)
                    elif ln == "unit":
                        self.unitDiscover(instElement)
                elif ns == XbrlConst.link:
                    pass
                elif ns in XbrlConst.ixbrlAll and ln=="relationship":
                    pass
                else: # concept elements
                    self.factDiscover(instElement, self.modelXbrl.facts)
        if len(self.modelXbrl.undefinedFacts) > nextUndefinedFact:
            undefFacts = self.modelXbrl.undefinedFacts[nextUndefinedFact:]
            self.modelXbrl.error("xbrl:schemaImportMissing",
                    _("Instance facts missing schema concept definition: %(elements)s"),
                    modelObject=undefFacts,
                    elements=", ".join(sorted(set(str(f.prefixedName) for f in undefFacts))))

    def contextDiscover(self, modelContext, targetModelXbrl=None) -> None:
        if not self.skipDTS:
            xmlValidate(self.modelXbrl, modelContext) # validation may have not completed due to errors elsewhere
        id = modelContext.id
        self.modelXbrl.contexts[id] = modelContext
        for container in (("{http://www.xbrl.org/2003/instance}segment", modelContext.segDimValues, modelContext.segNonDimValues),
                          ("{http://www.xbrl.org/2003/instance}scenario", modelContext.scenDimValues, modelContext.scenNonDimValues)):
            containerName, containerDimValues, containerNonDimValues = container
            for containerElement in modelContext.iterdescendants(tag=containerName):
                for sElt in containerElement.iterchildren():
                    if isinstance(sElt,ModelObject):
                        if sElt.namespaceURI == XbrlConst.xbrldi and sElt.localName in ("explicitMember","typedMember"):
                            dimQn = sElt.dimensionQname
                            if dimQn: # may be null if schema error omits dimension element
                                if targetModelXbrl is not None: # ixds possibly-shared context
                                    sElt.targetModelXbrl = targetModelXbrl
                                    if hasattr(sElt, "_dimension") and sElt._dimension is None:
                                        del sElt._dimension
                                modelContext.qnameDims[dimQn] = sElt # both seg and scen
                                if not self.skipDTS:
                                    dimension = sElt.dimension
                                    if dimension is not None and dimension not in containerDimValues:
                                        containerDimValues[dimension] = sElt
                                    else:
                                        modelContext.errorDimValues.append(sElt)
                        else:
                            containerNonDimValues.append(sElt)

    def unitDiscover(self, unitElement, targetModelXbrl=None) -> None:
        if not self.skipDTS:
            xmlValidate(self.modelXbrl, unitElement) # validation may have not completed due to errors elsewhere
        self.modelXbrl.units[unitElement.id] = unitElement
        if targetModelXbrl is not None: # ixds possibly-shared context
            unitElement.targetModelXbrl = targetModelXbrl

    def inlineXbrlDiscover(self, htmlElement):
        ixNS = None
        htmlBase = None
        conflictingNSelts = []
        # find namespace, only 1 namespace
        for inlineElement in htmlElement.iterdescendants():
            if isinstance(inlineElement,ModelObject) and inlineElement.namespaceURI in XbrlConst.ixbrlAll:
                if ixNS is None:
                    ixNS = inlineElement.namespaceURI
                elif ixNS != inlineElement.namespaceURI:
                    conflictingNSelts.append(inlineElement)
            elif inlineElement.tag == "{http://www.w3.org/1999/xhtml}base":
                htmlBase = inlineElement.get("href")
        if ixNS is None: # no inline element, look for xmlns namespaces on htmlElement:
            for _ns in htmlElement.nsmap.values():
                if _ns in XbrlConst.ixbrlAll:
                    ixNS = _ns
                    break
        # required by 12.4.1 of [HTML] bullet 3
        # use of document base is commented out because it discloses/uses absolute server directory and defeats URI redirection
        if htmlBase is None:
            htmlBase = "" # os.path.dirname(self.uri) + "/"
        if conflictingNSelts:
            self.modelXbrl.error("ix:multipleIxNamespaces",
                    _("Multiple ix namespaces were found"),
                    modelObject=conflictingNSelts)
        self.ixNS = ixNS
        self.ixNStag = ixNStag = "{" + ixNS + "}" if ixNS else ""
        self.htmlBase = htmlBase
        ixdsTarget = getattr(self.modelXbrl, "ixdsTarget", None)
        if all(pluginMethod(self.modelXbrl)
               for pluginMethod in pluginClassMethods("ModelDocument.DiscoverIxdsDts")):
            # load referenced schemas and linkbases (before validating inline HTML
            for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "references"):
                if inlineElement.get("target") == ixdsTarget:
                    self.schemaLinkbaseRefsDiscover(inlineElement)
                    xmlValidate(self.modelXbrl, inlineElement) # validate instance elements
        # validate resources only if no possibility of multi-document ixds for which ix:references not encountered yet
        if len(list(pluginClassMethods("ModelDocument.SelectIxdsTarget"))) == 0:
            for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "resources"):
                xmlValidate(self.modelXbrl, inlineElement) # validate instance elements
        # with DTS loaded, now validate inline HTML (so schema definition of facts is available)
        if htmlElement.namespaceURI == XbrlConst.xhtml:  # must validate xhtml
            XhtmlValidate.xhtmlValidate(self.modelXbrl, htmlElement)  # fails on prefixed content

        # subsequent inline elements have to be processed after all of the document set is loaded
        if not hasattr(self.modelXbrl, "ixdsHtmlElements"):
            self.modelXbrl.ixdsHtmlElements = []
        self.modelXbrl.ixdsHtmlElements.append(htmlElement)


    def factDiscover(self, modelFact, parentModelFacts=None, parentElement=None) -> None:
        if parentModelFacts is None: # may be called with parentElement instead of parentModelFacts list
            if isinstance(parentElement, ModelFact) and parentElement.isTuple:
                parentModelFacts = parentElement.modelTupleFacts
            else:
                parentModelFacts = self.modelXbrl.facts
        if isinstance(modelFact, ModelFact):
            parentModelFacts.append( modelFact )
            self.modelXbrl.factsInInstance.add( modelFact )
            tupleElementSequence = 0
            for tupleElement in modelFact:
                if isinstance(tupleElement,ModelObject):
                    tupleElementSequence += 1
                    tupleElement._elementSequence = tupleElementSequence
                    if tupleElement.tag not in fractionParts:
                        self.factDiscover(tupleElement, modelFact.modelTupleFacts)
        else:
            self.modelXbrl.undefinedFacts.append(modelFact)

    def testcasesIndexDiscover(self, rootNode, validateTestcaseSchema):
        if validateTestcaseSchema:
            lxmlSchemaValidate(self)
        for testcasesElement in rootNode.iter():
            if isinstance(testcasesElement,ModelObject) and testcasesElement.localName in ("testcases", "registries", "testSuite"):
                rootAttr = testcasesElement.get("root")
                if rootAttr:
                    base = os.path.join(os.path.dirname(self.filepath),rootAttr) + os.sep
                else:
                    base = self.filepath
                for testcaseElement in testcasesElement:
                    if isinstance(testcaseElement,ModelObject) and testcaseElement.localName in ("testcase", "registry", "testSetRef"):
                        uriAttr = testcaseElement.get("uri") or testcaseElement.get("file") or testcaseElement.get("{http://www.w3.org/1999/xlink}href")
                        if uriAttr:
                            doc = load(self.modelXbrl, uriAttr, base=base, referringElement=testcaseElement)
                            self.addDocumentReference(doc, "testcaseIndex", testcaseElement)
                    elif isinstance(testcaseElement,ModelObject) and testcaseElement.localName in ("testcases", "registries"):
                        uriAttr = testcaseElement.get("uri") or testcaseElement.get("{http://www.w3.org/1999/xlink}href")
                        if uriAttr:
                            doc = load(self.modelXbrl, uriAttr, base=base, referringElement=testcaseElement)
                            self.addDocumentReference(doc, "testcaseIndex", testcaseElement)

    def testcaseDiscover(self, testcaseElement, validateTestcaseSchema):
        if validateTestcaseSchema:
            lxmlSchemaValidate(self)
        isTransformTestcase = testcaseElement.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms"
        if XmlUtil.xmlnsprefix(testcaseElement, XbrlConst.cfcn) or isTransformTestcase:
            self.type = Type.REGISTRYTESTCASE
        self.outpath = self.xmlRootElement.get("outpath") or self.filepathdir
        self.testcaseVariations: list[ModelTestcaseVariation] = []
        priorTransformName = None
        for modelVariation in XmlUtil.descendants(testcaseElement, testcaseElement.namespaceURI, ("variation", "testGroup")):
            self.testcaseVariations.append(modelVariation)
            if isTransformTestcase and modelVariation.getparent().get("name") is not None:
                transformName = modelVariation.getparent().get("name")
                if transformName != priorTransformName:
                    priorTransformName = transformName
                    variationNumber = 1
                modelVariation._name = "{0} v-{1:02}".format(priorTransformName, variationNumber)
                variationNumber += 1
        if len(self.testcaseVariations) == 0:
            # may be a inline test case
            if XbrlConst.ixbrlAll.intersection(testcaseElement.values()):
                self.testcaseVariations.append(testcaseElement)

    def registryDiscover(self, rootNode):
        lxmlSchemaValidate(self)
        base = self.filepath
        for entryElement in rootNode.iterdescendants(tag="{http://xbrl.org/2008/registry}entry"):
            if isinstance(entryElement,ModelObject):
                uri = XmlUtil.childAttr(entryElement, XbrlConst.registry, "url", "{http://www.w3.org/1999/xlink}href")
                functionDoc = load(self.modelXbrl, uri, base=base, referringElement=entryElement)
                if functionDoc is not None:
                    testUriElt = XmlUtil.child(functionDoc.xmlRootElement, XbrlConst.function, "conformanceTest")
                    if testUriElt is not None:
                        testuri = testUriElt.get("{http://www.w3.org/1999/xlink}href")
                        testbase = functionDoc.filepath
                        if testuri is not None:
                            testcaseDoc = load(self.modelXbrl, testuri, base=testbase, referringElement=testUriElt)
                            self.addDocumentReference(testcaseDoc, "registryIndex", testUriElt)

    def xPathTestSuiteDiscover(self, rootNode):
        # no child documents to reference
        pass

    def addDocumentReference(self, doc, referenceType, referringModelObject=None):
        if doc is not None:
            if doc not in self.referencesDocument:
                self.referencesDocument[doc] = ModelDocumentReference(referenceType, referringModelObject)
            else:
                r = self.referencesDocument[doc]
                r.referenceTypes.add(referenceType)
                if r.referringModelObject is None and referringModelObject is not None:
                    r.referringModelObject = referringModelObject


# inline document set level compilation
# modelIxdsDocument is an inlineDocumentSet or entry inline document (if not a document set)
#   note that multi-target and multi-instance facts may have html elements belonging to primary ixds instead of this instance ixds
def inlineIxdsDiscover(modelXbrl, modelIxdsDocument, setTargetModelXbrl=False):
    for pluginMethod in pluginClassMethods("ModelDocument.SelectIxdsTarget"):
        pluginMethod(modelXbrl, modelIxdsDocument)
    # extract for a single target document
    ixdsTarget = getattr(modelXbrl, "ixdsTarget", None)
    # compile inline result set
    ixdsEltById = modelXbrl.ixdsEltById = defaultdict(list)
    for htmlElement in modelXbrl.ixdsHtmlElements:
        for elt in htmlElement.iterfind(".//*[@id]"):
            if isinstance(elt,ModelObject) and elt.id:
                ixdsEltById[elt.id].append(elt)

    # TODO: ixdsEltById duplication should be tested here and removed from ValidateXbrlDTS (about line 346 after if name == "id" and attrValue in val.elementIDs)
    footnoteRefs = defaultdict(list)
    tupleElements = []
    continuationElements = {}
    continuationReferences = defaultdict(set) # set of elements that have continuedAt source value
    tuplesByTupleID = {}
    factsByFactID = {} # non-tuple facts
    factTargetIDs = set() # target IDs referenced on facts
    factTargetContextRefs = defaultdict(set) # index is target, value is set of contextRefs
    factTargetUnitRefs = defaultdict(set) # index is target, value is set of unitRefs
    targetRoleUris = defaultdict(set) # index is target, value is set of roleUris
    targetArcroleUris = defaultdict(set) # index is target, value is set of arcroleUris
    targetReferenceAttrElts = defaultdict(dict) # target dict by attrname of elts
    targetReferenceAttrVals = defaultdict(dict) # target dict by attrname of attr value
    targetReferencePrefixNs = defaultdict(dict) # target dict by prefix, namespace
    targetReferencesIDs = {} # target dict by id of reference elts
    modelInlineFootnotesById = {} # inline 1.1 ixRelationships and ixFootnotes
    modelXbrl.targetRoleRefs = {} # roleRefs used by selected target
    modelXbrl.targetArcroleRefs = {}  # arcroleRefs used by selected target
    modelXbrl.targetRelationships = set() # relationship elements used by selected target
    targetModelXbrl = modelXbrl if setTargetModelXbrl else None # modelXbrl of target for contexts/units in multi-target/multi-instance situation
    assignUnusedContextsUnits = (not setTargetModelXbrl and not ixdsTarget and
                                 not getattr(modelXbrl, "supplementalModelXbrls", ()) and (
                                    not getattr(modelXbrl, "targetIXDSesToLoad", ()) or
                                    set(e.modelDocument for e in modelXbrl.ixdsHtmlElements) ==
                                    set(x.modelDocument for e in getattr(modelXbrl, "targetIXDSesToLoad", ()) for x in e[1])))
    hasResources = hasHeader = False
    for htmlElement in modelXbrl.ixdsHtmlElements:
        mdlDoc = htmlElement.modelDocument
        ixNStag = mdlDoc.ixNStag
        for modelInlineTuple in htmlElement.iterdescendants(tag=ixNStag + "tuple"):
            if isinstance(modelInlineTuple,ModelObject):
                modelInlineTuple.unorderedTupleFacts = defaultdict(list)
                if modelInlineTuple.qname is not None:
                    if modelInlineTuple.tupleID:
                        if modelInlineTuple.tupleID not in tuplesByTupleID:
                            tuplesByTupleID[modelInlineTuple.tupleID] = modelInlineTuple
                        else:
                            modelXbrl.error(ixMsgCode("tupleIdDuplication", modelInlineTuple, sect="validation"),
                                            _("Inline XBRL tuples have same tupleID %(tupleID)s: %(qname1)s and %(qname2)s"),
                                            modelObject=(modelInlineTuple,tuplesByTupleID[modelInlineTuple.tupleID]),
                                            tupleID=modelInlineTuple.tupleID, qname1=modelInlineTuple.qname,
                                            qname2=tuplesByTupleID[modelInlineTuple.tupleID].qname)
                    tupleElements.append(modelInlineTuple)
                    for r in modelInlineTuple.footnoteRefs:
                        footnoteRefs[r].append(modelInlineTuple)
                    if modelInlineTuple.id:
                        factsByFactID[modelInlineTuple.id] = modelInlineTuple
                factTargetIDs.add(modelInlineTuple.get("target"))
        for modelInlineFact in htmlElement.iterdescendants(ixNStag + "nonNumeric", ixNStag + "nonFraction", ixNStag + "fraction"):
            if isinstance(modelInlineFact,ModelObject):
                _target = modelInlineFact.get("target")
                factTargetContextRefs[_target].add(modelInlineFact.get("contextRef"))
                factTargetUnitRefs[_target].add(modelInlineFact.get("unitRef"))
                if modelInlineFact.id:
                    factsByFactID[modelInlineFact.id] = modelInlineFact
        for elt in htmlElement.iterdescendants(tag=ixNStag + "continuation"):
            if isinstance(elt,ModelObject) and elt.id:
                continuationElements[elt.id] = elt
        for elt in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Footnote.clarkNotation):
            if isinstance(elt,ModelObject):
                modelInlineFootnotesById[elt.footnoteID] = elt
        for elt in htmlElement.iterdescendants(tag=ixNStag + "references"):
            if isinstance(elt,ModelObject):
                target = elt.get("target")
                targetReferenceAttrsDict = targetReferenceAttrElts[target]
                for attrName, attrValue in elt.items():
                    if attrName.startswith('{') and not attrName.startswith(ixNStag) and attrName != "{http://www.w3.org/XML/1998/namespace}base":
                        if attrName in targetReferenceAttrsDict:
                            modelXbrl.error(ixMsgCode("referencesAttributeDuplication",ns=mdlDoc.ixNS,name="references",sect="validation"),
                                            _("Inline XBRL ix:references attribute %(name)s duplicated in target %(target)s"),
                                            modelObject=(elt, targetReferenceAttrsDict[attrName]), name=attrName, target=target)
                        else:
                            targetReferenceAttrsDict[attrName] = elt
                            targetReferenceAttrVals[target][attrName] = attrValue # use qname to preserve prefix
                    if attrName.startswith("{http://www.xbrl.org/2003/instance}"):
                        modelXbrl.error(ixMsgCode("qualifiedAttributeDisallowed",ns=mdlDoc.ixNS,name="references",sect="constraint"),
                            _("Inline XBRL element %(element)s has disallowed attribute %(name)s"),
                            modelObject=elt, element=str(elt.elementQname), name=attrName)
                if elt.id:
                    if ixdsEltById[elt.id] != [elt]:
                        modelXbrl.error(ixMsgCode("referencesIdDuplication",ns=mdlDoc.ixNS,name="references",sect="validation"),
                                        _("Inline XBRL ix:references id %(id)s duplicated in inline document set"),
                                        modelObject=ixdsEltById[elt.id], id=elt.id)
                    if target in targetReferencesIDs:
                        modelXbrl.error(ixMsgCode("referencesTargetId",ns=mdlDoc.ixNS,name="references",sect="validation"),
                                        _("Inline XBRL has multiple ix:references with id in target %(target)s"),
                                        modelObject=(elt, targetReferencesIDs[target]), target=target)
                    else:
                        targetReferencesIDs[target] = elt
                targetReferencePrefixNsDict = targetReferencePrefixNs[target]
                for _prefix, _ns in elt.nsmap.items():
                    if _prefix in targetReferencePrefixNsDict and _ns != targetReferencePrefixNsDict[_prefix][0]:
                        modelXbrl.error(ixMsgCode("referencesNamespacePrefixConflict",ns=mdlDoc.ixNS,name="references",sect="validation"),
                                        _("Inline XBRL ix:references prefix %(prefix)s has multiple namespaces %(ns1)s and %(ns2)s in target %(target)s"),
                                        modelObject=(elt, targetReferencePrefixNsDict[_prefix][1]), prefix=_prefix, ns1=_ns, ns2=targetReferencePrefixNsDict[_prefix], target=target)
                    else:
                        targetReferencePrefixNsDict[_prefix] = (_ns, elt)

        for hdrElt in htmlElement.iterdescendants(tag=ixNStag + "header"):
            hasHeader = True
            for elt in hdrElt.iterchildren(tag=ixNStag + "resources"):
                hasResources = True
                for subEltTag in ("{http://www.xbrl.org/2003/instance}context","{http://www.xbrl.org/2003/instance}unit"):
                    for resElt in elt.iterdescendants(tag=subEltTag):
                        if resElt.id:
                            if ixdsEltById[resElt.id] != [resElt]:
                                modelXbrl.error(ixMsgCode("resourceIdDuplication",ns=mdlDoc.ixNS,name="resources",sect="validation"),
                                                _("Inline XBRL ix:resources descendant id %(id)s duplicated in inline document set"),
                                                modelObject=ixdsEltById[resElt.id], id=resElt.id)
    if not hasHeader:
        modelXbrl.error(ixMsgCode("missingHeader", ns=mdlDoc.ixNS, name="header", sect="validation"),
                        _("Inline XBRL ix:header element not found"),
                        modelObject=modelXbrl)
    if not hasResources:
        modelXbrl.error(ixMsgCode("missingResources", ns=mdlDoc.ixNS, name="resources", sect="validation"),
                        _("Inline XBRL ix:resources element not found"),
                        modelObject=modelXbrl)

    del ixdsEltById, targetReferencesIDs

    # discovery of relationships which are used by target documents
    for htmlElement in modelXbrl.ixdsHtmlElements:
        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship.clarkNotation):
            if isinstance(modelInlineRel,ModelObject):
                linkrole = modelInlineRel.get("linkRole", XbrlConst.defaultLinkRole)
                arcrole = modelInlineRel.get("arcrole", XbrlConst.factFootnote)
                sourceFactTargets = set()
                for id in modelInlineRel.get("fromRefs","").split():
                    if id in factsByFactID:
                        _target = factsByFactID[id].get("target")
                        targetRoleUris[_target].add(linkrole)
                        targetArcroleUris[_target].add(arcrole)
                        sourceFactTargets.add(_target)
                for id in modelInlineRel.get("toRefs","").split():
                    if id in factsByFactID:
                        _target = factsByFactID[id].get("target")
                        targetRoleUris[_target].add(linkrole)
                        targetArcroleUris[_target].add(arcrole)
                    elif id in modelInlineFootnotesById:
                        footnoteRole = modelInlineFootnotesById[id].get("footnoteRole")
                        if footnoteRole:
                            for _target in sourceFactTargets:
                                targetRoleUris[_target].add(footnoteRole)

    contextRefs = factTargetContextRefs[ixdsTarget]
    unitRefs = factTargetUnitRefs[ixdsTarget]
    allContextRefs = set.union(*factTargetContextRefs.values())
    allUnitRefs = set.union(*factTargetUnitRefs.values())

    # discovery of contexts, units and roles which are used by target document
    for htmlElement in modelXbrl.ixdsHtmlElements:
        mdlDoc = htmlElement.modelDocument
        ixNStag = mdlDoc.ixNStag

        for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "resources"):
            for elt in inlineElement.iterchildren("{http://www.xbrl.org/2003/instance}context"):
                id = elt.get("id")
                if id in contextRefs or (assignUnusedContextsUnits and id not in allContextRefs):
                    modelIxdsDocument.contextDiscover(elt, targetModelXbrl=targetModelXbrl)
            for elt in inlineElement.iterchildren("{http://www.xbrl.org/2003/instance}unit"):
                id = elt.get("id")
                if id in unitRefs or (assignUnusedContextsUnits and id not in allUnitRefs):
                    modelIxdsDocument.unitDiscover(elt, targetModelXbrl=targetModelXbrl)
            for refElement in inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}roleRef"):
                r = refElement.get("roleURI")
                if r in targetRoleUris[ixdsTarget]:
                    modelXbrl.targetRoleRefs[r] = refElement
                    if modelIxdsDocument.discoverHref(refElement) is None: # discover role-defining schema file
                        modelXbrl.error("xmlSchema:requiredAttribute",
                                _("Reference for roleURI href attribute missing or malformed"),
                                modelObject=refElement)
            for refElement in inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}arcroleRef"):
                r = refElement.get("arcroleURI")
                if r in targetArcroleUris[ixdsTarget]:
                    modelXbrl.targetArcroleRefs[r] = refElement
                    if modelIxdsDocument.discoverHref(refElement) is None: # discover arcrole-defining schema file
                        modelXbrl.error("xmlSchema:requiredAttribute",
                                _("Reference for arcroleURI href attribute missing or malformed"),
                                modelObject=refElement)


    del factTargetContextRefs, factTargetUnitRefs

    # root elements by target
    modelXbrl.ixTargetRootElements = {}
    for target in targetReferenceAttrElts.keys() | {None}: # need default target in case any facts have no or invalid target
        try:
            modelXbrl.ixTargetRootElements[target] = elt = modelIxdsDocument.parser.makeelement(
                XbrlConst.qnPrototypeXbrliXbrl.clarkNotation, attrib=targetReferenceAttrVals.get(target),
                nsmap=dict((p,n) for p,(n,e) in targetReferencePrefixNs.get(target,{}).items()))
            elt.init(modelIxdsDocument)
        except Exception as err:
            modelXbrl.error(type(err).__name__,
                    _("Unrecoverable error creating target instance: %(error)s"),
                    modelObject=modelXbrl, error=err)

    def locateFactInTuple(modelFact, tuplesByTupleID, ixNStag):
        tupleRef = modelFact.tupleRef
        tuple = None
        if tupleRef:
            if tupleRef not in tuplesByTupleID:
                modelXbrl.error(ixMsgCode("tupleRefMissing", modelFact, sect="validation"),
                                _("Inline XBRL tupleRef %(tupleRef)s not found"),
                                modelObject=modelFact, tupleRef=tupleRef)
            else:
                tuple = tuplesByTupleID[tupleRef]
        else:
            for tupleParent in modelFact.iterancestors(tag=ixNStag + '*'):
                if tupleParent.localName == "tuple":
                    tuple = tupleParent
                break
        if tuple is not None:
            if modelFact.order is not None: # None when order missing failed validation
                tuple.unorderedTupleFacts[modelFact.order].append(modelFact)
            else:
                modelXbrl.error(ixMsgCode("tupleMemberOrderMissing", modelFact, sect="validation"),
                                _("Inline XBRL tuple member %(qname)s must have a numeric order attribute"),
                                modelObject=modelFact, qname=modelFact.qname)
            if modelFact.get("target") == tuple.get("target"):
                modelFact._ixFactParent = tuple # support ModelInlineFact parentElement()
            else:
                modelXbrl.error(ixMsgCode("tupleMemberDifferentTarget", modelFact, sect="validation"),
                                _("Inline XBRL tuple member %(qname)s must have a tuple parent %(tuple)s with same target"),
                                modelObject=modelFact, qname=modelFact.qname, tuple=tuple.qname)
        else:
            if modelFact.get("target") == ixdsTarget: # only process facts with target match
                modelXbrl.modelXbrl.facts.append(modelFact)
            try:
                modelFact._ixFactParent = modelXbrl.ixTargetRootElements[modelFact.get("target")]
            except KeyError:
                modelFact._ixFactParent = modelXbrl.ixTargetRootElements[None]

    def locateContinuation(element):
        contAt = element.get("continuedAt")
        if contAt: # has continuation
            chain = [element] # implement non-recursively for very long continuaion chains
            while contAt:
                continuationReferences[contAt].add(element)
                if contAt not in continuationElements:
                    if contAt in element.modelDocument.idObjects:
                        _contAtTarget = element.modelDocument.idObjects[contAt]
                        modelXbrl.error(ixMsgCode("continuationTarget", element, sect="validation"),
                                        _("continuedAt %(continuationAt)s target is an %(targetElement)s element instead of ix:continuation element."),
                                        modelObject=(element, _contAtTarget), continuationAt=contAt, targetElement=_contAtTarget.elementQname)
                    else:
                        modelXbrl.error(ixMsgCode("continuationMissing", element, sect="validation"),
                                        _("Inline XBRL continuation %(continuationAt)s not found"),
                                        modelObject=element, continuationAt=contAt)
                    break
                else:
                    contElt = continuationElements[contAt]
                    if contElt in chain:
                        cycle = ", ".join(e.get("continuedAt") for e in chain)
                        chain.append(contElt) # makes the cycle clear
                        modelXbrl.error(ixMsgCode("continuationCycle", element, sect="validation"),
                                        _("Inline XBRL continuation cycle: %(continuationCycle)s"),
                                        modelObject=chain, continuationCycle=cycle)
                        break
                    else:
                        chain.append(contElt)
                        element._continuationElement = contElt
                        element = contElt # loop to continuation element
                        contAt = element.get("continuedAt")
            # check if any chain element is descendant of another
            chainSet = set(chain)
            for chainElt in chain:
                for chainEltAncestor in chainElt.iterancestors(tag=chainElt.modelDocument.ixNStag + '*'):
                    if chainEltAncestor in chainSet:
                        if hasattr(chain[0], "_continuationElement"):
                            del chain[0]._continuationElement # break chain to prevent looping in chain
                        modelXbrl.error(ixMsgCode("continuationChainNested", chainElt, sect="validation"),
                                        _("Inline XBRL continuation chain element %(ancestorElement)s has descendant element %(descendantElement)s"),
                                        modelObject=(chainElt,chainEltAncestor),
                                        ancestorElement=chainEltAncestor.id or chainEltAncestor.get("name",chainEltAncestor.get("continuedAt")),
                                        descendantElement=chainElt.id or chainElt.get("name",chainElt.get("continuedAt")))

    def checkTupleIxDescendants(tupleFact, parentElt):
        for childElt in parentElt.iterchildren():
            if isinstance(childElt,ModelObject) and childElt.namespaceURI in XbrlConst.ixbrlAll:
                if childElt.localName in ("numerator", "denominator"):
                    modelXbrl.error(ixMsgCode("tupleContentError", tupleFact, sect="validation"),
                                    _("Inline XBRL tuple content illegal %(qname)s"),
                                    modelObject=(tupleFact, childElt), qname=childElt.qname)
            else:
                checkTupleIxDescendants(tupleFact, childElt)

    def addItemFactToTarget(modelInlineFact):
        if setTargetModelXbrl:
            modelInlineFact.targetModelXbrl = modelXbrl # fact's owning IXDS overrides initial loading document IXDS
        if modelInlineFact.concept is None:
                modelXbrl.error(ixMsgCode("missingReferences", modelInlineFact, name="references", sect="validation"),
                                _("Instance fact missing schema definition: %(qname)s of Inline Element %(localName)s"),
                                modelObject=modelInlineFact, qname=modelInlineFact.qname, localName=modelInlineFact.elementQname)
        elif modelInlineFact.isFraction != (modelInlineFact.localName == "fraction"):
            modelXbrl.error(ixMsgCode("fractionDeclaration", modelInlineFact, name="fraction", sect="validation"),
                            _("Inline XBRL element %(qname)s base type %(type)s mapped by %(localName)s"),
                            modelObject=modelInlineFact, qname=modelInlineFact.qname, localName=modelInlineFact.elementQname,
                            type=modelInlineFact.concept.baseXsdType)
        else:
            modelIxdsDocument.modelXbrl.factsInInstance.add( modelInlineFact )

    _customTransforms = modelXbrl.modelManager.customTransforms or {}
    for htmlElement in modelXbrl.ixdsHtmlElements:
        mdlDoc = htmlElement.modelDocument
        ixNStag = mdlDoc.ixNStag
        # hook up tuples to their container
        for tupleFact in tupleElements:
            if tupleFact.modelDocument == mdlDoc:
                locateFactInTuple(tupleFact, tuplesByTupleID, ixNStag)
                if tupleFact.get("target") == ixdsTarget:
                    addItemFactToTarget(tupleFact) # needs to be in factsInInstance


        for modelInlineFact in htmlElement.iterdescendants(ixNStag + "nonNumeric", ixNStag + "nonFraction", ixNStag + "fraction"):
            _target = modelInlineFact.get("target")
            factTargetIDs.add(_target)
            if modelInlineFact.qname is not None: # must have a qname to be in facts
                if _target == ixdsTarget: # if not the selected target, schema isn't loaded
                    addItemFactToTarget(modelInlineFact)
                locateFactInTuple(modelInlineFact, tuplesByTupleID, ixNStag)
                locateContinuation(modelInlineFact)
                for r in modelInlineFact.footnoteRefs:
                    footnoteRefs[r].append(modelInlineFact)
                if modelInlineFact.elementQname.localName == "fraction":
                    childCounts = {}
                    for child in modelInlineFact.iter(ixNStag + "*"):
                        childCounts[child.elementQname.localName] = childCounts.get(child.elementQname.localName, 0) + 1
                        if child.elementQname.localName == "fraction":
                            for attr in modelInlineFact.attrib:
                                if (attr.startswith("{") or attr == "unitRef") and modelInlineFact.get(attr,"").strip() != child.get(attr,"").strip():
                                    modelXbrl.error(ixMsgCode("fractionChildAttributes", modelInlineFact, sect="validation"),
                                                    _("Inline XBRL nested fractions must have same attribute values for %(attr)s"),
                                                    modelObject=(modelInlineFact,child), attr=attr)
                    if modelInlineFact.isNil:
                        if "numerator" in childCounts or "denominator" in childCounts:
                            modelXbrl.error(ixMsgCode("nilFractionChildren", modelInlineFact, sect="constraint"),
                                            _("Inline XBRL nil fractions must not have any ix:numerator or ix:denominator children"),
                                            modelObject=modelInlineFact)
                    else:
                        if childCounts.get("numerator",0) != 1 or childCounts.get("denominator",0) != 1:
                            modelXbrl.error(ixMsgCode("fractionChildren", modelInlineFact, sect="constraint"),
                                            _("Inline XBRL fractions must have one ix:numerator and one ix:denominator child"),
                                            modelObject=modelInlineFact)
                    disallowedChildren = sorted((k for k in childCounts.keys() if k not in ("numerator", "denominator", "fraction") ))
                    if disallowedChildren:
                        modelXbrl.error(ixMsgCode("fractionChildren", modelInlineFact, sect="constraint"),
                                        _("Inline XBRL fraction disallowed children: %(disallowedChildren)s"),
                                        modelObject=modelInlineFact, disallowedChildren=", ".join(disallowedChildren))
                elif modelInlineFact.elementQname.localName == "nonFraction":
                    if not modelInlineFact.isNil:
                        if any(True for e in modelInlineFact.iterchildren("{*}*")) and (
                            modelInlineFact.text is not None or any(e.tail is not None for e in modelInlineFact.iterchildren())):
                            modelXbrl.error(ixMsgCode("nonFractionChildren", modelInlineFact, sect="constraint"),
                                            _("Inline XBRL nonFraction must have only one child nonFraction or text/whitespace but not both"),
                                            modelObject=modelInlineFact)
                fmt = modelInlineFact.format
                if fmt:
                    if fmt in _customTransforms:
                        pass
                    elif fmt.namespaceURI not in FunctionIxt.ixtNamespaceFunctions:
                        modelXbrl.error(ixMsgCode("invalidTransformation", modelInlineFact, sect="validation"),
                            _("Fact %(fact)s has unrecognized transformation namespace %(namespace)s"),
                            modelObject=modelInlineFact, fact=modelInlineFact.qname, transform=fmt, namespace=fmt.namespaceURI)
                        modelInlineFact.setInvalid()
                    elif fmt.localName not in FunctionIxt.ixtNamespaceFunctions[fmt.namespaceURI]:
                        modelXbrl.error(ixMsgCode("invalidTransformation", modelInlineFact, sect="validation"),
                            _("Fact %(fact)s has unrecognized transformation name %(name)s"),
                            modelObject=modelInlineFact, fact=modelInlineFact.qname, transform=fmt, name=fmt.localName)
                        modelInlineFact.setInvalid()
            else:
                modelXbrl.error(ixMsgCode("missingReferences", modelInlineFact, name="references", sect="validation"),
                                _("Instance fact missing schema definition: %(qname)s of Inline Element %(localName)s"),
                                modelObject=modelInlineFact, qname=modelInlineFact.get("name","(no name)"), localName=modelInlineFact.elementQname)

        # order tuple facts
        for tupleFact in tupleElements:
            # check for duplicates
            for order, facts in tupleFact.unorderedTupleFacts.items():
                if len(facts) > 1:
                    if not all(normalizeSpace(facts[0].value) == normalizeSpace(f.value) and
                               all(normalizeSpace(facts[0].get(attr)) == normalizeSpace(f.get(attr))
                                   for attr in facts[0].keys() if attr != "order")
                               for f in facts[1:]):
                        modelXbrl.error(ixMsgCode("tupleSameOrderMembersUnequal", facts[0], sect="validation"),
                                        _("Inline XBRL tuple members %(qnames)s values %(values)s and attributes not whitespace-normalized equal"),
                                        modelObject=facts, qnames=", ".join(str(f.qname) for f in facts),
                                        values=", ".join(f.value for f in facts))
            # check nearest ix: descendants
            checkTupleIxDescendants(tupleFact, tupleFact)
            tupleFact.modelTupleFacts = [facts[0] # this deduplicates by order number
                                         for order,facts in sorted(tupleFact.unorderedTupleFacts.items(), key=lambda i:i[0])
                                         if len(facts) > 0]

        # check for tuple cycles
        def checkForTupleCycle(parentTuple, tupleNesting):
            for fact in parentTuple.modelTupleFacts:
                if fact in tupleNesting:
                    tupleNesting.append(fact)
                    modelXbrl.error(ixMsgCode("tupleNestingCycle", fact, sect="validation"),
                                    _("Tuple nesting cycle: %(tupleCycle)s"),
                                    modelObject=tupleNesting, tupleCycle="->".join(str(t.qname) for t in tupleNesting))
                    tupleNesting.pop()
                else:
                    tupleNesting.append(fact)
                    checkForTupleCycle(fact, tupleNesting)
                    tupleNesting.pop()

        for tupleFact in tupleElements:
            checkForTupleCycle(tupleFact, [tupleFact])

        for modelInlineFootnote in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Footnote.clarkNotation):
            if isinstance(modelInlineFootnote,ModelObject):
                locateContinuation(modelInlineFootnote)

        for elt in htmlElement.iterdescendants(ixNStag + "exclude"):
            if not any(True for ancestor in elt.iterancestors(ixNStag + "continuation", ixNStag + "footnote", ixNStag + "nonNumeric")):
                modelXbrl.error(ixMsgCode("excludeMisplaced", elt, sect="constraint"),
                                _("Ix:exclude must be a descendant of descendant of at least one ix:continuation, ix:footnote or ix:nonNumeric element."),
                                modelObject=elt)

    # validate particle structure of elements after transformations and established tuple structure
    fractionTermTags = (ixNStag + "numerator", ixNStag + "denominator")
    for rootModelFact in modelXbrl.facts:
        # validate XBRL (after complete document set is loaded)
        if rootModelFact.localName == "fraction":
            numDenom = [None,None]
            for i, tag in enumerate(fractionTermTags):
                for modelInlineFractionTerm in rootModelFact.iterchildren(tag=tag):
                    xmlValidate(modelXbrl, modelInlineFractionTerm, ixFacts=True)
                    if modelInlineFractionTerm.xValid >= VALID:
                        numDenom[i] = modelInlineFractionTerm.xValue
            rootModelFact._fractionValue = numDenom
        xmlValidate(modelXbrl, rootModelFact, ixFacts=True)

    if len(targetReferenceAttrElts) == 0:
        modelXbrl.error(ixMsgCode("missingReferences", None, name="references", sect="validation"),
                        _("There must be at least one reference"),
                        modelObject=modelXbrl)
    _missingReferenceTargets = factTargetIDs - set(targetReferenceAttrElts.keys())
    if _missingReferenceTargets:
        modelXbrl.error(ixMsgCode("missingReferenceTargets", None, name="references", sect="validation"),
                        _("Found no ix:references element%(plural)s having target%(plural)s '%(missingReferenceTargets)s' in IXDS."),
                        modelObject=modelXbrl, plural=("s" if len(_missingReferenceTargets) > 1 else ""),
                        missingReferenceTargets=", ".join(sorted("(default)" if t is None else t
                                                                 for t in _missingReferenceTargets)))

    if ixdsTarget not in factTargetIDs and ixdsTarget not in targetReferenceAttrElts.keys():
        modelXbrl.warning("arelle:ixdsTargetNotDefined",
                          _("Target parameter %(ixdsTarget)s is not a specified IXDS target property"),
                          modelObject=modelXbrl, ixdsTarget=ixdsTarget)

    del targetReferenceAttrElts, targetReferencePrefixNs, targetReferenceAttrVals, factTargetIDs


    footnoteLinkPrototypes = {}
    # inline 1.1 link prototypes, one per link role (so only one extended link element is produced per link role)
    linkPrototypes = {}
    # inline 1.1 ixRelationships and ixFootnotes
    linkModelInlineFootnoteIds = defaultdict(set)
    linkModelLocIds = defaultdict(set)
    for htmlElement in modelXbrl.ixdsHtmlElements:
        mdlDoc = htmlElement.modelDocument
        # inline 1.0 ixFootnotes, build resources (with ixContinuation)
        for modelInlineFootnote in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrlFootnote.clarkNotation):
            if isinstance(modelInlineFootnote,ModelObject):
                # link
                linkrole = modelInlineFootnote.get("footnoteLinkRole", XbrlConst.defaultLinkRole)
                arcrole = modelInlineFootnote.get("arcrole", XbrlConst.factFootnote)
                footnoteID = modelInlineFootnote.footnoteID or ""
                # check if any footnoteRef fact is in this target instance
                if not any(modelFact.get("target") == ixdsTarget for modelFact in footnoteRefs[footnoteID]):
                    continue # skip footnote, it's not in this target document
                footnoteLocLabel = footnoteID + "_loc"
                if linkrole in footnoteLinkPrototypes:
                    linkPrototype = footnoteLinkPrototypes[linkrole]
                else:
                    linkPrototype = LinkPrototype(modelIxdsDocument, mdlDoc.xmlRootElement, XbrlConst.qnLinkFootnoteLink, linkrole)
                    footnoteLinkPrototypes[linkrole] = linkPrototype
                    for baseSetKey in (("XBRL-footnotes",None,None,None),
                                       ("XBRL-footnotes",linkrole,None,None),
                                       (arcrole,linkrole,XbrlConst.qnLinkFootnoteLink, XbrlConst.qnLinkFootnoteArc),
                                       (arcrole,linkrole,None,None),
                                       (arcrole,None,None,None)):
                        modelXbrl.baseSets[baseSetKey].append(linkPrototype)
                # locs
                for modelFact in footnoteRefs[footnoteID]:
                    locPrototype = LocPrototype(modelIxdsDocument, linkPrototype, footnoteLocLabel, modelFact)
                    linkPrototype.childElements.append(locPrototype)
                    linkPrototype.labeledResources[footnoteLocLabel].append(locPrototype)
                # resource
                linkPrototype.childElements.append(modelInlineFootnote)
                linkPrototype.labeledResources[footnoteID].append(modelInlineFootnote)
                # arc
                linkPrototype.childElements.append(ArcPrototype(mdlDoc, linkPrototype, XbrlConst.qnLinkFootnoteArc,
                                                                footnoteLocLabel, footnoteID,
                                                                linkrole, arcrole, sourceElement=modelInlineFootnote))

        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship.clarkNotation):
            if isinstance(modelInlineRel,ModelObject):
                linkrole = modelInlineRel.get("linkRole", XbrlConst.defaultLinkRole)
                if linkrole not in linkPrototypes:
                    linkPrototypes[linkrole] = LinkPrototype(modelIxdsDocument, mdlDoc.xmlRootElement, XbrlConst.qnLinkFootnoteLink, linkrole, sourceElement=modelInlineRel)


    for htmlElement in modelXbrl.ixdsHtmlElements:
        mdlDoc = htmlElement.modelDocument
        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship.clarkNotation):
            if isinstance(modelInlineRel,ModelObject):
                fromLabels = set()
                relHasFromFactsInTarget = relHasToObjectsInTarget = False
                for fromId in modelInlineRel.get("fromRefs","").split():
                    fromLabels.add(fromId)
                    if not relHasFromFactsInTarget and fromId in factsByFactID and factsByFactID[fromId].get("target") == ixdsTarget:
                        relHasFromFactsInTarget = True
                linkrole = modelInlineRel.get("linkRole", XbrlConst.defaultLinkRole)
                arcrole = modelInlineRel.get("arcrole", XbrlConst.factFootnote)
                linkPrototype = linkPrototypes[linkrole]
                for baseSetKey in (("XBRL-footnotes",None,None,None),
                                   ("XBRL-footnotes",linkrole,None,None),
                                   (arcrole,linkrole,XbrlConst.qnLinkFootnoteLink, XbrlConst.qnLinkFootnoteArc),
                                   (arcrole,linkrole,None,None),
                                   (arcrole,None,None,None)):
                    if linkPrototype not in modelXbrl.baseSets[baseSetKey]: # only one link per linkrole
                        if relHasFromFactsInTarget:
                            modelXbrl.baseSets[baseSetKey].append(linkPrototype)
                for fromId in fromLabels:
                    if fromId not in linkModelLocIds[linkrole] and relHasFromFactsInTarget and fromId in factsByFactID:
                        linkModelLocIds[linkrole].add(fromId)
                        locPrototype = LocPrototype(factsByFactID[fromId].modelDocument, linkPrototype, fromId, fromId, sourceElement=modelInlineRel)
                        linkPrototype.childElements.append(locPrototype)
                        linkPrototype.labeledResources[fromId].append(locPrototype)
                toLabels = set()
                toFootnoteIds = set()
                toFactQnames = set()
                fromToMatchedIds = set()
                toIdsNotFound = []
                for toId in modelInlineRel.get("toRefs","").split():
                    if toId in modelInlineFootnotesById:
                        toLabels.add(toId)
                        toFootnoteIds.add(toId)
                        if relHasFromFactsInTarget:
                            modelInlineFootnote = modelInlineFootnotesById[toId]
                            if toId not in linkModelInlineFootnoteIds[linkrole]:
                                linkPrototype.childElements.append(modelInlineFootnote)
                                linkModelInlineFootnoteIds[linkrole].add(toId)
                                linkPrototype.labeledResources[toId].append(modelInlineFootnote)
                                relHasToObjectsInTarget = True
                    elif toId in factsByFactID:
                        toLabels.add(toId)
                        if toId not in linkModelLocIds[linkrole]:
                            modelInlineFact = factsByFactID[toId]
                            if relHasFromFactsInTarget and modelInlineFact.get("target") != ixdsTarget:
                                # copy fact to target when not there
                                if ixdsTarget:
                                    modelInlineFact.set("target", ixdsTarget)
                                else:
                                    modelInlineFact.attrib.pop("target", None)
                                addItemFactToTarget(modelInlineFact)
                                locateFactInTuple(modelInlineFact, tuplesByTupleID, modelInlineFact.modelDocument.ixNStag)
                            if modelInlineFact.get("target") == ixdsTarget:
                                linkModelLocIds[linkrole].add(toId)
                                locPrototype = LocPrototype(factsByFactID[toId].modelDocument, linkPrototype, toId, toId, sourceElement=modelInlineRel)
                                toFactQnames.add(str(locPrototype.dereference().qname))
                                linkPrototype.childElements.append(locPrototype)
                                linkPrototype.labeledResources[toId].append(locPrototype)
                                relHasToObjectsInTarget = True
                    else:
                        toIdsNotFound.append(toId)
                    if toId in fromLabels:
                        fromToMatchedIds.add(toId)
                if relHasFromFactsInTarget and relHasToObjectsInTarget:
                    modelXbrl.targetRelationships.add(modelInlineRel)
                if toIdsNotFound:
                    modelXbrl.error(ixMsgCode("relationshipToRef", ns=XbrlConst.ixbrl11, name="relationship", sect="validation"),
                                    _("Inline relationship toRef(s) %(toIds)s not found."),
                                    modelObject=modelInlineRel, toIds=', '.join(sorted(toIdsNotFound)))
                if fromToMatchedIds:
                    modelXbrl.error(ixMsgCode("relationshipFromToMatch", ns=XbrlConst.ixbrl11, name="relationship", sect="validation"),
                                    _("Inline relationship has matching values in fromRefs and toRefs: %(fromToMatchedIds)s"),
                                    modelObject=modelInlineRel, fromToMatchedIds=', '.join(sorted(fromToMatchedIds)))
                for fromLabel in fromLabels:
                    for toLabel in toLabels: # toLabels is empty if no to fact or footnote is in target
                        linkPrototype.childElements.append(ArcPrototype(modelIxdsDocument, linkPrototype, XbrlConst.qnLinkFootnoteArc,
                                                                        fromLabel, toLabel,
                                                                        linkrole, arcrole,
                                                                        modelInlineRel.get("order", "1"), sourceElement=modelInlineRel))
                if toFootnoteIds and toFactQnames:
                    modelXbrl.error(ixMsgCode("relationshipReferencesMixed", ns=XbrlConst.ixbrl11, name="relationship", sect="validation"),
                                    _("Inline relationship references footnote(s) %(toFootnoteIds)s and thereby is not allowed to reference %(toFactQnames)s."),
                                    modelObject=modelInlineRel, toFootnoteIds=', '.join(sorted(toFootnoteIds)),
                                    toFactQnames=', '.join(sorted(toFactQnames)))

    del modelInlineFootnotesById, linkPrototypes, linkModelInlineFootnoteIds # dereference

    # check for multiple use of continuation reference (same continuationAt on different elements)
    for _contAt, _contReferences in continuationReferences.items():
        if len(_contReferences) > 1:
            _refEltQnames = set(str(_contRef.elementQname) for _contRef in _contReferences)
            modelXbrl.error(ixMsgCode("continuationReferences", ns=XbrlConst.ixbrl11, name="continuation", sect="validation"),
                            _("continuedAt %(continuedAt)s has %(referencesCount)s references on %(sourceElements)s elements, only one reference allowed."),
                            modelObject=_contReferences, continuedAt=_contAt, referencesCount=len(_contReferences),
                            sourceElements=', '.join(str(qn) for qn in sorted(_refEltQnames)))

    # check for orphan or mis-located continuation elements
    for _contAt, _contElt in continuationElements.items():
        if _contAt not in continuationReferences:
            modelXbrl.error(ixMsgCode("continuationNotReferenced", ns=XbrlConst.ixbrl11, name="continuation", sect="validation"),
                            _("ix:continuation %(continuedAt)s is not referenced by a, ix:footnote, ix:nonNumeric or other ix:continuation element."),
                            modelObject=_contElt, continuedAt=_contAt)
        if XmlUtil.ancestor(_contElt, _contElt.modelDocument.ixNS, "hidden") is not None:
            modelXbrl.error(ixMsgCode("ancestorNodeDisallowed", ns=XbrlConst.ixbrl11, name="continuation", sect="constraint"),
                            _("ix:continuation %(continuedAt)s may not be nested in an ix:hidden element."),
                            modelObject=_contElt, continuedAt=_contAt)

    if ixdsTarget in modelXbrl.ixTargetRootElements:
        modelIxdsDocument.targetXbrlRootElement = modelXbrl.ixTargetRootElements[ixdsTarget]
        modelIxdsDocument.targetXbrlElementTree = PrototypeElementTree(modelIxdsDocument.targetXbrlRootElement)

    for pluginMethod in pluginClassMethods("ModelDocument.IxdsTargetDiscovered"):
        pluginMethod(modelXbrl, modelIxdsDocument)

class LoadingException(Exception):
    pass

class ModelDocumentReference:
    def __init__(self, referenceType, referringModelObject=None):
        self.referenceTypes = {referenceType}
        self.referringModelObject = referringModelObject

    @property
    def referringXlinkRole(self):
        if "href" in self.referenceTypes and isinstance(self.referringModelObject, ModelObject):
            return self.referringModelObject.get("{http://www.w3.org/1999/xlink}role")
        return None
