from __future__ import annotations

import io

from lxml import etree

from arelle import FileSource
from arelle import XbrlConst

class ModelDocumentType:
    """
    .. class:: ModelDocumentType

    Static class of Enumerated type representing modelDocument type
    """
    UnknownXML: int = 0
    UnknownNonXML: int = 1
    UnknownTypes: int = 1  # to test if any unknown type, use <= Type.UnknownTypes
    firstXBRLtype: int = 2  # first filetype that is XBRL and can hold a linkbase, etc inside it
    SCHEMA: int = 2
    LINKBASE: int = 3
    INSTANCE: int = 4
    INLINEXBRL: int = 5
    lastXBRLtype: int = 5  # first filetype that is XBRL and can hold a linkbase, etc inside it
    DTSENTRIES: int = 6  # multiple schema/linkbase Refs composing a DTS but not from an instance document
    INLINEXBRLDOCUMENTSET: int = 7
    VERSIONINGREPORT: int = 8
    TESTCASESINDEX: int = 9
    TESTCASE: int = 10
    REGISTRY: int = 11
    REGISTRYTESTCASE: int = 12
    XPATHTESTSUITE: int = 13
    RSSFEED: int = 14
    ARCSINFOSET: int = 15
    FACTDIMSINFOSET: int = 16
    HTML: int = 17

    TESTCASETYPES: tuple[int, ...] = (TESTCASESINDEX, TESTCASE, REGISTRY, REGISTRYTESTCASE, XPATHTESTSUITE)

    typeName: tuple[str, ...] = ("unknown XML",
                "unknown non-XML",
                "schema",
                "linkbase",
                "instance",
                "inline XBRL instance",
                "entry point set",
                "inline XBRL document set",
                "versioning report",
                "testcases index",
                "testcase",
                "registry",
                "registry testcase",
                "xpath test suite",
                "RSS feed",
                "arcs infoset",
                "fact dimensions infoset",
                "html non-XBRL")

    @staticmethod
    def identify(filesource: FileSource.FileSource, filepath: str) -> int:
        _type: int = ModelDocumentType.UnknownNonXML
        _file: io.BytesIO = filesource.file(filepath, stripDeclaration=True, binary=True)[0]  # type: ignore[assignment]
        try:
            _rootElt: bool = True
            _maybeHtml: bool = False
            for _event, elt in etree.iterparse(_file, events=("start",), recover=True, huge_tree=True):
                assert isinstance(elt, etree.Element)
                if _rootElt:
                    _rootElt = False
                    _type = {"testcases": ModelDocumentType.TESTCASESINDEX,
                             "documentation": ModelDocumentType.TESTCASESINDEX,
                             "testSuite": ModelDocumentType.TESTCASESINDEX,
                             "registries": ModelDocumentType.TESTCASESINDEX,
                             "testcase": ModelDocumentType.TESTCASE,
                             "testSet": ModelDocumentType.TESTCASE,
                             "rss": ModelDocumentType.RSSFEED
                        }.get(etree.QName(elt).localname, ModelDocumentType.UnknownXML)
                    if _type:
                        break
                    _type = {"{http://www.xbrl.org/2003/instance}xbrl": ModelDocumentType.INSTANCE,
                             "{http://www.xbrl.org/2003/linkbase}linkbase": ModelDocumentType.LINKBASE,
                             "{http://www.w3.org/2001/XMLSchema}schema": ModelDocumentType.SCHEMA,
                             "{http://xbrl.org/2008/registry}registry": ModelDocumentType.REGISTRY
                             }.get(elt.tag, ModelDocumentType.UnknownXML)  # type: ignore[arg-type]
                    if _type == ModelDocumentType.UnknownXML and elt.tag.endswith("html"):  # type: ignore[union-attr,arg-type]
                        _maybeHtml = True
                    else:
                        break # stop parsing
                if XbrlConst.ixbrlTagPattern.match(str(elt.tag)):
                    _type = ModelDocumentType.INLINEXBRL
                    break
            if _type == ModelDocumentType.UnknownXML and _maybeHtml:
                _type = ModelDocumentType.HTML
        except Exception as err:
            if not _rootElt: # if _rootElt is false then a root element was found and it's some kind of xml
                _type = ModelDocumentType.UnknownXML
                if filesource.cntlr:
                    filesource.cntlr.addToLog("%(error)s",
                                              messageCode="arelle:fileIdentificationError",
                                              messageArgs={"error":err}, file=filepath)
        _file.close()
        return _type
