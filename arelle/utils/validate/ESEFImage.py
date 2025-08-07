"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import binascii
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import unquote

import tinycss2  # type: ignore[import-untyped]
from lxml.etree import XML, XMLSyntaxError, _Element

from arelle import ModelDocument
from arelle.ModelObjectFactory import parser
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText
from arelle.UrlUtil import decodeBase64DataImage, scheme
from arelle.utils.validate.Validation import Validation
from arelle.ValidateFilingText import parseImageDataURL, validateGraphicHeaderType
from arelle.ValidateXbrl import ValidateXbrl

_: TypeGetText  # Handle gettext


@dataclass(frozen=True)
class ImageValidationParameters:
    checkMinExternalResourceSize: bool
    consolidated: bool
    contentOtherThanXHTMLGuidance: str
    missingMimeTypeIsIncorrect: bool
    recommendBase64EncodingEmbeddedImages: bool
    supportedImgTypes: dict[bool, tuple[str, ...]]

    @classmethod
    def from_non_esef(
        cls,
        checkMinExternalResourceSize: bool,
        missingMimeTypeIsIncorrect: bool,
        recommendBase64EncodingEmbeddedImages: bool,
        supportedImgTypes: dict[bool, tuple[str, ...]],
    ) -> ImageValidationParameters:
        return cls(
            checkMinExternalResourceSize=checkMinExternalResourceSize,
            consolidated=True,
            # This must be an ESEF code, even if it's later discarded.
            contentOtherThanXHTMLGuidance="ESEF.2.5.1",
            missingMimeTypeIsIncorrect=missingMimeTypeIsIncorrect,
            recommendBase64EncodingEmbeddedImages=recommendBase64EncodingEmbeddedImages,
            supportedImgTypes=supportedImgTypes,
        )


def validateImageAndLog(
    baseUrl: str | None,
    image: str,
    modelXbrl: ModelXbrl,
    val: ValidateXbrl,
    elts: _Element | list[_Element],
    evaluatedMsg: str,
    params: ImageValidationParameters,
    prelude: list[Any] | None = None,
) -> None:
    cssSelectors = None
    for validation in validateImage(
        baseUrl=baseUrl,
        image=image,
        modelXbrl=modelXbrl,
        val=val,
        elts=elts,
        evaluatedMsg=evaluatedMsg,
        params=params,
    ):
        if cssSelectorsArg := validation.args.get("cssSelectors"):
            raise ValueError(_("The 'cssSelectors' argument is reserved to record the CSS selector. It should not be present in the validation arguments: {}").format(cssSelectorsArg))
        if prelude and cssSelectors is None:
            cssSelectors = tinycss2.serialize(prelude).strip()
        args = validation.args.copy()
        if cssSelectors:
            args["cssSelectors"] = cssSelectors
        modelXbrl.log(level=validation.level.name, codes=validation.codes, msg=validation.msg, **args)

# check image contents against mime/file ext and for Steganography
def validateImage(
    baseUrl: str | None,
    image: str,
    modelXbrl: ModelXbrl,
    val: ValidateXbrl,
    elts: _Element | list[_Element],
    evaluatedMsg: str,
    params: ImageValidationParameters,
) -> Iterable[Validation]:
    """
    image: either an url or base64 in data:image style
    """
    contentOtherThanXHTMLGuidance = params.contentOtherThanXHTMLGuidance
    # a list of img elements are maintained because an SVG can reference another SVG
    # or other type of image and we need to log the entire reference chain.
    if not isinstance(elts, list):
        elts = [elts]
    if params.checkMinExternalResourceSize:
        minExternalRessourceSize = val.authParam["minExternalResourceSizekB"]
        if minExternalRessourceSize != -1:
            # transform kb to b
            minExternalRessourceSize = minExternalRessourceSize * 1024
    if scheme(image) in ("http", "https", "ftp"):
        yield Validation.error(("ESEF.4.1.6.xHTMLDocumentContainsExternalReferences" if not params.consolidated
                               else "ESEF.3.5.1.inlineXbrlDocumentContainsExternalReferences",
                               "NL.NL-KVK.3.6.2.1.inlineXbrlDocumentContainsExternalReferences"),
                               _("Inline XBRL instance documents MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                               modelObject=elts, element=elts[0].tag, evaluatedMsg=evaluatedMsg,
                               messageCodes=("ESEF.3.5.1.inlineXbrlDocumentContainsExternalReferences",
                                             "ESEF.4.1.6.xHTMLDocumentContainsExternalReferences",
                                             "NL.NL-KVK.3.6.2.1.inlineXbrlDocumentContainsExternalReferences"))
    elif image.startswith("data:image"):
        dataURLParts = parseImageDataURL(image)
        if not dataURLParts or not dataURLParts.isBase64:
            if params.recommendBase64EncodingEmbeddedImages:
                yield Validation.warning(f"{contentOtherThanXHTMLGuidance}.embeddedImageNotUsingBase64Encoding",
                                         _("Images included in the XHTML document SHOULD be base64 encoded: %(src)s."),
                                         modelObject=elts, src=image[:128], evaluatedMsg=evaluatedMsg)
            if dataURLParts and dataURLParts.mimeSubtype and dataURLParts.data:
                yield from checkImageContents(None, modelXbrl, elts, dataURLParts.mimeSubtype, False, unquote(dataURLParts.data), params, True, val)
        else:
            hasMimeType = bool(dataURLParts.mimeSubtype)
            if not hasMimeType:
                yield Validation.error((f"{contentOtherThanXHTMLGuidance}.MIMETypeNotSpecified", "NL.NL-KVK.3.5.1.2.MIMETypeNotSpecified"),
                                       _("Images included in the XHTML document MUST be saved with MIME type specifying PNG, GIF, SVG or JPG/JPEG formats: %(src)s."),
                                       modelObject=elts, src=image[:128], evaluatedMsg=evaluatedMsg)
            elif dataURLParts.mimeSubtype not in ("gif", "jpeg", "png", "svg+xml"):
                yield Validation.error((f"{contentOtherThanXHTMLGuidance}.imageFormatNotSupported", "NL.NL-KVK.3.5.1.5.imageFormatNotSupported"),
                                       _("Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPG/JPEG formats: %(src)s."),
                                       modelObject=elts, src=image[:128], evaluatedMsg=evaluatedMsg)
            # check for malicious image contents
            try:  # allow embedded newlines
                imgContents = decodeBase64DataImage(dataURLParts.data)
                yield from checkImageContents(None, modelXbrl, elts, str(dataURLParts.mimeSubtype), False, imgContents, params, hasMimeType, val)
                imgContents = b""  # deref, may be very large

            except binascii.Error as err:
                if params.recommendBase64EncodingEmbeddedImages:
                    yield Validation.error(f"{contentOtherThanXHTMLGuidance}.embeddedImageNotUsingBase64Encoding",
                                           _("Base64 encoding error %(err)s in image source: %(src)s."),
                                           modelObject=elts, err=str(err), src=image[:128], evaluatedMsg=evaluatedMsg)
    else:
        # presume it to be an image file, check image contents
        try:
            base = baseUrl
            normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(image, base)
            if not modelXbrl.fileSource.isInArchive(normalizedUri):
                normalizedUri = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
            imglen = 0
            with modelXbrl.fileSource.file(normalizedUri, binary=True)[0] as fh:
                imgContents = cast(bytes, fh.read())
                imglen += len(imgContents or '')
                yield from checkImageContents(normalizedUri, modelXbrl, elts, os.path.splitext(image)[1], True, imgContents, params, False, val)
                imgContents = b""  # deref, may be very large
            if params.checkMinExternalResourceSize and imglen < minExternalRessourceSize:
                yield Validation.warning(
                    ("%s.imageIncludedAndNotEmbeddedAsBase64EncodedString" % contentOtherThanXHTMLGuidance, "NL.NL-KVK.3.5.1.imageIncludedAndNotEmbeddedAsBase64EncodedString"),
                    _("Images SHOULD be included in the XHTML document as a base64 encoded string unless their size exceeds the minimum size for the authority (%(maxImageSize)s): %(file)s."),
                    modelObject=elts, maxImageSize=minExternalRessourceSize, file=os.path.basename(normalizedUri), evaluatedMsg=evaluatedMsg)
        except IOError as err:
            fileReferencingImage = os.path.basename(baseUrl) if baseUrl else ''
            yield Validation.error((f"{contentOtherThanXHTMLGuidance}.imageFileCannotBeLoaded", "NL.NL-KVK.3.5.1.imageFileCannotBeLoaded"),
                                   _("Error opening the file '%(src)s' referenced by '%(fileReferencingImage)s': %(error)s"),
                                   modelObject=elts, src=image, fileReferencingImage=fileReferencingImage, error=err, evaluatedMsg=evaluatedMsg)


def checkImageContents(
    baseURI: str | None,
    modelXbrl: ModelXbrl,
    imgElts: list[_Element],
    imgType: str,
    isFile: bool,
    data: bytes | str,
    params: ImageValidationParameters,
    hasMimeType: bool,
    val: ValidateXbrl,
) -> Iterable[Validation]:
    guidance = params.contentOtherThanXHTMLGuidance
    if "svg" in imgType:
        try:
            yield from checkSVGContent(baseURI, modelXbrl, imgElts, data, params, val)
        except XMLSyntaxError as err:
            try:
                yield from checkSVGContent(baseURI, modelXbrl, imgElts, unquote(data), params, val)  # Try with utf-8 decoded data as in conformance suite G4-1-3_2/TC2
            except XMLSyntaxError:
                yield Validation.error((f"{guidance}.imageFileCannotBeLoaded", "NL.NL-KVK.3.5.1.imageFileCannotBeLoaded"),
                                       _("Image SVG has XML error %(error)s"),
                                       modelObject=imgElts, error=err)
        except UnicodeDecodeError as err:
            yield Validation.error((f"{guidance}.imageFileCannotBeLoaded", "NL.NL-KVK.3.5.1.imageFileCannotBeLoaded"),
                                   _("Image SVG has XML error %(error)s"),
                                   modelObject=imgElts, error=err)
    else:
        headerType = validateGraphicHeaderType(data)  # type: ignore[arg-type]
        if (("gif" not in imgType and headerType == "gif") or
            ("jpeg" not in imgType and "jpg" not in imgType and headerType == "jpg") or
            ("png" not in imgType and headerType == "png")):
            imageDoesNotMatchItsFileExtension = (f"{guidance}.imageDoesNotMatchItsFileExtension", "NL.NL-KVK.3.5.1.4.imageDoesNotMatchItsFileExtension")
            incorrectMIMETypeSpecified = (f"{guidance}.incorrectMIMETypeSpecified", "NL.NL-KVK.3.5.1.3.incorrectMIMETypeSpecified")
            if isFile:
                codes = imageDoesNotMatchItsFileExtension
                message = _("File type %(headerType)s inferred from file signature does not match the file extension %(imgType)s")
            else:
                codes = incorrectMIMETypeSpecified
                message = _("File type %(headerType)s inferred from file signature does not match the data URL media subtype (MIME subtype) %(imgType)s")
            if isFile or params.missingMimeTypeIsIncorrect or hasMimeType:
                yield Validation.error(codes, message,
                    modelObject=imgElts, imgType=imgType, headerType=headerType,
                    messageCodes=(
                        imageDoesNotMatchItsFileExtension, incorrectMIMETypeSpecified,
                        "NL.NL-KVK.3.5.1.3.incorrectMIMETypeSpecified", "NL.NL-KVK.3.5.1.4.imageDoesNotMatchItsFileExtension",
                    ))
        elif not any(it in imgType for it in params.supportedImgTypes[isFile]):
            yield Validation.error((f"{guidance}.imageFormatNotSupported", "NL.NL-KVK.3.5.1.5.imageFormatNotSupported"),
                                   _("Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPEG formats: %(imgType)s is not supported"),
                                   modelObject=imgElts, imgType=imgType)


def checkSVGContent(
    baseURI: str | None,
    modelXbrl: ModelXbrl,
    imgElts: list[_Element],
    data: bytes | str,
    params: ImageValidationParameters,
    val: ValidateXbrl,
) -> Iterable[Validation]:
    if baseURI:
        svgDoc = cast(ModelDocument.ModelDocument, ModelDocument.load(modelXbrl, baseURI, referringElement=imgElts[0]))
        elt = svgDoc.xmlRootElement
    else:
        _parser, _, _ = parser(modelXbrl, baseURI)
        elt = XML(data, parser=_parser)
    yield from checkSVGContentElt(elt, baseURI, modelXbrl, imgElts, params, val)


def getHref(elt:_Element) -> str:
    simple_href = elt.get("href", "").strip()
    if len(simple_href) > 0:
        return simple_href
    else:
        # 'xlink:href' is deprecated but still used by some SVG generators
        return elt.get("{http://www.w3.org/1999/xlink}href", "").strip()


def checkSVGContentElt(
    elt: _Element,
    baseUrl: str | None,
    modelXbrl: ModelXbrl,
    imgElts: list[_Element],
    params: ImageValidationParameters,
    val: ValidateXbrl,
) -> Iterable[Validation]:
    guidance = params.contentOtherThanXHTMLGuidance
    rootElement = True
    for childElt in elt.iter():
        if rootElement:
            if childElt.tag != "{http://www.w3.org/2000/svg}svg":
                yield Validation.error((f"{guidance}.imageFileCannotBeLoaded", "NL.NL-KVK.3.5.1.imageFileCannotBeLoaded"),
                                       _("Image SVG has root element which is not svg"),
                                       modelObject=imgElts)
            rootElement = False
        # Comments, processing instructions, and maybe other special constructs don't have string tags.
        if not isinstance(childElt.tag, str):
            continue
        eltTag = childElt.tag.rpartition("}")[2] # strip namespace
        if eltTag == "image":
            imgElts = [*imgElts, childElt]
            yield from validateImage(baseUrl, getHref(childElt), modelXbrl, val, imgElts, "", params)
        if eltTag in ("object", "script", "audio", "foreignObject", "iframe", "image", "use", "video"):
            href = childElt.get("href","")
            if eltTag in ("object", "script") or "javascript:" in href:
                yield Validation.error((f"{guidance}.executableCodePresent", "NL.NL-KVK.3.5.1.1.executableCodePresent"),
                                       _("Inline XBRL images MUST NOT contain executable code: %(element)s"),
                                       modelObject=imgElts, element=eltTag)
            elif scheme(href) in ("http", "https", "ftp"):
                yield Validation.error((f"{guidance}.referencesPointingOutsideOfTheReportingPackagePresent", "NL.NL-KVK.3.6.2.1.inlineXbrlDocumentContainsExternalReferences"),
                                       _("Inline XBRL instance document [image] MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                                       modelObject=imgElts, element=eltTag)
