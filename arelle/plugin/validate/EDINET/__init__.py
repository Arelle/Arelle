"""
See COPYRIGHT.md for copyright information.
- [Operation Guides](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WEEK0060.html)
- [Document Search](https://disclosure2.edinet-fsa.go.jp/week0020.aspx)
"""
from __future__ import annotations

from collections import defaultdict
from io import IOBase
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipExtFile

from lxml import etree
from lxml.etree import _Element

from arelle.ModelDocument import LoadingException, ModelDocument, load
from arelle.Version import authorLabel, copyrightLabel
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import upload

PLUGIN_NAME = "Validate EDINET"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "EDINET"


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[
        upload,
    ],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def _parseManifestDoc(xmlRootElement: _Element, base: Path) -> dict[str, list[str]]:
    sets = defaultdict(list)
    for instanceElt in xmlRootElement.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}instance"):
        instanceId = instanceElt.attrib["id"]
        for ixbrlElt in instanceElt.iter(tag="{http://disclosure.edinet-fsa.go.jp/2013/manifest}ixbrl"):
            uri = ixbrlElt.text.strip()
            if uri:
                sets[instanceId].append(base / uri)
    return sets


def fileSourceEntrypointFiles(filesource, inlineOnly, *args, **kwargs):
    manifests = {}
    if filesource.isArchive:
        if filesource.isTaxonomyPackage:
            return None
        if filesource.reportPackage is not None:
            return None
        for _archiveFile in (filesource.dir or ()):
            if not Path(_archiveFile).stem.startswith('manifest'):
                continue
            with filesource.fs.open(_archiveFile) as manifestDoc:
                base = Path(_archiveFile).parent
                xmlRootElement = etree.fromstring(manifestDoc.read())
                manifests.update(_parseManifestDoc(xmlRootElement, base))
    elif (dirpath := Path(filesource.url)).is_dir():
        for file in dirpath.rglob("*"):
            if not file.is_file():
                continue
            if not file.stem.startswith('manifest'):
                continue
            with open(file, 'rb') as manifestDoc:
                base = file.parent
                xmlRootElement = etree.fromstring(manifestDoc.read())
                manifests.update(_parseManifestDoc(xmlRootElement, base))
    if len(manifests) == 0:
        return None

    entrypointFiles = []
    for instanceId, uris in manifests.items():
        entrypoints = []
        for uri in uris:
            filesource.select(str(uri))
            entrypoints.append({"file": filesource.url})
        entrypointFiles.append({'ixds': entrypoints})
    return entrypointFiles


def modelXbrlLoadComplete(*args: Any, **kwargs: Any) -> ModelDocument | LoadingException | None:
    return validationPlugin.modelXbrlLoadComplete(*args, **kwargs)


def validateFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateFinally(*args, **kwargs)


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Validation plugin for the EDINET taxonomies.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "import": ("inlineXbrlDocumentSet",),
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "FileSource.EntrypointFiles": fileSourceEntrypointFiles,
    "ModelXbrl.LoadComplete": modelXbrlLoadComplete,
    "Validate.XBRL.Finally": validateXbrlFinally,
    "ValidateFormula.Finished": validateFinally,
}
