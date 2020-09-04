'''
Created on January 5, 2020

Filer Guidelines: ESMA_ESEF Manula 2019.pdf

@author: Mark V Systems Limited
(c) Copyright 2020 Mark V Systems Limited, All rights reserved.
'''
from .Const import standardTaxonomyURIs, esefTaxonomyNamespaceURIs
from lxml.etree import XML, XMLSyntaxError
from arelle.UrlUtil import scheme

# check if a modelDocument URI is an extension URI (document URI)
# also works on a uri passed in as well as modelObject
def isExtension(val, modelObject):
    if modelObject is None:
        return False
    if isinstance(modelObject, str):
        uri = modelObject
    else:
        uri = modelObject.modelDocument.uri
    return (uri.startswith(val.modelXbrl.uriDir) or
            not any(uri.startswith(standardTaxonomyURI) for standardTaxonomyURI in standardTaxonomyURIs))

# check if in core esef taxonomy (based on namespace URI)
def isInEsefTaxonomy(val, modelObject):
    if modelObject is None:
        return False
    ns = modelObject.qname.namespaceURI
    return (any(ns.startswith(esefNsPrefix) for esefNsPrefix in esefTaxonomyNamespaceURIs))
    
# check image contents against mime/file ext and for Steganography
def checkImageContents(modelXbrl, imgElt, imgType, isFile, data):
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
    elif not any(t in imgType for t in ("gif", "jpg", "jpeg", "png")):
        modelXbrl.error("ESEF.2.5.1.imageFormatNotSupported",
            _("Images included in the XHTML document MUST be saved in PNG, GIF, SVG or JPG/JPEG formats: %(imgType)s is not supported"),
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
        