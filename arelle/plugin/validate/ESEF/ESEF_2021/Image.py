"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Union
from urllib.parse import unquote

from lxml.etree import XML, XMLSyntaxError

from arelle.ModelObject import ModelObject
from arelle.ModelXbrl import ModelXbrl
from arelle.UrlUtil import scheme
from arelle.ValidateFilingText import validateGraphicHeaderType
from arelle.typing import TypeGetText
from ..Const import supportedImgTypes
from ..Util import hasSvgEventAttributes

_: TypeGetText


# check image contents against mime/file ext and for Steganography
def checkImageContents(
    modelXbrl: ModelXbrl,
    imgElt: ModelObject,
    imgType: str,
    isFile: bool,
    data: bytes,
    consolidated: bool,
) -> None:
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


def checkSVGContent(
    modelXbrl: ModelXbrl,
    imgElt: ModelObject,
    data: Union[bytes, Any, str],
    guidance: str,
) -> None:
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
