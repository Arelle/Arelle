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

from typing import TYPE_CHECKING, cast, GenericAlias, Union, _GenericAlias, _UnionGenericAlias, get_origin, ClassVar, ForwardRef, get_args, Dict, Any
import os, io, json, cbor2, sys, time, traceback, inspect, types
JSON_SCHEMA_VALIDATOR = "jsonschema_rs" # select one of below JSON schema validator libraries (seriously different performance)
#JSON_SCHEMA_VALIDATOR = "jsonschema"
#JSON_SCHEMA_VALIDATOR = "fastjsonschema"
if JSON_SCHEMA_VALIDATOR == "jsonschema": # slow and thorough
    import jsonschema
    # finds all errors in source object but can be very slow on complex schemas like ours, especially with many errors
    jsonSchemaLoaderMethod = jsonschema.Draft7Validator
elif JSON_SCHEMA_VALIDATOR == "fastjsonschema": # faster but only provides first schema error
    import fastjsonschema
    # only provides first schema error in source object
    # see: https://github.com/horejsek/python-fastjsonschema/issues/36
    jsonSchemaLoaderMethod = fastjsonschema.compile
elif JSON_SCHEMA_VALIDATOR == "jsonschema_rs": # Rust implemented, fast with all errors via iter_errors
    import jsonschema_rs
    jsonSchemaLoaderMethod = jsonschema_rs.Draft7Validator
import regex as re
from collections import OrderedDict, defaultdict
from decimal import Decimal
from arelle.ModelDocument import load, Type,  create as createModelDocument
from arelle.ModelValue import qname, QName, AnyURI
from arelle.PythonUtil import SEQUENCE_TYPES
from ordered_set import OrderedSet
#from arelle.Version import authorLabel, copyrightLabel
from arelle.XmlUtil import setXmlns
from arelle import ModelDocument, PackageManager, UrlUtil, XmlValidate

# XbrlObject modules contain nested XbrlOBjects and their type objects

from .XbrlHeading import XbrlHeading
from .XbrlConcept import XbrlConcept, XbrlDataType, XbrlUnitType
from .XbrlConst import qnErrorQname, builtInPrefixTaxonomies
from .XbrlCube import (XbrlCube, XbrlCubeDimension, XbrlPeriodConstraint, XbrlDateResolution,
                       XbrlCubeType, coreDimensionsByLocalname)
from .XbrlDimension import XbrlDimension, XbrlDomainNetwork
from .XbrlEntity import XbrlEntity
from .XbrlGroup import XbrlGroup, XbrlGroupContent, XbrlGroupTree
from .XbrlLabel import XbrlLabel, XbrlLabelType
from .XbrlLayout import XbrlLayout
from .XbrlNetwork import XbrlNetwork, XbrlRelationship, XbrlRelationshipType
from .XbrlProperty import XbrlProperty, XbrlPropertyType
from .XbrlReference import XbrlReference, XbrlReferenceType
from .XbrlFact import XbrlFact, XbrlFootnote, XbrlFactSource, XbrlFactMap, XbrlTableTemplate
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlModel import XbrlCompiledModel, castToXbrlCompiledModel
from .XbrlModule import XbrlModule, xbrlObjectTypes
from .XbrlObject import XbrlModelClass, XbrlObject, XbrlReferencableModelObject, XbrlTaxonomyTagObject, XbrlObjectType
from .XbrlTypes import (XbrlTaxonomyModelAlias, XbrlModuleAlias, XbrlLayoutAlias, XbrlUnitTypeAlias,
                        QNameKeyType, SQNameKeyType, DefaultTrue, DefaultFalse, DefaultZero, DefaultOne, OptionalList, OptionalDict, NonemptySet)
from .ValidateXbrlModel import validateCompiledModel
from .ValidateFacts import validateDateResolutionConceptFacts, validateCompleteReportCubes
from .SelectImportedObjects import validateImportSelections, applyDeferredImportPruning
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
    XbrlLayoutAlias: XbrlLayout,
    XbrlPropertyType: XbrlProperty,
    XbrlTaxonomyModelAlias: XbrlCompiledModel,
    XbrlModuleAlias: XbrlModule,
    XbrlUnitTypeAlias: XbrlUnitType
    }

EMPTY_SET = set()
EMPTY_DICT = {}
UNSPECIFIABLE_STR = '\uDBFE' # impossible unicode character

# Characters not permitted unencoded in xs:anyURI (RFC 2396 / RFC 2732).
_anyURIInvalidChars = re.compile(r'[\s|<>{}\\^`]')

def jsonGet(tbl, key, default=None):
    """"""
    if isinstance(tbl, dict):
        return tbl.get(key, default)
    return default

def loadXbrlModule(cntlr, error, warning, modelXbrl, moduleFile, mappedUri, **kwargs):
    """Load an OIM Taxonomy module from JSON file or dict object, return the modelDocument or raise an exception if invalid.
        If modelXbrl is not None, then load as a XbrlModule into the modelXbrl, otherwise create and return a standalone
        XbrlCompiledModel.
    """
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

        def reservedAliasUriMap(namespaces=None):
            reservedAliasUris = {
                "xs": "http://www.w3.org/2001/XMLSchema",
                "iso4217": "http://www.xbrl.org/2003/iso4217",
                "oimce": "https://xbrl.org/2021/oim-common/error",
                "oime": "http://www.xbrl.org/2021/oim/error",
                "dtr-type": "http://www.xbrl.org/dtr/type/*",
            }

            year = None
            if isinstance(namespaces, dict):
                nsXbrl = namespaces.get("xbrl")
                if isinstance(nsXbrl, str):
                    m = re.match(r"https://xbrl\.org/(\d{4})(?:/|$)", nsXbrl)
                    if m:
                        year = m.group(1)
                if year is None:
                    for nsValue in namespaces.values():
                        if isinstance(nsValue, str):
                            m = re.match(r"https://xbrl\.org/(\d{4})(?:/|$)", nsValue)
                            if m:
                                year = m.group(1)
                                break
            if year is None:
                m = re.match(r"https://xbrl\.org/(\d{4})/", documentType or "")
                if m:
                    year = m.group(1)

            if year is None:
                return reservedAliasUris

            reservedAliasUris.update({
                "xbrl": f"https://xbrl.org/{year}",
                "xbrli": f"https://xbrl.org/{year}/instance",
                "ref": f"https://xbrl.org/{year}/ref",
                "utr": f"https://xbrl.org/{year}/utr",
                "xbrltt": f"https://xbrl.org/{year}/transform-types",
                "oimte": f"https://xbrl.org/{year}/oimtaxonomy/error",
            })
            return reservedAliasUris

        def loadDict(keyValuePairs):
            """"""
            _dict = {}
            _valueKeyDict = {}
            for key, value in keyValuePairs:
                if isinstance(value, dict):
                    if key == "documentInfo" and "documentType" in value:
                        nonlocal documentType
                        documentType = value["documentType"]
                    if key in ("namespaces", "xbrlModel"):
                        normalizedDict = {}
                        normalizedValueKeyDict = {}
                        reservedAliasMap = reservedAliasUriMap(value) if key == "namespaces" else EMPTY_DICT
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
                                    ldError("oimce:invalidURIAlias",
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
                                else:
                                    reservedNs = reservedAliasMap.get(_key)
                                    if reservedNs is not None:
                                        if "*" in reservedNs:
                                            reservedNsPrefix = reservedNs.partition("*")[0]
                                            if not _value.startswith(reservedNsPrefix):
                                                ldError("oimce:invalidURIForReservedAlias",
                                                        _("The reserved alias \"%(alias)s\" must map to URI pattern \"%(reservedURI)s\", found \"%(URI)s\"."),
                                                        modelObject=modelXbrl, alias=_key, reservedURI=reservedNs, URI=_value)
                                        elif _value != reservedNs:
                                            ldError("oimce:invalidURIForReservedAlias",
                                                    _("The reserved alias \"%(alias)s\" must map to URI \"%(reservedURI)s\", found \"%(URI)s\"."),
                                                    modelObject=modelXbrl, alias=_key, reservedURI=reservedNs, URI=_value)
                                    for reservedAlias, reservedURI in reservedAliasMap.items():
                                        if reservedAlias != _key and "*" not in reservedURI and _value == reservedURI:
                                            ldError("oimce:invalidAliasForReservedURI",
                                                    _("URI \"%(URI)s\" is reserved for alias \"%(reservedAlias)s\" and must not be bound to alias \"%(alias)s\"."),
                                                    modelObject=modelXbrl, URI=_value, reservedAlias=reservedAlias, alias=_key)
                                            break
                        value.clear() # replace with normalized values
                        for _key, _value in normalizedDict.items():
                            value[_key] = _value
                    if DUPJSONKEY in value:
                        for _errKey, _errValue, _otherValue in value[DUPJSONKEY]:
                            if key in ("namespaces", ):
                                ldError("oimce:multipleURIsForAlias",
                                                _("The %(map)s alias \"%(prefix)s\" is used on uri \"%(uri1)s\" and uri \"%(uri2)s\"."),
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
        moduleFileObj = None
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
        if moduleFileObj is None:
            raise OIMException("{}:noFile".format(errPrefix),
                    "File not loaded for schema validation: %(file)s",
                    file=moduleFile)
        if jsonschemaValidator is None:
            cntlr.showStatus(_("Loading schema validator schema file"))
            with io.open(OIMT_SCHEMA, mode="rt", encoding="utf-8") as fh:
                jsonschemaValidator = jsonSchemaLoaderMethod(json.load(fh))
            modelXbrl.profileActivity("Load schema validator schema file", minTimeToShow=PROFILE_MIN_TIME)
        cntlr.showStatus(_("Schema validating: {0}").format(moduleFileBasename))
        """ JSON Schema Validation, support multiple validator libraries based on constant at top of module.

            jsonschema_rs (Rust) is the recommended default: fast and finds all errors via iter_errors().
            jsonschema (Python) also finds all errors but is much slower on complex schemas.
            fastjsonschema compiles to Python for speed but only reports the first error.

            For some error types such as missing required property or invalid property value, we attempt to map the error message
            to a more specific OIM error code, but for other errors we just report a general invalid JSON structure error with the
            error message from the validator.
        """
        if JSON_SCHEMA_VALIDATOR == "jsonschema_rs":
            try:
                for err in jsonschemaValidator.iter_errors(moduleFileObj):
                    path = []
                    p_last = p_beforeLast = None
                    for p in err.instance_path:
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
                    elif "unique elements" in msg: # any uniqueItems violation is a duplicate set item
                        errCode = "oimte:duplicateItemsInSet"
                    elif p_beforeLast == "dimensions" and ("valid under each of" in msg or "not valid under any of" in msg):
                        errCode = "oimte:invalidDimensionObject"
                    else:
                        errCode = "oime:invalidJSONStructure",
                    error(errCode,
                          _("Error: %(error)s, jsonObj: %(path)s"),
                          sourceFileLine=href, error=msg, path="".join(path))
            except jsonschema_rs.ReferencingError as ex:
                error("jsonschema:schemaError",
                      _("Error in json schema processing: %(error)s"),
                      sourceFileLine=href, error=str(ex))
        elif JSON_SCHEMA_VALIDATOR == "jsonschema":
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
                    elif "unique elements" in msg: # any uniqueItems violation is a duplicate set item
                        errCode = "oimte:duplicateItemsInSet"
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
                elif " unique items" in msg: # any uniqueItems violation is a duplicate set item
                    errCode = "oimte:duplicateItemsInSet"
                elif p_beforeLast == "dimensions" and isinstance(ex.rule_definition, list) and all(k == "required" for o in ex.rule_definition for k in o.keys()):
                    errCode = "oimte:invalidDimensionObject"
                else:
                    errCode = "oimte:invalidJSONStructure",
                error(errCode,
                      _("Error: %(error)s, jsonObj: %(path)s"),
                      sourceFileLine=href, error=msg, path="".join(path))
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
        ''' stop loading built-in taxonomies
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
        '''
        namespacePrefixes = {}
        prefixNamespaces = {}
        namespaceUrls = {}
        for prefix, ns in documentInfo.get("namespaces", EMPTY_DICT).items():
            if ns and prefix:
                namespacePrefixes[ns] = prefix
                prefixNamespaces[prefix] = ns
                try:
                    setXmlns(schemaDoc, prefix, ns)
                except ValueError:
                    # invalid namespace URI (already reported as oimce:invalidURI / oime:invalidJSONStructure);
                    # lxml rejects it when building the nsmap — skip registration rather than abort the load
                    pass
        if "documentNamespace" in documentInfo:
            pfx = documentInfo["documentNamespace"]
            # must be a prefix or URL in namespaces
            if pfx in prefixNamespaces:
                schemaDoc.targetNamespace = prefixNamespaces[pfx]
            elif pfx in namespaceUrls:
                schemaDoc.targetNamespace = pfx
            else:
                xbrlCompMdl.error("oime:documentNamespaceHasNoPrefix",
                            _("Taxonomy document namespace '%(namespace)s' is not defined in namespaces"),
                            sourceFileLine=href, namespace=pfx)
        # The mapping key was renamed from urlMapping to importMapping in newer schemas.
        # Accept both keys and normalize values to a tuple of URLs.
        importMapping = documentInfo.get("importMapping") or EMPTY_DICT
        isCompiledDocType = documentType == "https://xbrl.org/2026/compiled"

        # Validate documentNamespacePrefix: required for module-type, forbidden for compiled.
        _documentNamespaceURI = None  # resolved and stored on the module object after creation
        _docNsPrefix = documentInfo.get("documentNamespacePrefix")
        if _docNsPrefix:
            if isCompiledDocType:
                xbrlCompMdl.error("oimte:documentNamespaceDefinedForCompiledModel",
                            _("Compiled models MUST NOT define a documentNamespacePrefix."),
                            sourceFileLine=href)
            elif _docNsPrefix not in prefixNamespaces:
                xbrlCompMdl.error("oimte:documentNamespacePrefixNotDefined",
                            _("The documentNamespacePrefix '%(prefix)s' is not defined in the namespaces map."),
                            sourceFileLine=href, prefix=_docNsPrefix)
            else:
                _documentNamespaceURI = prefixNamespaces[_docNsPrefix]
                schemaDoc.targetNamespace = _documentNamespaceURI
        elif not isCompiledDocType and not kwargs.get("loadingBakedInObjects"):
            xbrlCompMdl.error("oimte:documentNamespaceNotDefined",
                        _("Module-type taxonomy must define documentNamespacePrefix."),
                        sourceFileLine=href)
        if isCompiledDocType:
            if "importedTaxonomies" in moduleObj:
                xbrlCompMdl.error("oimte:importedTaxonomyDefinedForCompiledTaxonomy",
                            _("A compiled taxonomy MUST NOT define importedTaxonomies."),
                            sourceFileLine=href)
            elif importMapping:
                xbrlCompMdl.error("oimte:importMappingDefinedForCompiledTaxonomy",
                            _("A compiled taxonomy MUST NOT define importMapping."),
                            sourceFileLine=href)
        resolvedImportMapping = {} # QName xbrlModelName -> URL, for the cross-module consistency check
        if importMapping:
            for qn, url in importMapping.copy().items():
                qnImpName = qname(qn, prefixNamespaces)
                if not qnImpName:
                    xbrlCompMdl.error("oimte:invalidJSONStructureMissingRequiredProperty",
                                _("ImportMapping %(qname)smust have a modelQName (QName) key"),
                                sourceFileLine=href, qname=qn)
                else:
                    importMapping[qnImpName] = url
                    resolvedImportMapping[qnImpName] = url
        xbrlModelName = qname(moduleObj.get("name"), prefixNamespaces)
        if not xbrlModelName:
            xbrlCompMdl.error("oimte:invalidJSONStructureMissingRequiredProperty",
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
            if parentCol is not None:
                if key:
                    parentCol[key] = newObj
                else:
                    parentCol.add(newObj)

        jsonEltsNotInObjClass = []
        jsonEltsReqdButMissing = []
        namedObjectDuplicates = defaultdict(OrderedSet)
        def createModelObject(jsonObj, oimParentObj, keyClass, objClass, newObj, pathParts):
            keyValue = None
            forObjectsList = [] # to tag an object with labels or references
            oimParentTypes = (type(oimParentObj), type(oimParentObj).__name__) # allow actual type or TypeAlias type
            unexpectedJsonProps = set(jsonObj.keys())
            propertyMap = getattr(objClass, "_propertyMap", EMPTY_DICT).get(type(oimParentObj), EMPTY_DICT)
            initialParentObjProp = True
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
                        (isinstance(propType, _UnionGenericAlias) and isinstance(propType.__args__[0], GenericAlias) and propType.__args__[0].__origin__ in (OrderedSet, Dict)) or
                        (isinstance(propType, _GenericAlias) and propType.__origin__ in (list, set, OrderedSet, dict, Dict))):
                        _keyClass = None
                        # for Optional OrderedSets where the jsonValue exists, handle as propType, _keyClass and eltClass
                        if isinstance(propType.__args__[0], GenericAlias) and len(propType.__args__[0].__args__) == 1 and propType.__args__[0].__origin__ == OrderedSet:
                            # handle as non-optional OrderedSet
                            propClass = propType.__args__[0].__origin__ # collection type such as OrderedSet
                            collectionProp = propClass()
                            setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                            eltClass = propType.__args__[0].__args__[0]
                        elif isinstance(propType, _GenericAlias) and propType.__origin__ in (list, set, OrderedSet):
                            propClass = propType.__origin__
                            collectionProp = propClass()
                            setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                            eltClass = propType.__args__[0]
                        elif len(propType.__args__) == 2 and propType.__origin__ in (dict, Dict, OptionalDict): # dict
                            propClass = propType.__origin__
                            collectionProp = propClass()
                            setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                            _keyClass = propType.__args__[0] # class of key such as QNameKey
                            eltClass = propType.__args__[1] # class of collection elements such as XbrlConcept
                        elif len(propType.__args__) == 1: # set such as OrderedSet or list
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
                                            error("oimce:unboundPrefix",
                                                  _("QName has undefined prefix: %(qname)s, jsonObj: %(path)s"),
                                                  sourceFileLine=href, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [f'{propName}[{iObj}]'])}")
                                            # must have None value for validation to work
                                        if propName == "forObjects":
                                            forObjectsList.append(listObj)
                                    if propClass in (set, OrderedSet, NonemptySet):
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
                            if propClass == NonemptySet and not collectionProp:
                                error("oimte:invalidEmptySet",
                                      _("Property %(propName)s is a NonemptySet but is empty: %(path)s"),
                                      sourceFileLine=href, propName=propName, path="/".join(pathParts + [propName]))
                                # non-optional NonemptySet branch (GenericAlias): the correct empty value is
                                # an empty collection, not None (the property is never absent) — keeps
                                # downstream iteration safe. (Optional[NonemptySet] uses None; see below.)
                                setattr(newObj, propName, propClass())
                        elif isinstance(jsonValue, dict) and _keyClass is not None:
                            for iObj, (valKey, valVal) in enumerate(jsonValue.items()):
                                if isinstance(_keyClass, type) and issubclass(_keyClass,QName):
                                    if jsonKey == "dimensions" and objClass == XbrlFact:
                                        valKey = coreDimensionsByLocalname.get(valKey, valKey) # unprefixed core dimension localNames
                                    _valKey = qname(valKey, prefixNamespaces)
                                    if _valKey is None:
                                        error("oimce:unboundPrefix",
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
                        propClass = propType.__args__[0].__origin__ # collection type such as OrderedSet, dict
                        for iObj, listObj in enumerate(jsonValue):
                            if iObj == 0: # create collection only if any objects for collection
                                collectionProp = propClass()
                                setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet (even if no contents for it)
                            createModelObjects(propName, listObj, newObj, pathParts + [f'{propName}[{iObj}]'])
                        if not jsonValue and propClass == NonemptySet:
                            error("oimte:invalidEmptySet",
                                  _("Property %(property)s is a NonemptySet but is empty: %(path)s"),
                                  sourceFileLine=href, property=propName, path=f"{'/'.join(pathParts)}")
                            setattr(newObj, propName, None) # Optional[NonemptySet] branch: absent-semantics is None
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
                                error("oimce:unboundPrefix",
                                      _("QName has undefined prefix: %(qname)s, jsonObj: %(path)s"),
                                      sourceFileLine=href, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [propName])}")
                                if optional:
                                    jsonValue = None
                                else:
                                    jsonValue = qnErrorQname # allow processing to proceed with marker bad qname
                            elif propType == QNameAt:
                                jsonValue = QNameAt(jsonValue.prefix, jsonValue.namespaceURI, jsonValue.localName, atSuffix)
                            if propName == "forObject":
                                forObjectsList.append(jsonValue)
                        elif propType == AnyURI and isinstance(jsonValue, str):
                            # xs:anyURI forbids unencoded whitespace, pipe, and other chars invalid in RFC 2396.
                            if not UrlUtil.isAbsolute(jsonValue) or _anyURIInvalidChars.search(jsonValue):
                                error("oimce:invalidURI",
                                      _("The %(propName)s value is not a valid URI: %(uri)s, jsonObj: %(path)s"),
                                      sourceFileLine=href, propName=propName, uri=jsonValue,
                                      path=f"{'/'.join(pathParts + [propName])}")
                        setattr(newObj, propName, jsonValue)
                        if (keyClass and keyClass == propType) or (not keyClass and propType in (QNameKeyType, SQNameKeyType)):
                            keyValue = jsonValue # e.g. the QNAme of the new object for parent object collection
                elif initialParentObjProp and (propType in oimParentTypes or # propType may be a TypeAlias which is a string name of class
                      (isinstance(propType, _UnionGenericAlias) and any(t.__forward_arg__ in oimParentTypes for t in propType.__args__ if isinstance(t,ForwardRef)))): # Union of TypeAliases are ForwardArgs
                    setattr(newObj, propName, oimParentObj)
                elif (((get_origin(propType) is Union) or isinstance(get_origin(propType), type(Union))) and # Optional[ ] type
                       propType.__args__[-1] in (type(None), DefaultTrue, DefaultFalse, DefaultZero, DefaultOne)):
                          pass # absent Optional / Default* value already applied by XbrlObject.initDefaults
                else: # absent json element
                    if not (propClass in (dict, set, OrderedSet, OrderedDict) or
                            (isinstance(propClass, _GenericAlias) and propClass.__origin__ == list)):
                        if propClass not in (OptionalList, NonemptySet, OptionalDict): # OptionalList, NonemptySet is null if completely absent, not an empty list
                            # if this object extends another (has extends), missing scalar properties
                            # are inherited from the extension target — do not report them as missing
                            if "extends" not in jsonObj:
                                jsonEltsReqdButMissing.append(f"{'/'.join(pathParts + [propName])}")
                        # absent scalar default (None) already applied by XbrlObject.initDefaults
                initialParentObjProp = False
            if unexpectedJsonProps:
                for propName in unexpectedJsonProps:
                    jsonEltsNotInObjClass.append(f"{'/'.join(pathParts + [propName])}={jsonObj.get(propName,'(absent)')}")
            if (isinstance(newObj, XbrlReferencableModelObject) or # most referencable taxonomy objects
                (isinstance(newObj, (XbrlFact, XbrlFootnote, XbrlFactSource, XbrlFactMap, XbrlTableTemplate)) and isinstance(oimParentObj, XbrlModule))): # taxonomy-owned fact / table template
                if keyValue is not None: # otherwise expect some error occured above
                    if keyValue in xbrlCompMdl.namedObjects:
                        existingObj = xbrlCompMdl.namedObjects[keyValue]
                        existingIsCompiled = getattr(getattr(existingObj, "module", None), "modelForm", None) == "compiled"
                        if not isCompiledDocType and not existingIsCompiled:
                            namedObjectDuplicates[keyValue].add(newObj)
                            namedObjectDuplicates[keyValue].add(existingObj)
                    else:
                        xbrlCompMdl.namedObjects[keyValue] = newObj
            elif isinstance(newObj, XbrlTaxonomyTagObject) and forObjectsList:
                for relatedQn in forObjectsList:
                    xbrlCompMdl.tagObjects[relatedQn].append(newObj)
            return keyValue

        def createModelObjects(jsonKey, jsonObj, oimParentObj, pathParts):
            """"""
            # find collection owner in oimParentObj
            for objName in (jsonKey, plural(jsonKey)):
                ownrPropType = inspect.get_annotations(type(oimParentObj)).get(objName)
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
                    if objClass == XbrlModuleAlias:
                        objClass = XbrlModule
                    elif objClass == XbrlLayoutAlias:
                        objClass = XbrlLayout
                    if isinstance(objClass,ForwardRef) and objClass.__forward_arg__ in xbrlTypeAliasClass:
                        objClass = xbrlTypeAliasClass[objClass.__forward_arg__]
                    if isinstance(objClass, type) and issubclass(objClass, XbrlModelClass): # XBRL classes
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
                    else: # probably a primitive or scalar object
                        keyValue = newObj = jsonObj if objClass == Any else objClass(jsonObj) if objClass not in (QName, QNameKeyType, SQName, SQNameKeyType) else qname(jsonObj, prefixNamespaces)
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
        
        # imported taxonomy modules are needed before creating objects in this module, so that imported objects are available for reference and validation as the module is processed. This matches the expectation in the OIM spec that imported modules are processed before the importing module.
        impTxmyNameModuleObjs = {}
        if "importedTaxonomies" in moduleFileObj["xbrlModel"] and not isCompiledDocType:
            for impTxJsonObj in moduleFileObj["xbrlModel"]["importedTaxonomies"]:
                impTxModelName = impTxJsonObj.get("xbrlModelName")
                impModuleName = qname(impTxModelName, prefixNamespaces)
                if impModuleName:
                    if impModuleName not in xbrlCompMdl.xbrlModels:
                        impSchemaDoc = None
                        impTxModuleObj = None
                        # is it built in?
                        if impModuleName.prefix in builtInPrefixTaxonomies:
                            url = os.path.join(RESOURCES_DIR, builtInPrefixTaxonomies[impModuleName.prefix])
                            impSchemaDoc = loadXbrlModule(cntlr, error, warning, modelXbrl, url, "BakedInXbrlSpecObjects", **kwargs)
                        # is it present in importMapping?
                        elif impModuleName in importMapping:
                            url = importMapping[impModuleName]
                            normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(url, moduleFileName)
                            if modelXbrl.fileSource.isMappedUrl(normalizedUri):
                                mappedUrl = modelXbrl.fileSource.mappedUrl(normalizedUri)
                            elif PackageManager.isMappedUrl(normalizedUri):
                                mappedUrl = PackageManager.mappedUrl(normalizedUri)
                            else:
                                mappedUrl = modelXbrl.modelManager.disclosureSystem.mappedUrl(normalizedUri)
                            impSchemaDoc = loadXbrlModule(cntlr, error, warning, modelXbrl,
                                                        mappedUrl, url, importingTxmyObj=impTxJsonObj)
                        if isinstance(impSchemaDoc, ModelDocument): # if an exception object is returned, loading didn't succeed\
                            if impSchemaDoc._txmyModule.name == impModuleName:
                                impTxModuleObj = impSchemaDoc._txmyModule
                                impTxmyNameModuleObjs[impModuleName] = impTxModuleObj # key is a QName
                                # If an imported module reuses an alias for a different URI and
                                # the importing model has no alias for that URI, remapping is ambiguous.
                                impPrefixNamespaces = getattr(impTxModuleObj, "_prefixNamespaces", EMPTY_DICT) or EMPTY_DICT
                                for impPrefix, impNamespace in impPrefixNamespaces.items():
                                    if (impPrefix in prefixNamespaces and
                                        prefixNamespaces[impPrefix] != impNamespace and
                                        impNamespace not in prefixNamespaces.values()):
                                        xbrlCompMdl.error("oimce:multipleURIsForAlias",
                                                            _("Alias %(alias)s maps to %(ns1)s in importing taxonomy and %(ns2)s in imported taxonomy %(importedModel)s, and %(ns2)s has no alias in the importing taxonomy."),
                                                            xbrlObject=impTxJsonObj,
                                                            alias=impPrefix,
                                                            ns1=prefixNamespaces[impPrefix],
                                                            ns2=impNamespace,
                                                            importedModel=impModuleName)
                                        break
                                # selecting imported objects is deferred until this module's objects are created, so that imported objects are available for reference and validation as the module is processed. This matches the expectation in the OIM spec that imported modules are processed before the importing module.
                            else:
                                xbrlCompMdl.error("oimte:taxonomyNotFound",
                                                    _("Imported taxonomy for %(qname)s found at %(url)s has mismatching xbrlModelName %(name)s."),
                                                    xbrlObject=impTxJsonObj, url=url, qname=impModuleName, name= impSchemaDoc._txmyModule.name)
                                foundMismatchedNameReported = True
                        if impTxModuleObj is None:
                            xbrlCompMdl.error("oimte:taxonomyNotFound",
                                            _("Imported taxonomy for %(qname)s not found because the QName could not be resolved."),
                                            xbrlObject=impTxJsonObj, qname=impModuleName)
                    else:
                        impTxModuleObj = xbrlCompMdl.xbrlModels[impModuleName]
                        impTxmyNameModuleObjs[impModuleName] = impTxModuleObj
                else:
                    xbrlCompMdl.error("oimte:taxonomyNotFound",
                                    _("Imported taxonomy for %(qname)s not found because the URL mapping namespace is incorrect."),
                                    xbrlObject=impTxJsonObj, qname=impTxModelName)
        modelXbrl.profileActivity(f"Load taxonomies imported from {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)
        


        newModule = createModelObjects("xbrlModel", moduleFileObj["xbrlModel"], xbrlCompMdl, ["", "xbrlModel"])
        modelXbrl.profileActivity(f"Create taxonomy objects from {moduleFileBasename}", minTimeToShow=PROFILE_MIN_TIME)
        newModule._prefixNamespaces = prefixNamespaces
        newModule._documentNamespaceURI = _documentNamespaceURI  # None when documentNamespacePrefix absent/invalid
        if not newModule.modelForm and documentType == "https://xbrl.org/2026/compiled":
            newModule.modelForm = "compiled"
        newModule._lastMdlObjIndex = len(xbrlCompMdl.xbrlObjects) - 1

        # validate import selections now (errors reported in loading context),
        # but defer actual pruning until the entire import graph is resolved
        for impTxMdlObj in newModule.importedTaxonomies or ():
            if impTxMdlObj.xbrlModelName in impTxmyNameModuleObjs:
                impTxMdlObj._txmyModule = impTxmyNameModuleObjs[impTxMdlObj.xbrlModelName] # used by validation
                validateImportSelections(xbrlCompMdl, newModule, impTxMdlObj)
                xbrlCompMdl._pendingImportEntries[impTxMdlObj.xbrlModelName].append(impTxMdlObj)

        # Parse documentInfo.sourceMappings into a lightweight list of mapping
        # objects accessible via module._sourceMappings for FactValueResolver
        # (step 6 -- HTML / PDF locator-property registry).
        # sourceMappings is a non-empty set when present; parsed manually here (not via the type-driven
        # NonemptySet loader), so the present-but-empty check must be explicit.
        if "sourceMappings" in documentInfo and not documentInfo["sourceMappings"]:
            error("oimte:invalidEmptySet",
                  _("The documentInfo sourceMappings MUST NOT be empty."),
                  sourceFileLine=href)
        sourceMappingsRaw = documentInfo.get("sourceMappings") or ()
        parsedSourceMappings = []
        seenSourceNames = set()
        for _m in sourceMappingsRaw:
            if not isinstance(_m, dict):
                continue
            _rawUrl = _m.get("url")
            _absUrl = _rawUrl
            if _rawUrl:
                try:
                    _absUrl = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(_rawUrl, moduleFileName)
                except Exception:
                    _absUrl = _rawUrl
            _snQn = qname(_m.get("sourceName"), prefixNamespaces) if _m.get("sourceName") else None
            if _snQn is not None:
                if _snQn in seenSourceNames:
                    error("oimte:duplicateSourceNameProperty",
                          _("The sourceMappings array contains duplicate sourceName %(sourceName)s."),
                          sourceFileLine=href, sourceName=_snQn)
                else:
                    seenSourceNames.add(_snQn)
            _ns = types.SimpleNamespace(sourceName=_snQn, url=_absUrl)
            parsedSourceMappings.append(_ns)
        newModule._sourceMappings = parsedSourceMappings
        # Retain the documentInfo.description so the compiled-model validation can check any
        # RESOLVED:{...} expected object-count block a conformance test may declare in it.
        newModule._description = documentInfo.get("description")
        # Retain the resolved importMapping (xbrlModelName QName -> URL) so the compiled-model
        # validation can verify all modules map each xbrlModelName to the same URL.
        newModule._importMapping = resolvedImportMapping
        schemaDoc._txmyModule = newModule
        if xbrlModelName is not None:
            xbrlCompMdl.xbrlModels[xbrlModelName] = newModule

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
                  _("Multiple referenceable objects have the same name: %(qname)s processing file %(href)s"),
                  xbrlObject=dupObjs, qname=qname, href=href)

        # remove imported objects not wanted
        if xbrlModelName is not None: # otherwise some error would have occured
            xbrlCompMdl.namespaceDocs[xbrlModelName.namespaceURI].append(schemaDoc)

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
    """ ModelDocument.Validate:
        Validate an XBRL model, if it is an XBRL compiled model, by validating the taxonomy model, then validating facts whose values represent dateResolution concepts, then validating each report
    """
    if not isinstance(val.modelXbrl, XbrlCompiledModel): # if no ModelCompiledXbrl give up
        return
    try:
        # Deferred import pruning normally runs from the CntlrCmdLine.Xbrl.Loaded /
        # CntlrWinMain.Xbrl.Views hooks (xbrlModelLoaded), which only fire when
        # driven by the CLI or GUI. Callers that invoke validation directly via the
        # API (e.g. test harnesses calling modelXbrl.validate()) skip those hooks,
        # so pruning - and any oimte:invalidQNameReference errors it raises for
        # unresolved importObjects - must also be guaranteed here.
        if hasattr(val.modelXbrl, '_pendingImportEntries'):
            applyDeferredImportPruning(val.modelXbrl)

        # validate taxonomy model
        validateCompiledModel(val.modelXbrl)

        # validate facts whose values represent dateResolution concepts first
        validateDateResolutionConceptFacts(val.modelXbrl)

        # build search vocabulary to support cube construction (after date resolution concepts validated)
        from .VectorSearch import buildXbrlVectors
        buildXbrlVectors(val.modelXbrl)

        # Cube completeness checks (facts are owned by XbrlModule; XbrlReport has been removed)
        validateCompleteReportCubes(val.modelXbrl)
    except Exception as ex:
        val.modelXbrl.error("arelleOIMloader:error",
                "Error while validating, error %(errorType)s %(error)s\n traceback %(traceback)s",
                modelObject=val.modelXbrl, errorType=ex.__class__.__name__, error=ex,
                traceback=traceback.format_tb(sys.exc_info()[2]))

lastFilePath = None
lastFilePathIsOIM = False

def isXbrlModelLoadable(modelXbrl, mappedUri, normalizedUri, filepath, **kwargs):
    """ ModelDocument.IsPullLoadable:
        Determine if the file at filepath is an OIM taxonomy file, returning True if it is, False if not
    """
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
    """ ModelDocument.PullLoader:
        Load an OIM taxonomy file, returning a ModelDocument if successful,
        None if not an OIM file,
        or an exception if an error occurs during loading
    """
    if filepath != lastFilePath or not lastFilePathIsOIM:
        return None # not an OIM file

    cntlr = modelXbrl.modelManager.cntlr
    modelXbrl.profileActivity()
    doc = loadXbrlModule(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri, **kwargs)
    if doc is None:
        return None # not an OIM file
    return doc

def optionsExtender(parser, *args, **kwargs):
    """ CntlrCmdLine.Options:
        Extend command line options to include option for saving XML schema files from OIM taxonomies"""
    parser.add_option(SAVE_XML_SCHEMA_CMDLINE_PARAMETER,
                      action="store",
                      dest="saveXMLSchemaFiles",
                      help=_("Save OIM taxonomy namespaces to xsd files in specified directory."))
    parser.add_option("--xbrlModelStreamThreshold",
                      action="store",
                      type="int",
                      dest="xbrlModelStreamThreshold",
                      help=_("Fact count above which an XbrlFactSource MUST stream rather than "
                             "materialize. Default 50000. Overridden per-source by "
                             "factSourceMetadata.factCount when present."))

def filingStart(self, options, *args, **kwargs):
    #global saveOIMTaxonomySchemaFiles
    #if options.saveOIMTaxonomySchemaFiles:
    #    saveOIMTaxonomySchemaFiles = True
    pass

def xbrlModelLoaded(cntlr, options, xbrlCompMdl, *args, **kwargs):
    """ CntlrCmdLine.Xbrl.Loaded:
        After an XBRL model is loaded, if it is an XBRL compiled model, index group contents and load CSV tables
    """
    if not isinstance(xbrlCompMdl, XbrlCompiledModel):
        return

    # Stash streaming threshold from CLI option for FactPipeline consumers.
    if options is not None and getattr(options, "xbrlModelStreamThreshold", None) is not None:
        xbrlCompMdl.xbrlModelStreamThreshold = options.xbrlModelStreamThreshold

    if hasattr(xbrlCompMdl, '_pendingImportEntries'):
        applyDeferredImportPruning(xbrlCompMdl)

    xbrlCompMdl.groupContents = defaultdict(OrderedSet)
    for txmy in xbrlCompMdl.xbrlModels.values():
        for grpCnts in txmy.groupContents or ():
            for relName in getattr(grpCnts, "forObjects", ()): # if object was invalid there are no attributes, e.g. bad QNames
                xbrlCompMdl.groupContents[grpCnts.groupName].add(relName)

    # load CSV tables: XbrlReport has been removed; tableTemplates and facts live on XbrlModule.
    # NOTE: the legacy report-based CSV loop iterated `reportObj.tables.values()` which has never
    # been populated since the spec changed. This is a placeholder for the streaming CSV pipeline
    # introduced in subsequent refactor steps.


    # save schema files if specified by command line option or formula parameter
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
    """ CntlrWinMain.Xbrl.Views:
        After an XBRL model is loaded, if it is an XBRL compiled model, add views for the taxonomy objects
    """
    xbrlModelLoaded(cntlr, None, xbrlCompMdl)
    if isinstance(xbrlCompMdl, XbrlCompiledModel):
        initialViews = []
        initialViews.extend(((XbrlConcept, cntlr.tabWinBtm, "XBRL Concepts"),
                             (XbrlGroup, cntlr.tabWinTopRt, "XBRL Groups"),
                             (XbrlNetwork, cntlr.tabWinTopRt, "XBRL Networks"),
                             (XbrlCube, cntlr.tabWinTopRt, "XBRL Cubes"),
                             (XbrlDomainNetwork, cntlr.tabWinTopRt, "XBRL Domain Networks")
                            ))
        if any(xbrlCompMdl.filterNamedObjects(XbrlFact)):
            initialViews.append( (XbrlFact, cntlr.tabWinTopRt, "Taxonomy Facts") )
        initialViews = tuple(initialViews)
        additionalViews = ((XbrlHeading, cntlr.tabWinBtm, "XBRL Headings"),
                           (XbrlCubeType, cntlr.tabWinBtm, "XBRL Cube Types"),
                           (XbrlDataType, cntlr.tabWinBtm, "XBRL Data Types"),
                           (XbrlDimension, cntlr.tabWinBtm, "XBRL Dimensions"),
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
