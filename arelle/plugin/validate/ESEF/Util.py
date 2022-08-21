'''
Created on January 5, 2020

Filer Guidelines: ESMA_ESEF Manula 2019.pdf

@author: Workiva
(c) Copyright 2022 Workiva, All rights reserved.
'''
from __future__ import annotations
import os, json

from arelle.ModelObject import ModelObject
from .Const import esefTaxonomyNamespaceURIs
from lxml.etree import XML, XMLSyntaxError
from arelle.FileSource import openFileStream
from arelle.UrlUtil import scheme
from arelle.ModelManager import ModelManager
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from typing import Any, Union, cast
from arelle.ModelDocument import ModelDocument
from .common import TypeGetText

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
    ns = modelObject.qname.namespaceURI
    return (any(ns.startswith(esefNsPrefix) for esefNsPrefix in esefTaxonomyNamespaceURIs))

supportedImgTypes: dict[bool, tuple[str, ...]] = {
    True: ("gif", "jpg", "jpeg", "png"), # file extensions
    False: ("gif", "jpeg", "png") # mime types: jpg is not a valid mime type
    }
# check image contents against mime/file ext and for Steganography
def checkImageContents(modelXbrl: ModelXbrl, imgElt: ModelObject, imgType: str, isFile: bool, data: bytes) -> None:
    if "svg" in imgType:
        try:
            rootElement = True
            for elt in XML(data).iter():
                if rootElement:
                    if elt.tag != "{http://www.w3.org/2000/svg}svg":
                        modelXbrl.error("ESEF.2.5.1.imageFileCannotBeLoaded",
                            _("Image SVG has root element which is not svg"),
                            modelObject=imgElt)
                    rootElement = False
                eltTag = elt.tag.rpartition("}")[2] # strip namespace
                if ((eltTag in ("object", "script")) or
                    (eltTag in ("audio", "foreignObject", "iframe", "image", "use", "video"))):
                    href = elt.get("href","")
                    if eltTag in ("object", "script") or "javascript:" in href:
                        modelXbrl.error("ESEF.2.5.1.executableCodePresent",
                            _("Inline XBRL images MUST NOT contain executable code: %(element)s"),
                            modelObject=imgElt, element=eltTag)
                    elif scheme(href) in ("http", "https", "ftp"):
                        modelXbrl.error("ESEF.2.5.1.referencesPointingOutsideOfTheReportingPackagePresent",
                            _("Inline XBRL instance document [image] MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                            modelObject=imgElt, element=eltTag)
        except (XMLSyntaxError, UnicodeDecodeError) as err:
            modelXbrl.error("ESEF.2.5.1.imageFileCannotBeLoaded",
                _("Image SVG has XML error %(error)s"),
                modelObject=imgElt, error=err)
    elif not any(it in imgType for it in supportedImgTypes[isFile]):
        modelXbrl.error("ESEF.2.5.1.imageFormatNotSupported",
            _("Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPEG formats: %(imgType)s is not supported"),
            modelObject=imgElt, imgType=imgType)
    else:
        if data[:3] == b"GIF" and data[3:6] in (b'89a', b'89b', b'87a'):
            headerType = "gif"
        elif ((data[:4] == b'\xff\xd8\xff\xe0' and data[6:11] == b'JFIF\x00') or
              (data[:4] == b'\xff\xd8\xff\xe1' and data[6:11] == b'Exif\x00')):
            headerType = "jpg"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            headerType = "png"
        elif data[:2] in (b"MM", b"II"):
            headerType = "tiff"
        elif data[:2] in (b"BM", b"BA"):
            headerType = "bmp"
        elif data[:4] == b"\x00\x00\x01\x00":
            headerType = "ico"
        elif data[:4] == b"\x00\x00\x02\x00":
            headerType = "cur"
        elif len(data) == 0:
            headerType = "none"
        else:
            headerType = "unrecognized"
        if (("gif" in imgType and headerType != "gif") or
            (("jpg" in imgType or "jpeg" in imgType) and headerType != "jpg") or
            ("png" in imgType and headerType != "png")):
            modelXbrl.error("ESEF.2.5.1.imageDoesNotMatchItsFileExtension" if isFile
                            else "ESEF.2.5.1.incorrectMIMETypeSpecified",
                _("Image type %(imgType)s has wrong header type: %(headerType)s"),
                modelObject=imgElt, imgType=imgType, headerType=headerType,
                messageCodes=("ESEF.2.5.1.imageDoesNotMatchItsFileExtension", "ESEF.2.5.1.incorrectMIMETypeSpecified"))

def resourcesFilePath(modelManager: ModelManager, fileName: str) -> str:
    # resourcesDir can be in cache dir (production) or in validate/EFM/resources (for development)
    _resourcesDir = os.path.join( os.path.dirname(__file__), "resources") # dev/testing location

    if not os.path.isabs(_resourcesDir):
        _resourcesDir = os.path.abspath(_resourcesDir)
    if not os.path.exists(_resourcesDir): # production location
        _resourcesDir = os.path.join(modelManager.cntlr.webCache.cacheDir, "resources", "validation", "ESEF")

    return os.path.join(_resourcesDir, fileName)

def loadAuthorityValidations(modelXbrl: ModelXbrl) -> list[Any] | dict[Any, Any]:
    _file = openFileStream(modelXbrl.modelManager.cntlr, resourcesFilePath(modelXbrl.modelManager, "authority-validations.json"), 'rt', encoding='utf-8')  # type: ignore[no-untyped-call]
    validations = json.load(_file) # {localName: date, ...}
    _file.close()
    return cast(Union[dict[Any, Any], list[Any]], validations)
