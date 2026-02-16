"""
See COPYRIGHT.md for copyright information.

## Overview

The XBRL Model plugin is designed to load taxonomy objects from JSON that adheres to the Open Information
Model (OIM) Taxonomy Specification.

## Usage Instructions

Any import or direct opening of a JSON-specified taxonomy behaves the same as if loading from an xsd taxonomy or xml linkbases

For XBRL 2.1 XML schema validation purposes, saves schema files in directory if
  command line: specify --saveXMLSchemaFiles {directoryName}
  GUI: provide a formula parameter named saveXMLSchemaFiles (value is directory to save in)

"""

from typing import TYPE_CHECKING, cast, GenericAlias, Union, _GenericAlias, _UnionGenericAlias, get_origin, ClassVar, ForwardRef

import os, io, json, cbor2, sys, time, traceback
JSON_SCHEMA_VALIDATOR = "jsonschema" # select one of below JSON schema validator libraries (seriously different performance)
#JSON_SCHEMA_VALIDATOR = "fastjsonschema"
if JSON_SCHEMA_VALIDATOR == "jsonschema": # slow and thorough
    import jsonschema
    # finds all errors in source object
    jsonSchemaLoaderMethod = jsonschema.Draft7Validator
elif JSON_SCHEMA_VALIDATOR == "fastjsonschema": # may be faster if it works on our schemas
    import fastjsonschema
    # only provides first schema error in source object
    # see: https://github.com/horejsek/python-fastjsonschema/issues/36
    jsonSchemaLoaderMethod = fastjsonschema.compile
elif JSON_SCHEMA_VALIDATOR == "jsonschema_rs": # RUST implemented, does hot support Python values like long ints
    import jsonschema_rs
    # appears to raise RUST ValueError on us-gaap taxonomy validation
    jsonSchemaLoaderMethod = jsonschema_rs.Draft202012Validator
import regex as re
from collections import OrderedDict, defaultdict
from decimal import Decimal
from arelle.ModelDocument import load, Type,  create as createModelDocument
from arelle.ModelValue import qname, QName
from arelle.PythonUtil import SEQUENCE_TYPES, OrderedSet
#from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import setXmlns
from arelle import ModelDocument, PackageManager, UrlUtil, XmlValidate

# XbrlObject modules contain nested XbrlOBjects and their type objects

from .XbrlAbstract import XbrlAbstract
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import qnErrorQname
from .XbrlCube import (XbrlCube, XbrlCubeDimension, XbrlPeriodConstraint, XbrlDateResolution,
                       XbrlCubeType, coreDimensionsByLocalname)
from .XbrlDimension import XbrlDimension
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent, XbrlGroupTree
from .XbrlLabel import XbrlLabel, XbrlLabelType
from .XbrlLayout import XbrlLayout
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlReport import XbrlReport, XbrlFact, XbrlFootnote, XbrlFactSource, XbrlFactMap
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlModel import XbrlCompiledModel, castToXbrlCompiledModel
from .XbrlModule import XbrlModule, xbrlObjectTypes
from .XbrlObject import XbrlObject, XbrlReferencableModelObject, XbrlTaxonomyTagObject, XbrlObjectType
from .XbrlTypes import (XbrlTaxonomyModelType, XbrlModuleType, XbrlLayoutType, XbrlReportType, XbrlUnitTypeType,
                        QNameKeyType, SQNameKeyType, DefaultTrue, DefaultFalse, DefaultZero, DefaultOne, OptionalList, OptionalNonemptySet)
from .ValidateXbrlModel import validateCompiledModel
from .ValidateReport import validateReport, validateDateResolutionConceptFacts
from .SelectImportedObjects import selectImportedObjects
from .ModelValueMore import SQName, QNameAt
from .ViewXbrlTaxonomyObject import viewXbrlTaxonomyObject
from .XbrlConst import xbrl, oimTaxonomyDocTypePattern, oimTaxonomyDocTypes, oimTaxonomyDocTypes, xbrlTaxonomyObjects
from .ParseSelectionWhereClause import parseSelectionWhereClause
from .LoadCsvTable import csvTableRowFacts
from .SaveModel import xbrlModelSave
from .SaveXmlSchema import saveXmlSchema

from arelle.oim.Load import (DUPJSONKEY, DUPJSONVALUE, EMPTY_DICT, EMPTY_LIST, UrlInvalidPattern,
                             OIMException, NotOIMException)

RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
OIMT_SCHEMA = os.path.join(RESOURCES_DIR, "oim-taxonomy-schema.json")

PROFILE_MIN_TIME = 0.1

saveOIMTaxonomySchemaFiles = False
SAVE_XML_SCHEMA_CMDLINE_PARAMETER = "--saveXMLSchemaFiles"
SAVE_XML_SCHEMA_FORMULA_PARAMETER = qname("saveXMLSchemaFiles", noPrefixIsNoNamespace=True)
jsonschemaValidator = None

xbrlTypeAliasClass = {
    XbrlLabelType: XbrlLabel,
    XbrlLayoutType: XbrlLayout,
    XbrlPropertyType: XbrlProperty,
    XbrlTaxonomyModelType: XbrlCompiledModel,
    XbrlModuleType: XbrlModule,
    XbrlReportType: XbrlModule,
    XbrlUnitTypeType: XbrlUnitType
    }

EMPTY_SET = set()
EMPTY_DICT = {}
UNSPECIFIABLE_STR = '\uDBFE' # impossible unicode character

def jsonGet(tbl, key, default=None):
    if isinstance(tbl, dict):
        return tbl.get(key, default)
    return default

def loadXbrlModule(cntlr, error, warning, modelXbrl, moduleFile, mappedUri, **kwargs):
    global jsonschemaValidator
    from arelle import ModelDocument, ModelXbrl, XmlUtil
    from arelle.ModelDocument import ModelDocument, ModelDocumentReference
    from arelle.ModelValue import qname

    _return = None # modelDocument or an exception

    try:
        currentAction = "initializing"
        startingErrorCount = len(modelXbrl.errors) if modelXbrl else 0
        startedAt = time.time()
        documentType = None # set by loadDict
        importingTxmyObj = kwargs.get("importingTxmyObj")

        currentAction = "loading and parsing OIM Taxonomy module"
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
                    if key in ("namespaces", "xbrlModel"):
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

        errPrefix = "oime"
        try:
            if isinstance(moduleFile, dict) and moduleFile.get("documentInfo",{}).get("documentType") in oimTaxonomyDocTypes:
                moduleFileObj = moduleFile
                href = "BakedInConstants"
                moduleFileName = href
                moduleFileBasename = os.path.basename(moduleFileName)
                txBase = None
            else:
                href = os.path.basename(moduleFile)
                moduleFileName = moduleFile
                txBase = os.path.dirname(moduleFile) # import referenced taxonomies
                moduleFileBasename = os.path.basename(moduleFileName)
                fileExt = os.path.splitext(moduleFile)[1].lower()
                cntlr.showStatus(_("Loading OIM taxonomy file: {0}").format(moduleFileBasename))
                if fileExt == ".json":
                    _file = modelXbrl.fileSource.file(moduleFile, encoding="utf-8-sig")[0]
                    with _file as f:
                        moduleFileObj = json.load(f, object_pairs_hook=loadDict, parse_float=Decimal)
                elif fileExt == ".cbor":
                    _file = modelXbrl.fileSource.file(moduleFile, binary="true")[0]
                    with _file as f:
                        moduleFileObj = cbor2.load(f)
            modelXbrl.profileActivity(f"Load OIM Taxonomy file {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)

        except UnicodeDecodeError as ex:
            raise OIMException("{}:invalidJSON".format(errPrefix),
                  _("File MUST use utf-8 encoding: %(file)s, error %(error)s"),
                  sourceFileLine=moduleFile, error=str(ex))
        except json.JSONDecodeError as ex:
            raise OIMException("{}:invalidJSON".format(errPrefix),
                    "JSON error while %(action)s, %(file)s, error %(error)s",
                    file=moduleFile, action=currentAction, error=ex)
        except FileNotFoundError as ex:
            raise OIMException("{}:noFile".format(errPrefix),
                    "File IO error while %(action)s, %(file)s, error %(error)s",
                    file=moduleFile, action=currentAction, error=ex)
        # schema validation
        if jsonschemaValidator is None:
            cntlr.showStatus(_("Loading schema validator schema file"))
            with io.open(OIMT_SCHEMA, mode="rt") as fh:
                jsonschemaValidator = jsonSchemaLoaderMethod(json.load(fh))
            modelXbrl.profileActivity("Load schema validator schema file", minTimeToShow=PROFILE_MIN_TIME)
        cntlr.showStatus(_("Schema validating: {0}").format(moduleFileBasename))
        if JSON_SCHEMA_VALIDATOR == "jsonschema":
            try:
                for err in jsonschemaValidator.iter_errors(moduleFileObj) or ():
                    path = []
                    p_last = p_beforeLast = None
                    for p in err.absolute_path:
                        path.append(f"[{p}]" if isinstance(p,int) else f"/{p}")
                        p_beforeLast = p_last
                        p_last = p
                    msg = err.message
                    if p_last == "allowedAsLinkProperty" and " is not of type " in msg:
                        errCode = "oimte:invalidPropertyValue"
                    elif " is a required property" in msg:
                        errCode = "oimte:invalidJSONStructureMissingRequiredProperty"
                    elif "Additional properties are not allowed " in msg:
                        errCode = "oimte:invalidJSONStructureInvalidPropertyDefined"
                    elif p_last == "language" and " does not match " in msg:
                        errCode = "oimte:invalidLanguage"
                    elif p_last == "coreDimensions" and "unique elements" in msg:
                        errCode = "oimte:duplicateCoreDimension"
                    elif p_beforeLast == "dimensions" and " valid under each of {'required': ['domainClass']}, {'required': ['domainDataType']}" in msg:
                        errCode = "oimte:invalidDimensionObject"
                    else:
                        errCode = "oime:invalidJSONStructure",
                    error(errCode,
                          _("Error: %(error)s, jsonObj: %(path)s"),
                          sourceFileLine=href, error=msg, path="".join(path))
            except (jsonschema.exceptions.SchemaError, jsonschema.exceptions._RefResolutionError, jsonschema.exceptions.UndefinedTypeCheck) as ex:
                msg = str(ex)
                if "PointerToNowhere" in msg:
                    msg = msg[:121]
                error("jsonschema:schemaError",
                      _("Error in json schema processing: %(error)s"),
                      sourceFileLine=href, error=msg)
        elif JSON_SCHEMA_VALIDATOR == "fastjsonschema":
            try:
                jsonschemaValidator(moduleFileObj)
            except fastjsonschema.JsonSchemaValueException as ex:
                # only provides first schema error in source object
                # see: https://github.com/horejsek/python-fastjsonschema/issues/36
                path = []
                p_last = p_beforeLast = None
                for p in ex.path:
                    path.append(f"[{p}]" if isinstance(p,int) else f"/{p}")
                    p_beforeLast = p_last
                    p_last = p
                msg = ex.message
                if p_last == "allowedAsLinkProperty" and " must be boolean" in msg:
                    errCode = "oimte:invalidPropertyValue"
                elif re.match(r".* must contain .* properties", msg):
                    errCode = "oimte:invalidJSONStructureMissingRequiredProperty"
                elif re.match(r".* must not contain .* properties", msg):
                    errCode = "oimte:invalidJSONStructureInvalidPropertyDefined"
                elif p_last == "language" and " must match " in msg:
                    errCode = "oimte:invalidLanguage"
                elif p_last == "coreDimensions" and " unique items" in msg:
                    errCode = "oimte:duplicateCoreDimension"
                elif p_beforeLast == "dimensions" and isinstance(ex.rule_definition, list) and all(k == "required" for o in ex.rule_definition for k in o.keys()):
                    errCode = "oimte:invalidDimensionObject"
                else:
                    errCode = "oimte:invalidJSONStructure",
                error(errCode,
                      _("Error: %(error)s, jsonObj: %(path)s"),
                      sourceFileLine=href, error=msg, path="".join(path))
        elif JSON_SCHEMA_VALIDATOR == "jsonschema_rs":
            try:
                jsonschemaValidator.validate(moduleFileObj)
            except Exception as ex: # jsonschema_rs.alidationError as ex:
                error("oime:invalidJSONStructure",
                      _("Error: %(error)s"),
                      sourceFileLine=href, error=str(ex))
        modelXbrl.profileActivity(f"Json schema validation {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)
        cntlr.showStatus(_("Loading model objects from: {0}").format(moduleFileBasename))
        documentInfo = jsonGet(moduleFileObj, "documentInfo", {})
        documentType = jsonGet(documentInfo, "documentType")
        moduleObj = jsonGet(moduleFileObj, "xbrlModel", {})
        isReport = "report" in moduleFileObj # for test purposes report facts can be in json object
        if not documentType:
            error("oimce:unsupportedDocumentType",
                  _("/documentInfo/docType is missing."),
                  file=moduleFile)
        elif documentType not in oimTaxonomyDocTypes:
            error("oimce:unsupportedDocumentType",
                  _("Unrecognized /documentInfo/docType: %(documentType)s"),
                  file=moduleFile, documentType=documentType)
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
                  moduleFileName,
                  initialComment="loaded from OIM Taxonomy {}".format(mappedUri),
                  documentEncoding="utf-8",
                  # base=txBase or modelXbrl.entryLoadingUrl
                  )
            schemaDoc.inDTS = True
            xbrlCompMdl = castToXbrlCompiledModel(modelXbrl, isReport)
        else: # API implementation
            xbrlCompMdl = ModelDts.create(
                cntlr.modelManager,
                Type.SCHEMA,
                initialComment="loaded from OIM Taxonomy {}".format(mappedUri),
                base=txBase)
            _return = xbrlCompMdl.modelDocument
        if len(modelXbrl.errors) > prevErrLen:
            error("oime:invalidTaxonomy",
                  _("Unable to obtain a valid taxonomy from URLs provided"),
                  sourceFileLine=href)
        # first OIM Taxonomy load Baked In objects
        if not xbrlCompMdl.namedObjects and not "loadingBakedInObjects" in kwargs:
            # load object types (internally for now, switch to xbrl-objectTypes.json when covered by spec)
            for objTypeQn in sorted(xbrlObjectTypes.keys()):
                newObj = XbrlObjectType(xbrlMdlObjIndex=len(xbrlCompMdl.xbrlObjects), name=objTypeQn)
                xbrlCompMdl.xbrlObjects.append(newObj)
            #loadXbrlModule(cntlr, error, warning, modelXbrl, xbrlTaxonomyObjects, "BakedInCoreObjects", loadingBakedInObjects=True, **kwargs)
            loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "xs-types.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "xbrlSpec.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            #loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "xbrl-objects.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "types.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "utr.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "ref.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
            loadXbrlModule(cntlr, error, warning, modelXbrl, os.path.join(RESOURCES_DIR, "iso4217.json"), "BakedInXbrlSpecObjects", loadingBakedInObjects=True, **kwargs)
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
                namespaceUrls[prefix] = url
        xbrlModelName = qname(moduleObj.get("name"), prefixNamespaces)
        if not xbrlModelName:
            xbrlCompMdl.error("oime:missingQNameProperty",
                          _("Taxonomy must have a name (QName) property"),
                          sourceFileLine=href)

        # check extension properties (where metadata specifies CheckPrefix)
        for extPropSQName, extPropertyPath in extensionProperties.items():
            extPropPrefix = extPropSQName.partition(":")[0]
            if extPropPrefix not in prefixNamespaces:
                error("oimte:unboundPrefix",
                      _("The extension property QName prefix was not defined in namespaces: %(extensionProperty)s."),
                      sourceFileLine=href, extensionProperty=extPropertyPath)

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
        def createModelObject(jsonObj, oimParentObj, keyClass, objClass, newObj, pathParts):
            keyValue = None
            relatedNames = [] # to tag an object with labels or references
            oimParentTypes = (type(oimParentObj), type(oimParentObj).__name__) # allow actual type or TypeAlias type
            unexpectedJsonProps = set(jsonObj.keys())
            propertyMap = getattr(objClass, "_propertyMap", EMPTY_DICT).get(type(oimParentObj), EMPTY_DICT)
            for propName, propType in objClass.propertyNameTypes():
                if isinstance(propType, GenericAlias) or (isinstance(propType, _GenericAlias) and propType.__origin__ == list):
                    propClass = propType.__origin__ # collection type such as OrderedSet, dict
                    collectionProp = propClass()
                    setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                else:
                    propClass = propType
                if propertyMap.get(propName) in jsonObj:
                    jsonKey = propertyMap[propName]  # use mapped name instead
                else:
                    jsonKey = propName
                if jsonKey in jsonObj:
                    unexpectedJsonProps.remove(jsonKey)
                    jsonValue = jsonObj[jsonKey]
                    if (isinstance(propType, GenericAlias) or
                        (isinstance(propType, _UnionGenericAlias) and isinstance(propType.__args__[0], GenericAlias) and propType.__args__[0].__origin__ == OrderedSet) or
                        (isinstance(propType, _GenericAlias) and propType.__origin__ in (list, set, OrderedSet))):
                        # for Optional OrderedSets where the jsonValue exists, handle as propType, _keyClass and eltClass
                        if isinstance(propType.__args__[0], GenericAlias) and len(propType.__args__[0].__args__) == 1 and propType.__args__[0].__origin__ == OrderedSet:
                            # handle as non-optional OrderedSet
                            propClass = propType.__args__[0].__origin__ # collection type such as OrderedSet
                            collectionProp = propClass()
                            setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                            _keyClass = None
                            eltClass = propType.__args__[0].__args__[0]
                        elif isinstance(propType, _GenericAlias) and propType.__origin__ in (list, set, OrderedSet):
                            propClass = propType.__origin__
                            collectionProp = propClass()
                            setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                            _keyClass = None
                            eltClass = propType.__args__[0]
                        elif len(propType.__args__) == 2: # dict
                            _keyClass = propType.__args__[0] # class of key such as QNameKey
                            eltClass = propType.__args__[1] # class of collection elements such as XbrlConcept
                        elif len(propType.__args__) == 1: # set such as OrderedSet or list
                            _keyClass = None
                            eltClass = propType.__args__[0]
                        if isinstance(jsonValue, list):
                            for iObj, listObj in enumerate(jsonValue):
                                if isinstance(eltClass, str) or getattr(eltClass, "__name__", "").startswith("Xbrl"): # nested Xbrl objects
                                    if propName == "selections" and isinstance(listObj, str):
                                        listObj = parseSelectionWhereClause(listObj) # parse unstructured selection
                                    if isinstance(listObj, dict):
                                        # this handles lists of dict objects.  For dicts of key-value dict objects see above.
                                        createModelObjects(propName, listObj, newObj, pathParts + [f'{propName}[{iObj}]'])
                                    else:
                                        error("oimte:invalidObjectType",
                                              _("Object expected but non-object found: %(listObj)s, jsonObj: %(path)s"),
                                              sourceFileLine=href, listObj=listObj, path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                elif isinstance(listObj, dict) and get_origin(eltClass) is Union and getattr(eltClass.__args__[0], "__name__", "").startswith("Xbrl"): # nested Xbrl objects such as selector
                                    print(f"union propName {propName}")
                                    createModelObjects(propName, listObj, newObj, pathParts + [f'{propName}[{iObj}]'])
                                else: # collection contains ordinary values
                                    if eltClass in (QName, QNameKeyType, SQName, SQNameKeyType):
                                        listObj = qname(listObj, prefixNamespaces)
                                        if listObj is None:
                                            error("oimte:objectNamespacePrefixNotDefined",
                                                  _("QName has undefined prefix: %(qname)s, jsonObj: %(path)s"),
                                                  sourceFileLine=href, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                            # must have None value for validation to work
                                        if propName == "relatedNames":
                                            relatedNames.append(listObj)
                                    if propClass in (set, OrderedSet, OptionalNonemptySet):
                                        try:
                                            if listObj not in collectionProp:
                                                collectionProp.add(listObj)
                                            else:
                                                error("oimte:duplicateObjects",
                                                      _("Duplicate %(listObj)s in jsonObj: %(path)s"),
                                                      sourceFileLine=href, listObj=listObj, path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                        except TypeError as ex:
                                            print("exception adding collection property")
                                    else:
                                        collectionProp.append(listObj)
                            if propClass == OptionalNonemptySet and not collectionProp:
                                error("oimte:invalidEmptySet",
                                      _("Invalid empty set %(propName)s in jsonObj: %(path)s"),
                                      sourceFileLine=href, propName=propName, path="/".join(pathParts + [propName]))
                        elif isinstance(jsonValue, dict) and _keyClass is not None:
                            for iObj, (valKey, valVal) in enumerate(jsonValue.items()):
                                if isinstance(_keyClass, type) and issubclass(_keyClass,QName):
                                    if jsonKey == "dimensions" and objClass == XbrlFact:
                                        valKey = coreDimensionsByLocalname.get(valKey, valKey) # unprefixed core dimension localNames
                                    _valKey = qname(valKey, prefixNamespaces)
                                    if _valKey is None:
                                        error("oimte:objectNamespacePrefixNotDefined",
                                              _("QName has undefined prefix: %(qname)s, jsonObj: %(path)s"),
                                              sourceFileLine=href, qname=_valKey, path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                        # must have None value for validation to work
                                elif isinstance(_keyClass, str):
                                    _valKey = valKey
                                else:
                                    continue
                                collectionProp[_valKey] = valVal
                    elif isinstance(propType, _UnionGenericAlias) and isinstance(propType.__args__[0], GenericAlias) and propType.__args__[-1] == type(None) and isinstance(jsonValue,list): # optional embdded list of objects like allowedCubeDimensions
                        eltClass = propType.__args__[0].__args__[0]
                        for iObj, listObj in enumerate(jsonValue):
                            if iObj == 0: # create collection only if any objects for collection
                                propClass = propType.__args__[0].__origin__ # collection type such as OrderedSet, dict
                                collectionProp = propClass()
                                setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                        createModelObjects(propName, listObj, newObj, pathParts + [f'{propName}[{iObj}]'])
                    elif isinstance(propType, _UnionGenericAlias) and propType.__args__[-1] == type(None) and isinstance(jsonValue,dict): # optional embdded object
                        createModelObjects(propName, jsonValue, newObj, pathParts + [propName]) # object property
                    elif isinstance(propType, type) and issubclass(propType, XbrlObject) and isinstance(jsonValue,dict): # mandatory embdded object
                        createModelObjects(propName, jsonValue, newObj, pathParts + [propName]) # object property
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
                                error("oimte:objectNamespacePrefixNotDefined",
                                      _("QName has undefined prefix: %(qname)s, jsonObj: %(path)s"),
                                      sourceFileLine=href, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [propName])}")
                                if optional:
                                    jsonValue = None
                                else:
                                    jsonValue = qnErrorQname # allow processing to proceed with marker bad qname
                            elif propType == QNameAt:
                                jsonValue = QNameAt(jsonValue.prefix, jsonValue.namespaceURI, jsonValue.localName, atSuffix)
                            if propName == "relatedName":
                                relatedNames.append(jsonValue)
                        setattr(newObj, propName, jsonValue)
                        if (keyClass and keyClass == propType) or (not keyClass and propType in (QNameKeyType, SQNameKeyType)):
                            keyValue = jsonValue # e.g. the QNAme of the new object for parent object collection
                elif (propType in oimParentTypes or # propType may be a TypeAlias which is a string name of class
                      (isinstance(propType, _UnionGenericAlias) and any(t.__forward_arg__ in oimParentTypes for t in propType.__args__ if isinstance(t,ForwardRef)))): # Union of TypeAliases are ForwardArgs
                    setattr(newObj, propName, oimParentObj)
                elif (((get_origin(propType) is Union) or isinstance(get_origin(propType), type(Union))) and # Optional[ ] type
                       propType.__args__[-1] in (type(None), DefaultTrue, DefaultFalse, DefaultZero, DefaultOne)):
                          setattr(newObj, propName, {type(None): None, DefaultTrue: True, DefaultFalse: False, DefaultZero:0, DefaultOne:1}[propType.__args__[-1]]) # use first of union for prop value creation
                else: # absent json element
                    if not (propClass in (dict, set, OrderedSet, OrderedDict) or
                            (isinstance(propClass, _GenericAlias) and propClass.__origin__ == list)):
                        if propClass not in (OptionalList, OptionalNonemptySet): # OptionalList, OptionalNonemptySet is null if completely absent, not an empty list
                            jsonEltsReqdButMissing.append(f"{'/'.join(pathParts + [propName])}")
                        setattr(newObj, propName, None) # not defaultable but set to None anyway
            if unexpectedJsonProps:
                for propName in unexpectedJsonProps:
                    jsonEltsNotInObjClass.append(f"{'/'.join(pathParts + [propName])}={jsonObj.get(propName,'(absent)')}")
            if (isinstance(newObj, XbrlReferencableModelObject) or # most referencable taxonomy objects
                (isinstance(newObj, (XbrlFact, XbrlFootnote, XbrlFactSource, XbrlFactMap)) and isinstance(oimParentObj, XbrlModule))): # taxonomy-owned fact
                if keyValue is not None: # otherwise expect some error occured above
                    if keyValue in xbrlCompMdl.namedObjects:
                        namedObjectDuplicates[keyValue].add(newObj)
                        namedObjectDuplicates[keyValue].add(xbrlCompMdl.namedObjects[keyValue])
                    else:
                        xbrlCompMdl.namedObjects[keyValue] = newObj
            elif isinstance(newObj, XbrlTaxonomyTagObject) and relatedNames:
                for relatedQn in relatedNames:
                    xbrlCompMdl.tagObjects[relatedQn].append(newObj)
            return keyValue

        def createModelObjects(jsonKey, jsonObj, oimParentObj, pathParts):
            # find collection owner in oimParentObj
            for objName in (jsonKey, plural(jsonKey)):
                ownrPropType = getattr(oimParentObj, "__annotations__", EMPTY_DICT).get(objName)
                if ownrPropType is not None:
                    break
            if ownrPropType is not None:
                ownrProp = getattr(oimParentObj, objName, None) # owner collection or property
                if ownrPropType is not None:
                    keyClass = None
                    if isinstance(ownrPropType, GenericAlias):
                        ownrPropClass = ownrPropType.__origin__ # collection type such as OrderedSet, dict
                        if len(ownrPropType.__args__) == 2: # dict
                            keyClass = ownrPropType.__args__[0] # class of key such as QNameKey
                            objClass = ownrPropType.__args__[1] # class of obj such as XbrlConcept
                        elif len(ownrPropType.__args__) == 1: # set such as OrderedSet or list
                            keyClass = None
                            objClass = ownrPropType.__args__[0]
                    elif isinstance(ownrPropType, _UnionGenericAlias) and isinstance(ownrPropType.__args__[0], GenericAlias) and ownrPropType.__args__[-1] == type(None): # optional embdded list of objects like allowedCubeDimensions
                        objClass = ownrPropType.__args__[0].__args__[0]
                    elif isinstance(ownrPropType, _UnionGenericAlias) and ownrPropType.__args__[-1] == type(None): # optional nested object
                        objClass = ownrPropType.__args__[0]
                    elif isinstance(ownrPropType, _GenericAlias): # e.g. OptionalList
                        objClass = ownrPropType.__args__[0]
                    else: # parent      is just an object field, not a  collection
                        objClass = ownrPropType # e.g just a Concept but no owning collection
                    if get_origin(objClass) is Union: # union of structured class or string such as select
                        objClass = objClass.__args__[0]
                    if objClass == XbrlModuleType:
                        objClass = XbrlModule
                    elif objClass == XbrlLayoutType:
                        objClass = XbrlLayout
                    if isinstance(objClass,ForwardRef) and objClass.__forward_arg__ in xbrlTypeAliasClass:
                        objClass = xbrlTypeAliasClass[objClass.__forward_arg__]
                    if issubclass(objClass, XbrlObject):
                        newObj = objClass(xbrlMdlObjIndex=len(xbrlCompMdl.xbrlObjects)) # e.g. this is the new Concept
                        xbrlCompMdl.xbrlObjects.append(newObj)
                        classCountProp = f"_{objClass.__name__}Count"
                        classIndex = getattr(oimParentObj, classCountProp, 0)
                        setattr(newObj, "_classIndex", classIndex)
                        setattr(oimParentObj, classCountProp, classIndex+1)
                    else:
                        newObj = objClass() # e.g. XbrlProperty
                    keyValue = createModelObject(jsonObj, oimParentObj, keyClass, objClass, newObj, pathParts)
                    if isinstance(ownrPropType, GenericAlias):
                        if len(ownrPropType.__args__) == 2:
                            if keyValue:
                                ownrProp[keyValue] = newObj
                        elif isinstance(ownrProp, (set, OrderedSet)):
                            ownrProp.add(newObj)
                        else:
                            ownrProp.append(newObj)
                    elif isinstance(ownrPropType, _UnionGenericAlias) and ownrPropType.__args__[-1] == type(None): # optional nested object
                        if isinstance(ownrProp, (set, OrderedSet)):
                            ownrProp.add(newObj)
                        else:
                            setattr(oimParentObj, pathParts[-1], newObj)
                    elif isinstance(ownrPropType, _GenericAlias):
                        if issubclass(ownrPropType.__origin__, (set, OrderedSet)):
                            ownrProp.add(newObj)
                        elif issubclass(ownrPropType.__origin__, list):
                            ownrProp.append(newObj)
                    elif isinstance(ownrPropType, type) and issubclass(ownrPropType, XbrlObject):
                        setattr(oimParentObj, jsonKey, newObj)
                    return newObj
            return None

        if "xbrlModel" not in moduleFileObj:
            error("oimce:unsupportedDocumentType",
                  _("Missing /xbrlModel object"),
                  file=moduleFile)
            return {}

        newModule = createModelObjects("xbrlModel", moduleFileObj["xbrlModel"], xbrlCompMdl, ["", "xbrlModel"])
        modelXbrl.profileActivity(f"Create taxonomy objects from {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)
        newModule._prefixNamespaces = prefixNamespaces
        if isReport:
            newReport = createModelObjects("report", moduleFileObj["report"], xbrlCompMdl, ["", "report"])
            newReport._prefixNamespaces = prefixNamespaces
            newReport._url = moduleFile
            modelXbrl.profileActivity(f"Create report objects from {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)
        newModule._lastMdlObjIndex = len(xbrlCompMdl.xbrlObjects) - 1
        schemaDoc._txmyModule = newModule


        if jsonEltsNotInObjClass:
            error("arelle:undeclaredOimTaxonomyJsonElements",
                  _("Json file has elements not declared in Arelle object classes: %(undeclaredElements)s"),
                  sourceFileLine=href, undeclaredElements=", ".join(jsonEltsNotInObjClass))
        if jsonEltsReqdButMissing:
            error("arelle:missingOimTaxonomyJsonElements",
                  _("Json file missing required elements: %(missingElements)s"),
                  sourceFileLine=href, missingElements=", ".join(jsonEltsReqdButMissing))

        for qname, dupObjs in namedObjectDuplicates.items():
            xbrlCompMdl.error("oimte:duplicateObjects",
                  _("Multiple referenceable objects have the same name: %(qname)s"),
                  xbrlObject=dupObjs, qname=qname)

        # remove imported objects not wanted

        if newModule is not None:
            for impTxObj in newModule.importedTaxonomies:
                if impTxObj.xbrlModelName and impTxObj.xbrlModelName not in xbrlCompMdl.xbrlModels:
                    # is it present in urlMapping?
                    url = None
                    foundMismatchedNameReported = False
                    for url in namespaceUrls.get(impTxObj.xbrlModelName.prefix, ()):
                        normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(url, moduleFileName)
                        if modelXbrl.fileSource.isMappedUrl(normalizedUri):
                            mappedUrl = modelXbrl.fileSource.mappedUrl(normalizedUri)
                        elif PackageManager.isMappedUrl(normalizedUri):
                            mappedUrl = PackageManager.mappedUrl(normalizedUri)
                        else:
                            mappedUrl = modelXbrl.modelManager.disclosureSystem.mappedUrl(normalizedUri)
                        impSchemaDoc = loadXbrlModule(cntlr, error, warning, modelXbrl,
                                                       mappedUrl, url, importingTxmyObj=impTxObj)
                        if isinstance(impSchemaDoc, ModelDocument): # if an exception object is returned, loading didn't succeed\
                            if impSchemaDoc._txmyModule.name == impTxObj.xbrlModelName:
                                impTxObj._txmyModule = impSchemaDoc._txmyModule
                                selectImportedObjects(xbrlCompMdl, newModule, impTxObj)
                            else:
                                xbrlCompMdl.error("oimte:taxonomyNotFound",
                                                  _("Imported taxonomy for %(qname)s found at %(url)s has mismatching xbrlModelName %(name)s."),
                                                  xbrlObject=impTxObj, url=url, qname=impTxObj.xbrlModelName, name= impSchemaDoc._txmyModule.name)
                                foundMismatchedNameReported = True
                    if not getattr(impTxObj, "_txmyModule", None) and not foundMismatchedNameReported:
                        xbrlCompMdl.error("oimte:taxonomyNotFound",
                                          _("Imported taxonomy for %(qname)s not found at %(url)s because the URL mapping namespace is incorrect."),
                                          xbrlObject=impTxObj, url=url, qname=impTxObj.xbrlModelName)

        modelXbrl.profileActivity(f"Load taxonomies imported from {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)
        if xbrlModelName is not None: # otherwise some error would have occured
            xbrlCompMdl.namespaceDocs[xbrlModelName.namespaceURI].append(schemaDoc)

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
        if "cubes" in moduleObj and not any(t["namespace"] == "http://xbrl.org/2005/xbrldt" for t in taxonomyRefs):
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
                      modelObject=modelXbrl, path=f"xbrlModel/concept[{conceptI+1}]", name=conceptObj.get("name", ""))

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
            .get(SAVE_XML_SCHEMA_FORMULA_PARAMETER, ("",None))[1] not in (None, "", "false")):
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

def xbrlModelValidator(val, parameters):
    if not isinstance(val.modelXbrl, XbrlCompiledModel): # if no ModelCompiledXbrl give up
        return
    try:
        # validate taxonomy model
        validateCompiledModel(val.modelXbrl)

        # validate facts whose values represent dateResolution concepts first
        validateDateResolutionConceptFacts(val.modelXbrl)

        # build search vocabulary to support cube construction (after date resolution concepts validated)
        from .VectorSearch import buildXbrlVectors
        buildXbrlVectors(val.modelXbrl)

        # validate facts whose values represent dateResolution concepts first
        for reportQn, reportObj in val.modelXbrl.reports.items():
            validateReport(reportQn, reportObj, val.modelXbrl)
    except Exception as ex:
        val.modelXbrl.error("arelleOIMloader:error",
                "Error while validating, error %(errorType)s %(error)s\n traceback %(traceback)s",
                modelObject=val.modelXbrl, errorType=ex.__class__.__name__, error=ex,
                traceback=traceback.format_tb(sys.exc_info()[2]))

lastFilePath = None
lastFilePathIsOIM = False

def isXbrlModelLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    global lastFilePath, lastFilePathIsOIM
    lastFilePath = None
    lastFilePathIsOIM = False
    _ext = os.path.splitext(filepath)[1]
    if _ext == ".json":
        try:
            with io.open(filepath, 'rt', encoding='utf-8') as f:
                _fileStart = f.read(4096)
            if _fileStart and oimTaxonomyDocTypePattern.match(_fileStart):
                lastFilePathIsOIM = True
                lastFilePath = filepath
        except IOError:
            pass # nothing to open
    elif _ext == ".cbor":
        try:
            with io.open(filepath, 'rb', buffering=2048) as f:
                decoder = cbor2.CBORDecoder(f)
                obj = decoder.decode() # this stream-reads outermost object, documentInfo should be first
                if (isinstance(obj, dict) and isinstance(obj.get("documentInfo",{}), dict) and
                    obj.get("documentInfo",{}).get("documentType","") in oimTaxonomyDocTypes):
                    lastFilePathIsOIM = True
                    lastFilePath = filepath
        except IOError as ex:
            print(ex)
            pass # nothing to open
    return lastFilePathIsOIM

def xbrlModelLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    if filepath != lastFilePath or not lastFilePathIsOIM:
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    modelXbrl.profileActivity()
    doc = loadXbrlModule(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri, **kwargs)
    if doc is None:
        return None # not an OIM file
    return doc

def optionsExtender(parser, *args, **kwargs):
    parser.add_option(SAVE_XML_SCHEMA_CMDLINE_PARAMETER,
                      action="store",
                      dest="saveXMLSchemaFiles",
                      help=_("Save OIM taxonomy namespaces to xsd files in specified directory."))

def filingStart(self, options, *args, **kwargs):
    #global saveOIMTaxonomySchemaFiles
    #if options.saveOIMTaxonomySchemaFiles:
    #    saveOIMTaxonomySchemaFiles = True
    pass

def xbrlModelLoaded(cntlr, options, xbrlCompMdl, *args, **kwargs):
    # index groupContents
    if not isinstance(xbrlCompMdl, XbrlCompiledModel):
        return

    xbrlCompMdl.groupContents = defaultdict(OrderedSet)
    for txmy in xbrlCompMdl.xbrlModels.values():
        for grpCnts in txmy.groupContents:
            for relName in getattr(grpCnts, "relatedNames", ()): # if object was invalid there are no attributes, e.g. bad QNames
                xbrlCompMdl.groupContents[grpCnts.groupName].add(relName)

    # load CSV tables
    for reportQn, reportObj in xbrlCompMdl.reports.items():
        for table in reportObj.tables.values():
            for rowIndex, rowFacts in csvTableRowFacts(table, xbrlCompMdl, xbrlCompMdl.error, xbrlCompMdl.warning, reportObj._url):
                for fact in rowFacts:
                    reportObj.facts[fact.name] = fact


    # save schema files if specified
    saveXmlSchemaFiles = None
    if options is not None and  options.saveXMLSchemaFiles:
        saveXmlSchemaFiles = options.saveXMLSchemaFiles
    else:
        param = cntlr.modelManager.formulaOptions.typedParameters(xbrlCompMdl.prefixedNamespaces
            ).get(SAVE_XML_SCHEMA_FORMULA_PARAMETER, ("",None))
        if param is not None:
            saveXmlSchemaFiles = param[1]
    if saveXmlSchemaFiles:
        saveXmlSchema(cntlr, xbrlCompMdl, saveXmlSchemaFiles)


def xbrlModelViews(cntlr, xbrlCompMdl):
    xbrlModelLoaded(cntlr, None, xbrlCompMdl)
    if isinstance(xbrlCompMdl, XbrlCompiledModel):
        initialViews = []
        if getattr(xbrlCompMdl, "reports", ()): # has instance facts
            initialViews.append( (XbrlReport, cntlr.tabWinTopRt, "Reports") )
        initialViews.extend(((XbrlConcept, cntlr.tabWinBtm, "XBRL Concepts"),
                             (XbrlGroup, cntlr.tabWinTopRt, "XBRL Groups"),
                             (XbrlNetwork, cntlr.tabWinTopRt, "XBRL Networks"),
                             (XbrlCube, cntlr.tabWinTopRt, "XBRL Cubes")
                            ))
        if any(xbrlCompMdl.filterNamedObjects(XbrlFact)):
            initialViews.append( (XbrlFact, cntlr.tabWinTopRt, "Taxonomy Facts") )
        initialViews = tuple(initialViews)
        additionalViews = ((XbrlAbstract, cntlr.tabWinBtm, "XBRL Abstracts"),
                           (XbrlCubeType, cntlr.tabWinBtm, "XBRL Cube Types"),
                           (XbrlDataType, cntlr.tabWinBtm, "XBRL Data Types"),
                           (XbrlEntity, cntlr.tabWinBtm, "XBRL Entities"),
                           (XbrlGroupTree, cntlr.tabWinTopRt, "XBRL Group Tree"),
                           (XbrlLabel, cntlr.tabWinBtm, "XBRL Labels"),
                           (XbrlLabelType, cntlr.tabWinBtm, "XBRL Label Types"),
                           (XbrlPropertyType, cntlr.tabWinBtm, "XBRL Property Types"),
                           (XbrlReference, cntlr.tabWinBtm, "XBRL References"),
                           (XbrlReferenceType, cntlr.tabWinBtm, "XBRL Reference Types"),
                           (XbrlRelationshipType, cntlr.tabWinBtm, "XBRL Relationship Types"),
                           (XbrlTransform, cntlr.tabWinBtm, "XBRL Transforms"),
                           (XbrlUnit, cntlr.tabWinBtm, "XBRL Units"),)
        for view in initialViews:
            viewXbrlTaxonomyObject(xbrlCompMdl, *view, additionalViews)

        return True # block ordinary taxonomy views
    return False

__pluginInfo__ = {
    'name': 'XBRL Model',
    'version': '1.2',
    'description': "This plug-in implements XBRL model modules loaded from JSON.",
    'license': 'Apache-2',
    'author': 'Herm Fischer',
    'copyright': 'Exbee Ltd',
    # classes of mount points (required)
    'CntlrCmdLine.Options': optionsExtender,
    'CntlrCmdLine.Filing.Start': filingStart,
    'CntlrCmdLine.Xbrl.Loaded': xbrlModelLoaded,
    'CntlrWinMain.Xbrl.Views': xbrlModelViews,
    'CntlrWinMain.Xbrl.Save': xbrlModelSave,
    'ModelDocument.IsPullLoadable': isXbrlModelLoadable,
    'ModelDocument.PullLoader': xbrlModelLoader,
    'Validate.XBRL.Start': xbrlModelValidator
}
