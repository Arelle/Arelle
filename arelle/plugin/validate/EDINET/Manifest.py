"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lxml import etree
from lxml.etree import _Element

from arelle import XbrlConst
from arelle.FileSource import FileSource
from arelle.ModelValue import QName, qname
from . import Constants


@dataclass(frozen=True)
class Manifest:
    instances: list[ManifestInstance]
    path: Path
    titlesByLang: dict[str, str]
    tocItems: list[ManifestTocItem]


@dataclass(frozen=True)
class ManifestTocItem:
    extrole: str
    childItems: list[ManifestTocItem]
    itemIn: str
    parent: QName | None
    ref: str
    start: QName | None


@dataclass(frozen=True)
class ManifestInstance:
    id: str
    ixbrlFiles: list[Path]
    preferredFilename: str
    type: str


def _parseManifestTocItems(parentElt: _Element, parentQName: QName | None) -> list[ManifestTocItem]:
    tocItems = []
    for itemElt in parentElt.iterchildren(tag=Constants.qnEdinetManifestItem.clarkNotation):
        childTocItems = []
        for insertElt in itemElt.iterchildren(tag=Constants.qnEdinetManifestInsert.clarkNotation):
            childParentQName = qname(insertElt.attrib.get("parent"), insertElt.nsmap) if insertElt.attrib.get("parent") else None
            childTocItems.extend(_parseManifestTocItems(insertElt, childParentQName))
        tocItems.append(ManifestTocItem(
            extrole=itemElt.attrib.get("extrole", ""),
            childItems=childTocItems,
            parent=parentQName,
            itemIn=itemElt.attrib.get("in", ""),
            ref=itemElt.attrib.get("ref", ""),
            start=qname(itemElt.attrib.get("start"), itemElt.nsmap) if itemElt.attrib.get("start") else None,
        ))
    return tocItems


def _parseManifestDoc(xmlRootElement: _Element, path: Path) -> Manifest:
    instances = []
    titlesByLang = {}
    base = path.parent
    tocElts = list(xmlRootElement.iterchildren(tag=Constants.qnEdinetManifestTocComposition.clarkNotation))
    assert len(tocElts) == 1, 'There should be exactly one tocComposition element in the manifest.'
    for titleElt in tocElts[0].iterchildren(tag=Constants.qnEdinetManifestTitle.clarkNotation):
        lang = titleElt.attrib.get(XbrlConst.qnXmlLang.clarkNotation, "")
        titlesByLang[lang] = titleElt.text.strip() if titleElt.text else ""
    tocItems = _parseManifestTocItems(tocElts[0], None)
    listElts = list(xmlRootElement.iterchildren(tag=Constants.qnEdinetManifestList.clarkNotation))
    assert len(listElts) == 1, 'There should be exactly one list element in the manifest.'
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
            preferredFilename=preferredFilename,
            type=instanceType,
        ))
    return Manifest(
        instances=instances,
        path=path,
        titlesByLang=titlesByLang,
        tocItems=tocItems,
    )


@lru_cache(1)
def parseManifests(filesource: FileSource) -> list[Manifest]:
    manifests: list[Manifest] = []
    if filesource.isArchive:
        if filesource.isTaxonomyPackage:
            return manifests
        if filesource.reportPackage is not None:
            return manifests
        for _archiveFile in (filesource.dir or ()):
            if not Path(_archiveFile).stem.startswith('manifest'):
                continue
            assert isinstance(filesource.fs, zipfile.ZipFile), \
                "The EDINET plugin only supports archives in .zip format."
            with filesource.fs.open(_archiveFile) as manifestDoc:
                xmlRootElement = etree.fromstring(manifestDoc.read())
                manifests.append(_parseManifestDoc(xmlRootElement, Path(_archiveFile)))
    elif (dirpath := Path(str(filesource.url))).is_dir():
        for file in dirpath.rglob("*"):
            if not file.is_file():
                continue
            if not file.stem.startswith('manifest'):
                continue
            with open(file, 'rb') as manifestDoc:
                xmlRootElement = etree.fromstring(manifestDoc.read())
                manifests.append(_parseManifestDoc(xmlRootElement, file))
    return manifests
