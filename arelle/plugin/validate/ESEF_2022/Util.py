'''
Version 2022 created on September 19, 2022

Filer Guidelines: https://www.esma.europa.eu/sites/default/files/library/esma32-60-254_esef_reporting_manual.pdf

See COPYRIGHT.md for copyright information.
'''
from __future__ import annotations
import binascii
from lxml.etree import _Element
from urllib.parse import unquote
import os, json, regex as re

from arelle.ModelDtsObject import ModelConcept
from arelle.ModelInstanceObject import ModelContext, ModelFact, ModelUnit
from arelle.ModelObject import ModelObject
from arelle.ModelObjectFactory import parser
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ModelValue import QName
from arelle.XmlValidateConst import VALID
from .Const import esefTaxonomyNamespaceURIs, esefNotesStatementConcepts,\
    esefCorNsPattern, htmlEventHandlerAttributes, svgEventAttributes
from lxml.etree import XML, XMLSyntaxError
from arelle.FileSource import openFileStream
from arelle.UrlUtil import scheme, decodeBase64DataImage
from arelle.ModelManager import ModelManager
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateFilingText import parseImageDataURL, validateGraphicHeaderType
from arelle.ValidateXbrl import ValidateXbrl
from typing import Any, Dict, List, Optional, Union, cast
from arelle.ModelDocument import ModelDocument
from arelle.typing import TypeGetText
from collections import defaultdict

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

def validateImage(baseUrl:Optional[str], image: str, modelXbrl: ModelXbrl, val:ValidateXbrl, elt:_Element, evaluatedMsg:str, contentOtherThanXHTMLGuidance:str) -> None:
    """
    image: either an url or base64 in data:image style
    """
    minExternalRessourceSize = val.authParam["minExternalResourceSizekB"]
    if minExternalRessourceSize != -1:
        # transform kb to b
        minExternalRessourceSize = minExternalRessourceSize * 1024
    if scheme(image) in ("http", "https", "ftp"):
        modelXbrl.error("ESEF.4.1.6.xHTMLDocumentContainsExternalReferences" if val.unconsolidated
                        else "ESEF.3.5.1.inlineXbrlDocumentContainsExternalReferences",
                        _("Inline XBRL instance documents MUST NOT contain any reference pointing to resources outside the reporting package: %(element)s"),
                        modelObject=elt, element=elt.tag, evaluatedMsg=evaluatedMsg,
                        messageCodes=("ESEF.3.5.1.inlineXbrlDocumentContainsExternalReferences",
                                      "ESEF.4.1.6.xHTMLDocumentContainsExternalReferences"))
    elif image.startswith("data:image"):
        dataURLParts = parseImageDataURL(image)
        if not dataURLParts or not dataURLParts.isBase64:
            modelXbrl.warning(f"{contentOtherThanXHTMLGuidance}.embeddedImageNotUsingBase64Encoding",
                              _("Images included in the XHTML document SHOULD be base64 encoded: %(src)s."),
                              modelObject=elt, src=image[:128], evaluatedMsg=evaluatedMsg)
            if dataURLParts and dataURLParts.mimeSubtype and dataURLParts.data:
                checkImageContents(None, modelXbrl, elt, dataURLParts.mimeSubtype, False, unquote(dataURLParts.data), val.consolidated, val)
        else:
            if not dataURLParts.mimeSubtype:
                modelXbrl.error(f"{contentOtherThanXHTMLGuidance}.MIMETypeNotSpecified",
                                _("Images included in the XHTML document MUST be saved with MIME type specifying PNG, GIF, SVG or JPG/JPEG formats: %(src)s."),
                                modelObject=elt, src=image[:128], evaluatedMsg=evaluatedMsg)
            elif dataURLParts.mimeSubtype not in ("gif", "jpeg", "png", "svg+xml"):
                modelXbrl.error(f"{contentOtherThanXHTMLGuidance}.imageFormatNotSupported",
                                _("Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPG/JPEG formats: %(src)s."),
                                modelObject=elt, src=image[:128], evaluatedMsg=evaluatedMsg)
            # check for malicious image contents
            try:  # allow embedded newlines
                imgContents:Union[bytes, Any, str] = decodeBase64DataImage(dataURLParts.data)
                checkImageContents(None, modelXbrl, elt, str(dataURLParts.mimeSubtype), False, imgContents, val.consolidated, val)
                imgContents = b""  # deref, may be very large

            except binascii.Error as err:
                modelXbrl.error(f"{contentOtherThanXHTMLGuidance}.embeddedImageNotUsingBase64Encoding",
                                _("Base64 encoding error %(err)s in image source: %(src)s."),
                                modelObject=elt, err=str(err), src=image[:128], evaluatedMsg=evaluatedMsg)
    else:
        # presume it to be an image file, check image contents
        try:
            base = baseUrl
            normalizedUri = modelXbrl.modelManager.cntlr.webCache.normalizeUrl(image, base)
            if not modelXbrl.fileSource.isInArchive(normalizedUri):
                normalizedUri = modelXbrl.modelManager.cntlr.webCache.getfilename(normalizedUri)
            imglen = 0
            with modelXbrl.fileSource.file(normalizedUri, binary=True)[0] as fh:
                imgContents = fh.read()
                imglen += len(imgContents or '')
                checkImageContents(normalizedUri, modelXbrl, elt, os.path.splitext(image)[1], True, imgContents,
                                   val.consolidated, val)
                imgContents = b""  # deref, may be very large
            if imglen < minExternalRessourceSize:
                modelXbrl.warning(
                    "%s.imageIncludedAndNotEmbeddedAsBase64EncodedString" % contentOtherThanXHTMLGuidance,
                    _("Images SHOULD be included in the XHTML document as a base64 encoded string unless their size exceeds the minimum size for the authority (%(maxImageSize)s): %(file)s."),
                    modelObject=elt, maxImageSize=minExternalRessourceSize, file=os.path.basename(normalizedUri), evaluatedMsg=evaluatedMsg)
        except IOError as err:
            modelXbrl.error(f"{contentOtherThanXHTMLGuidance}.imageFileCannotBeLoaded",
                            _("Error opening the file '%(src)s': %(error)s"),
                            modelObject=elt, src=image, error=err, evaluatedMsg=evaluatedMsg)

def checkImageContents(baseURI: Optional[str], modelXbrl: ModelXbrl, imgElt: _Element, imgType: str, isFile: bool, data: Union[bytes, Any, str], consolidated: bool, val: ValidateXbrl) -> None:
    guidance = 'ESEF.2.5.1' if consolidated else 'ESEF.4.1.3'
    if "svg" in imgType:
        try:
            checkSVGContent(baseURI, modelXbrl, imgElt, data, guidance, val)
        except XMLSyntaxError as err:
            try:
                checkSVGContent(baseURI, modelXbrl, imgElt, unquote(data), guidance, val)  # Try with utf-8 decoded data as in conformance suite G4-1-3_2/TC2
            except XMLSyntaxError:
                modelXbrl.error(f"{guidance}.imageFileCannotBeLoaded",
                                _("Image SVG has XML error %(error)s"),
                                modelObject=imgElt, error=err)
        except UnicodeDecodeError as err:
            modelXbrl.error(f"{guidance}.imageFileCannotBeLoaded",
                _("Image SVG has XML error %(error)s"),
                modelObject=imgElt, error=err)
    else:
        headerType = validateGraphicHeaderType(data)  # type: ignore[arg-type]
        if (("gif" not in imgType and headerType == "gif") or
            ("jpeg" not in imgType and "jpg" not in imgType and headerType == "jpg") or
            ("png" not in imgType and headerType == "png")):
            imageDoesNotMatchItsFileExtension = f"{guidance}.imageDoesNotMatchItsFileExtension"
            incorrectMIMETypeSpecified = f"{guidance}.incorrectMIMETypeSpecified"
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


def checkSVGContent(baseURI: Optional[str], modelXbrl: ModelXbrl, imgElt: _Element, data: Union[bytes, Any, str],
                    guidance: str, val: ValidateXbrl) -> None:
    _parser, _ignored, _ignored = parser(modelXbrl, baseURI)
    elt = XML(data, parser=_parser)
    checkSVGContentElt(elt, baseURI, modelXbrl, imgElt, guidance, val)

def getHref(elt:_Element) -> str :
    simple_href = elt.get("href", "").strip()
    if len(simple_href) > 0:
        return simple_href
    else:
        # 'xlink:href' is deprecated but still used by some SVG generators
        return elt.get("{http://www.w3.org/1999/xlink}href", "").strip()

def checkSVGContentElt(elt: _Element, baseUrl: Optional[str], modelXbrl: ModelXbrl, imgElt: _Element,
                       guidance: str, val:ValidateXbrl) -> None:
    rootElement = True
    for elt in elt.iter():
        if rootElement:
            if elt.tag != "{http://www.w3.org/2000/svg}svg":
                modelXbrl.error(f"{guidance}.imageFileCannotBeLoaded",
                                _("Image SVG has root element which is not svg"),
                                modelObject=imgElt)
            rootElement = False
        eltTag = elt.tag.rpartition("}")[2] # strip namespace
        if eltTag == "image":
            validateImage(baseUrl, getHref(elt), modelXbrl, val, elt, "", guidance)
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


def checkForMultiLangDuplicates(modelXbrl: ModelXbrl) -> None:
    _factConceptContextUnitHash: defaultdict[int, list[ModelFact]] = defaultdict(list)

    for f in modelXbrl.factsInInstance:
        if (
            (f.isNil or getattr(f, "xValid", 0) >= VALID)
            and f.context is not None
            and f.concept is not None
            and f.concept.type is not None
            and f.concept.type.isWgnStringFactType
        ):
            _factConceptContextUnitHash[f.conceptContextUnitHash].append(f)

    for hashEquivalentFacts in _factConceptContextUnitHash.values():
        if len(hashEquivalentFacts) <= 1:  # skip facts present only once
            continue
        _aspectEqualFacts: defaultdict[tuple[QName, str], dict[tuple[ModelContext, ModelUnit | None], list[ModelFact]]] = defaultdict(dict)
        for f in hashEquivalentFacts:  # check for hash collision by value checks on context and unit
            cuDict = _aspectEqualFacts[(f.qname, (f.xmlLang or "").lower())]
            _matched = False
            for (_cntx, _unit), fList in cuDict.items():
                if (f.context.isEqualTo(_cntx)
                        and ((_unit is None and f.unit is None)
                             or (f.unit is not None and f.unit.isEqualTo(_unit)))):
                    _matched = True
                    fList.append(f)
                    break
            if not _matched:
                cuDict[(f.context, f.unit)] = [f]
        for cuDict in _aspectEqualFacts.values():
            for fList in cuDict.values():
                if len(fList) > 1 and not all(f.xValue == fList[0].xValue for f in fList):
                    modelXbrl.warning("ESEF.2.2.4.inconsistentDuplicateNonnumericFactInInlineXbrlDocument",
                        "Inconsistent duplicate non-numeric facts SHOULD NOT appear in the content of an inline XBRL document. "
                        "%(fact)s that was used more than once in contexts equivalent to %(contextID)s, with different values but same language (%(language)s).",
                        modelObject=fList, fact=fList[0].qname, contextID=fList[0].contextID, language=fList[0].xmlLang)

def getEsefNotesStatementConcepts(modelXbrl: ModelXbrl) -> set[str]:
    document_name_spaces = modelXbrl.namespaceDocs
    esef_notes_statement_concepts:set[str] = set()
    esef_cor_Nses = []
    for targetNs, models in document_name_spaces.items():
        if esefCorNsPattern.match(targetNs):
            found_prefix = ''
            found_namespace = ''
            for prefix, namespace in models[0].targetXbrlRootElement.nsmap.items():
                if targetNs == namespace:
                    found_namespace = targetNs
                    found_prefix = '' if prefix is None else prefix
                    break
            esef_cor_Nses.append((found_prefix, found_namespace))
    if len(esef_cor_Nses) == 0:
        modelXbrl.error("ESEF.RTS.efrsCoreRequired",
                          _("RTS on ESEF requires EFRS core taxonomy."),
                          modelObject=modelXbrl)
    elif len(esef_cor_Nses) > 1:
        modelXbrl.warning("Arelle.ESEF.multipleEsefTaxonomies",
                        _("Multiple ESEF taxonomies were imported %(esefNamespaces)s."),
                        modelObject=modelXbrl, esefNamespaces=", ".join(ns[1] for ns in esef_cor_Nses))
    else:
        esef_notes_statement_concepts = set(str(QName(esef_cor_Nses[0][0], esef_cor_Nses[0][1], n)) for n in esefNotesStatementConcepts)
    return esef_notes_statement_concepts

def isChildOfNotes(child: ModelConcept, relSet: ModelRelationshipSet,
                   esefNotesConcepts: set[str], _visited: set[ModelConcept]) -> bool:
    if len(esefNotesConcepts) == 0:
        return False
    relations_to = relSet.toModelObject(child)
    if not relations_to and str(child.qname) in esefNotesConcepts:
        return True

    _visited.add(child)
    for rel in relations_to:
        parent = rel.fromModelObject
        if parent is not None and parent not in _visited:
            if isChildOfNotes(parent, relSet, esefNotesConcepts, _visited):
                return True
    _visited.remove(child)
    return False

def hasEventHandlerAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, htmlEventHandlerAttributes)

def hasSvgEventAttributes(elt: Any) -> bool:
    return _hasEventAttributes(elt, svgEventAttributes)

def _hasEventAttributes(elt: Any, attributes: set[str]) -> bool:
    if isinstance(elt, _Element):
        return any(a in attributes for a in elt.keys())
    return False
