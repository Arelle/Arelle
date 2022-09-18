'''
Created on Oct 3, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, io, sys, traceback
from collections import defaultdict
from decimal import Decimal
from lxml import etree
from xml.sax import SAXParseException
from arelle.arelle_c import genobj, ModelObject, QName
from arelle import (arelle_c, PackageManager, XbrlConst, XmlUtil, UrlUtil, ValidateFilingText, 
                    XhtmlValidate, XmlValidateSchema, ModelTestcaseObject)
from arelle.ModelValue import qname
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact
from arelle.PrototypeDtsObject import LinkPrototype, LocPrototype, ArcPrototype, DocumentPrototype
from arelle.PluginManager import pluginClassMethods
from arelle.PythonUtil import OrderedDefaultDict, OrderedSet, Fraction 
ModelRssObject = None
ModelVersReport = None
from arelle.XhtmlValidate import ixMsgCode
from arelle.XmlValidate import UNVALIDATED, VALID, validate as xmlValidate

creationSoftwareNames = None

def load(modelXbrl, url, base=None, referringElement=None, isEntry=False, isDiscovered=False, isIncluded=None, namespace=None, reloadCache=False, **kwargs):
    """Returns a new modelDocument, performing DTS discovery for instance, inline XBRL, schema, 
    linkbase, and versioning report entry urls.
    
    :param url: Identification of file to load by string filename or by a FileSource object with a selected content file.
    :type url: str or FileSource
    :param referringElement: Source element causing discovery or loading of this document, such as an import or xlink:href
    :type referringElement: ModelObject
    :param isEntry: True for an entry document
    :type isEntry: bool
    :param isDiscovered: True if this document is discovered by XBRL rules, otherwise False (such as when schemaLocation and xmlns were the cause of loading the schema)
    :type isDiscovered: bool
    :param isIncluded: True if this document is the target of an xs:include
    :type isIncluded: bool
    :param namespace: The schema namespace of this document, if known and applicable
    :type isSupplemental: True if this document is supplemental (not discovered or in DTS but adds labels or instance facts)
    :type namespace: str
    :param reloadCache: True if desired to reload the web cache for any web-referenced files.
    :type reloadCache: bool
    :param checkModifiedTime: True if desired to check modifed time of web cached entry point (ahead of usual time stamp checks).
    :type checkModifiedTime: bool
    """
    
    global ModelRssObject, ModelVersReport
    if ModelRssObject is None:
        from arelle.ModelRssObject import ModelRssObject
        from arelle.ModelVersReport import ModelVersReport
    if referringElement is None: # used for error messages
        referringElement = modelXbrl
    normalizedUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(url, base)
    modelDocument = modelXbrl.urlDocs.get(normalizedUrl)
    if modelDocument:
        # if it wasn't previously in DTS but is being discovered here, mark it inDTS
        if not modelDocument.inDTS and isDiscovered:
            modelDocument.inDTS = True
        return modelDocument
    elif modelXbrl.urlUnloadableDocs.get(normalizedUrl):  # only return None if in this list and marked True (really not loadable)
        return None

    if isEntry:
        modelXbrl.entryLoadingUrl = normalizedUrl   # for error loggiong during loading
        modelXbrl.url = normalizedUrl
        modelXbrl.urlDir = os.path.dirname(normalizedUrl)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.urlDir = os.path.dirname(modelXbrl.urlDir)
    if modelXbrl.modelManager.validateDisclosureSystem and \
       not normalizedUrl.startswith(modelXbrl.urlDir) and \
       not modelXbrl.modelManager.disclosureSystem.hrefValid(normalizedUrl):
        blocked = modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences
        if normalizedUrl not in modelXbrl.urlUnloadableDocs:
            # HMRC note, HMRC.blockedFile should be in this list if hmrc-taxonomies.xml is maintained an dup to date
            modelXbrl.error(("EFM.6.22.00", "GFM.1.1.3", "SBR.NL.2.1.0.06" if normalizedUrl.startswith("http") else "SBR.NL.2.2.0.17"),
                    _("Prohibited file for filings %(blockedIndicator)s: %(url)s"),
                    modelObject=referringElement, url=normalizedUrl,
                    blockedIndicator=_(" blocked") if blocked else "",
                    messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
            #modelXbrl.debug("EFM.6.22.02", "traceback %(traceback)s",
            #                modeObject=referringElement, traceback=traceback.format_stack())
            modelXbrl.urlUnloadableDocs[normalizedUrl] = blocked
        if blocked:
            return None
    
    if modelXbrl.modelManager.skipLoading and modelXbrl.modelManager.skipLoading.match(normalizedUrl):
        return None
    
    if modelXbrl.fileSource.isMappedUrl(normalizedUrl):
        mappedUrl = modelXbrl.fileSource.mappedUrl(normalizedUrl)
    elif PackageManager.isMappedUrl(normalizedUrl):
        mappedUrl = PackageManager.mappedUrl(normalizedUrl)
    else:
        mappedUrl = modelXbrl.modelManager.disclosureSystem.mappedUrl(normalizedUrl)
        
    if isEntry:
        modelXbrl.entryLoadingUrl = mappedUrl   # for error loggiong during loading
        
    # don't try reloading if not loadable
    
    if modelXbrl.fileSource.isInArchive(mappedUrl):
        filepath = mappedUrl
    else:
        filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(mappedUrl, reload=reloadCache, checkModifiedTime=kwargs.get("checkModifiedTime",False))
        if filepath:
            url = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(filepath)
    if filepath is None: # error such as HTTPerror is already logged
        if modelXbrl.modelManager.abortOnMajorError and (isEntry or isDiscovered):
            modelXbrl.error("FileNotLoadable",
                    _("File can not be loaded: %(fileName)s \nLoading terminated."),
                    modelObject=referringElement, fileName=mappedUrl)
            raise LoadingException()
        if normalizedUrl not in modelXbrl.urlUnloadableDocs:
            if "referringElementUrl" in kwargs:
                modelXbrl.error("FileNotLoadable",
                        _("File can not be loaded: %(fileName)s, referenced from %(referencingFileName)s"),
                        modelObject=referringElement, fileName=normalizedUrl, referencingFileName=kwargs["referringElementUrl"])
            else:
                modelXbrl.error("FileNotLoadable",
                        _("File can not be loaded: %(fileName)s"),
                        modelObject=referringElement, fileName=normalizedUrl)
            modelXbrl.urlUnloadableDocs[normalizedUrl] = True # always blocked if not loadable on this error
        return None
    
    isPullLoadable = any(pluginMethod(modelXbrl, mappedUrl, normalizedUrl, filepath, isEntry=isEntry, namespace=namespace, **kwargs)
                         for pluginMethod in pluginClassMethods("ModelDocument.IsPullLoadable"))
    
    if not isPullLoadable and os.path.splitext(filepath)[1] in (".xlsx", ".xls", ".csv", ".json"):
        modelXbrl.error("FileNotLoadable",
                _("File can not be loaded, requires loadFromExcel or loadFromOIM plug-in: %(fileName)s"),
                modelObject=referringElement, fileName=normalizedUrl)
        return None
    
    
    # load XML and determine type of model document
    modelXbrl.modelManager.showStatus(_("parsing {0}").format(url))
    try:
        current_activity = "plugins class ModelDocument.PullLoader"
        for pluginMethod in pluginClassMethods("ModelDocument.PullLoader"):
            # assumes not possible to check file in string format or not all available at once
            modelDocument = pluginMethod(modelXbrl, normalizedUrl, filepath, isEntry=isEntry, namespace=namespace, **kwargs)
            if isinstance(modelDocument, Exception):
                return None
            if modelDocument is not None:
                return modelDocument
        current_activity = "opening FileSource"
        if not modelXbrl.fileSource.exists(filepath):
            if kwargs.get("notErrorIfNoFile"):
                return None
            raise EnvironmentError
        if (modelXbrl.modelManager.validateDisclosureSystem and 
            modelXbrl.modelManager.disclosureSystem.validateFileText and
            not normalizedUrl in modelXbrl.modelManager.disclosureSystem.standardTaxonomiesDict):
            fileSrcObj = ValidateFilingText.checkfile(modelXbrl,filepath)
        else:
            fileSrcObj = modelXbrl.fileSource.file(filepath, bytesOrLocalpathObj=True)
        fileSrcObj.url = normalizedUrl
        if normalizedUrl != fileSrcObj.filepath:
            modelXbrl.mappedUrls[fileSrcObj.filepath] = normalizedUrl
        xmlDocument = None
        isPluginParserDocument = False
        current_activity = "plugins class ModelDocument.CustomLoader"
        for pluginMethod in pluginClassMethods("ModelDocument.CustomLoader"):
            modelDocument = pluginMethod(modelXbrl, fileSrcObj, mappedUrl, filepath)
            if modelDocument is not None:
                return modelDocument
        if modelXbrl.cntlr.traceToStdout: print("identifying file contents and type {} isDiscovered {}".format(os.path.basename(fileSrcObj.filepath), isDiscovered))
        current_activity = "identifying file contents and type"
        identifiedDoc = modelXbrl.identifyXmlFile(fileSrcObj)
        if modelXbrl.cntlr.traceToStdout: print("identified {}".format(identifiedDoc))
        current_activity = "done identifying file contents and type"
        
        if identifiedDoc.errors:
            for error in identifiedDoc.errors:
                modelXbrl.error("xerces:{}".format(error.level),
                        _("%(error)s, %(fileName)s, line %(line)s, column %(column)s, %(sourceAction)s source element"),
                        modelObject=referringElement, fileName=os.path.basename(url), 
                        error=error.message, line=error.line, column=error.column, sourceAction=("including" if isIncluded else "importing"))
            return None
        
        if identifiedDoc.type == "unknown XML":
            isDiscovered = False # only schemas and linkbases can be discovered
            #modelXbrl.error("xmlSchema:unidentifiedInput",
            #        _("XML file type was not identified."),
            #        modelObject=referringElement, fileName=os.path.basename(url))
            #return None
            
        current_activity = "creating ModelDocument object"
        modelDocument = {"rss": ModelRssObject,
                         "versioning-report": ModelVersReport}.get(identifiedDoc.type, 
            ModelDocument)(modelXbrl, Type.nameType(identifiedDoc.type), normalizedUrl, fileSrcObj.filepath)
            
        if ((isEntry and identifiedDoc.type in ("schema", "linkbase", "instance", "inline XBRL instance") )
            or isDiscovered):
            modelDocument.inDTS = True
            
        if modelXbrl.cntlr.traceToStdout: print("load {}".format(os.path.basename(fileSrcObj.filepath)))
                        
        if identifiedDoc.type == "schema":
            if identifiedDoc.hasXmlBase:
                    if modelXbrl.modelManager.validateDisclosureSystem:
                        modelXbrl.error(("EFM.6.03.11", "GFM.1.1.7", "EBA.2.1", "EIOPA.2.1"),
                            _("Prohibited base attribute: %(attribute)s"),
                            edgarCode="du-0311-Xml-Base-Used",
                            modelObject=element, attribute="in schema file", element="in schema file")
            modelDocument.targetNamespace = modelXbrl.internString(identifiedDoc.targetNamespace)
            modelDocument.targetNamespacePrefix = modelXbrl.internString(identifiedDoc.targetNamespacePrefix)
            modelDocument.elementDeclIds = identifiedDoc.elementDeclIds
            modelDocument.annotationInfos = identifiedDoc.annotationInfos
            modelDocument.schemaXmlBase = identifiedDoc.schemaXmlBase
            # load appinfo-parsing grammar before any schema (so it's already in grammar pool before processing annotations)
            for hrefXsdSchemaRef in XbrlConst.hrefScheamImports:
                load(modelXbrl, hrefXsdSchemaRef)
            # load dependent linkbaseRefs
            current_activity = "loading DTS schema references"
            for base, href in identifiedDoc.schemaRefs:
                load(modelXbrl, href, base=modelDocument.baseForHref(base), isDiscovered=modelDocument.inDTS)
            current_activity = "loading schema non-DTS schema references"
            for base, href in identifiedDoc.nonDtsSchemaRefs:
                load(modelXbrl, href, base=modelDocument.baseForHref(base))
            # load schema grammar
            current_activity = "xerces schema parsing"
            if normalizedUrl not in modelXbrl.resolvedUrls: # may have been loaded by xerces already
                if modelXbrl.cntlr.traceToStdout: print("modelDocument.loadSchema call {}".format(modelDocument.targetNamespace))
                modelDocument.loadSchema(fileSrcObj, isIncluded, namespace)
            else: # already loaded by xerces indicate the document exists to cython layer
                if modelXbrl.cntlr.traceToStdout: print("modelDocument already-loadedSchema set targetNamespaceDocs {}".format(modelDocument.targetNamespace))
                modelXbrl.targetNamespaceDocs[modelDocument.targetNamespace].append(modelDocument)
            current_activity = "loading schema linkbaseRefs"
            if modelXbrl.cntlr.traceToStdout: print("modelDocument load linkbaseRefs")
            for base, href in identifiedDoc.linkbaseRefs: # OrderedSet in document order of reference
                hrefUrl, hrefId = UrlUtil.splitDecodeFragment(href)
                if hrefUrl != "":
                    load(modelXbrl, hrefUrl, base=modelDocument.baseForHref(base), isDiscovered=modelDocument.inDTS)
            # create modelDocuments for any dependent grammar (namespaces) imported by this loadSchema
            if modelXbrl.cntlr.traceToStdout: print("modelDocument load schema dependencies")
            if normalizedUrl in modelXbrl.resolvedUrls:
                current_activity = "loading schema dependencies"
                for requestType in range(1,4): # 1=SchemaImport, 2=SchemaInclude, 3=SchemaRedefine
                    for dependentUrl in modelXbrl.resolvedUrls[normalizedUrl][requestType]:
                        if dependentUrl not in modelXbrl.urlDocs:
                            load(modelXbrl, dependentUrl, 
                                 isDiscovered=modelDocument.inDTS and requestType != 4,
                                 isIncluded=requestType == 2,
                                 namespace=modelDocument.targetNamespace if requestType != 1 else None)
                        if requestType == 3 and not normalizedUrl.startswith("http://www.xbrl.org"):
                            # allow redefines in  http://www.xbrl.org/2013/inlineXBRL/xhtml-inlinexbrl-1_1-modules.xsd
                            modelXbrl.error("xbrl.5.6.1:Redefine",
                                            "Redefine is not allowed, schemaLocation: %(schemaLocation)s",
                                            modelObject=modelDocument, schemaLocation=dependentUrl)
            if modelXbrl.cntlr.traceToStdout: print("modelDocument load schema dependencies done")

        elif identifiedDoc.type in ("linkbase", "instance", "inline XBRL instance"):
            schemaLocations = []
                # load(modelXbrl, schemaLocations[1], namespace=schemaLocations[0]) # load inline schema ahead of any other references
            if identifiedDoc.type in ("linkbase", "instance"):
                schemaLocations.append(XbrlConst.link)
                schemaLocations.append(XbrlConst.hrefLink)
                schemaLocations.append(XbrlConst.xml) # needed for xml attribute validation
                schemaLocations.append(XbrlConst.hrefXml)
                if XbrlConst.hrefLink not in identifiedDoc.schemaRefs and ("",XbrlConst.hrefLink) not in identifiedDoc.nonDtsSchemaRefs:
                    identifiedDoc.nonDtsSchemaRefs.add(("",XbrlConst.hrefLink))
            if identifiedDoc.type in ("instance", "inline XBRL instance"):
                schemaLocations.append(XbrlConst.xbrli)
                schemaLocations.append(XbrlConst.hrefXbrli)
                if XbrlConst.hrefXbrli not in identifiedDoc.schemaRefs:
                    identifiedDoc.nonDtsSchemaRefs.add(("",XbrlConst.hrefXbrli))
                schemaLocations.append(XbrlConst.xbrldi)
                schemaLocations.append(XbrlConst.hrefXbrldi)
                if XbrlConst.hrefXbrldi not in identifiedDoc.schemaRefs:
                    identifiedDoc.nonDtsSchemaRefs.add(("",XbrlConst.hrefXbrldi))
            # load schemaRefs and linkbaseRefs
            current_activity = "loading linkbaseRefs and schemaRefs"
            for refs in (identifiedDoc.schemaRefs, identifiedDoc.linkbaseRefs): # OrderedSets in document order
                for base, href in refs:
                    if href != "": # href "" is reference to containing document
                        load(modelXbrl, href, base=modelDocument.baseForHref(base), isDiscovered=modelDocument.inDTS)
            #assert modelXbrl.testXercesIntegrity("after load schema/LB refs"), "Xerces integrity after load schema/LB refs"
            for base, href in identifiedDoc.nonDtsSchemaRefs:
                if href != XbrlConst.hrefIxbrl11 and href.endswith(XbrlConst.hrefIxbrl11xsd): # superfluous, don't load and remap for xerces resolver
                    modelXbrl.mappedUrls[href] = XbrlConst.hrefIxbrl11
                else:
                    load(modelXbrl, href, base=modelDocument.baseForHref(base))
            #assert modelXbrl.testXercesIntegrity("after load extraSchema refs"), "Xerces integrity after load extraSchema refs"
            # add all referenced document schemaRefs
            current_activity = "loading schema grammar"
            priorXsModelGeneration = modelXbrl.xsModelGeneration
            for i in range(100): 
                modelXbrl.loadSchemaGrammar()
                if priorXsModelGeneration == modelXbrl.xsModelGeneration:
                    break # model may change as assertions cause recursive discovery
                priorXsModelGeneration = modelXbrl.xsModelGeneration
            current_activity = "testXercesIntegrity after loading schema grammar"
            assert modelXbrl.testXercesIntegrity("after loadSchemaGrammar"), "Xerces integrity after loadSchemaGrammar"
            resolvedUrlLogLen = len(modelXbrl.resolvedUrlLog)
            #modelXbrl.loadXml(modelDocument, fileDesc, schemaLocations)
            current_activity = "parse xml file"
            # skip validation for unrecognized xml files without schemq references
            skipValidation = identifiedDoc.type == "unknown XML" and not identifiedDoc.nonDtsSchemaRefs
            if modelXbrl.cntlr.traceToStdout: print("loadXml call {}".format(url))
            modelDocument.loadXml(fileSrcObj, schemaLocations, skipValidation)
            if modelXbrl.cntlr.traceToStdout: print("finished loadXml call {}".format(url))
            current_activity = "testXercesIntegrity after parse xml file"
            assert modelXbrl.testXercesIntegrity("after loadXml"), "Xerces integrity after loadXml"
            # discovered hrefs from loc elements 
            loadedDocsBeforeHrefResolution = set(doc for doc in modelXbrl.urlDocs.values())
            current_activity = "resolve hrefs from loc elements"
            modelDocument.resolveHrefs()
            current_activity = "testXercesIntegrity after resolve hrefs from loc elements"
            assert modelXbrl.testXercesIntegrity("after resolveHrefs"), "Xerces integrity after resolveHrefs"
            # schemaRef'ed non-discovered schemas
            for _referencingUrl, _referenceType, _referencedUrl in modelXbrl.resolvedUrlLog[resolvedUrlLogLen:]:
                pass # non-DTS schemaLocation-referenced schema
        elif identifiedDoc.type in ("unknown XML", "testcase", "testcases index", "rss", "arcs infoset", "fact dimensions infoset"):
            current_activity = "loading " + identifiedDoc.type
            hasLoadedNonDtsSchemaRef = any(
                load(modelXbrl, href, base=modelDocument.baseForHref(base), notErrorIfNoFile=True)
                for base, href in identifiedDoc.nonDtsSchemaRefs)
            modelXbrl.loadSchemaGrammar()
            modelDocument.loadXml(fileSrcObj, [], not hasLoadedNonDtsSchemaRef) # no schemaLocations, skipValidation
        else:
            modelXbrl.error("arelle:unsupportedDocument",
                    _("XML document type \"%(documentType)s\" is not yet supported with arelle-Cython."),
                    modelObject=referringElement, documentType=identifiedDoc.type)
            return None
        # process imported schemas
        if isEntry:
            current_activity = "loading schema grammar"
            modelXbrl.loadSchemaGrammar()
            # discovered hrefs from loc elements 
            for doc in sorted(modelXbrl.urlDocs.values(), key=lambda d: d.objectIndex):
                doc.resolveHrefs()
            if modelXbrl.cntlr.traceToStdout: print("finished loadSchemaGrammar call for isEntry")
            current_activity = "testing Xerces integrity after loading schema grammar"
            assert modelXbrl.testXercesIntegrity("after loading entry schema grammar"), "Xerces integrity after loading entry schema grammar"
        if identifiedDoc.type == "inline XBRL instance":
            modelDocument.inlineXbrlDiscover(modelDocument.xmlRootElement)
            assert modelXbrl.testXercesIntegrity("before inlineXbrlDiscover"), "Xerces integrity after inlineXbrlDiscover"
            if isEntry:
                current_activity = "inline IXDS discovery"
                inlineIxdsDiscover(modelXbrl, modelDocument)
                assert modelXbrl.testXercesIntegrity("before inlineIxdsDiscover"), "Xerces integrity after inlineIxdsDiscover"
        elif identifiedDoc.type == "instance":
            if modelXbrl.cntlr.traceToStdout: print("instance loaded")
        elif identifiedDoc.type == "testcase":
            modelDocument.testcaseDiscover(modelDocument.xmlRootElement)
        elif identifiedDoc.type == "testcases index":
            modelDocument.testcasesIndexDiscover(modelDocument.xmlRootElement)
        return modelDocument
        
    except (EnvironmentError, RuntimeError, KeyError) as err:  # missing zip file raises KeyError
        # retry in case of well known schema locations
        if not isIncluded and namespace and namespace in XbrlConst.standardNamespaceSchemaLocations and url != XbrlConst.standardNamespaceSchemaLocations[namespace]:
            return load(modelXbrl, XbrlConst.standardNamespaceSchemaLocations[namespace], 
                        base, referringElement, isEntry, isDiscovered, isIncluded, namespace, reloadCache)
        if modelXbrl.modelManager.abortOnMajorError and (isEntry or isDiscovered):
            modelXbrl.error("IOerror",
                _("%(fileName)s: file error: %(error)s \nLoading terminated."),
                modelObject=referringElement, fileName=os.path.basename(url), error=str(err))
            raise LoadingException()
        #import traceback
        #if modelXbrl.cntlr.traceToStdout: print("traceback {}".format(traceback.format_tb(sys.exc_info()[2])))
        modelXbrl.error("IOerror",
                _("%(fileName)s: file error while %(currentActivity)s: %(error)s"),
                modelObject=referringElement, fileName=os.path.basename(url), error=str(err), currentActivity=current_activity,)
        modelXbrl.debug("IOerror", "traceback %(traceback)s",
                        modeObject=referringElement, traceback=traceback.format_tb(sys.exc_info()[2]))
        modelXbrl.urlUnloadableDocs[normalizedUrl] = True  # not loadable due to IO issue
        return None
    except (etree.LxmlError, etree.XMLSyntaxError,
            SAXParseException,
            ValueError) as err:  # ValueError raised on bad format of qnames, xmlns'es, or parameters
        if not isEntry and str(err) == "Start tag expected, '<' not found, line 1, column 1":
            return ModelDocument(modelXbrl, Type.UnknownNonXML, normalizedUrl, filepath, None)
        else:
            modelXbrl.error("xmlSchema:syntax",
                    _("Unrecoverable error: %(error)s, %(fileName)s, %(sourceAction)s source element"),
                    modelObject=referringElement, fileName=os.path.basename(url), 
                    error=str(err), sourceAction=("including" if isIncluded else "importing"), exc_info=True)
            modelXbrl.urlUnloadableDocs[normalizedUrl] = True  # not loadable due to parser issues
            return None
    except Exception as err:
        modelXbrl.error(type(err).__name__,
                _("Unrecoverable error while %(currentActivity)s: %(error)s, %(fileName)s, %(sourceAction)s source element"),
                modelObject=referringElement, fileName=os.path.basename(url), currentActivity=current_activity,
                error=str(err), sourceAction=("including" if isIncluded else "importing"), exc_info=True)
        modelXbrl.urlUnloadableDocs[normalizedUrl] = True  # not loadable due to exception issue
        return None

def loadSchemalocatedSchema(modelXbrl, element, relativeUrl, namespace, baseUrl):
    if namespace == XbrlConst.xhtml: # block loading xhtml as a schema (e.g., inline which is xsd validated instead)
        return None
    importSchemaLocation = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(relativeUrl, baseUrl)
    doc = load(modelXbrl, importSchemaLocation, isIncluded=False, isDiscovered=False, namespace=namespace, referringElement=element, referringElementUrl=baseUrl)
    if doc:
        if doc.targetNamespace != namespace:
            modelXbrl.error("xmlSchema1.4.2.3:refSchemaNamespace",
                _("SchemaLocation of %(fileName)s expected namespace %(namespace)s found targetNamespace %(targetNamespace)s"),
                modelObject=element, fileName=baseUrl,
                namespace=namespace, targetNamespace=doc.targetNamespace)
        else:
            doc.inDTS = False
    return doc
            
def create(modelXbrl, type, url, schemaRefs=None, isEntry=False, initialXml=None, initialComment=None, base=None, discover=True, documentEncoding="utf-8"):
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
    normalizedUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(url, base)
    if isEntry:
        modelXbrl.url = normalizedUrl
        modelXbrl.entryLoadingUrl = normalizedUrl
        modelXbrl.urlDir = os.path.dirname(normalizedUrl)
        for i in range(modelXbrl.modelManager.disclosureSystem.maxSubmissionSubdirectoryEntryNesting):
            modelXbrl.urlDir = os.path.dirname(modelXbrl.urlDir)
    filepath = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUrl, filenameOnly=True)
    if initialComment:
        initialComment = "<!--" + initialComment + "-->"
    # XML document has nsmap root element to replace nsmap as new xmlns entries are required
    if initialXml and type in (Type.INSTANCE, Type.SCHEMA, Type.LINKBASE, Type.RSSFEED):
        Xml = '{}{}'.format(initialComment or '', initialXml or '')
    elif type == Type.INSTANCE:
        # modelXbrl.urlDir = os.path.dirname(normalizedUrl)
        Xml = ('{}'
               '<xbrl xmlns="http://www.xbrl.org/2003/instance"'
               ' xmlns:link="http://www.xbrl.org/2003/linkbase"'
               ' xmlns:xlink="http://www.w3.org/1999/xlink">').format(initialComment)
        if schemaRefs:
            for schemaRef in schemaRefs:
                Xml += '<link:schemaRef xlink:type="simple" xlink:href="{0}"/>'.format(schemaRef.replace("\\","/"))
        Xml += '</xbrl>'
    elif type == Type.SCHEMA:
        Xml = ('{}<schema xmlns="http://www.w3.org/2001/XMLSchema" />').format(initialComment)
    elif type == Type.RSSFEED:
        Xml = '<rss version="2.0" />'
    elif type == Type.DTSENTRIES:
        Xml = None
    elif type == Type.INLINEXBRLDOCUMENTSET:
        Xml = initialXml
    else:
        type = Type.UnknownXML
        Xml = initialXml or ''
    if type == Type.RSSFEED:
        from arelle.ModelRssObject import ModelRssObject 
        modelDocument = ModelRssObject(modelXbrl, type, url, filepath)
    else:
        modelDocument = ModelDocument(modelXbrl, type, normalizedUrl, filepath)
    if Xml:
        fileSrcObj = genobj(bytes=Xml.encode(documentEncoding), 
                            filepath=url, 
                            cntlr=modelXbrl.modelManager.cntlr)
        modelDocument.loadXml(fileSrcObj, [], True)
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
    XHTML=2
    firstXBRLtype=3  # first filetype that is XBRL and can hold a linkbase, etc inside it
    SCHEMA=3
    LINKBASE=4
    INSTANCE=5
    INLINEXBRL=6
    lastXBRLtype=6  # first filetype that is XBRL and can hold a linkbase, etc inside it
    DTSENTRIES=7  # multiple schema/linkbase Refs composing a DTS but not from an instance document
    INLINEXBRLDOCUMENTSET=8
    VERSIONINGREPORT=9
    TESTCASESINDEX=10
    TESTCASE=11
    REGISTRY=12
    REGISTRYTESTCASE=13
    XPATHTESTSUITE=14
    RSSFEED=15
    ARCSINFOSET=16
    FACTDIMSINFOSET=17
    
    TESTCASETYPES = (TESTCASESINDEX, TESTCASE, REGISTRY, REGISTRYTESTCASE, XPATHTESTSUITE)

    typeName = ("unknown XML",
                "unknown non-XML",
                "xhtml", 
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
                "fact dimensions infoset")
    
    def nameType(name):
        return Type.typeName.index(name)
    
    def identify(filesource, filepath):
        file, = filesource.file(filepath, stripDeclaration=True, binary=True)
        try:
            for _event, elt in etree.iterparse(file, events=("start",)):
                _type = {"{http://www.xbrl.org/2003/instance}xbrl": Type.INSTANCE,
                         "{http://www.xbrl.org/2003/linkbase}linkbase": Type.LINKBASE,
                         "{http://www.w3.org/2001/XMLSchema}schema": Type.SCHEMA}.get(elt.tag, Type.UnknownXML)
                if _type == Type.UnknownXML and elt.tag.endswith("html") and XbrlConst.ixbrlAll.intersection(elt.nsmap.values()):
                    _type = Type.INLINEXBRL
                break
        except Exception:
            _type = Type.UnknownXML
        file.close()
        return _type

# schema elements which end the include/import scah
schemaBottom = {"element", "attribute", "notation", "simpleType", "complexType", "group", "attributeGroup"}
fractionParts = {"{http://www.xbrl.org/2003/instance}numerator",
                 "{http://www.xbrl.org/2003/instance}denominator"}



class ModelDocument(arelle_c.ModelDocument):
    """
    .. class:: ModelDocment(modelXbrl, type, url, filepath, xmlDocument)

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
    :param url:  The document's source entry URI (such as web site URL)
    :type url: str
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

        .. attribute:: url

        Url as discovered

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
    
    def __init__(self, modelXbrl, type, url, filepath):
        super(ModelDocument, self).__init__(modelXbrl, type, url, filepath)
        self.skipDTS = modelXbrl.skipDTS
        modelXbrl.urlDocs[url] = self
        self.objectIndex = len(modelXbrl.modelObjects)
        modelXbrl.modelObjects.append(self)
        self.hrefObjects = []
        self.schemaLocationElements = set()
        self.referencedNamespaces = set()
        self.referencesDocument = {}
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

    def relativeUrl(self, url): # return url relative to this modelDocument url
        return UrlUtil.relativeUrl(self.url, url)
        
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
                ("url", self.url)) + \
                (("fromDTS", self.fromDTS.url),
                 ("toDTS", self.toDTS.url)
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

    def save(self, overrideFilepath=None, outputZip=None, outputFile=None, updateFileHistory=True, encoding="utf-8", **kwargs):
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
    
    def close(self, visited=None, urlDocs=None):
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
            urlDocs.pop(self.url,None)
            # TBD: clean model objects
            self.__dict__.clear() # dereference everything before clearing xml tree
        except AttributeError:
            pass    # maybe already cloased
        if len(visited) == 1:  # outer call
            while urlDocs:
                urlDocs.popitem()[1].close(visited=visited,urlDocs=urlDocs)
        visited.remove(self)
        super(ModelDocument, self).close() 
        
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
            import json, re
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

    def resolveHrefs(self):
        for modelHref in sorted(self.hrefs.values()): # sort for repeatable runs
            if modelHref.modelDocument is None:
                if modelHref.baseForElement: # neither None nor ''
                    if UrlUtil.isAbsolute(modelHref.baseForElement) or os.path.isabs(modelHref.baseForElement):
                        _base = modelHref.baseForElement
                    else:
                        _base =  os.path.dirname(self.url) + "/" + modelHref.baseForElement
                elif not modelHref.urlWithoutFragment: # refers to self, e.g., href="#foo"
                    modelHref.modelDocument = self
                else:
                    _base =  self.url
            if modelHref.modelDocument is None:
                modelHref.modelDocument = load(self.modelXbrl, modelHref.urlWithoutFragment, base=_base, isDiscovered=modelHref.inDTS)

    def baseForElement(self, element):
        return self.baseForHref(element.baseForElement())
                        
    def baseForHref(self, baseOfHrefElement):
        if baseOfHrefElement: # neither None nor ''
            if UrlUtil.isAbsolute(baseOfHrefElement) or os.path.isabs(baseOfHrefElement):
                return baseOfHrefElement
            else:
                return os.path.dirname(self.url) + "/" + baseOfHrefElement
        return self.url
                        
    def importDiscover(self, localName, attrs): # called from cython
        schemaLocation = element.get("schemaLocation")
        if element.localName in ("include", "redefine"): # add redefine, loads but type definitons of redefine not processed yet (See below)
            importNamespace = self.targetNamespace
            isIncluded = True
        else:
            importNamespace = element.get("namespace")
            isIncluded = False
        if importNamespace and schemaLocation:
            importSchemaLocation = self.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(schemaLocation, self.baseForElement(element))
            if (self.modelXbrl.modelManager.validateDisclosureSystem and 
                    self.modelXbrl.modelManager.disclosureSystem.blockDisallowedReferences and
                    self.modelXbrl.modelManager.disclosureSystem.disallowedHrefOfNamespace(importSchemaLocation, importNamespace)):
                self.modelXbrl.error(("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06" if importSchemaLocation.startswith("http") else "SBR.NL.2.2.0.17"),
                        _("Namespace: %(namespace)s disallowed schemaLocation blocked %(schemaLocation)s"),
                        modelObject=self, namespace=importNamespace, schemaLocation=importSchemaLocation, url=importSchemaLocation,
                        messageCodes=("EFM.6.22.02", "GFM.1.1.3", "SBR.NL.2.1.0.06", "SBR.NL.2.2.0.17"))
                return
            doc = None
            importSchemaLocationBasename = os.path.basename(importNamespace)
            # is there an exact match for importNamespace and url?
            for otherDoc in self.modelXbrl.namespaceDocs[importNamespace]:
                doc = otherDoc
                if otherDoc.url == importSchemaLocation:
                    break
                elif isIncluded:
                    doc = None  # don't allow matching namespace lookup on include (NS is already loaded!)
                elif doc.basename != importSchemaLocationBasename:
                    doc = None  # different file (may have imported a file now being included)
            # if no url match, doc will be some other that matched targetNamespace
            if doc is not None:
                if self.inDTS and not doc.inDTS:
                    doc.inDTS = True    # now known to be discovered
            else:
                doc = load(self.modelXbrl, importSchemaLocation, isDiscovered=self.inDTS, 
                           isIncluded=isIncluded, namespace=importNamespace, referringElement=element,
                           base='' if self.url == self.basename else None)
            if doc is not None and doc not in self.referencesDocument:
                self.referencesDocument[doc] = ModelDocumentReference(localName, attrs)  #import or include
                self.referencedNamespaces.add(importNamespace)
            # future note: for redefine, if doc was just loaded, process redefine type definitions
                

                
    def inlineXbrlDiscover(self, htmlElement):
        ixNS = None
        htmlBase = None
        conflictingNSelts = []
        # find namespace, only 1 namespace
        for inlineElement in htmlElement.iterdescendants():
            if isinstance(inlineElement,arelle_c.ModelObject) and inlineElement.namespaceURI in XbrlConst.ixbrlAll:
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
        # load referenced schemas and linkbases (before validating inline HTML
        # these now discovered by identifyXmlFile and pre-loaded according to ixdsTarget in effect 
        #for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "references"):
        #    self.schemaLinkbaseRefsDiscover(inlineElement)
        #    xmlValidate(self.modelXbrl, inlineElement) # validate instance elements
        # with DTS loaded, now validate inline HTML (so schema definition of facts is available)
        if htmlElement.namespaceURI == XbrlConst.xhtml:  # must validate xhtml
            XhtmlValidate.xhtmlValidate(self.modelXbrl, htmlElement)  # fails on prefixed content
        # may be multiple targets across inline document set
        if not hasattr(self.modelXbrl, "targetRoleRefs"):
            self.modelXbrl.targetRoleRefs = {}     # first inline instance in inline document set
            self.modelXbrl.targetArcroleRefs = {}
        ''' these elements are found in parsing the instance by ModelDocument.pxi
        for inlineElement in htmlElement.iterdescendants(tag=ixNStag + "resources"):
            self.instanceContentsDiscover(inlineElement)
            xmlValidate(self.modelXbrl, inlineElement) # validate instance elements
            for refElement in inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}roleRef"):
                self.modelXbrl.targetRoleRefs[refElement.get("roleURI")] = refElement
                if self.discoverHref(refElement) is None: # discover role-defining schema file
                    self.modelXbrl.error("xmlSchema:requiredAttribute",
                            _("Reference for roleURI href attribute missing or malformed"),
                            modelObject=refElement)
            for refElement in inlineElement.iterchildren("{http://www.xbrl.org/2003/linkbase}arcroleRef"):
                self.modelXbrl.targetArcroleRefs[refElement.get("arcroleURI")] = refElement
                if self.discoverHref(refElement) is None: # discover arcrole-defining schema file
                    self.modelXbrl.error("xmlSchema:requiredAttribute",
                            _("Reference for arcroleURI href attribute missing or malformed"),
                            modelObject=refElement)
        '''
        # subsequent inline elements have to be processed after all of the document set is loaded
        if not hasattr(self.modelXbrl, "ixdsHtmlElements"):
            self.modelXbrl.ixdsHtmlElements = []
        self.modelXbrl.ixdsHtmlElements.append(htmlElement)
        
                
    def factDiscover(self, modelFact, parentModelFacts=None, parentElement=None):
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
    
    def testcasesIndexDiscover(self, rootNode):
        for testcasesElement in rootNode.iter():
            if isinstance(testcasesElement,arelle_c.ModelObject) and testcasesElement.localName in ("testcases", "registries", "testSuite"):
                rootAttr = testcasesElement.get("root")
                if rootAttr:
                    base = os.path.join(os.path.dirname(self.filepath),rootAttr) + os.sep
                else:
                    base = self.filepath
                for testcaseElement in testcasesElement:
                    if isinstance(testcaseElement,arelle_c.ModelObject) and testcaseElement.localName in ("testcase", "registry", "testSetRef"):
                        urlAttr = testcaseElement.get("uri") or testcaseElement.get("file") or testcaseElement.get("{http://www.w3.org/1999/xlink}href")
                        if urlAttr:
                            doc = load(self.modelXbrl, urlAttr, base=base, referringElement=testcaseElement)
                            if doc is not None and doc not in self.referencesDocument:
                                self.referencesDocument[doc] = ModelDocumentReference("testcaseIndex", testcaseElement)
                    elif isinstance(testcaseElement,ModelObject) and testcaseElement.localName in ("testcases", "registries"):
                        urlAttr = testcaseElement.get("uri") or testcaseElement.get("{http://www.w3.org/1999/xlink}href")
                        if urlAttr:
                            doc = load(self.modelXbrl, urlAttr, base=base, referringElement=testcaseElement)
                            if doc is not None and doc not in self.referencesDocument:
                                self.addDocumentReference(doc, "testcaseIndex", testcaseElement)

    def testcaseDiscover(self, testcaseElement):
        isTransformTestcase = testcaseElement.namespaceURI == "http://xbrl.org/2011/conformance-rendering/transforms"
        if XmlUtil.xmlnsprefix(testcaseElement, XbrlConst.cfcn) or isTransformTestcase:
            self.type = Type.REGISTRYTESTCASE
        self.outpath = self.xmlRootElement.get("outpath") or self.filepathdir
        self.testcaseVariations = []
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
        base = self.filepath
        for entryElement in rootNode.iterdescendants(tag="{http://xbrl.org/2008/registry}entry"):
            if isinstance(entryElement,ModelObject): 
                url = XmlUtil.childAttr(entryElement, XbrlConst.registry, "url", "{http://www.w3.org/1999/xlink}href")
                functionDoc = load(self.modelXbrl, url, base=base, referringElement=entryElement)
                if functionDoc is not None:
                    testUrlElt = XmlUtil.child(functionDoc.xmlRootElement, XbrlConst.function, "conformanceTest")
                    if testUrlElt is not None:
                        testurl = testUrlElt.get("{http://www.w3.org/1999/xlink}href")
                        testbase = functionDoc.filepath
                        if testurl is not None:
                            testcaseDoc = load(self.modelXbrl, testurl, base=testbase, referringElement=testUrlElt)
                            if testcaseDoc is not None and testcaseDoc not in self.referencesDocument:
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
def inlineIxdsDiscover(modelXbrl, modelIxdsDocument): 
    # extract for a single target document
    ixdsTarget = getattr(modelXbrl, "ixdsTarget", None)
    # compile inline result set
    ixdsEltById = defaultdict(list)
    ixNS = None
    for htmlElement in modelXbrl.ixdsHtmlElements:
        if not ixNS:
            ixNS = htmlElement.modelDocument.ixNS # first inline namespace
        for elt in htmlElement.iter(ModelObject):
            if elt.id:
                ixdsEltById[elt.id].append(elt)
                
    # check for duplicate IDs
    for id in sorted(id for id, elts in ixdsEltById.items() 
                     if len(elts)>1 and 
                     any(e.elementQName.namespaceURI == ixNS for e in elts)):
        elts = ixdsEltById[id]
        name = elts[0].elementQName.localName # take name of first duplicated element
        modelXbrl.error(ixMsgCode("{}IdDuplication".format(name), elts[0], sect="validation"),
                        _("Inline XBRL element id property matches multiple elements in IXDS, \"%(id)s\": %(qnames)s"),
                        modelObject=elts, id=id, qnames=", ".join(sorted(set(str(e.elementQName) for e in elts))))
             
                
    # TODO: ixdsEltById duplication should be tested here and removed from ValidateXbrlDTS (about line 346 after if name == "id" and attrValue in val.elementIDs)
    footnoteRefs = defaultdict(list)
    tupleElements = []
    continuationElements = {}
    continuationReferences = defaultdict(set) # set of elements that have continuedAt source value
    tuplesByTupleID = {}
    factsByFactID = {} # non-tuple facts
    factTargetIDs = set() # target IDs referenced on facts
    targetReferenceAttrElts = defaultdict(dict) # target dict by attrname of elts
    targetReferenceAttrVals = defaultdict(dict) # target dict by attrname of attr value
    targetReferencePrefixNs = defaultdict(dict) # target dict by prefix, namespace
    targetReferencesIDs = {} # target dict by id of reference elts
    modelInlineFootnotesById = {} # inline 1.1 ixRelationships and ixFootnotes
    hasResources = hasHeader = False
    for htmlElement in modelXbrl.ixdsHtmlElements:  
        mdlDoc = htmlElement.modelDocument
        qnIxContinuation = QName(mdlDoc.ixNS, "ix", "continuation")
        qnIxHeader = QName(mdlDoc.ixNS, "ix", "header")
        qnIxTuple = QName(mdlDoc.ixNS, "ix", "tuple")
        qnIxReferences = QName(mdlDoc.ixNS, "ix", "references")
        qnIxResources = QName(mdlDoc.ixNS, "ix", "resources")
        for modelInlineTuple in htmlElement.iterdescendants(tag=qnIxTuple):
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
        for elt in htmlElement.iterdescendants(tag=qnIxContinuation):
            if isinstance(elt,ModelObject) and elt.id:
                continuationElements[elt.id] = elt
        for elt in htmlElement.iterdescendants(tag=qnIxReferences):
            if isinstance(elt,ModelObject):
                target = elt.get("target")
                targetReferenceAttrsDict = targetReferenceAttrElts[target]
                if elt.attrs:
                    for attrName, attrValue in elt.attrs.items():
                        if attrName.startswith('{') and not attrName.startswith(mdlDoc.ixNStag) and attrName != "{http://www.w3.org/XML/1998/namespace}base":
                            if attrName in targetReferenceAttrsDict:
                                modelXbrl.error(ixMsgCode("referencesAttributeDuplication",ns=mdlDoc.ixNS,name="references",sect="validation"),
                                                _("Inline XBRL ix:references attribute %(name)s duplicated in target %(target)s"),
                                                modelObject=(elt, targetReferenceAttrsDict[attrName]), name=attrName, target=target)
                            else:
                                targetReferenceAttrsDict[attrName] = elt
                                targetReferenceAttrVals[target][attrName] = attrValue    
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
                if elt.nsmap:
                    for _prefix, _ns in elt.nsmap.items():
                        if _prefix in targetReferencePrefixNsDict and _ns != targetReferencePrefixNsDict[_prefix][0]:
                            modelXbrl.error(ixMsgCode("referencesNamespacePrefixConflict",ns=mdlDoc.ixNS,name="references",sect="validation"),
                                            _("Inline XBRL ix:references prefix %(prefix)s has multiple namespaces %(ns1)s and %(ns2)s in target %(target)s"),
                                            modelObject=(elt, targetReferencePrefixNsDict[_prefix][1]), prefix=_prefix, ns1=_ns, ns2=targetReferencePrefixNsDict[_prefix], target=target)
                        else:
                            targetReferencePrefixNsDict[_prefix] = (_ns, elt)

        for hdrElt in htmlElement.iterdescendants(tag=qnIxHeader):
            hasHeader = True
            for elt in hdrElt.iterdescendants(tag=qnIxResources):
                hasResources = True
                for resElt in elt.iterdescendants(XbrlConst.qnXbrliContext,XbrlConst.qnXbrliUnit):
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
    
    # root elements by target
    modelXbrl.ixTargetRootElements = {}
    for target in targetReferenceAttrElts.keys() | {None}: # need default target in case any facts have no or invalid target
        try:
            modelXbrl.ixTargetRootElements[target] = ModelObject(modelIxdsDocument, 
                XbrlConst.qnXbrliXbrl, attrs=targetReferenceAttrVals.get(target),
                nsmap=dict((p,n) for p,(n,e) in targetReferencePrefixNs.get(target,{}).items())) 
        except Exception as err:
            modelXbrl.error(type(err).__name__,
                    _("Unrecoverable error creating target instance: %(error)s"),
                    modelObject=modelXbrl, error=err)
                    
    def locateFactInTuple(modelFact, tuplesByTupleID, qnIxTuple):
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
            for tupleParent in modelFact.iterancestors(tag=qnIxTuple):
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
                        element.set("=continuationElement", contElt)
                        element = contElt # loop to continuation element
                        contAt = element.get("continuedAt")
            # check if any chain element is descendant of another
            chainSet = set(chain)
            for chainElt in chain:
                for chainEltAncestor in chainElt.iterancestors(tag=chainElt.modelDocument.ixNStag + '*'):
                    if chainEltAncestor in chainSet:
                        if chain[0].hasAttr("=continuationElement"):
                            chain[0].delAttr("=continuationElement") # break chain to prevent looping in chain
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
        modelInlineFact.setupTargetInlineFact() # setup for effective target
        modelInlineFact.setInlineFactValue(UNVALIDATED) # invalidate html text value so ix typed value can be set by xmlValidate
        if modelInlineFact.concept is None:
            modelXbrl.error(ixMsgCode("missingReferences", modelInlineFact, name="references", sect="validation"),
                            _("Instance fact missing schema definition: %(qname)s of Inline Element %(localName)s"),
                            modelObject=modelInlineFact, qname=modelInlineFact.qname, localName=modelInlineFact.elementQName)
        elif modelInlineFact.isFraction != (modelInlineFact.localName == "fraction"):
            modelXbrl.error(ixMsgCode("fractionDeclaration", modelInlineFact, name="fraction", sect="validation"),
                            _("Inline XBRL element %(qname)s base type %(type)s mapped by %(localName)s"),
                            modelObject=modelInlineFact, qname=modelInlineFact.qname, localName=modelInlineFact.elementQName,
                            type=modelInlineFact.concept.baseXsdType)
        else:
            mdlDoc.modelXbrl.factsInInstance.add( modelInlineFact )

    for htmlElement in modelXbrl.ixdsHtmlElements:  
        mdlDoc = htmlElement.modelDocument
        qnIxTuple = QName(mdlDoc.ixNS, "ix", "tuple")
        ixNStag = mdlDoc.ixNStag
        # hook up tuples to their container
        for tupleFact in tupleElements:
            locateFactInTuple(tupleFact, tuplesByTupleID, qnIxTuple)
            if tupleFact.get("target") == ixdsTarget:
                addItemFactToTarget(tupleFact) # needs to be in factsInInstance

        for modelInlineFact in htmlElement.iterdescendants(ModelInlineFact): 
            if modelInlineFact.localName != "tuple": # can only process "ix:nonNumeric", "ix:nonFraction", "ix:fraction"
                _target = modelInlineFact.get("target")
                factTargetIDs.add(_target)
                if modelInlineFact.qname is not None: # must have a qname to be in facts
                    if _target == ixdsTarget: # if not the selected target, schema isn't loaded
                        addItemFactToTarget(modelInlineFact)
                    locateFactInTuple(modelInlineFact, tuplesByTupleID, qnIxTuple)
                    locateContinuation(modelInlineFact)
                    for r in modelInlineFact.footnoteRefs:
                        footnoteRefs[r].append(modelInlineFact)
                    if modelInlineFact.id:
                        factsByFactID[modelInlineFact.id] = modelInlineFact
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
            
            # deduplicate and add tuple facts by order
            del tupleFact.modelTupleFacts[:]
            for order,facts in sorted(tupleFact.unorderedTupleFacts.items(), key=lambda i:i[0]):
                if len(facts) > 0:
                    tupleFact.modelTupleFacts.append(facts[0]) # this deduplicates by order number
            
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
                        
        for modelInlineFootnote in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Footnote):
            if isinstance(modelInlineFootnote,ModelObject):
                locateContinuation(modelInlineFootnote)
                modelInlineFootnotesById[modelInlineFootnote.footnoteID] = modelInlineFootnote
  
    # validate particle structure of elements after transformations and established tuple structure
    fractionTermTags = (QName(ixNS, "ix", "numerator"), QName(ixNS, "ix", "denominator"))
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
        for modelInlineFootnote in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrlFootnote):
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
                    linkPrototype = LinkPrototype(mdlDoc, mdlDoc.xmlRootElement, XbrlConst.qnLinkFootnoteLink, linkrole)
                    footnoteLinkPrototypes[linkrole] = linkPrototype
                    for baseSetKey in (("XBRL-footnotes",None,None,None), 
                                       ("XBRL-footnotes",linkrole,None,None),
                                       (arcrole,linkrole,XbrlConst.qnLinkFootnoteLink, XbrlConst.qnLinkFootnoteArc), 
                                       (arcrole,linkrole,None,None),
                                       (arcrole,None,None,None)):
                        modelXbrl.baseSets[baseSetKey].append(linkPrototype)
                # locs
                for modelFact in footnoteRefs[footnoteID]:
                    locPrototype = LocPrototype(mdlDoc, linkPrototype, footnoteLocLabel, modelFact)
                    linkPrototype.childElements.append(locPrototype)
                    linkPrototype.labeledResources[footnoteLocLabel].append(locPrototype)
                # resource
                linkPrototype.childElements.append(modelInlineFootnote)
                linkPrototype.labeledResources[footnoteID].append(modelInlineFootnote)
                # arc
                linkPrototype.childElements.append(ArcPrototype(mdlDoc, linkPrototype, XbrlConst.qnLinkFootnoteArc,
                                                                footnoteLocLabel, footnoteID,
                                                                linkrole, arcrole, sourceElement=modelInlineFootnote))
                
        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship):
            if isinstance(modelInlineRel,ModelObject):
                linkrole = modelInlineRel.get("linkRole", XbrlConst.defaultLinkRole)
                if linkrole not in linkPrototypes:
                    linkPrototypes[linkrole] = LinkPrototype(mdlDoc, mdlDoc.xmlRootElement, XbrlConst.qnLinkFootnoteLink, linkrole, sourceElement=modelInlineRel) 
                    
        
    for htmlElement in modelXbrl.ixdsHtmlElements:  
        mdlDoc = htmlElement.modelDocument
        for modelInlineRel in htmlElement.iterdescendants(tag=XbrlConst.qnIXbrl11Relationship):
            if isinstance(modelInlineRel,ModelObject):
                fromLabels = set()
                relHasFromFactsInTarget = False
                for fromId in modelInlineRel.get("fromRefs",""): # xs:list value
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
                for toId in modelInlineRel.get("toRefs",""): # xs:list value
                    if toId in modelInlineFootnotesById:
                        toLabels.add(toId)
                        toFootnoteIds.add(toId)
                        if relHasFromFactsInTarget:
                            modelInlineFootnote = modelInlineFootnotesById[toId]
                            if toId not in linkModelInlineFootnoteIds[linkrole]:
                                linkPrototype.childElements.append(modelInlineFootnote)
                                linkModelInlineFootnoteIds[linkrole].add(toId)
                                linkPrototype.labeledResources[toId].append(modelInlineFootnote)
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
                                locateFactInTuple(modelInlineFact, tuplesByTupleID, QName(modelInlineFact.modelDocument.ixNS,"ix","tuple"))
                            if modelInlineFact.get("target") == ixdsTarget:
                                linkModelLocIds[linkrole].add(toId)
                                locPrototype = LocPrototype(factsByFactID[toId].modelDocument, linkPrototype, toId, toId, sourceElement=modelInlineRel)
                                toFactQnames.add(str(locPrototype.dereference().qname))
                                linkPrototype.childElements.append(locPrototype)
                                linkPrototype.labeledResources[toId].append(locPrototype)
                    else: 
                        toIdsNotFound.append(toId)
                    if toId in fromLabels:
                        fromToMatchedIds.add(toId)
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
                        linkPrototype.childElements.append(ArcPrototype(mdlDoc, linkPrototype, XbrlConst.qnLinkFootnoteArc,
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
            _refEltQnames = set(str(_contRef.elementQName) for _contRef in _contReferences)
            modelXbrl.error(ixMsgCode("continuationReferences", ns=XbrlConst.ixbrl11, name="continuation", sect="validation"),
                            _("continuedAt %(continuedAt)s has %(referencesCount)s references on %(sourceElements)s elements, only one reference allowed."),
                            modelObject=_contReferences, continuedAt=_contAt, referencesCount=len(_contReferences), 
                            sourceElements=', '.join(str(qn) for qn in sorted(_refEltQnames)))

    # check for orphan continuation elements
    for _contAt, _contElt in continuationElements.items():
        if _contAt not in continuationReferences:
            modelXbrl.error(ixMsgCode("continuationNotReferenced", ns=XbrlConst.ixbrl11, name="continuation", sect="validation"),
                            _("ix:continuation %(continuedAt)s is not referenced by a, ix:footnote, ix:nonNumeric or other ix:continuation element."),
                            modelObject=_contElt, continuedAt=_contAt)
    
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
