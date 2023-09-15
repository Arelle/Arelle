'''
Filer Guidelines: ESMA_ESEF Manula 2019.pdf

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
from lxml.etree import _Element
from urllib.parse import unquote
import os, json
from arelle.ModelObject import ModelObject
from .Const import esefTaxonomyNamespaceURIs, htmlEventHandlerAttributes, svgEventAttributes
from lxml.etree import XML, XMLSyntaxError
from arelle.FileSource import openFileStream
from arelle.UrlUtil import scheme
from arelle.ModelManager import ModelManager
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateFilingText import validateGraphicHeaderType
from arelle.ValidateXbrl import ValidateXbrl
from typing import Any, Dict, List, Union, cast
from arelle.ModelDocument import ModelDocument
from arelle.typing import TypeGetText


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

supportedImgTypes: dict[bool, tuple[str, ...]] = {
    True: ("gif", "jpg", "jpeg", "png"), # file extensions
    False: ("gif", "jpeg", "png") # mime types: jpg is not a valid mime type
    }
# check image contents against mime/file ext and for Steganography

def checkImageContents(modelXbrl: ModelXbrl, imgElt: ModelObject, imgType: str, isFile: bool, data: bytes, consolidated: bool) -> None:
    guidance = 'ESEF.2.5.1' if consolidated else 'ESEF.4.1.3'
    if "svg" in imgType:
        try:
            checkSVGContent(modelXbrl, imgElt, data, guidance)
        except XMLSyntaxError as err:
            try:
                checkSVGContent(modelXbrl, imgElt, unquote(data), guidance)  # Try with utf-8 decoded data as in conformance suite G4-1-3_2/TC2
            except XMLSyntaxError:
                modelXbrl.error(f"{guidance}.imageFileCannotBeLoaded",
                                _("Image SVG has XML error %(error)s"),
                                modelObject=imgElt, error=err)
        except UnicodeDecodeError as err:
            modelXbrl.error(f"{guidance}.imageFileCannotBeLoaded",
                _("Image SVG has XML error %(error)s"),
                modelObject=imgElt, error=err)
    else:
        headerType = validateGraphicHeaderType(data)
        if (("gif" not in imgType and headerType == "gif") or
            ("jpeg" not in imgType and "jpg" not in imgType and headerType == "jpg") or
            ("png" not in imgType and headerType == "png")):
            imageDoesNotMatchItsFileExtension = f"ESEF.{guidance}.imageDoesNotMatchItsFileExtension"
            incorrectMIMETypeSpecified = f"ESEF.{guidance}.incorrectMIMETypeSpecified"
            if isFile:
                code = imageDoesNotMatchItsFileExtension
                message = _("File type %(headerType)s inferred from file signature does not match the file extension %(imgType)s")
            else:
                code = incorrectMIMETypeSpecified
                message = _("File type %(headerType)s inferred from file signature does not match the data URL media subtype (MIME subtype) %(imgType)s")
            modelXbrl.error(code, message,
                modelObject=imgElt, imgType=imgType, headerType=headerType,
                messageCodes=(imageDoesNotMatchItsFileExtension, incorrectMIMETypeSpecified))
        elif not any(it in imgType for it in supportedImgTypes[isFile]):
            modelXbrl.error(f"{guidance}.imageFormatNotSupported",
                            _("Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPEG formats: %(imgType)s is not supported"),
                            modelObject=imgElt, imgType=imgType)


def checkSVGContent(modelXbrl: ModelXbrl, imgElt: ModelObject, data: Union[bytes, Any, str], guidance: str) -> None:
    rootElement = True
    for elt in XML(data).iter():
        if rootElement:
            if elt.tag != "{http://www.w3.org/2000/svg}svg":
                modelXbrl.error(f"{guidance}.imageFileCannotBeLoaded",
                                _("Image SVG has root element which is not svg"),
                                modelObject=imgElt)
            rootElement = False
        eltTag = elt.tag.rpartition("}")[2] # strip namespace
        if eltTag in ("object", "script", "audio", "foreignObject", "iframe", "image", "use", "video"):
            href = elt.get("href","")
            if eltTag in ("object", "script") or "javascript:" in href:
                modelXbrl.error(f"{guidance}.executableCodePresent",
                                _("Inline XBRL images MUST NOT contain executable code: %(element)s"),
                                modelObject=imgElt, element=eltTag)
            elif scheme(href) in ("http", "https", "ftp"):
                modelXbrl.error(f"{guidance}.referencesPointingOutsideOfTheReportingPackagePresent",
                                _("Inline XBRL instance document [image] MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                                modelObject=imgElt, element=eltTag)
        if hasSvgEventAttributes(elt):
            modelXbrl.error(f"{guidance}.executableCodePresent",
                            _("Inline XBRL images MUST NOT contain executable code: %(element)s"),
                            modelObject=imgElt, element=eltTag)

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

def _hasEventAttributes(elt: Any, attributes: set[str]) -> bool:
    if isinstance(elt, _Element):
        return any(a in attributes for a in elt.keys())
    return False
