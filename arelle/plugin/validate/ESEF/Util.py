"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import os
from collections.abc import Collection
from typing import Any, Dict, List, Union, cast

from lxml.etree import _Element

from arelle.FileSource import openFileStream
from arelle.ModelDocument import ModelDocument
from arelle.ModelManager import ModelManager
from arelle.ModelObject import ModelObject
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from .Const import esefTaxonomyNamespaceURIs, htmlEventHandlerAttributes, svgEventAttributes

_: TypeGetText  # Handle gettext


# check if a modelDocument URI is an extension URI (document URI)
# also works on a uri passed in as well as modelObject
def isExtension(val: ValidateXbrl, modelObject: ModelObject | ModelDocument | str | None) -> bool:
    if modelObject is None:
        return False
    if isinstance(modelObject, str):
        uri = modelObject
    else:
        uri = modelObject.modelDocument.uri
    return (uri.startswith(val.modelXbrl.uriDir) or
            not any(uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in val.authParam["standardTaxonomyURIs"]))


# check if in core esef taxonomy (based on namespace URI)
def isInEsefTaxonomy(val: ValidateXbrl, modelObject: ModelObject | None) -> bool:
    if modelObject is None:
        return False

    assert modelObject.qname is not None
    ns = modelObject.qname.namespaceURI
    assert ns is not None
    return (any(ns.startswith(esefNsPrefix) for esefNsPrefix in esefTaxonomyNamespaceURIs))


def resourcesFilePath(modelManager: ModelManager, fileName: str) -> str:
    # resourcesDir can be in cache dir (production) or in validate/EFM/resources (for development)
    _resourcesDir = os.path.join( os.path.dirname(__file__), "resources") # dev/testing location

    if not os.path.isabs(_resourcesDir):
        _resourcesDir = os.path.abspath(_resourcesDir)
    if not os.path.exists(_resourcesDir): # production location
        _resourcesDir = os.path.join(modelManager.cntlr.webCache.cacheDir, "resources", "validation", "ESEF")

    return os.path.join(_resourcesDir, fileName)


def loadAuthorityValidations(modelXbrl: ModelXbrl) -> list[Any] | dict[Any, Any]:
    _file = openFileStream(modelXbrl.modelManager.cntlr, resourcesFilePath(modelXbrl.modelManager, "authority-validations.json"), 'rt', encoding='utf-8')
    validations = json.load(_file) # {localName: date, ...}
    _file.close()
    return cast(Union[Dict[Any, Any], List[Any]], validations)


def hasEventHandlerAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, htmlEventHandlerAttributes)


def hasSvgEventAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, svgEventAttributes)


def _hasEventAttributes(elt: Any, attributes: Collection[str]) -> bool:
    if isinstance(elt, _Element):
        return any(a in attributes for a in elt.keys())
    return False
