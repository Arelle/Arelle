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

from typing import TYPE_CHECKING, cast, GenericAlias, Union

import os, io, json, sys, time, traceback
import regex as re
from decimal import Decimal
from arelle.ModelDocument import Type,  create as createModelDocument
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
from .XbrlTransform import XbrlTransform
from .XbrlUnit import XbrlUnit
from .XbrlTaxonomy import XbrlTaxonomy
from .XbrlTaxonomyObject import XbrlReferencableTaxonomyObject
from .XbrlDts import XbrlDts, castToDts
from .XbrlTypes import XbrlTaxonomyType, QNameKeyType, SQNameKeyType, DefaultTrue, DefaultFalse
from .ModelValueMore import SQName
from .ViewXbrlTxmyObj import viewXbrlTxmyObj


from arelle.oim.Load import (SQNameType, QNameType, URIType, LangType, NoRecursionCheck,
                             DUPJSONKEY, DUPJSONVALUE, EMPTY_DICT, EMPTY_LIST,
                             CheckPrefix, OIMException, NotOIMException,
                             WhitespaceUntrimmedPattern, SQNamePattern, CanonicalIntegerPattern)
from arelle.FunctionFn import name, true

oimTaxonomyDocTypePattern = re.compile(r"\s*\{.*\"documentType\"\s*:\s*\"https://xbrl.org/PWD/[0-9]{4}-[0-9]{2}-[0-9]{2}/oim\"", flags=re.DOTALL)
oimTaxonomyDocTypes = (
        "https://xbrl.org/PWD/2025-01-31/oim",
    )

saveOIMTaxonomySchemaFiles = False
SAVE_OIM_SCHEMA_CMDLINE_PARAMETER = "--saveOIMschemafile"
SAVE_OIM_SCHEMA_FORULA_PARAMETER = qname("saveOIMschemafile", noPrefixIsNoNamespace=True)

class QNameAtContextType:
    pass # fake class for detecting QName type + @start/end in JSON structure check

PROPERTY_TYPE = (QNameType,str,int,float,bool,NoRecursionCheck,CheckPrefix)


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
    "/*:*": (int,bool,str,dict,list,type(None),NoRecursionCheck,CheckPrefix), # custom extensions
    # documentInfo
    "/documentInfo/documentType": str,
    "/documentInfo/namespaces": list,
    "/documentInfo/namespaces/*": dict,
    "/documentInfo/namespaces/*/prefix": str,
    "/documentInfo/namespaces/*/documentNamespace": bool,
    "/documentInfo/namespaces/*/uri": URIType,
    "/documentInfo/namespaces/*/url": URIType,
    "/documentInfo/*:*": (int,float,bool,str,dict,list,type(None),NoRecursionCheck,CheckPrefix), # custom extensions
    # taxonomy
    "/taxonomy": dict,
    "/taxonomy/name": str,
    "/taxonomy/familyName": str,
    "/taxonomy/version": str,
    "/taxonomy/entryPoint": str,

    "/taxonomy/importedTaxonomies": list,
    "/taxonomy/importedTaxonomies/*": dict,
    "/taxonomy/importedTaxonomies/*/taxonomyName": QNameType,

    "/taxonomy/abstracts": list,
    "/taxonomy/abstracts/*": dict,
    "/taxonomy/abstracts/*/name": QNameType,

    "/taxonomy/concepts": list,
    "/taxonomy/concepts/*": dict,
    "/taxonomy/concepts/*/name": QNameType,
    "/taxonomy/concepts/*/dataType": QNameType,
    "/taxonomy/concepts/*/periodType": str,
    "/taxonomy/concepts/*/enumerationDomain": QNameType,
    "/taxonomy/concepts/*/nillable": bool,
    "/taxonomy/concepts/*/properties": list,
    "/taxonomy/concepts/*/properties/*": dict,
    "/taxonomy/concepts/*/properties/*/xbrl:balance": str,
    "/taxonomy/concepts/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/cubes": list,
    "/taxonomy/cubes/*": dict,
    "/taxonomy/cubes/*/name": QNameType,
    "/taxonomy/cubes/*/cubeType": QNameType,
    "/taxonomy/cubes/*/cubeDimensions": list,
    "/taxonomy/cubes/*/cubeDimensions/*": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/dimensionName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/domainName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/domainSort": str,
    "/taxonomy/cubes/*/cubeDimensions/*/allowDomainFacts": bool,
    "/taxonomy/cubes/*/cubeDimensions/*/exclude": bool,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints": list,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/periodType": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/timeSpan": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/periodFormat": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/gMonthDay": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/gMonthDay/conceptName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/gMonthDay/context": QNameAtContextType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/gMonthDay/value": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/gMonthDay/timeShift": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/endDate": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/endDate/conceptName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/endDate/context": QNameAtContextType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/endDate/value": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/endDate/timeShift": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/startDate": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/startDate/conceptName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/startDate/context": QNameAtContextType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/startDate/value": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/startDate/timeShift": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/after": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/after/conceptName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/after/context": QNameAtContextType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/after/value": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/after/timeShift": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/before": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/before/conceptName": QNameType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/before/context": QNameAtContextType,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/before/value": str,
    "/taxonomy/cubes/*/cubeDimensions/*/periodConstraints/*/before/timeShift": str,
    "/taxonomy/cubes/*/cubeDimensions/*/unitConstraints": list,
    "/taxonomy/cubes/*/cubeDimensions/*/unitConstraints/*": dict,
    "/taxonomy/cubes/*/cubeDimensions/*/unitConstraints/*/": QNameType,
    "/taxonomy/cubes/*/cubeNetworks": list,
    "/taxonomy/cubes/*/cubeNetworks/*": QNameType,
    "/taxonomy/cubes/*/excludeCubes": list,
    "/taxonomy/cubes/*/excludeCubes/*": QNameType,
    "/taxonomy/cubes/*/cubeComplete": bool,
    "/taxonomy/cubes/*/properties": list,
    "/taxonomy/cubes/*/properties/*": dict,
    "/taxonomy/cubes/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/cubeTypes": list,
    "/taxonomy/cubeTypes/*": dict,
    "/taxonomy/cubeTypes/*/name": QNameType,
    "/taxonomy/cubeTypes/*/baseCubeType": QNameType,
    "/taxonomy/cubeTypes/*/conceptDimension": bool,
    "/taxonomy/cubeTypes/*/periodDimension": bool,
    "/taxonomy/cubeTypes/*/entityDimension": bool,
    "/taxonomy/cubeTypes/*/unitDimension": bool,
    "/taxonomy/cubeTypes/*/taxonomyDefinedDimensions": bool,
    "/taxonomy/cubeTypes/*/allowedCubeDimensions": list,
    "/taxonomy/cubeTypes/*/allowedCubeDimensions/*": dict,
    "/taxonomy/cubeTypes/*/allowedCubeDimensions/*/dimensionName": QNameType,
    "/taxonomy/cubeTypes/*/allowedCubeDimensions/*/min": int,
    "/taxonomy/cubeTypes/*/allowedCubeDimensions/*/max": int,
    "/taxonomy/cubeTypes/*/requiredCubeRelationships": list,
    "/taxonomy/cubeTypes/*/requiredCubeRelationships/*": dict,
    "/taxonomy/cubeTypes/*/requiredCubeRelationships/*/relationshipTypeName": QNameType,
    "/taxonomy/cubeTypes/*/requiredCubeRelationships/*/source": QNameType,
    "/taxonomy/cubeTypes/*/requiredCubeRelationships/*/target": QNameType,

    "/taxonomy/dataTypes": list,
    "/taxonomy/dataTypes/*": dict,
    "/taxonomy/dataTypes/*/name": QNameType,
    "/taxonomy/dataTypes/*/baseType": QNameType,
    "/taxonomy/dataTypes/*/enumeration": list,
    "/taxonomy/dataTypes/*/enumeration/*": (QNameType, str, int, float),
    "/taxonomy/dataTypes/*/minInclusive": Decimal,
    "/taxonomy/dataTypes/*/maxInclusive": Decimal,
    "/taxonomy/dataTypes/*/minExclusive": Decimal,
    "/taxonomy/dataTypes/*/maxExclusive": Decimal,
    "/taxonomy/dataTypes/*/totalDigits": int,
    "/taxonomy/dataTypes/*/fractionDigits": int,
    "/taxonomy/dataTypes/*/length": int,
    "/taxonomy/dataTypes/*/minLength": int,
    "/taxonomy/dataTypes/*/maxLength": int,
    "/taxonomy/dataTypes/*/whiteSpace": str,
    "/taxonomy/dataTypes/*/pattern": str,
    "/taxonomy/dataTypes/*/unitTypes": dict,
    "/taxonomy/dataTypes/*/unitTypes/*": dict,

    "/taxonomy/dimensions": list,
    "/taxonomy/dimensions/*": dict,
    "/taxonomy/dimensions/*/name": QNameType,
    "/taxonomy/dimensions/*/domainDataType": QNameType,
    "/taxonomy/dimensions/*/dimensionType": str,
    "/taxonomy/dimensions/*/cubeTypes": list,
    "/taxonomy/dimensions/*/cubeTypes/*": QNameType,

    "/taxonomy/domains": list,
    "/taxonomy/domains/*": dict,
    "/taxonomy/domains/*/name": QNameType,
    "/taxonomy/domains/*/baseDomain": QNameType,
    "/taxonomy/domains/*/allowedMembers": list,
    "/taxonomy/domains/*/allowedMembers/*": QNameType,
    "/taxonomy/domains/*/relationships": list,
    "/taxonomy/domains/*/relationships/*": dict,
    "/taxonomy/domains/*/relationships/*/source": QNameType,
    "/taxonomy/domains/*/relationships/*/target": QNameType,
    "/taxonomy/domains/*/relationships/*/order": (int,float),
    "/taxonomy/domains/*/relationships/*/weight": (int,float),
    "/taxonomy/domains/*/relationships/*/preferredLabel": QNameType,
    "/taxonomy/domains/*/relationships/*/usable": bool,
    "/taxonomy/domains/*/relationships/*/properties": list,
    "/taxonomy/domains/*/relationships/*/properties/*": dict,
    "/taxonomy/domains/*/relationships/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/entities": list,
    "/taxonomy/entities/*": dict,
    "/taxonomy/entities/*/name": SQNameType,
    "/taxonomy/entities/*/properties": list,
    "/taxonomy/entities/*/properties/*": dict,
    "/taxonomy/entities/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/groups": list,
    "/taxonomy/groups/*": dict,
    "/taxonomy/groups/*/name": QNameType,
    "/taxonomy/groups/*/groupURI": URIType,
    "/taxonomy/groups/*/properties": list,
    "/taxonomy/groups/*/properties/*": dict,
    "/taxonomy/groups/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/groupContents": list,
    "/taxonomy/groupContents/*": dict,
    "/taxonomy/groupContents/*/groupName": QNameType,
    "/taxonomy/groupContents/*/relatedNames": list,
    "/taxonomy/groupContents/*/relatedNames/*": QNameType,

    "/taxonomy/labels": list,
    "/taxonomy/labels/*": dict,
    "/taxonomy/labels/*/relatedName": QNameType,
    "/taxonomy/labels/*/labelType": QNameType,
    "/taxonomy/labels/*/language": LangType,
    "/taxonomy/labels/*/value": str,

    "/taxonomy/members": list,
    "/taxonomy/members/*": dict,
    "/taxonomy/members/*/name": QNameType,

    "/taxonomy/networks": list,
    "/taxonomy/networks/*": dict,
    "/taxonomy/networks/*/name": QNameType,
    "/taxonomy/networks/*/relationshipTypeName": QNameType,
    "/taxonomy/networks/*/roots": list,
    "/taxonomy/networks/*/roots/*": QNameType,
    "/taxonomy/networks/*/extendTargetName": bool,
    "/taxonomy/networks/*/relationships": list,
    "/taxonomy/networks/*/relationships/*": dict,
    "/taxonomy/networks/*/relationships/*/source": QNameType,
    "/taxonomy/networks/*/relationships/*/target": QNameType,
    "/taxonomy/networks/*/relationships/*/order": (int,float),
    "/taxonomy/networks/*/relationships/*/weight": (int,float),
    "/taxonomy/networks/*/relationships/*/preferredLabel": QNameType,
    "/taxonomy/networks/*/relationships/*/usable": bool,
    "/taxonomy/networks/*/relationships/*/properties": list,
    "/taxonomy/networks/*/relationships/*/properties/*": dict,
    "/taxonomy/networks/*/relationships/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/propertyTypes": list,
    "/taxonomy/propertyTypes/*": dict,
    "/taxonomy/propertyTypes/*/name": QNameType,
    "/taxonomy/propertyTypes/*/dataType": QNameType,
    "/taxonomy/propertyTypes/*/enumerationDomain": QNameType,
    "/taxonomy/propertyTypes/*/immutable": bool,
    "/taxonomy/propertyTypes/*/allowedObjects": list,
    "/taxonomy/propertyTypes/*/allowedObjects/*": QNameType,

    "/taxonomy/references": list,
    "/taxonomy/references/*": dict,
    "/taxonomy/references/*/name": QNameType,
    "/taxonomy/references/*/extendTargetName": QNameType,
    "/taxonomy/references/*/relatedNames": list,
    "/taxonomy/references/*/relatedNames/*": QNameType,
    "/taxonomy/references/*/referenceType": QNameType,
    "/taxonomy/references/*/language": LangType,
    "/taxonomy/references/*/properties": list,
    "/taxonomy/references/*/properties/*": dict,
    "/taxonomy/references/*/properties/*/*:*": PROPERTY_TYPE,

    "/taxonomy/referenceTypes": list,
    "/taxonomy/referenceTypes/*": dict,
    "/taxonomy/referenceTypes/*/name": QNameType,
    "/taxonomy/referenceTypes/*/uri": URIType,
    "/taxonomy/referenceTypes/*/allowedObjects": list,
    "/taxonomy/referenceTypes/*/allowedObjects/*": QNameType,
    "/taxonomy/referenceTypes/*/orderedProperties": list,
    "/taxonomy/referenceTypes/*/orderedProperties/*": QNameType,
    "/taxonomy/referenceTypes/*/requiredProperties": list,
    "/taxonomy/referenceTypes/*/requiredProperties/*": QNameType,

    "/taxonomy/relationshipTypes": list,
    "/taxonomy/relationshipTypes/*": dict,
    "/taxonomy/relationshipTypes/*/name": QNameType,
    "/taxonomy/relationshipTypes/*/relationshipTypeURI": URIType,
    "/taxonomy/relationshipTypes/*/cycles": str,
    "/taxonomy/relationshipTypes/*/allowedLinkProperties": list,
    "/taxonomy/relationshipTypes/*/allowedLinkProperties/*": QNameType,
    "/taxonomy/relationshipTypes/*/requiredLinkProperties": list,
    "/taxonomy/relationshipTypes/*/requiredLinkProperties/*": QNameType,
    "/taxonomy/relationshipTypes/*/sourceObjects": list,
    "/taxonomy/relationshipTypes/*/sourceObjects/*": QNameType,
    "/taxonomy/relationshipTypes/*/targetObjects": list,
    "/taxonomy/relationshipTypes/*/targetObjects/*": QNameType,

    "/taxonomy/units": list,
    "/taxonomy/units/*": dict,
    "/taxonomy/units/*/name": SQNameType,
    "/taxonomy/units/*/dataType": QNameType,
    "/taxonomy/units/*/baseStandard": str,
    "/taxonomy/units/*/dataTypeNumerator": QNameType,
    "/taxonomy/units/*/dataTypeDenominator": QNameType,

    "/taxonomy/networks/*/properties": list,
    "/taxonomy/networks/*/properties/*": dict,
    "/taxonomy/networks/*/properties/*/*:*": PROPERTY_TYPE,

    # custom properties on taxonomy are unchecked
    "/taxonomy/*:*": (int,float,bool,str,dict,list,type(None),NoRecursionCheck,CheckPrefix), # custom extensions
    }
JsonRequiredMembers = {
    "/": {"documentInfo"},
    "/documentInfo/": {"documentType", "namespaces"},
    "/taxonomy/": {"name", "entryPoint"},
    "/taxonomy/importedTaxonomies/*/":  {"taxonomyName"},
    "/taxonomy/concepts/*/": {"name", "dataType", "periodType"},
    "/taxonomy/abstracts/*/": {"name"},
    "/taxonomy/dimensions/*/": {"name", "dimensionType"},
    "/taxonomy/domains/*/": {"name"},
    "/taxonomy/members/*/": {"name"},
    "/taxonomy/cubes/*/": {"name", "cubeDimensions"},
    "/taxonomy/cubes/*/cubeDimensions/*/": {"dimensionName"},
    "/taxonomy/networks/*/relationships/*/": {"source","target"},
    "/taxonomy/labels/*/": {"labelType", "value", "language"},
    "/taxonomy/references/*/": {"referenceType"},
    "/taxonomy/propertyTypes/*/":  {"name", "dataType"},
    "/taxonomy/dataTypes/*/":  {"name", "baseType"},

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
        documentType = None # set by loadDict

        currentAction = "loading and parsing OIM Taxonomy file"
        loadDictErrors = []
        def ldError(msgCode, msgText, **kwargs):
            loadDictErrors.append((msgCode, msgText, kwargs))

        def loadDict(keyValuePairs):
            global loadDict
            _dict = {}
            _valueKeyDict = {}
            for key, value in keyValuePairs:
                if key == "frameworkName":
                    print("trace")
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
                    if isinstance(value, str):
                        if value in _valueKeyDict:
                            if DUPJSONVALUE not in _dict:
                                _dict[DUPJSONVALUE] = []
                            _dict[DUPJSONVALUE].append((value, key, _valueKeyDict[value]))
                        else:
                            _valueKeyDict[value] = key
            return _dict

        errPrefix = "xbrlte"
        try:
            _file = modelXbrl.fileSource.file(oimFile, encoding="utf-8-sig")[0]
            with _file as f:
                oimObject = json.load(f, object_pairs_hook=loadDict)
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
            error(msgCode.format(errPrefix), msgText, href=oimFile, **kwargs)
        del loadDictErrors[:]

        oimRequiredMembers = JsonRequiredMembers
        oimMemberTypes = JsonMemberTypes

        invalidMemberTypes = []
        invalidQNames = []
        missingRequiredMembers = []
        unexpectedMembers = []
        extensionProperties = {} # key is property QName, value is property path

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
                        elif (mbrTypes is QNameAtContextType or (isinstance(mbrTypes,tuple) and QNameAtContextType in mbrTypes)):
                            if not isinstance(mbrObj, str):
                                invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                            _qn, _sep, _atCntx = mbrObj.partition("@")
                            if _atCntx not in ("start", "end", "") or not XmlValidate.QNamePattern.match(_qn):
                                invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                        elif (not ((mbrTypes is QNameType or (isinstance(mbrTypes,tuple) and QNameType in mbrTypes)) and isinstance(mbrObj, str) and XmlValidate.QNamePattern.match(mbrObj)) and
                            not ((mbrTypes is LangType or (isinstance(mbrTypes,tuple) and LangType in mbrTypes)) and isinstance(mbrObj, str) and XmlValidate.languagePattern.match(mbrObj)) and
                            not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and URIType in mbrTypes)) and isinstance(mbrObj, str) and UrlUtil.isValidUriReference(mbrObj) and not WhitespaceUntrimmedPattern.match(mbrObj)) and
                            #not (mbrTypes is IdentifierType and isinstance(mbrObj, str) and isinstance(mbrObj, str) and IdentifierPattern.match(mbrObj)) and
                            not ((mbrTypes is int or (isinstance(mbrTypes,tuple) and int in mbrTypes)) and isinstance(mbrObj, str) and CanonicalIntegerPattern.match(mbrObj)) and
                            not isinstance(mbrObj, mbrTypes)):
                            invalidMemberTypes.append(showPathObj(pathParts, mbrObj))
                    elif ":" in mbrName and path + "*:*" in oimMemberTypes:
                        _mbrTypes = oimMemberTypes[path + "*:*"]
                        if not (XmlValidate.QNamePattern.match(mbrName) and isinstance(mbrObj, _mbrTypes)):
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
                    if isinstance(mbrObj, dict):
                        checkMemberTypes(mbrObj, mbrPath + "/", pathParts)
                    elif isinstance(mbrObj, list):
                        checkMemberTypes(mbrObj, mbrPath + "/*", pathParts)
                    pathParts.pop() # remove mbrName
            if (isinstance(obj,list)):
                mbrNdx = 1
                for mbrObj in obj:
                    mbrPath = path # list entry just uses path ending in /
                    pathParts.append(mbrNdx)
                    if mbrPath in oimMemberTypes:
                        mbrTypes = oimMemberTypes[mbrPath]
                        if (not ((mbrTypes is URIType or (isinstance(mbrTypes,tuple) and URIType in mbrTypes)) and isinstance(mbrObj, str) and isValidUriReference(mbrObj) and not WhitespaceUntrimmedPattern.match(mbrObj)) and
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

        # import referenced taxonomies
        txBase = os.path.dirname(oimFile)

        # create the taxonomy document
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
            xbrlDts = castToDts(modelXbrl)
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
                  modelObject=xbrlDts)
        namespacePrefixes = {}
        prefixNamespaces = {}
        for nsObj in documentInfo.get("namespaces", EMPTY_DICT):
            ns = nsObj.get("uri","")
            prefix = nsObj.get("prefix","")
            if ns and prefix:
                namespacePrefixes[ns] = prefix
                prefixNamespaces[prefix] = ns
                setXmlns(schemaDoc, prefix, ns)
            if nsObj.get("documentNamespace",False):
                schemaDoc.targetNamespace = ns
            url = nsObj.get("url","")
        taxonomyName = qname(taxonomyObj.get("name"), prefixNamespaces)
        if not taxonomyName:
            xbrlDts.error("oime:missingQNameProperty",
                          _("Taxonomy must have a name (QName) property"),
                          modelObject=xbrlDts, ref=oimFile)

        # check extension properties (where metadata specifies CheckPrefix)
        for extPropSQName, extPropertyPath in extensionProperties.items():
            extPropPrefix = extPropSQName.partition(":")[0]
            if extPropPrefix not in prefixNamespaces:
                error("oimte:unboundPrefix",
                      _("The extension property QName prefix was not defined in namespaces: %(extensionProperty)s."),
                      modelObject=modelXbrl, extensionProperty=extPropertyPath)

        for iImpTxmy, impTxmyObj in enumerate(taxonomyObj.get("importedTaxonomies", EMPTY_LIST)):
            impTxmyName = qname(impTxmyObj.get("taxonomyName"), prefixNamespaces)
            if not impTxmyName:
                xbrlDts.error("oime:missingQNameProperty",
                              _("/taxonomy/importedTaxonomies[%(iImpTxmy)s] must have a taxonomyName (QName) property"),
                              modelObject=modelDts, ref=oimFile, index=iImpTxmy)
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
                return name
        def addToCol(oimParentObj, objName, newObj, key):
            parentCol = getattr(oimParentObj, plural(objName), None) # parent collection object
            if colObj is not None:
                if key:
                    colObj[key] = newObj
                else:
                    colObj.add(newObj)

        jsonEltsNotInObjClass = []
        jsonEltsReqdButMissing = []
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
                    else: # parent      is just an object field, not a  collection
                        objClass = ownrPropType # e.g just a Concept but no owning collection
                    if objClass == XbrlTaxonomyType:
                        objClass = XbrlTaxonomy
                    dtsObjectIndex = len(xbrlDts.modelObjects)
                    newObj = objClass(dtsObjectIndex=dtsObjectIndex) # e.g. this is the new Concept
                    xbrlDts.modelObjects.append(newObj)
                    keyValue = None
                    for propName, propType in getattr(objClass, "__annotations__", EMPTY_DICT).items():
                        optional = False
                        if isinstance(getattr(propType, "__origin__", None), type(Union)): # Optional[ ] type
                            if propType.__args__[-1] in (type(None), DefaultTrue, DefaultFalse):
                                optional = True
                            propType = propType.__args__[0] # use first of union for prop value creation
                        if propName in jsonObj:
                            jsonValue = jsonObj[propName]
                            if isinstance(propType, GenericAlias):
                                propClass = propType.__origin__ # collection type such as OrderedSet, dict
                                if len(propType.__args__) == 2: # dict
                                    _keyClass = propType.__args__[0] # class of key such as QNameKey
                                    eltClass = propType.__args__[1] # class of collection elements such as XbrlConcept
                                elif len(propType.__args__) == 1: # set such as OrderedSet or list
                                    _keyClass = None
                                    eltClass = propType.__args__[0]
                                collectionProp = propClass()
                                setattr(newObj, propName, collectionProp) # fresh new dict or OrderedSet
                                if isinstance(jsonValue, list):
                                    for iObj, listObj in enumerate(jsonValue):
                                        if isinstance(eltClass, str) or eltClass.__name__.startswith("Xbrl"): # nested Xbrl objects
                                            createTaxonomyObjects(propName, listObj, newObj, pathParts + [propName, str(iObj)])
                                        else: # collection contains ordinary values
                                            if eltClass in (QName, QNameKeyType, SQName, SQNameKeyType):
                                                listObj = qname(listObj, prefixNamespaces)
                                                if listObj is None:
                                                    error("xbrlte:invalidQName",
                                                          _("QName is invalid: %(qname)s, jsonObj: %(path)s"),
                                                          file=oimFile, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [propName, str(iObj)])}")
                                                    continue # skip this property
                                            if propClass in (set, OrderedSet):
                                                collectionProp.add(listObj)
                                            else:
                                                collectionProp.append(listObj)
                            else:
                                if propType in (QName, QNameKeyType, SQName, SQNameKeyType):
                                    jsonValue = qname(jsonValue, prefixNamespaces)
                                    if jsonValue is None:
                                        error("xbrlte:invalidQName",
                                              _("QName is invalid: %(qname)s, jsonObj: %(path)s"),
                                              file=oimFile, qname=jsonObj[propName], path=f"{'/'.join(pathParts + [propName])}")
                                        continue # skip this property
                                setattr(newObj, propName, jsonValue)
                                if keyClass and keyClass == propType:
                                    keyValue = jsonValue # e.g. the QNAme of the new object for parent object collection
                        elif propType == type(oimParentObj):
                            setattr(newObj, propName, oimParentObj)
                        elif propType == DefaultTrue:
                            setattr(newObj, propName, True)
                        elif propType == DefaultFalse:
                            setattr(newObj, propName, False)
                        else: # unexpected json element
                            propPath = f"{'/'.join(pathParts + [objName, propName])}={jsonObj.get(propName,'absent')}"
                            if not optional:
                                jsonEltsReqdButMissing.append(propPath)
                    if isinstance(ownrPropType, GenericAlias):
                        if len(ownrPropType.__args__) == 2:
                            if keyValue:
                                ownrProp[keyValue] = newObj
                        elif isinstance(ownrProp, (set, OrderedSet)):
                            ownrProp.add(newObj)
                        else:
                            ownrProp.append(newObj)
                    if isinstance(newObj, XbrlReferencableTaxonomyObject):
                        xbrlDts.taxonomyObjects[keyValue] = newObj

        createTaxonomyObjects("taxonomy", oimObject["taxonomy"], xbrlDts, ["", "taxonomy"])

        if jsonEltsNotInObjClass:
            error("arelle:undeclaredOimTaxonomyJsonElements",
                  _("Json file has elements not declared in Arelle object classes: %(undeclaredElements)s"),
                  file=oimFile, undeclaredElements=", ".join(jsonEltsNotInObjClass))
        if jsonEltsReqdButMissing:
            error("arelle:missingOimTaxonomyJsonElements",
                  _("Json file missing required elements: %(missingElements)s"),
                  file=oimFile, missingElements=", ".join(jsonEltsReqdButMissing))

        return schemaDoc

        ####################### convert to XML Taxonomy

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
    doc = loadOIMTaxonomy(cntlr, modelXbrl.error, modelXbrl.warning, modelXbrl, filepath, mappedUri)
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
        
def oimTaxonomyViews(cntlr, xbrlDts):
    if isinstance(xbrlDts, XbrlDts):
        if xbrlDts.taxonomies: # has at least one taxonomy
            xbrlTxmy = next(iter(xbrlDts.taxonomies.values())) # first taxonomy for now
            viewXbrlTxmyObj(xbrlDts, XbrlConcept, xbrlTxmy.concepts, cntlr.tabWinBtm, "XBRL Concepts")
            viewXbrlTxmyObj(xbrlDts, XbrlGroupContent, xbrlTxmy.groupContents, cntlr.tabWinTopRt, "XBRL Groups")
            viewXbrlTxmyObj(xbrlDts, XbrlNetwork, xbrlTxmy.networks, cntlr.tabWinTopRt, "XBRL Networks")
            viewXbrlTxmyObj(xbrlDts, XbrlCube, xbrlTxmy.cubes, cntlr.tabWinTopRt, "XBRL Cubes")
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
    'CntlrWinMain.Xbrl.Views': oimTaxonomyViews,
    'ModelDocument.IsPullLoadable': isOimTaxonomyLoadable,
    'ModelDocument.PullLoader': oimTaxonomyLoader
}
