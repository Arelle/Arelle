"""
See COPYRIGHT.md for copyright information.

## Overview

The OIM Taxonomy plugin is designed to load taxonomy objects from JSON that adheres to the Open Information
Model (OIM) Taxonomy Specification.

## Usage Instructions

Any import or direct opening of a JSON-specified taxonomy behaves the same as if loading from an xsd taxonomy or xml linkbases

For debugging, saves the xsd objects loaded from the OIM taxonomy if
  command line: specify --saveOIMschemafile
  GUIL provide a formula parameter named saveOIMschemafile (value not null or false)x

"""

from typing import TYPE_CHECKING, cast, GenericAlias, Union, _UnionGenericAlias, get_origin

import os, io, json, sys, time, traceback
import jsonschema
import regex as re
from collections import OrderedDict, defaultdict
from decimal import Decimal
from arelle.ModelDocument import load, Type,  create as createModelDocument
from arelle.ModelValue import qname, QName
from arelle.PythonUtil import SEQUENCE_TYPES, OrderedSet
from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import setXmlns
from arelle import ModelDocument, UrlUtil, XmlValidate

# XbrlObject modules contain nested XbrlOBjects and their type objects

from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlCube import (XbrlCube, XbrlCubeDimension, XbrlPeriodConstraint, XbrlDateResolution,
                       XbrlCubeType, XbrlAllowedCubeDimension, XbrlRequiredCubeRelationship)
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent
from .XbrlImportedTaxonomy import XbrlImportedTaxonomy
from .XbrlLabel import XbrlLabel, XbrlLabelType
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlReport import XbrlFact
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlTaxonomy import XbrlTaxonomy
from .XbrlTaxonomyObject import XbrlObject, XbrlReferencableTaxonomyObject, XbrlTaxonomyTagObject
from .XbrlDts import XbrlDts, castToDts
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, SQNameKeyType, DefaultTrue, DefaultFalse, DefaultZero
from .ValidateDTS import validateDTS
from .ModelValueMore import SQName, QNameAt
from .ViewXbrlTxmyObj import viewXbrlTxmyObj
from .XbrlConst import xbrl, oimTaxonomyDocTypePattern, oimTaxonomyDocTypes, qnXbrlLabelObj, xbrlTaxonomyObjects


from arelle.oim.Load import (DUPJSONKEY, DUPJSONVALUE, EMPTY_DICT, EMPTY_LIST, UrlInvalidPattern,
                             OIMException, NotOIMException)

RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
OIMT_SCHEMA = os.path.join(RESOURCES_DIR, "oim-taxonomy-schema.json")

saveOIMTaxonomySchemaFiles = False
SAVE_OIM_SCHEMA_CMDLINE_PARAMETER = "--saveOIMschemafile"
SAVE_OIM_SCHEMA_FORULA_PARAMETER = qname("saveOIMschemafile", noPrefixIsNoNamespace=True)
jsonschemaValidator = None

EMPTY_SET = set()

def jsonGet(tbl, key, default=None):
    if isinstance(tbl, dict):
        return tbl.get(key, default)
    return default

def loadOIMTaxonomy(cntlr, error, warning, modelXbrl, oimFile, mappedUri, **kwargs):
    global jsonschemaValidator
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocumentReference
    from arelle.ModelValue import qname

    _return = None # modelDocument or an exception

    try:
        currentAction = "initializing"
        startingErrorCount = len(modelXbrl.errors) if modelXbrl else 0
        startedAt = time.time()
        documentType = None # set by loadDict
        includeObjects = kwargs.get("includeObjects")
        includeObjectTypes = kwargs.get("includeObjectTypes")
        excludeLabels = kwargs.get("excludeLabels", False)
        followImport = kwargs.get("followImport", True)

        currentAction = "loading and parsing OIM Taxonomy file"
        loadDictErrors = []
        def ldError(msgCode, msgText, **kwargs):
            loadDictErrors.append((msgCode, msgText, kwargs))

        def loadDict(keyValuePairs):
            _dict = {}
            _valueKeyDict = {}
            for key, value in keyValuePairs:
                if isinstance(value, dict):
                    if key == "documentInfo" and "documentType" in value:
                        global documentType
                        documentType = value["documentType"]
                    if key in ("namespaces", "taxonomy"):
                        normalizedDict = {}
                        normalizedValueKeyDict = {}
                        if DUPJSONKEY in value:
                            normalizedDict[DUPJSONKEY] = value[DUPJSONKEY]
                        if DUPJSONVALUE in value:
                            normalizedDict[DUPJSONVALUE] = value[DUPJSONVALUE]
                        for _key, _value in value.items():
                            # _key = _key.strip() # per !178 keys have only normalized values, don't normalize key
                            # _value = _value.strip()
                            if _key in normalizedDict: # don't put the duplicate in the dictionary but report it as error
                                if DUPJSONKEY not in normalizedDict:
                                    normalizedDict[DUPJSONKEY] = []
                                normalizedDict[DUPJSONKEY].append((_key, _value, normalizedDict[_key]))
                            elif isinstance(_value, SEQUENCE_TYPES):
                                normalizedDict[_key] = _value
                            else: # do put into dictionary, only report if it's a map object
                                normalizedDict[_key] = _value
                                if key == "namespaces":
                                    if _value in normalizedValueKeyDict:
                                        if DUPJSONVALUE not in normalizedDict:
                                            normalizedDict[DUPJSONVALUE] = []
                                        normalizedDict[DUPJSONVALUE].append((_value, _key, normalizedValueKeyDict[_value]))
                                    else:
                                        normalizedValueKeyDict[_value] = _key
                            if key == "namespaces":
                                if not XmlValidate.NCNamePattern.match(_key):
                                    ldError("{}:invalidJSONStructure",
                                          _("The %(map)s alias \"%(alias)s\" must be a canonical NCName value"),
                                          modelObject=modelXbrl, map=key, alias=_key)
                                if UrlInvalidPattern.match(_value):
                                    ldError("{}:invalidJSONStructure",
                                          _("The %(map)s alias \"%(alias)s\" URI must be a canonical URI value: \"%(URI)s\"."),
                                          modelObject=modelXbrl, map=key, alias=_key, URI=_value)
                                elif not (_value and UrlUtil.isAbsolute(_value)) or UrlInvalidPattern.match(_value):
                                    ldError("oimce:invalidURI",
                                            _("The %(map)s \"%(alias)s\" URI is invalid: \"%(URI)s\"."),
                                            modelObject=modelXbrl, map=key, alias=_key, URI=_value)
                        value.clear() # replace with normalized values
                        for _key, _value in normalizedDict.items():
                            value[_key] = _value
                    if DUPJSONKEY in value:
                        for _errKey, _errValue, _otherValue in value[DUPJSONKEY]:
                            if key in ("namespaces", ):
                                ldError("{}:invalidJSON", # {} expanded when loadDictErrors are processed
                                                _("The %(map)s alias \"%(prefix)s\" is used on uri \"%(uri1)s\" and uri \"\"%(uri2)s."),
                                                modelObject=modelXbrl, map=key, prefix=_errKey, uri1=_errValue, uri2=_otherValue)
                            else:
                                ldError("{}:invalidJSON", # {} expanded when loadDictErrors are processed
                                                _("The %(obj)s key \"%(key)s\" is used on multiple objects."),
                                                modelObject=modelXbrl, obj=key, key=_errKey)
                        del value[DUPJSONKEY]
                    if DUPJSONVALUE in value:
                        if key in ("namespaces", ):
                            for _errValue, _errKey, _otherKey in value[DUPJSONVALUE]:
                                ldError("oimce:multipleAliasesForURI",
                                                _("The \"%(map)s\" value \"%(uri)s\" is used on alias \"%(alias1)s\" and alias \"%(alias2)s\"."),
                                                modelObject=modelXbrl, map=key, uri=_errValue, alias1=_errKey, alias2=_otherKey)
                        del value[DUPJSONVALUE]
                if key in _dict: # don't put the duplicate in the dictionary but report it as error
                    if DUPJSONKEY not in _dict:
                        _dict[DUPJSONKEY] = []
                    _dict[DUPJSONKEY].append((key, value, _dict[key]))
                else: # do put into dictionary, only report if it's a map object
                    _dict[key] = value
                    '''
                    if isinstance(value, str):
                        if value in _valueKeyDict:
                            if DUPJSONVALUE not in _dict:
                                _dict[DUPJSONVALUE] = []
                            _dict[DUPJSONVALUE].append((value, key, _valueKeyDict[value]))
                        else:
                            _valueKeyDict[value] = key
                    '''
            return _dict

        errPrefix = "xbrlte"
        try:
            if isinstance(oimFile, dict) and oimFile.get("documentInfo",{}).get("documentType") in oimTaxonomyDocTypes:
                oimObject = oimFile
                href = "BakedInConstants"
                txFileName = href
                txBase = None
            else:
                _file = modelXbrl.fileSource.file(oimFile, encoding="utf-8-sig")[0]
                href = os.path.basename(oimFile)
                txFileName = oimFile
                txBase = os.path.dirname(oimFile) # import referenced taxonomies
                with _file as f:
                    oimObject = json.load(f, object_pairs_hook=loadDict, parse_float=Decimal)
        except UnicodeDecodeError as ex:
            raise OIMException("{}:invalidJSON".format(errPrefix),
                  _("File MUST use utf-8 encoding: %(file)s, error %(error)s"),
                  sourceFileLine=oimFile, error=str(ex))
        except json.JSONDecodeError as ex:
            raise OIMException("{}:invalidJSON".format(errPrefix),
                    "JSON error while %(action)s, %(file)s, error %(error)s",
                    file=oimFile, action=currentAction, error=ex)
        # schema validation
        if jsonschemaValidator is None:
            with io.open(OIMT_SCHEMA, mode="rt") as fh:
                jsonschemaValidator = jsonschema.Draft7Validator(json.load(fh))
        try:
            for err in jsonschemaValidator.iter_errors(oimObject) or ():
                path = []
                for p in err.absolute_path:
                    path.append(f"[{p}]" if isinstance(p,int) else f"/{p}")
                msg = err.message
                error("jsonschema:oimTaxonomyError",
                      _("Error: %(error)s, jsonObj: %(path)s"),
                      sourceFileLine=href, error=msg, path="".join(path))
        except (jsonschema.exceptions.SchemaError, jsonschema.exceptions._RefResolutionError, jsonschema.exceptions.UndefinedTypeCheck) as ex:
            msg = str(ex)
            if "PointerToNowhere" in msg:
                msg = msg[:121]
            error("jsonschema:schemaError",
                  _("Error in json schema processing: %(error)s"),
                  sourceFileLine=href, error=msg)
        documentInfo = jsonGet(oimObject, "documentInfo", {})
        documentType = jsonGet(documentInfo, "documentType")
        taxonomyObj = jsonGet(oimObject, "taxonomy", {})
        isReport = "facts" in oimObject # for test purposes report facts can be in json object
        if not documentType:
            error("oimce:unsupportedDocumentType",
                  _("/documentInfo/docType is missing."),
                  file=oimFile)
        elif documentType not in oimTaxonomyDocTypes:
            error("oimce:unsupportedDocumentType",
                  _("Unrecognized /documentInfo/docType: %(documentType)s"),
                  file=oimFile, documentType=documentType)
            return {}

        # report loadDict errors
        for msgCode, msgText, kwargs in loadDictErrors:
            error(msgCode.format(errPrefix), msgText, sourceFileLine=href, **kwargs)
        del loadDictErrors[:]

        extensionProperties = {} # key is property QName, value is property path

        currentAction = "identifying Metadata objects"

        # create the taxonomy document
        currentAction = "creating schema"
        prevErrLen = len(modelXbrl.errors) # track any xbrl validation errors
        if modelXbrl: # pull loader implementation
            modelXbrl.blockDpmDBrecursion = True
            schemaDoc = _return = createModelDocument(
                  modelXbrl,
                  Type.SCHEMA,
                  txFileName,
                  initialComment="loaded from OIM Taxonomy {}".format(mappedUri),
                  documentEncoding="utf-8",
                  # base=txBase or modelXbrl.entryLoadingUrl
                  )
            schemaDoc.inDTS = True
            xbrlDts = castToDts(modelXbrl, isReport)
        else: # API implementation
            xbrlDts = ModelDts.create(
                cntlr.modelManager,
                Type.SCHEMA,
                initialComment="loaded from OIM Taxonomy {}".format(mappedUri),
                base=txBase)
            _return = xbrlDts.modelDocument
        if len(modelXbrl.errors) > prevErrLen:
            error("oime:invalidTaxonomy",
                  _("Unable to obtain a valid taxonomy from URLs provided"),
                  sourceFileLine=href)
        # first OIM Taxonomy load Baked In objects
        if not xbrlDts.namedObjects and not "loadingBakedInObjects" in kwargs:
            loadOIMTaxonomy(cntlr, error, warning, modelXbrl, xbrlTaxonomyObjects, "BakedInCoreObjects", loadingBakedInObjects=True, **kwargs)
            loadOIMTaxonomy(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "xbrlSpec.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadOIMTaxonomy(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "types.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadOIMTaxonomy(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "utr.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadOIMTaxonomy(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "ref.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadOIMTaxonomy(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "iso4217.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
        namespacePrefixes = {}
        prefixNamespaces = {}
        namespaceUrls = {}
        for prefix, ns in documentInfo.get("namespaces", EMPTY_DICT).items():
            if ns and prefix:
                namespacePrefixes[ns] = prefix
                prefixNamespaces[prefix] = ns
                setXmlns(schemaDoc, prefix, ns)
        if "documentNamespace" in documentInfo:
            schemaDoc.targetNamespace = prefixNamespaces.get(documentInfo["documentNamespace"])
        if "urlMapping" in documentInfo:
            for prefix, url in documentInfo["urlMapping"].items():
                namespaceUrls[prefixNamespaces.get(prefix)] = url
        taxonomyName = qname(taxonomyObj.get("name"), prefixNamespaces)
        if not taxonomyName:
            xbrlDts.error("oime:missingQNameProperty",
                          _("Taxonomy must have a name (QName) property"),
                          sourceFileLine=href)

        # check extension properties (where metadata specifies CheckPrefix)
        for extPropSQName, extPropertyPath in extensionProperties.items():
            extPropPrefix = extPropSQName.partition(":")[0]
            if extPropPrefix not in prefixNamespaces:
                error("oimte:unboundPrefix",
                      _("The extension property QName prefix was not defined in namespaces: %(extensionProperty)s."),
                      sourceFileLine=href, extensionProperty=extPropertyPath)

        for iImpTxmy, impTxmyObj in enumerate(taxonomyObj.get("importedTaxonomies", EMPTY_LIST)):
            if qnXbrlLabelObj in getattr(impTxmyObj, "includeObjectTypes",()):
                impTxmyObj.includeObjectTypes.delete(qnXbrlLabelObj)
                xbrlDts.error("oimte:invalidObjectType",
                              _("/taxonomy/importedTaxonomies[%(iImpTxmy)s] must not have a label object in the includeObjectTypes property"),
                              sourceFileLine=href, index=iImpTxmy)
            impTxmyName = qname(impTxmyObj.get("taxonomyName"), prefixNamespaces)
            if impTxmyName:
                ns = impTxmyName.namespaceURI
                # if already imported ignore it (for now)
                if ns not in xbrlDts.namespaceDocs and followImport:
                    url = namespaceUrls.get(ns)
                    if url:
                        load(xbrlDts, url, base=oimFile, isDiscovered=schemaDoc.inDTS, isIncluded=kwargs.get("isIncluded"), namespace=ns,
                             includeObjects=(qname(qn, prefixNamespaces) for qn in impTxmyObj.get("includeObjects",())) or None,
                             includeObjectTypes=(qname(qn, prefixNamespaces) for qn in impTxmyObj.get("includeObjectTypes",())) or None,
                             excludeLabels=impTxmyObj.get("excludeLabels",False),
                             followImport=impTxmyObj.get("followImport",True))
            else:
                xbrlDts.error("oime:missingQNameProperty",
                              _("/taxonomy/importedTaxonomies[%(iImpTxmy)s] must have a taxonomyName (QName) property"),
                              sourceFileLine=href, index=iImpTxmy)
        def singular(name):
            if name.endswith("ies"):
                return name[:-3] + "y"
            elif name.endswith("s"):
                return name[:-1]
            return name
        def plural(name):
            if name.endswith("y"):
                return name[:-1] + "ies"
            else:
                return name + "s"
        def addToCol(oimParentObj, objName, newObj, key):
            parentCol = getattr(oimParentObj, plural(objName), None) # parent collection object
            if colObj is not None:
                if key:
                    colObj[key] = newObj
                else:
                    colObj.add(newObj)

        jsonEltsNotInObjClass = []
        jsonEltsReqdButMissing = []
        namedObjectDuplicates = defaultdict(OrderedSet)
        def createTaxonomyObject(jsonObj, oimParentObj, keyClass, objClass, newObj, pathParts):
            keyValue = None
            relatedNames = [] # to tag an object with labels or references
            unexpectedJsonProps = set(jsonObj.keys())
            for propName, propType in getattr(objClass, "__annotations__", EMPTY_DICT).items():
                if isinstance(propType, GenericAlias):
                    propClass = propType.__origin__ # collection type such as OrderedSet, dict
                    collectionProp = propClass()
                    setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                else:
                    propClass = propType
                if propName in jsonObj:
                    unexpectedJsonProps.remove(propName)
                    if propName == "labels" and excludeLabels:
                        continue
                    jsonValue = jsonObj[propName]
                    if isinstance(propType, GenericAlias):
                        if len(propType.__args__) == 2: # dict
                            _keyClass = propType.__args__[0] # class of key such as QNameKey
                            eltClass = propType.__args__[1] # class of collection elements such as XbrlConcept
                        elif len(propType.__args__) == 1: # set such as OrderedSet or list
                            _keyClass = None
                            eltClass = propType.__args__[0]
                        if isinstance(jsonValue, list):
                            for iObj, listObj in enumerate(jsonValue):
                                if isinstance(eltClass, str) or getattr(eltClass, "__name__", "").startswith("Xbrl"): # nested Xbrl objects
                                    if isinstance(listObj, dict):
                                        # this handles lists of dict objects.  For dicts of key-value dict objects see above.
                                        createTaxonomyObjects(propName, listObj, newObj, pathParts + [f'{propName}[{iObj}]'])
                                    else:
                                        error("xbrlte:invalidObjectType",
                                              _("Object expected but non-object found: %(listObj)s, jsonObj: %(path)s"),
                                              sourceFileLine=href, listObj=listObj, path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                else: # collection contains ordinary values
                                    if eltClass in (QName, QNameKeyType, SQName, SQNameKeyType):
                                        listObj = qname(listObj, prefixNamespaces)
                                        if listObj is None:
                                            error("xbrlte:invalidQName",
                                                  _("QName is invalid: %(qname)s, jsonObj: %(path)s"),
                                                  sourceFileLine=href, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                            continue # skip this property
                                        if propName == "relatedNames":
                                            relatedNames.append(listObj)
                                    if propClass in (set, OrderedSet):
                                        collectionProp.add(listObj)
                                    else:
                                        collectionProp.append(listObj)
                        elif isinstance(jsonValue, dict) and keyClass:
                            for iObj, (valKey, valVal) in enumerate(jsonValue.items()):
                                if get_origin(_keyClass) is Union:
                                    if QName in _keyClass.__args__ and ":" in valKey:
                                        _valKey = qname(listObj, prefixNamespaces)
                                        if _valKey is None:
                                            error("xbrlte:invalidQName",
                                                  _("QName is invalid: %(qname)s, jsonObj: %(path)s"),
                                                  sourceFileLine=href, qname=_valKey, path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                            continue # skip this property
                                    elif str in _keyClass.__args__:
                                        _valKey = valKey
                                    else:
                                        continue
                                elif isinstance(_keyClass, str):
                                    _valKey = valKey
                                else:
                                    continue
                                collectionProp[_valKey] = valVal
                    elif isinstance(propType, _UnionGenericAlias) and propType.__args__[-1] == type(None) and isinstance(jsonValue,dict): # optional embdded object
                        createTaxonomyObjects(propName, jsonValue, newObj, pathParts + [propName]) # object property
                    else:
                        optional = False
                        if isinstance(propType, _UnionGenericAlias) and propType.__args__[-1] == type(None):
                            propType = propType.__args__[0] # scalar property
                            optional = True
                        if propType == QNameAt:
                            jsonValue, _sep, atSuffix = jsonValue.partition("@")
                        if propType in (QName, QNameKeyType, SQName, SQNameKeyType, QNameAt):
                            jsonValue = qname(jsonValue, prefixNamespaces)
                            if jsonValue is None:
                                error("xbrlte:invalidQName",
                                      _("QName is invalid: %(qname)s, jsonObj: %(path)s"),
                                      sourceFileLine=href, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [propName])}")
                                if optional:
                                    jsonValue = None
                                else:
                                    # TBD: set newObj to invalid so it isn't usable (it was already set in collection objects above when being created)
                                    return # skip this nested object entirely
                            elif propType == QNameAt:
                                jsonValue = QNameAt(jsonValue.prefix, jsonValue.namespaceURI, jsonValue.localName, atSuffix)
                            if propName == "relatedName":
                                relatedNames.append(jsonValue)
                        setattr(newObj, propName, jsonValue)
                        if (keyClass and keyClass == propType) or (not keyClass and propType in (QNameKeyType, SQNameKeyType)):
                            keyValue = jsonValue # e.g. the QNAme of the new object for parent object collection
                elif propType in (type(oimParentObj), type(oimParentObj).__name__): # propType may be a TypeAlias which is a string name of class
                    setattr(newObj, propName, oimParentObj)
                elif (((get_origin(propType) is Union) or isinstance(get_origin(propType), type(Union))) and # Optional[ ] type
                       propType.__args__[-1] in (type(None), DefaultTrue, DefaultFalse, DefaultZero)):
                          setattr(newObj, propName, {type(None): None, DefaultTrue: True, DefaultFalse: False, DefaultZero:0}[propType.__args__[-1]]) # use first of union for prop value creation
                else: # absent json element
                    if not propClass in (dict, set, OrderedSet, OrderedDict):
                        jsonEltsReqdButMissing.append(f"{'/'.join(pathParts + [propName])}")
                        setattr(newObj, propName, None) # not defaultable but set to None anyway
            if unexpectedJsonProps:
                for propName in unexpectedJsonProps:
                    jsonEltsNotInObjClass.append(f"{'/'.join(pathParts + [propName])}={jsonObj.get(propName,'(absent)')}")
            if isinstance(newObj, XbrlReferencableTaxonomyObject):
                if keyValue in xbrlDts.namedObjects:
                    namedObjectDuplicates[keyValue].add(newObj)
                    namedObjectDuplicates[keyValue].add(xbrlDts.namedObjects[keyValue])
                else:
                    xbrlDts.namedObjects[keyValue] = newObj
            elif isinstance(newObj, XbrlTaxonomyTagObject) and relatedNames:
                for relatedQn in relatedNames:
                    xbrlDts.tagObjects[relatedQn].append(newObj)
            return keyValue

        def createTaxonomyObjects(jsonKey, jsonObj, oimParentObj, pathParts):
            # find collection owner in oimParentObj
            for objName in (jsonKey, plural(jsonKey)):
                ownrPropType = getattr(oimParentObj, "__annotations__", EMPTY_DICT).get(objName)
                if ownrPropType is not None:
                    break
            if ownrPropType is not None:
                ownrProp = getattr(oimParentObj, objName, None) # owner collection or property
                if ownrPropType is not None:
                    if isinstance(ownrPropType, GenericAlias):
                        ownrPropClass = ownrPropType.__origin__ # collection type such as OrderedSet, dict
                        if len(ownrPropType.__args__) == 2: # dict
                            keyClass = ownrPropType.__args__[0] # class of key such as QNameKey
                            objClass = ownrPropType.__args__[1] # class of obj such as XbrlConcept
                        elif len(ownrPropType.__args__) == 1: # set such as OrderedSet or list
                            keyClass = None
                            objClass = ownrPropType.__args__[0]
                        if ownrProp is None: # the parent object's dict or OrderedSet doesn't exist yet
                            ownrProp = ownrPropClass()
                            setattr(oimParentObj, propName, ownrProp) # fresh new dict or OrderedSet
                        if objClass == XbrlFact and isinstance(jsonObj, dict): # this is a JSON key-value dict going into a dict, for lists of dicts see below
                            for id, value in jsonObj.items():
                                newObj = objClass(dtsObjectIndex=len(xbrlDts.xbrlObjects))
                                xbrlDts.xbrlObjects.append(newObj)
                                newObj.id = id
                                createTaxonomyObject(value, oimParentObj, str, objClass, newObj, pathParts + [f"[{id}]"])
                                ownrProp[id] = newObj
                            return None # facts not returnable
                    elif isinstance(ownrPropType, _UnionGenericAlias) and ownrPropType.__args__[-1] == type(None): # optional nested object
                        keyClass = None
                        objClass = ownrPropType.__args__[0]
                    else: # parent      is just an object field, not a  collection
                        objClass = ownrPropType # e.g just a Concept but no owning collection
                    if objClass == XbrlTaxonomyType:
                        objClass = XbrlTaxonomy
                    if issubclass(objClass, XbrlObject):
                        newObj = objClass(dtsObjectIndex=len(xbrlDts.xbrlObjects)) # e.g. this is the new Concept
                        xbrlDts.xbrlObjects.append(newObj)
                        classCountProp = f"_{objClass.__name__}Count"
                        classIndex = getattr(oimParentObj, classCountProp, 0)
                        setattr(newObj, "_classIndex", classIndex)
                        setattr(oimParentObj, classCountProp,classIndex+1)
                    else:
                        newObj = objClass() # e.g. XbrlProperty
                    keyValue = createTaxonomyObject(jsonObj, oimParentObj, keyClass, objClass, newObj, pathParts)
                    if isinstance(ownrPropType, GenericAlias):
                        if len(ownrPropType.__args__) == 2:
                            if keyValue:
                                ownrProp[keyValue] = newObj
                        elif isinstance(ownrProp, (set, OrderedSet)):
                            ownrProp.add(newObj)
                        else:
                            ownrProp.append(newObj)
                    elif isinstance(ownrPropType, _UnionGenericAlias) and ownrPropType.__args__[-1] == type(None): # optional nested object
                        setattr(oimParentObj, pathParts[-1], newObj)
                    return newObj
            return None

        newTxmy = createTaxonomyObjects("taxonomy", oimObject["taxonomy"], xbrlDts, ["", "taxonomy"])
        if isReport:
            createTaxonomyObjects("facts", oimObject["facts"], xbrlDts, ["", "facts"])

        if jsonEltsNotInObjClass:
            error("arelle:undeclaredOimTaxonomyJsonElements",
                  _("Json file has elements not declared in Arelle object classes: %(undeclaredElements)s"),
                  sourceFileLine=href, undeclaredElements=", ".join(jsonEltsNotInObjClass))
        if jsonEltsReqdButMissing:
            error("arelle:missingOimTaxonomyJsonElements",
                  _("Json file missing required elements: %(missingElements)s"),
                  sourceFileLine=href, missingElements=", ".join(jsonEltsReqdButMissing))

        for qname, dupObjs in namedObjectDuplicates.items():
            xbrlDts.error("oimte:duplicateObjects",
                  _("Multiple referenceable objects have the same name: %(qname)s"),
                  xbrlObject=dupObjs, qname=qname)

        if newTxmy is not None:
            for impTxmy in newTxmy.importedTaxonomies:
                if impTxmy.taxonomyName not in xbrlDts.taxonomies:
                    # is it present in urlMapping?
                    url = namespaceUrls.get(impTxmy.taxonomyName.prefix)
                    if url:
                        loadOIMTaxonomy(cntlr, error, warning, modelXbrl, url, impTxmy.taxonomyName.localName)

        xbrlDts.namespaceDocs[taxonomyName.namespaceURI].append(schemaDoc)

        return schemaDoc

        ####################### convert to XML Taxonomy


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

        # convert into XML Taxonomy
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

        # additional namespaces needed
        for prefix, ns in (("xlink", "http://www.w3.org/1999/xlink"),
                           ("ref", "http://www.xbrl.org/2006/ref"),
                           ("xbrldt", "http://xbrl.org/2005/xbrldt"),
                           ("xbrl", xbrl)):
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
            periodType = conceptObj.get("periodType", True)
            balance = conceptObj.get("balance", None)
            abstract = conceptObj.get("abstract", None)
            nillable = conceptObj.get("abstract", None)
            name = qname(conceptObj.get("name", ""), prefixNamespaces)
            if name:
                dataType = qname(conceptObj.get("dataType", ""), prefixNamespaces)
                substitutionGroup = qname(conceptObj.get("substitutionGroup", ""), prefixNamespaces)
                attributes = {"id": f"{name.prefix}_{name.localName}",
                              "name": name.localName}
                if dataType:
                    attributes["type"] = str(dataType)
                if periodType:
                    attributes[QN_PERIOD_TYPE.clarkNotation] = periodType
                if balance:
                    attributes[QN_BALANCE.clarkNotation] = balance
                if abstract is not None:
                    attributes["abstract"] = str(abstract).lower()
                if nillable is not None:
                    attributes["nillable"] = str(nillable).lower()
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
        for networkObj in taxonomyObj.get("cubes", []):
            networkURI = networkObj.get("networkURI", "")
            if networkURI and networkObj.get("dimensions", []):
                usedOn[networkURI].add("link:definitionLink")

        # define role types
        locallyDefinedRoles = OrderedDict() # URI: {name, description, usedOns}
        # networkURI can appear multiple times in different places, infer a single role definition from all
        for objI, networkObj in enumerate(taxonomyObj.get("networks", []) + taxonomyObj.get("domains", [])):
            networkURI = networkObj.get("networkURI", "")
            if networkURI in locallyDefinedRoles:
                roleDef = locallyDefinedRoles[networkURI]
            else:
                locallyDefinedRoles[networkURI] = roleDef = {}
            if "name" in networkObj:
                roleDef["name"] = networkObj["name"]
            if "description" in networkObj:
                roleDev["description"] = networkObj["description"]
        locallyDefinedRoleHrefs = {}
        for objI, (networkURI, networkObj) in enumerate(locallyDefinedRoles.items()):
            name = networkObj.get("name", f"_roleType_{objI+1}")
            description = networkObj.get("description", "")
            locallyDefinedRoleHrefs[networkURI] = f"#{name}"

            roleTypeElt = addChild(appinfoElt, QN_ROLE_TYPE,
                                   attributes={"id": name,
                                               "roleURI": networkURI})
            if description:
                addChild(roleTypeElt, QN_DEFINITION, text=description)
            for u in usedOn[networkURI]:
                addChild(roleTypeElt, QN_USED_ON, text=u)
            modelXbrl.roleTypes[networkURI].append(roleTypeElt)

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

        def addRoleRefs(lbElt, roles, arcroles):
            firstElr = lbElt[0]
            for role in sorted(roles):
                if role in locallyDefinedRoleHrefs:
                    href = locallyDefinedRoleHrefs[role]
                    addChild(lbElt, XbrlConst.qnLinkRoleRef,
                             beforeSibling=firstElr,
                             attributes={
                                 "{http://www.w3.org/1999/xlink}roleURI": role,
                                 "{http://www.w3.org/1999/xlink}type": "simple",
                                 "{http://www.w3.org/1999/xlink}href": href})
            for arcrole in sorted(arcroles):
                if arcrole.startswith("http://xbrl.org/int/dim/arcrole"):
                    href = f"http://www.xbrl.org/2005/xbrldt-2005.xsd#{os.path.basename(arcrole)}"
                    addChild(lbElt, XbrlConst.qnLinkArcroleRef,
                             beforeSibling=firstElr,
                                 attributes={
                                     "{http://www.w3.org/1999/xlink}arcroleURI": arcrole,
                                     "{http://www.w3.org/1999/xlink}type": "simple",
                                     "{http://www.w3.org/1999/xlink}href": href})
            roles.clear()
            arcroles.clear()

        domainIDHypercubeQNames = {}
        domainIDPrimaryDimensions = {}
        domainIDPeriodDimensions = {}
        lbElt = addChild(appinfoElt, XbrlConst.qnLinkLinkbase)
        lbElts.append(lbElt)
        lbEltRoleRefs = set()
        lbEltArcroleRefs = set()
        for cubeI, cubeObj in enumerate(taxonomyObj.get("cubes", [])):
            locXlinkLabels.clear() # separate locs per elr
            networkURI = cubeObj.get("networkURI", "") # ELR
            hypercubeConcept = cubeObj.get("name", "") # hypercube concept clark name
            cubeType = cubeObj.get("cubeType", "")
            elrElt = addChild(lbElt, XbrlConst.qnLinkDefinitionLink,
                             attributes={"{http://www.w3.org/1999/xlink}role": networkURI,
                                         "{http://www.w3.org/1999/xlink}type": "extended"})
            lbEltRoleRefs.add(networkURI)
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
                    lbEltArcroleRefs.add(XbrlConst.hypercubeDimension)

        for domI, domObj in enumerate(taxonomyObj.get("domains", [])):
            locXlinkLabels.clear() # separate locs per elr
            networkURI = domObj.get("networkURI", "")
            domainID = domObj.get("domainID", "")
            domainConcept = domObj.get("domainConcept", "")
            relationships = domObj.get("relationships", [])
            elrElt = addChild(lbElt, XbrlConst.qnLinkDefinitionLink,
                             attributes={"{http://www.w3.org/1999/xlink}role": networkURI,
                                         "{http://www.w3.org/1999/xlink}type": "extended"})
            lbEltRoleRefs.add(networkURI)
            if domainID not in domainIDPrimaryDimensions and domainID not in domainIDPeriodDimensions:
                addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                         attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, domainIDHypercubeQNames.get(domainID), f"domain[{domI}]/domainID"),
                                     "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, domainConcept, f"domain[{domI}]/domainConcept"),
                                     "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.dimensionDomain,
                                     "{http://www.w3.org/1999/xlink}type": "arc"})
                lbEltArcroleRefs.add(XbrlConst.dimensionDomain)
            for relI, relObj in enumerate(relationships):
                source = relObj.get("source", "")
                target = relObj.get("target", "")
                order = relObj.get("order", "1")
                if domainID in domainIDPrimaryDimensions and relI == 0:
                    addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                             attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, target, f"domain[{domI}]/relationship[{relI}/target"),
                                         "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, domainIDPrimaryDimensions.get(domainID), f"domain[{domI}]/domainID"),
                                         "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.all,
                                         "{http://www.w3.org/1999/xlink}type": "arc",
                                         # TBD - determine values dynamically from taxonomy and authority
                                         "{http://xbrl.org/2005/xbrldt}closed": "true",
                                         "{http://xbrl.org/2005/xbrldt}contextElement": "segment"})
                    lbEltArcroleRefs.add(XbrlConst.all)
                else:
                    addChild(elrElt, XbrlConst.qnLinkDefinitionArc,
                             attributes={"{http://www.w3.org/1999/xlink}from": locXlinkLabel(elrElt, source, f"domain[{domI}]/relationship[{relI}/source"),
                                         "{http://www.w3.org/1999/xlink}to": locXlinkLabel(elrElt, target, f"domain[{domI}]/relationship[{relI}/target"),
                                         "{http://www.w3.org/1999/xlink}arcrole": XbrlConst.domainMember,
                                         "{http://www.w3.org/1999/xlink}type": "arc",
                                         "order": order})
                    lbEltArcroleRefs.add(XbrlConst.domainMember)
        addRoleRefs(lbElt, lbEltRoleRefs, lbEltArcroleRefs)

        lbElt = addChild(appinfoElt, XbrlConst.qnLinkLinkbase)
        lbElts.append(lbElt)
        for networkI, networkObj in enumerate(taxonomyObj.get("networks", [])):
            locXlinkLabels.clear() # separate locs per elr
            networkURI = networkObj.get("networkURI", "")
            elrElt = addChild(lbElt, XbrlConst.qnLinkDefinitionLink,
                             attributes={"{http://www.w3.org/1999/xlink}role": networkURI,
                                         "{http://www.w3.org/1999/xlink}type": "extended"})
            lbEltRoleRefs.add(networkURI)
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
                lbEltArcroleRefs.add(relationshipType)
                if weight is not None:
                    attributes["weight"] = weight
                if preferredLabel is not None:
                    attributes["preferredLabel"] = preferredLabel
                addChild(elrElt, XbrlConst.qnLinkDefinitionArc, attributes)
        addRoleRefs(lbElt, lbEltRoleRefs, lbEltArcroleRefs)

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
                lbEltArcroleRefs.add(XbrlConst.conceptReference)
        addRoleRefs(lbElt, lbEltRoleRefs, lbEltArcroleRefs)

        # discover linkbases
        for lbElt in lbElts:
            schemaDoc.linkbaseDiscover(lbElt)

        # errors
        for hrefNs, paths in sorted(hrefsNsWithoutPrefix.items(), key=lambda i:i[0]):
            error("oimte:missingConceptRefPrefx",
                  "Namespace has no prefix %(namespace)s in %(paths)s",
                  modelObject=modelXbrl, namespace=hrefNs, paths=", ".join(paths))

        # save schema files if specified
        if (saveOIMTaxonomySchemaFiles or
            modelXbrl.modelManager.formulaOptions.typedParameters(modelXbrl.prefixedNamespaces)
            .get(SAVE_OIM_SCHEMA_FORULA_PARAMETER, ("",None))[1] not in (None, "", "false")):
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

def oimTaxonomyValidator(val, parameters):
    if not isinstance(val.modelXbrl, XbrlDts): # if no OIM Taxonomy DTS give up
        return
    try:
        validateDTS(val.modelXbrl)
    except Exception as ex:
        val.modelXbrl.error("arelleOIMloader:error",
                "Error while validating, error %(errorType)s %(error)s\n traceback %(traceback)s",
                modelObject=val.modelXbrl, errorType=ex.__class__.__name__, error=ex,
                traceback=traceback.format_tb(sys.exc_info()[2]))

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
        if _fileStart and oimTaxonomyDocTypePattern.match(_fileStart):
            lastFilePathIsOIM = True
            lastFilePath = filepath
    return lastFilePathIsOIM

def oimTaxonomyLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if filepath != lastFilePath or not lastFilePathIsOIM:
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    cntlr.showStatus(_("Loading OIM taxonomy file: {0}").format(os.path.basename(filepath)))
    doc = loadOIMTaxonomy(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri, **kwargs)
    if doc is None:
        return None # not an OIM file
    return doc

def optionsExtender(parser, *args, **kwargs):
    parser.add_option(SAVE_OIM_SCHEMA_CMDLINE_PARAMETER,
                      action="store_true",
                      dest="saveOIMTaxonomySchemaFiles",
                      help=_("Save each OIM taxonomy file an xsd named -json.xsd."))
def filingStart(self, options, *args, **kwargs):
    global saveOIMTaxonomySchemaFiles
    if options.saveOIMTaxonomySchemaFiles:
        saveOIMTaxonomySchemaFiles = True

def oimTaxonomyLoaded(cntlr, options, xbrlDts, *args, **kwargs):
    # index groupContents
    xbrlDts.groupContents = defaultdict(OrderedSet)
    for txmy in xbrlDts.taxonomies.values():
        for grpCnts in txmy.groupContents:
            for relName in getattr(grpCnts, "relatedNames", ()): # if object was invalid there are no attributes, e.g. bad QNames
                xbrlDts.groupContents[grpCnts.groupName].add(relName)

def oimTaxonomyViews(cntlr, xbrlDts):
    oimTaxonomyLoaded(cntlr, None, xbrlDts)
    if isinstance(xbrlDts, XbrlDts):
        initialViews = []
        if getattr(xbrlDts, "facts", ()): # has instance facts
            initialViews.append( (XbrlFact, cntlr.tabWinTopRt, "Report Facts") )
        initialViews.extend(((XbrlConcept, cntlr.tabWinBtm, "XBRL Concepts"),
                             (XbrlGroup, cntlr.tabWinTopRt, "XBRL Groups"),
                             (XbrlNetwork, cntlr.tabWinTopRt, "XBRL Networks"),
                             (XbrlCube, cntlr.tabWinTopRt, "XBRL Cubes")
                            ))
        initialViews = tuple(initialViews)
        additionalViews = ((XbrlAbstract, cntlr.tabWinBtm, "XBRL Abstracts"),
                           (XbrlCubeType, cntlr.tabWinBtm, "XBRL Cube Types"),
                           (XbrlDataType, cntlr.tabWinBtm, "XBRL Data Types"),
                           (XbrlEntity, cntlr.tabWinBtm, "XBRL Entities"),
                           (XbrlLabel, cntlr.tabWinBtm, "XBRL Labels"),
                           (XbrlLabelType, cntlr.tabWinBtm, "XBRL Label Types"),
                           (XbrlPropertyType, cntlr.tabWinBtm, "XBRL Property Types"),
                           (XbrlReference, cntlr.tabWinBtm, "XBRL References"),
                           (XbrlReferenceType, cntlr.tabWinBtm, "XBRL Reference Types"),
                           (XbrlRelationshipType, cntlr.tabWinBtm, "XBRL Relationship Types"),
                           (XbrlTransform, cntlr.tabWinBtm, "XBRL Transforms"),
                           (XbrlUnit, cntlr.tabWinBtm, "XBRL Units"),)
        for view in initialViews:
            viewXbrlTxmyObj(xbrlDts, *view, additionalViews)
        return True # block ordinary taxonomy views
    return False

__pluginInfo__ = {
    'name': 'OIM Taxonomy',
    'version': '1.2',
    'description': "This plug-in implements XBRL taxonomy objects loaded from JSON.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrCmdLine.Options': optionsExtender,
    'CntlrCmdLine.Filing.Start': filingStart,
    'CntlrCmdLine.Xbrl.Loaded': oimTaxonomyLoaded,
    'CntlrWinMain.Xbrl.Views': oimTaxonomyViews,
    'ModelDocument.IsPullLoadable': isOimTaxonomyLoadable,
    'ModelDocument.PullLoader': oimTaxonomyLoader,
    'Validate.XBRL.Start': oimTaxonomyValidator
}
