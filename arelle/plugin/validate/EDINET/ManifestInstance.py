"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import traceback
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import cast

from lxml import etree
from lxml.etree import _Element

from arelle import XbrlConst
from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.ModelValue import QName, qname
from arelle.typing import TypeGetText
from . import Constants

_: TypeGetText


@dataclass(frozen=True)
class ManifestInstance:
    id: str
    ixbrlFiles: list[Path]
    path: Path
    preferredFilename: str
    titlesByLang: dict[str, str]
    tocItems: list[ManifestTocItem]
    type: str


@dataclass(frozen=True)
class ManifestTocItem:
    element: _Element
    extrole: str
    childItems: list[ManifestTocItem]
    itemIn: str
    parent: QName | None
    ref: str
    start: QName | None
    end: QName | None


def _invalidManifestError(cntlr: Cntlr, file: str, message: str | None = None) -> None:
    if message is None:
        message = _("Please correct the content.")
    cntlr.error(
        "EDINET.EC5800E.FATAL_ERROR_INVALID_MANIFEST",
        _("The manifest file definition is incorrect <file=%(file)s>. %(message)s"),
        file=file,
        message=message,
    )


def _parseManifestTocItems(parentElt: _Element, parentQName: QName | None) -> list[ManifestTocItem]:
    tocItems = []
    for itemElt in parentElt.iterchildren(tag=Constants.qnEdinetManifestItem.clarkNotation):
        childTocItems = []
        for insertElt in itemElt.iterchildren(tag=Constants.qnEdinetManifestInsert.clarkNotation):
            childParentQName = qname(insertElt.attrib.get("parent"), insertElt.nsmap) if insertElt.attrib.get("parent") else None
            childTocItems.extend(_parseManifestTocItems(insertElt, childParentQName))
        tocItems.append(ManifestTocItem(
            element=itemElt,
            extrole=itemElt.attrib.get("extrole", ""),
            childItems=childTocItems,
            parent=parentQName,
            itemIn=itemElt.attrib.get("in", ""),
            ref=itemElt.attrib.get("ref", ""),
            start=qname(itemElt.attrib.get("start"), itemElt.nsmap) if itemElt.attrib.get("start") else None,
            end=qname(itemElt.attrib.get("end"), itemElt.nsmap) if itemElt.attrib.get("end") else None,
        ))
    return tocItems


def _parseManifestDoc(xmlRootElement: _Element, path: Path) -> list[ManifestInstance]:
    instances = []
    titlesByLang = {}
    base = path.parent
    tocElts = list(xmlRootElement.iterchildren(tag=Constants.qnEdinetManifestTocComposition.clarkNotation))
    assert len(tocElts) == 1, _('There should be exactly one tocComposition element in the manifest.')
    for titleElt in tocElts[0].iterchildren(tag=Constants.qnEdinetManifestTitle.clarkNotation):
        lang = titleElt.attrib.get(XbrlConst.qnXmlLang.clarkNotation, "")
        titlesByLang[lang] = titleElt.text.strip() if titleElt.text else ""
    tocItems = _parseManifestTocItems(tocElts[0], None)
    tocItemsByRef = defaultdict(list)
    for tocItem in tocItems:
        tocItemsByRef[tocItem.ref].append(tocItem)
    listElts = list(xmlRootElement.iterchildren(tag=Constants.qnEdinetManifestList.clarkNotation))
    assert len(listElts) == 1, _('There should be exactly one list element in the manifest.')
    for instanceElt in listElts[0].iterchildren(tag=Constants.qnEdinetManifestInstance.clarkNotation):
        instanceId = str(instanceElt.attrib.get("id", ""))
        instanceType = str(instanceElt.attrib.get("type", ""))
        preferredFilename = str(instanceElt.attrib.get("preferredFilename", ""))
        ixbrlFiles = []
        for ixbrlElt in instanceElt.iterchildren(tag=Constants.qnEdinetManifestIxbrl.clarkNotation):
            uri = ixbrlElt.text.strip() if ixbrlElt.text is not None else None
            if uri is not None and len(uri) > 0:
                ixbrlFiles.append(base / uri)
        instances.append(ManifestInstance(
            id=instanceId,
            ixbrlFiles=ixbrlFiles,
            path=path,
            preferredFilename=preferredFilename,
            titlesByLang=titlesByLang,
            tocItems=tocItemsByRef.get(instanceId, []),
            type=instanceType,
        ))
    return instances


@lru_cache(1)
def parseManifests(filesource: FileSource) -> list[ManifestInstance]:
    assert filesource.cntlr is not None, "FileSource controller must be set before parsing manifests."
    cntlr = filesource.cntlr
    instances: list[ManifestInstance] = []
    if filesource.isArchive:
        if filesource.isTaxonomyPackage:
            return instances
        if filesource.reportPackage is not None:
            return instances
        if not isinstance(filesource.fs, zipfile.ZipFile):
            _invalidManifestError(
                cntlr,
                cast(str, filesource.url),
                _("The EDINET plugin only supports archives in .zip format.")
            )
        else:
            for _archiveFile in (filesource.dir or ()):
                if not Path(_archiveFile).stem.startswith('manifest'):
                    continue
                try:
                    with filesource.fs.open(_archiveFile) as manifestDoc:
                        xmlRootElement = etree.fromstring(manifestDoc.read())
                        instances.extend(_parseManifestDoc(xmlRootElement, Path(_archiveFile)))
                except AssertionError as err:
                    _invalidManifestError(cntlr, str(_archiveFile), str(err))
                except Exception as err:
                    _invalidManifestError(cntlr, str(_archiveFile))
                    cntlr.addToLog(_("[Exception] Failed to parse manifest \"{0}\": \n{1} \n{2}").format(
                        str(_archiveFile),
                        err,
                        traceback.format_exc()
                    ))
    elif (dirpath := Path(str(filesource.url))).is_dir():
        for file in dirpath.rglob("*"):
            if not file.is_file():
                continue
            if not file.stem.startswith('manifest'):
                continue
            try:
                with open(file, 'rb') as manifestDoc:
                    xmlRootElement = etree.fromstring(manifestDoc.read())
                    instances.extend(_parseManifestDoc(xmlRootElement, file))
            except AssertionError as err:
                _invalidManifestError(cntlr, str(file), str(err))
            except Exception as err:
                _invalidManifestError(cntlr, str(file))
                cntlr.addToLog(_("[Exception] Failed to parse manifest \"{0}\": \n{1} \n{2}").format(
                    str(file),
                    err,
                    traceback.format_exc()
                ))
    return sorted(instances, key=lambda i: i.id)
