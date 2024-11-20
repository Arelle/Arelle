"""
See COPYRIGHT.md for copyright information.

## Overview

The Load OIM Taxonomy plugin is designed to load taxonomy objects from JSON that adheres to the Open Information
Model (OIM) Taxonomy Specification.

## Usage Instructions

Any import or direct opening of a JSON-specified taxonomy behaves the same as if loading from an xsd taxonomy or xml linkbases

"""
import os, sys, io, time, traceback, json, logging, zipfile, datetime, isodate
import regex as re
from math import isnan, log10
from lxml import etree
from collections import defaultdict, OrderedDict
from arelle.ModelDocument import Type, create as createModelDocument, load as loadModelDocument
from arelle.ModelDtsObject import ModelResource
from arelle import XbrlConst, ModelDocument, ModelXbrl, PackageManager, ValidateXbrlDimensions
from arelle.ModelObject import ModelObject
from arelle.PluginManager import pluginClassMethods
from arelle.ModelValue import qname, dateTime, DateTime, DATETIME, yearMonthDuration, dayTimeDuration
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.oim.Load import (OIMException, NotOIMException, EMPTY_DICT, EMPTY_LIST, NoRecursionCheck,
                             CheckPrefix, WhitespaceUntrimmedPattern,
                             URIType, QNameType, LangType, URIType, SQNameType
                             )
from arelle.PythonUtil import attrdict, flattenToSet, strTruncate
from arelle.UrlUtil import isHttpUrl, isAbsolute as isAbsoluteUri, isValidUriReference
from arelle.ValidateDuplicateFacts import DuplicateTypeArg, getDuplicateFactSetsWithType
from arelle.Version import authorLabel, copyrightLabel
from arelle.XbrlConst import (xbrli, qnLinkLabel, standardLabelRoles, qnLinkReference, standardReferenceRoles,
                              qnLinkPart, gen, link, defaultLinkRole, footnote, factFootnote, isStandardRole,
                              conceptLabel, elementLabel, conceptReference, all as hc_all, notAll as hc_notAll,
                              xhtml, qnXbrliDateItemType,
                              dtrPrefixedContentItemTypes, dtrPrefixedContentTypes, dtrSQNameNamesItemTypes, dtrSQNameNamesTypes,
                              lrrRoleHrefs, lrrArcroleHrefs)
from arelle.XmlUtil import addChild, addQnameValue, copyIxFootnoteHtml, setXmlns
from arelle.XmlValidateConst import VALID
from arelle.XmlValidate import integerPattern, languagePattern, NCNamePattern, QNamePattern, validate as xmlValidate
from arelle.ValidateXbrlCalcs import inferredDecimals, rangeValue

saveOIMTaxonomySchemaFiles = False

ClarkQNamePattern = re.compile(
    r"\{[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
     r"[_\-\."
     r"\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*\}"
    "[_A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
     r"[_\-\."
     "\xB7A-Za-z0-9\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\u0300-\u036F\u203F-\u2040]*")


jsonDocumentTypes = (
        "https://xbrl.org/PWD/2023-05-17/cti",
    )

UnrecognizedDocMemberTypes = {
    "/documentInfo": dict,
    "/documentInfo/documentType": str,
    }
UnrecognizedDocRequiredMembers = {
    "/": {"documentInfo", "taxonomy"},
    "/documentInfo/": {"documentType","documentName"},
    }

JsonMemberTypes = {
    # keys are json pointer with * meaning any id,  and *:* meaning any SQName or QName, for array no index is used
    # report
    "/documentInfo": dict,
    "/taxonomy": dict,
    "/*:*": (int,bool,str,dict,list,type(None),NoRecursionCheck,CheckPrefix), # custom extensions
    # documentInfo
    "/documentInfo/documentType": str,
    "/documentInfo/namespaces": list,
    "/documentInfo/namespaces/*": dict,
    "/documentInfo/namespaces/*/prefix": str,
    "/documentInfo/namespaces/*/uri": URIType,
    "/documentInfo/*:*": (int,float,bool,str,dict,list,type(None),NoRecursionCheck,CheckPrefix), # custom extensions
    # taxonomy
    "/taxonomy/*": dict,
    "/taxonomy/*/name": str,
    "/taxonomy/*/namespace": (URIType,type(None)),
    "/taxonomy/*/entryPoint": str,

    "/taxonomy/*/importedTaxonomies": list,
    "/taxonomy/*/importedTaxonomies/*": dict,
    "/taxonomy/*/importedTaxonomies/*/entryPoint": URIType,
    "/taxonomy/*/importedTaxonomies/*/namespace": URIType,

    "/taxonomy/*/concepts": list,
    "/taxonomy/*/concepts/*": dict,
    "/taxonomy/*/concepts/*/abstract": bool,
    "/taxonomy/*/concepts/*/balance": (str,type(None)),
    "/taxonomy/*/concepts/*/name": QNameType,
    "/taxonomy/*/concepts/*/dataType": QNameType,
    "/taxonomy/*/concepts/*/nillable": bool,
    "/taxonomy/*/concepts/*/periodType": str,
    "/taxonomy/*/concepts/*/substitutionGroup": QNameType,

    "/taxonomy/*/networks": list,
    "/taxonomy/*/networks/*": dict,
    "/taxonomy/*/networks/*/name": str,
    "/taxonomy/*/networks/*/description": str,
    "/taxonomy/*/networks/*/networkURI": URIType,
    "/taxonomy/*/concepts/*/order": (int,float),
    "/taxonomy/*/networks/*/relationships": list,
    "/taxonomy/*/networks/*/relationships/*": dict,
    "/taxonomy/*/networks/*/relationships/*/order": (int,float),
    "/taxonomy/*/networks/*/relationships/*/weight": (int,float),
    "/taxonomy/*/networks/*/relationships/*/preferredLabel": (QNameType,type(None)),
    "/taxonomy/*/networks/*/relationships/*/source": QNameType,
    "/taxonomy/*/networks/*/relationships/*/target": QNameType,

    "/taxonomy/*/labels": list,
    "/taxonomy/*/labels/*": dict,
    "/taxonomy/*/labels/*/labelType": URIType,
    "/taxonomy/*/labels/*/value": str,
    "/taxonomy/*/labels/*/language": LangType,
    "/taxonomy/*/labels/*/relatedID": list,
    "/taxonomy/*/labels/*/relatedID/*": QNameType,

    "/taxonomy/*/references": list,
    "/taxonomy/*/references/*": dict,
    "/taxonomy/*/references/*/referenceType": URIType,
    "/taxonomy/*/references/*/parts": list,
    "/taxonomy/*/references/*/parts/*": dict,
    "/taxonomy/*/references/*/parts/*/name": QNameType,
    "/taxonomy/*/references/*/parts/*/order": (int,float),
    "/taxonomy/*/references/*/parts/*/value": (int,float,str,type(None)),

    "/taxonomy/*/cubes": list,
    "/taxonomy/*/cubes/*": dict,
    "/taxonomy/*/cubes/*/networkURI": URIType,
    "/taxonomy/*/cubes/*/name": QNameType,
    "/taxonomy/*/cubes/*/cubeType": str,
    "/taxonomy/*/cubes/*/dimensions": list,
    "/taxonomy/*/cubes/*/dimensions/*": dict,
    "/taxonomy/*/cubes/*/dimensions/*/dimensionType": str,
    "/taxonomy/*/cubes/*/dimensions/*/dimensionConcept": QNameType,
    "/taxonomy/*/cubes/*/dimensions/*/domainID": str,

    "/taxonomy/*/domains": list,
    "/taxonomy/*/domains/*": dict,
    "/taxonomy/*/domains/*/networkURI": URIType,
    "/taxonomy/*/domains/*/domainConcept": QNameType,
    "/taxonomy/*/domains/*/domainID": str,
    "/taxonomy/*/domains/*/relationships": list,
    "/taxonomy/*/domains/*/relationships/*": dict,
    "/taxonomy/*/domains/*/relationships/*/source": QNameType,
    "/taxonomy/*/domains/*/relationships/*/target": QNameType,
    "/taxonomy/*/domains/*/relationships/*/order": (int,float),

    "/taxonomy/*/networks": list,
    "/taxonomy/*/networks/*": dict,
    "/taxonomy/*/networks/*/networkURI": URIType,
    "/taxonomy/*/networks/*/name": str,
    "/taxonomy/*/networks/*/description": str,
    "/taxonomy/*/networks/*/order": (int,float),
    "/taxonomy/*/networks/*/relationships": list,
    "/taxonomy/*/networks/*/relationships/*": dict,
    "/taxonomy/*/networks/*/relationships/*/source": QNameType,
    "/taxonomy/*/networks/*/relationships/*/target": QNameType,
    "/taxonomy/*/networks/*/relationships/*/relationshipType": URIType,
    "/taxonomy/*/networks/*/relationships/*/order": (int,float),
    "/taxonomy/*/networks/*/relationships/*/weight": (int,float,type(None)),

    # custom properties on taxonomy are unchecked
    "/taxonomy/*/*:*": (int,float,bool,str,dict,list,type(None),NoRecursionCheck,CheckPrefix), # custom extensions
    }
JsonRequiredMembers = {
    "/": {"documentInfo"},
    "/documentInfo/": {"documentType","namespaces"},
    "/taxonomy/*/": {"name", "namespace","entryPoint"},
    "/taxonomy/*/networks/*/": {"name", "networkURI", "relationships"},
    "/taxonomy/*/networks/*/relationships/*/": {"relationshipType", "source","target"},
    "/taxonomy/*/labels/*/": {"labelType", "value", "language"},
    "/taxonomy/*/references/*/": {"referenceType"},

    "/facts/*/dimensions/": {"concept"}
    }

EMPTY_SET = set()

NS_XBRL = "https://xbrl.org/2021"

QN_SCHEMA = qname("{http://www.w3.org/2001/XMLSchema}xs:schema")
QN_ANNOTATION = qname("{http://www.w3.org/2001/XMLSchema}xs:annotation")
QN_APPINFO = qname("{http://www.w3.org/2001/XMLSchema}xs:appinfo")
QN_IMPORT = qname("{http://www.w3.org/2001/XMLSchema}xs:import")
QN_ELEMENT = qname("{http://www.w3.org/2001/XMLSchema}xs:element")
QN_PERIOD_TYPE = qname("{http://www.xbrl.org/2003/instance}xbrli:periodType")
QN_BALANCE = qname("{http://www.xbrl.org/2003/instance}xbrli:balance")
QN_SUBS_GROUP = qname("{http://www.w3.org/2001/XMLSchema}xs:substitutionGroup")
QN_ROLE_TYPE = qname("{http://www.xbrl.org/2003/linkbase}link:roleType")
QN_ROLE_TYPE = qname("{http://www.xbrl.org/2003/linkbase}link:roleType")
QN_DEFINITION = qname("{http://www.xbrl.org/2003/linkbase}link:definition")
QN_USED_ON = qname("{http://www.xbrl.org/2003/linkbase}link:usedOn")

QN_PRIMARY_DIMENSION = qname(f"{NS_XBRL}xbrl:PrimaryDimension")
QN_PERIOD_DIMENSION = qname(f"{NS_XBRL}xbrl:PeriodDimension")

def jsonGet(tbl, key, default=None):
    if isinstance(tbl, dict):
        return tbl.get(key, default)
    return default

def loadOIMTaxonomy(cntlr, error, warning, modelXbrl, oimFile, mappedUri):
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocumentReference
    from arelle.ModelValue import qname

    _return = None # modelDocument or an exception

    try:
        currentAction = "initializing"
        startingErrorCount = len(modelXbrl.errors) if modelXbrl else 0
        startedAt = time.time()

        currentAction = "loading and parsing OIM Taxonomy file"
        loadDictErrors = []
        def ldError(msgCode, msgText, **kwargs):
            loadDictErrors.append((msgCode, msgText, kwargs))

        errPrefix = "xbrlte"
        try:
            _file = modelXbrl.fileSource.file(oimFile, encoding="utf-8-sig")[0]
            with _file as f:
                oimObject = json.load(f)
        except UnicodeDecodeError as ex:
            raise OIMException("{}:invalidJSON".format(errPrefix),
                  _("File MUST use utf-8 encoding: %(file)s, error %(error)s"),
                  file=oimFile, error=str(ex))
        except json.JSONDecodeError as ex:
            raise OIMException("{}:invalidJSON".format(errPrefix),
                    "JSON error while %(action)s, %(file)s, error %(error)s",
                    file=oimFile, action=currentAction, error=ex)
        # identify document type (JSON or CSV)
        documentInfo = jsonGet(oimObject, "documentInfo", {})
        documentType = jsonGet(documentInfo, "documentType")
        taxonomyObj = jsonGet(oimObject, "taxonomy", {})
        if documentType not in jsonDocumentTypes:
            error("oimce:unsupportedDocumentType",
                  _("Unrecognized /documentInfo/docType: %(documentType)s"),
                  documentType=documentType)
            return {}
        oimRequiredMembers = JsonRequiredMembers
        oimMemberTypes = JsonMemberTypes

        invalidMemberTypes = []
        invalidQNames = []
        missingRequiredMembers = []
        unexpectedMembers = []
        def showPathObj(parts, obj): # this can be replaced with jsonPath syntax if appropriate
            try:
                shortObjStr = json.dumps(obj)
            except TypeError:
                shortObjStr = str(obj)
            if len(shortObjStr) > 34:
                shortObjStr = "{:.32}...".format(shortObjStr)
            return "/{}={}".format("/".join(str(p) for p in parts), shortObjStr)
        def checkMemberTypes(obj, path, pathParts):
            if (isinstance(obj,dict)):
                for missingMbr in oimRequiredMembers.get(path,EMPTY_SET) - obj.keys():
                    missingRequiredMembers.append(path + missingMbr)
                for mbrName, mbrObj in obj.items():
                    mbrPath = path + mbrName
                    pathParts.append(mbrName)
                    # print("mbrName {} mbrObj {}".format(mbrName, mbrObj))
                    if mbrPath in oimMemberTypes:
                        mbrTypes = oimMemberTypes[mbrPath]
                        if (mbrTypes is SQNameType or (isinstance(mbrTypes,tuple) and SQNameType in mbrTypes)):
                            if not isinstance(mbrObj, str) or not SQNamePattern.match(mbrObj):
                                invalidSQNames.append(showPathObj(pathParts, mbrObj))
                        elif (not ((mbrTypes is QNameType or (isinstance(mbrTypes,tuple) and QNameType in mbrTypes)) and isinstance(mbrObj, str) and ClarkQNamePattern.match(mbrObj)) and
                            not ((mbrTypes is LangType or (isinstance(mbrTypes,tuple) and LangType in mbrTypes)) and isinstance(mbrObj, str) and languagePattern.match(mbrObj)) and
                            not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and URIType in mbrTypes)) and isinstance(mbrObj, str) and isValidUriReference(mbrObj) and not WhitespaceUntrimmedPattern.match(mbrObj)) and
                            #not (mbrTypes is IdentifierType and isinstance(mbrObj, str) and isinstance(mbrObj, str) and IdentifierPattern.match(mbrObj)) and
                            not ((mbrTypes is int or (isinstance(mbrTypes,tuple) and int in mbrTypes)) and isinstance(mbrObj, str) and CanonicalIntegerPattern.match(mbrObj)) and
                            not isinstance(mbrObj, mbrTypes)):
                            invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                    elif ":" in mbrName and path + "*:*" in oimMemberTypes:
                        _mbrTypes = oimMemberTypes[path + "*:*"]
                        if not (QNamePattern.match(mbrName) and isinstance(mbrObj, _mbrTypes)):
                            invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                        elif isinstance(_mbrTypes,tuple):
                            if CheckPrefix in _mbrTypes:
                                extensionProperties[mbrName] = showPathObj(pathParts, mbrObj)
                            if NoRecursionCheck in _mbrTypes:
                                continue # custom types, block recursive check
                        mbrPath = path + "*:*" # for recursion
                    elif path + "*" in oimMemberTypes:
                        mbrTypes = oimMemberTypes[path + "*"]
                        if (not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and isinstance(mbrObj, str) and URIType in mbrTypes)) and isValidUriReference(mbrObj)) and
                            not isinstance(mbrObj, mbrTypes)):
                            invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                        if isinstance(mbrTypes,tuple) and KeyIsNcName in mbrTypes and not NCNamePattern.match(mbrName):
                            invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                        mbrPath = path + "*" # for recursion
                    else:
                        unexpectedMembers.append(showPathObj(pathParts, mbrObj))
                    if isinstance(mbrObj, (dict,list)):
                        checkMemberTypes(mbrObj, mbrPath + "/", pathParts)
                    pathParts.pop() # remove mbrName
            if (isinstance(obj,list)):
                mbrNdx = 1
                for mbrObj in obj:
                    mbrPath = path # list entry just uses path ending in /
                    pathParts.append(mbrNdx)
                    if mbrPath in oimMemberTypes:
                        mbrTypes = oimMemberTypes[mbrPath]
                        if (not (mbrTypes is IdentifierType and isinstance(mbrObj, str) and isinstance(mbrObj, str) and IdentifierPattern.match(mbrObj)) and
                            not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and URIType in mbrTypes)) and isinstance(mbrObj, str) and isValidUriReference(mbrObj) and not WhitespaceUntrimmedPattern.match(mbrObj)) and
                            not isinstance(mbrObj, mbrTypes)):
                            invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                    if isinstance(mbrObj, (dict,list)):
                        checkMemberTypes(mbrObj, mbrPath + "/", pathParts)
                    pathParts.pop() # remove mbrNdx
                    mbrNdx += 1
        errorIndexBeforeLoadOim = len(modelXbrl.errors)
        checkMemberTypes(oimObject, "/", [])
        numErrorsBeforeJsonCheck = len(modelXbrl.errors)
        msg = []
        if missingRequiredMembers:
            msg.append(_("Required element(s) are missing from metadata: %(missing)s"))
        if unexpectedMembers:
            msg.append(_("Unexpected element(s) in metadata: %(unexpected)s"))
        error("{}:invalidJSONStructure".format(errPrefix),
              "\n ".join(msg), documentType=documentType,
              sourceFileLine=oimFile, missing=", ".join(missingRequiredMembers), unexpected=", ".join(unexpectedMembers))

        currentAction = "identifying Metadata objects"
        taxonomyRefs = taxonomyObj.get("importedTaxonomies", EMPTY_LIST)

        # import referenced taxonomies
        txBase = os.path.dirname(oimFile)

        # create the instance document
        currentAction = "creating schema"
        prevErrLen = len(modelXbrl.errors) # track any xbrl validation errors
        if modelXbrl: # pull loader implementation
            modelXbrl.blockDpmDBrecursion = True
            schemaDoc = _return = createModelDocument(
                  modelXbrl,
                  Type.SCHEMA,
                  oimFile,
                  initialComment="loaded from OIM Taxonomy {}".format(mappedUri),
                  documentEncoding="utf-8",
                  # base=txBase or modelXbrl.entryLoadingUrl
                  )
            schemaDoc.inDTS = True
        else: # API implementation
            modelXbrl = ModelXbrl.create(
                cntlr.modelManager,
                Type.SCHEMA,
                initialComment="loaded from OIM Taxonomy {}".format(mappedUri),
                base=txBase)
            _return = modelXbrl.modelDocument
        schemaDoc.targetNamespace = taxonomyObj.get("namespace")
        if len(modelXbrl.errors) > prevErrLen:
            error("oime:invalidTaxonomy",
                  _("Unable to obtain a valid taxonomy from URLs provided"),
                  modelObject=modelXbrl)
        schemaElt = schemaDoc.xmlRootElement
        annotationElt = addChild(schemaElt, QN_ANNOTATION)
        appinfoElt = addChild(annotationElt, QN_APPINFO)

        if not any(t["namespace"] == "http://www.xbrl.org/2003/instance" for t in taxonomyRefs):
            taxonomyRefs.insert(0, {"namespace":"http://www.xbrl.org/2003/instance", "entryPoint":"http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd"})
        if "cubes" in taxonomyObj and not any(t["namespace"] == "http://xbrl.org/2005/xbrldt" for t in taxonomyRefs):
            taxonomyRefs.insert(0, {"namespace":"http://xbrl.org/2005/xbrldt", "entryPoint": "http://www.xbrl.org/2005/xbrldt-2005.xsd"})
        for txmyRefObj in taxonomyRefs:
            schemaDoc.addDocumentReference(
                loadModelDocument(modelXbrl, txmyRefObj.get("entryPoint"), txBase, namespace=txmyRefObj.get("namespace"), isDiscovered=True),
                "import")
            addChild(schemaElt, QN_IMPORT, attributes={
                "namespace": txmyRefObj.get("namespace"),
                "schemaLocation": txmyRefObj.get("entryPoint")})

        namespacePrefixes = {}
        prefixNamespaces = {}
        for nsObj in documentInfo.get("namespaces", EMPTY_DICT):
            ns = nsObj.get("uri","")
            prefix = nsObj.get("prefix","")
            if ns and prefix:
                namespacePrefixes[ns] = prefix
                prefixNamespaces[prefix] = ns
                setXmlns(schemaDoc, prefix, ns)
        # additional namespaces needed
        for prefix, ns in (("xlink", "http://www.w3.org/1999/xlink"),
                           ("ref", "http://www.xbrl.org/2006/ref"),
                           ("xbrldt", "http://xbrl.org/2005/xbrldt"),
                           ("xbrl", NS_XBRL)):
            if ns not in namespacePrefixes:
                namespacePrefixes[ns] = prefix
                prefixNamespaces[prefix] = ns
                setXmlns(schemaDoc, prefix, ns)



        ##### Move to end
        currentAction = "identifying default dimensions"
        if modelXbrl is not None:
            ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults

        currentAction = "creating concepts"
        conceptObjs = taxonomyObj.get("concepts", [])
        conceptNum = 0 # for synthetic concept number
        syntheticConceptFormat = "_f{{:0{}}}".format(int(log10(len(conceptObjs) or 1))) #want

        numConceptCreationXbrlErrors = 0

        for conceptI, conceptObj in enumerate(conceptObjs):
            nillable = conceptObj.get("nillable", True)
            dataType = conceptObj.get("dataType", True)
            periodType = conceptObj.get("periodType", True)
            balance = conceptObj.get("balance", None)
            abstract = conceptObj.get("abstract", False)
            name = qname(conceptObj.get("name", ""), prefixNamespaces)
            if name:
                substitutionGroup = qname(conceptObj.get("substitutionGroup", ""), prefixNamespaces)
                attributes = {"id": f"{name.prefix}_{name.localName}",
                              "name": name.localName}
                if periodType:
                    attributes[QN_PERIOD_TYPE.clarkNotation] = periodType
                if balance:
                    attributes[QN_BALANCE.clarkNotation] = balance
                attributes["substitutionGroup"] = str(substitutionGroup)
    
                conceptElt = addChild(schemaElt,
                                      QN_ELEMENT,
                                      attributes=attributes)
            else:
                error("oimte:invalidConceptName",
                      "%(path)s concept name %(name)s is not valid",
                      modelObject=modelXbrl, path=f"taxonomy/concept[{conceptI+1}]", name=conceptObj.get("name", ""))

        # find which linkbases networkURIs are used on
        usedOn = defaultdict(set)
        for dimObj in taxonomyObj.get("cubes", []) + taxonomyObj.get("domains", []):
            networkURI = dimObj.get("networkURI", "")
            if networkURI:
                usedOn[networkURI].add("link:definitionLink")
        for networkObj in taxonomyObj.get("networks", []) + taxonomyObj.get("domains", []):
            networkURI = networkObj.get("networkURI", "")
            if networkURI:
                for relObj in networkObj.get("relationships", []):
                    relType = relObj.get("relationshipType", "")
                    if relType == XbrlConst.parentChild:
                        usedOn[networkURI].add("link:presentationLink")
                    elif relType in XbrlConst.summationItems:
                        usedOn[networkURI].add("link:calculationLink")
                    elif relType in (XbrlConst.requiresElement, XbrlConst.generalSpecial):
                        usedOn[networkURI].add("link:definitionLink")

        # define role types
        for objI, networkObj in enumerate(taxonomyObj.get("networks", []) + taxonomyObj.get("domains", [])):
            name = networkObj.get("name", "")
            description = networkObj.get("description", "")
            networkURI = networkObj.get("networkURI", "")

            roleTypeElt = addChild(appinfoElt, QN_ROLE_TYPE,
                                   attributes={"id": name or f"_roleType_{objI+1}",
                                               "roleURI": networkURI})
            if description:
                addChild(roleTypeElt, QN_DEFINITION, text=description)
            for u in usedOn[networkURI]:
                addChild(roleTypeElt, QN_USED_ON, text=u)

        # create ELRs
        lbElts = []
        xlinkLabelFormat = "{{}}{{:0{}}}".format(int(log10(len(taxonomyObj.get("labels", [])) or 1)))
        locXlinkLabels = {}
        hrefsNsWithoutPrefix = defaultdict(list)
        def locXlinkLabel(elrElt, conceptRef, path):
            if conceptRef not in locXlinkLabels:
                qn = qname(conceptRef, prefixNamespaces)
                if qn is None:
                    error("oimte:invalidConceptRef",
                          "%(path)s concept reference %(conceptRef)s is not a defined prefix or not a valid qname",
                          modelObject=modelXbrl, path=path, conceptRef=conceptRef)
                elif qn.namespaceURI not in namespacePrefixes:
                    hrefsNsWithoutPrefix[qn.namespaceURI or "(none)"].append(path)
                concept = modelXbrl.qnameConcepts.get(qn)
                xlinkLabel = xlinkLabelFormat.format("loc", len(locXlinkLabels)+1)
                locXlinkLabels[conceptRef] = xlinkLabel
                if concept is not None:
                    addChild(elrElt, XbrlConst.qnLinkLoc,
                             attributes={"{http://www.w3.org/1999/xlink}label": xlinkLabel,
                                         "{http://www.w3.org/1999/xlink}href": f"{concept.modelDocument.uri}#{concept.id}",
                                         "{http://www.w3.org/1999/xlink}type": "locator"})
                else:
                    error("oimte:invalidConceptQName",
                          "%(path)s concept reference %(conceptRef)s, qname %(qname)s, does not correspond to a defined concept",
                          modelObject=modelXbrl, path=path, qname=qn, conceptRef=conceptRef)
            return locXlinkLabels[conceptRef]
        lbElt = addChild(appinfoElt, XbrlConst.qnLinkLinkbase,
                         attributes={"id":"_labels_"})
        lbElts.append(lbElt)
        elrElt = addChild(lbElt, XbrlConst.qnLinkLabelLink,
                         attributes={"{http://www.w3.org/1999/xlink}role": XbrlConst.defaultLinkRole,
                                     "{http://www.w3.org/1999/xlink}type": "extended"})
        for labelI, labelObj in enumerate(taxonomyObj.get("labels", [])):
            labelType = labelObj.get("labelType", "")
            value = labelObj.get("value", "")
            language = labelObj.get("language", "")
            relatedID = labelObj.get("relatedID", [])
            xlinkLbl = xlinkLabelFormat.format("label", labelI+1)
            addChild(elrElt, XbrlConst.qnLinkLabel, text=value,
                     attributes={# "id": xlinkLbl,
                                 "{http://www.w3.org/1999/xlink}label": xlinkLbl,
                                 "{http://www.w3.org/1999/xlink}role": labelType,
                                 "{http://www.w3.org/1999/xlink}lang": language,
                                 "{http://www.w3.org/1999/xlink}type": "resource"})
            for refI, ref in enumerate(relatedID):
                addChild(elrElt, XbrlConst.qnLinkLabelArc,
                         attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, ref, f"label[{labelI}]/relatedID[{refI}]"),
                                     "{http://www.w3.org/1999/xlink}to": xlinkLbl,
                                     "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.conceptLabel,
                                     "{http://www.w3.org/1999/xlink}type": "arc"})

        domainIDHypercubeQNames = {}
        domainIDPrimaryDimensions = {}
        domainIDPeriodDimensions = {}
        lbElt = addChild(appinfoElt, XbrlConst.qnLinkLinkbase)
        lbElts.append(lbElt)
        for cubeI, cubeObj in enumerate(taxonomyObj.get("cubes", [])):
            locXlinkLabels.clear() # separate locs per elr
            networkURI = cubeObj.get("networkURI", "") # ELR
            hypercubeConcept = cubeObj.get("name", "") # hypercube concept clark name
            cubeType = cubeObj.get("cubeType", "")
            elrElt = addChild(lbElt, XbrlConst.qnLinkDefinitionLink,
                             attributes={"{http://www.w3.org/1999/xlink}role": networkURI,
                                         "{http://www.w3.org/1999/xlink}type": "extended"})
            for dimI, dimObj in enumerate(cubeObj.get("dimensions", [])):
                dimensionType = dimObj.get("dimensionType", "")
                domainID = dimObj.get("domainID", "")
                dimensionType = dimObj.get("dimensionType", "")
                dimensionConcept = dimObj.get("dimensionConcept", "")
                if dimensionConcept == "xbrl:PrimaryDimension":
                    domainIDPrimaryDimensions[domainID] = hypercubeConcept
                elif dimensionConcept == "xbrl:PeriodDimension":
                    domainIDPeriodDimensions[domainID] = hypercubeConcept
                else:
                    domainIDHypercubeQNames[domainID] = hypercubeConcept
                    addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                             attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, hypercubeConcept, f"cube[{cubeI}]/cube.name"),
                                         "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, dimensionConcept, f"cube[{cubeI}]/dimension[{dimI}]/dimensionConcept"),
                                         "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.hypercubeDimension,
                                         "{http://www.w3.org/1999/xlink}type": "arc"})

        for domI, domObj in enumerate(taxonomyObj.get("domains", [])):
            locXlinkLabels.clear() # separate locs per elr
            networkURI = domObj.get("networkURI", "")
            domainID = domObj.get("domainID", "")
            domainConcept = domObj.get("domainConcept", "")
            relationships = domObj.get("relationships", [])
            elrElt = addChild(lbElt, XbrlConst.qnLinkDefinitionLink,
                             attributes={"{http://www.w3.org/1999/xlink}role": networkURI,
                                         "{http://www.w3.org/1999/xlink}type": "extended"})
            if domainID not in domainIDPrimaryDimensions and domainID not in domainIDPeriodDimensions:
                addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                         attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, domainIDHypercubeQNames.get(domainID), f"domain[{domI}]/domainID"),
                                     "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, domainConcept, f"domain[{domI}]/domainConcept"),
                                     "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.dimensionDomain,
                                     "{http://www.w3.org/1999/xlink}type": "arc"})
            for relI, relObj in enumerate(relationships):
                source = relObj.get("source", "")
                target = relObj.get("target", "")
                order = relObj.get("order", "1")
                if domainID in domainIDPrimaryDimensions and relI == 0:
                    addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                             attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, target, f"domain[{domI}]/relationship[{relI}/target"),
                                         "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, domainIDPrimaryDimensions.get(domainID), f"domain[{domI}]/domainID"),
                                         "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.all,
                                         "{http://www.w3.org/1999/xlink}type": "arc"})
                else:
                    addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                             attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, source, f"domain[{domI}]/relationship[{relI}/source"),
                                         "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, target, f"domain[{domI}]/relationship[{relI}/target"),
                                         "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.domainMember,
                                         "{http://www.w3.org/1999/xlink}type": "arc",
                                         "order": order})

        lbElt = addChild(appinfoElt, XbrlConst.qnLinkLinkbase)
        lbElts.append(lbElt)
        for networkI, networkObj in enumerate(taxonomyObj.get("networks", [])):
            locXlinkLabels.clear() # separate locs per elr
            networkURI = networkObj.get("networkURI", "")
            elrElt = addChild(lbElt, XbrlConst.qnLinkDefinitionLink,
                             attributes={"{http://www.w3.org/1999/xlink}role": networkURI,
                                         "{http://www.w3.org/1999/xlink}type": "extended"})
            relationships = networkObj.get("relationships", [])
            for relI, relObj in enumerate(relationships):
                source = relObj.get("source", "")
                target = relObj.get("target", "")
                order = relObj.get("order", None)
                relationshipType = relObj.get("relationshipType", "")
                preferredLabel = relObj.get("preferredLabel", None)
                weight = relObj.get("weight", None)
                attributes = {"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, source, f"network[{networkI}]/relationship[{relI}/source"),
                              "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, target, f"network[{networkI}]/relationship[{relI}/target"),
                              "{http://www.w3.org/1999/xlink}arcrole": relationshipType,
                              "{http://www.w3.org/1999/xlink}type": "arc"}
                if weight is not None:
                    attributes["weight"] = weight
                if preferredLabel is not None:
                    attributes["preferredLabel"] = preferredLabel
                addChild(elrElt, XbrlConst.qnLinkDefinitionArc, attributes)

        locXlinkLabels.clear() # separate locs per elr
        elrElt = addChild(lbElt, XbrlConst.qnLinkReferenceLink,
                         attributes={"{http://www.w3.org/1999/xlink}role": XbrlConst.defaultLinkRole,
                                     "{http://www.w3.org/1999/xlink}type": "extended"})
        for refI, refObj in enumerate(taxonomyObj.get("references", [])):
            referenceType = refObj.get("referenceType", "")
            relatedIDs = refObj.get("relatedID", "")
            xlinkLbl = xlinkLabelFormat.format("reference", refI+1)
            refElt = addChild(elrElt, XbrlConst.qnLinkReference,
                              attributes={"{http://www.w3.org/1999/xlink}label": xlinkLbl,
                                          "{http://www.w3.org/1999/xlink}role": referenceType,
                                          "{http://www.w3.org/1999/xlink}type": "resource"})
            for partObj in sorted(refObj.get("parts", []), key=lambda o:refObj.get("order", 0)):
                name = partObj.get("name", "")
                value = partObj.get("value", "")
                partI = partObj.get("order", "")
                addChild(refElt, qname(name, prefixNamespaces), text=value)
            for relatedID in relatedIDs:
                addChild(elrElt, XbrlConst.qnLinkLabelArc,
                         attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, relatedID, f"reference[{refI}]/relatedID"),
                                     "{http://www.w3.org/1999/xlink}to": xlinkLbl,
                                     "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.conceptReference,
                                     "{http://www.w3.org/1999/xlink}type": "arc"})

        # discover linkbases
        for lbElt in lbElts:
            schemaDoc.linkbaseDiscover(lbElt)

        # errors
        for hrefNs, paths in sorted(hrefsNsWithoutPrefix.items(), key=lambda i:i[0]):
            error("oimte:missingConceptRefPrefx",
                  "Namespace has no prefix %(namespace)s in %(paths)s",
                  modelObject=modelXbrl, namespace=hrefNs, paths=", ".join(paths))

        # save schema files if specified
        if saveOIMTaxonomySchemaFiles:
            schemaDoc.save(schemaDoc.filepath.replace(".json", "-json.xsd"))

        return schemaDoc

    except NotOIMException as ex:
        _return = ex # not an OIM document
    except Exception as ex:
        _return = ex
        if isinstance(ex, OIMException):
            if ex.code and ex.message:
                error(ex.code, ex.message, modelObject=modelXbrl, **ex.msgArgs)
        else:
            error("arelleOIMloader:error",
                    "Error while %(action)s, error %(errorType)s %(error)s\n traceback %(traceback)s",
                    modelObject=modelXbrl, action=currentAction, errorType=ex.__class__.__name__, error=ex,
                    traceback=traceback.format_tb(sys.exc_info()[2]))

    global lastFilePath, lastFilePath
    lastFilePath = None
    lastFilePathIsOIM = False
    return _return

lastFilePath = None
lastFilePathIsOIM = False

def isOimTaxonomyLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    global lastFilePath, lastFilePathIsOIM
    lastFilePath = None
    lastFilePathIsOIM = False
    _ext = os.path.splitext(filepath)[1]
    if _ext == ".json":
        with io.open(filepath, 'rt', encoding='utf-8') as f:
            _fileStart = f.read(4096)
        if _fileStart and re.match(r"\s*\{.*\"documentType\"\s*:\s*\"https://xbrl.org/PWD/[0-9]{4}-[0-9]{2}-[0-9]{2}/cti\"", _fileStart, flags=re.DOTALL):
            lastFilePathIsOIM = True
            lastFilePath = filepath
    return lastFilePathIsOIM

def oimTaxonomyLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if filepath != lastFilePath or not lastFilePathIsOIM:
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading OIM taxonomy file: {0}").format(os.path.basename(filepath)))
    doc = loadOIMTaxonomy(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri)
    if doc is None:
        return None # not an OIM file
    return doc

def optionsExtender(parser, *args, **kwargs):
    parser.add_option("--saveOIMschemafile",
                      action="store_true",
                      dest="saveOIMTaxonomySchemaFiles",
                      help=_("Save each OIM taxonomy file an xsd named -json.xsd."))
def filingStart(self, options, *args, **kwargs):
    global saveOIMTaxonomySchemaFiles
    if options.saveOIMTaxonomySchemaFiles:
        saveOIMTaxonomySchemaFiles = True

__pluginInfo__ = {
    'name': 'Load OIM Taxonomy',
    'version': '1.2',
    'description': "This plug-in loads XBRL taxonomy objects from JSON.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': optionsExtender,
    'CntlrCmdLine.Filing.Start': filingStart,
    'ModelDocument.IsPullLoadable': isOimTaxonomyLoadable,
    'ModelDocument.PullLoader': oimTaxonomyLoader
}
