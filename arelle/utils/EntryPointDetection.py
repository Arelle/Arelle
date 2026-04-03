"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING, BinaryIO, cast

from arelle import (
    FileSource, PackageManager,
)
from arelle.FileSource import FileNamedBytesIO
from arelle.ModelDocumentType import ModelDocumentType
from arelle.UrlUtil import isHttpUrl
from arelle.typing import TypeGetText

_: TypeGetText

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr


@dataclass(frozen=True)
class EntrypointParseResult:
    success: bool
    entrypointFiles: list[dict[str, Any]]
    filesource: FileSource.FileSource | None


def parseEntrypointFileInput(cntlr: Cntlr, entrypointFile: str | None, sourceZipStream: BinaryIO | FileNamedBytesIO | None = None, fallbackSelect: bool = True) -> EntrypointParseResult:
    # entrypointFile may be absent (if input is a POSTED zip or file name ending in .zip)
    #    or may be a | separated set of file names
    _entryPoints = []
    _checkIfXmlIsEis = cast(bool, cntlr.modelManager.disclosureSystem and cntlr.modelManager.disclosureSystem.validationType == "EFM")
    if entrypointFile:
        _f = entrypointFile
        try: # may be a json list
            _entryPoints = json.loads(_f)
            _checkIfXmlIsEis = False # json entry objects never specify an xml EIS archive
        except ValueError as e:
            # is it malformed json?
            if _f.startswith("[{") or _f.endswith("]}") or '"file:"' in _f:
                cntlr.addToLog(_("File name parameter appears to be malformed JSON: {}\n{}").format(e, _f),
                              messageCode="FileNameFormatError",
                              level=logging.ERROR)
            else: # try as file names separated by '|'
                for f in (_f or '').split('|'):
                    if not sourceZipStream and not isHttpUrl(f) and not os.path.isabs(f):
                        f = os.path.normpath(os.path.join(os.getcwd(), f)) # make absolute normed path
                    _entryPoints.append({"file":f})
    filesource = None # file source for all instances if not None
    if sourceZipStream:
        filesource = FileSource.openFileSource(None, cntlr, sourceZipStream)
    elif len(_entryPoints) == 1 and "file" in _entryPoints[0]: # check if an archive and need to discover entry points (and not IXDS)
        entryPath = PackageManager.mappedUrl(_entryPoints[0]["file"])
        filesource = FileSource.openFileSource(entryPath, cntlr, checkIfXmlIsEis=_checkIfXmlIsEis)
    _entrypointFiles = _entryPoints
    if filesource and not filesource.selection and not (sourceZipStream and len(_entrypointFiles) > 0):
        try:
            filesourceEntrypointFiles(filesource, _entrypointFiles, fallbackSelect=fallbackSelect)
        except Exception as err:
            cntlr.addToLog(str(err), messageCode="error", level=logging.ERROR)
            return EntrypointParseResult(success=False, entrypointFiles=_entrypointFiles, filesource=filesource)
    return EntrypointParseResult(success=True, entrypointFiles=_entrypointFiles, filesource=filesource)


def filesourceEntrypointFiles(filesource: FileSource.FileSource, entrypointFiles: list[dict[str, Any]] | None = None, inlineOnly: bool = False, fallbackSelect: bool = True) -> list[dict[str, str]]:
    if entrypointFiles is None:
        entrypointFiles = []
    for pluginXbrlMethod in filesource.hooks("FileSource.EntrypointFiles"):
        resultEntrypointFiles = pluginXbrlMethod(filesource, inlineOnly)
        if resultEntrypointFiles is not None:
            del entrypointFiles[:]  # clear list
            entrypointFiles.extend(resultEntrypointFiles)
            return entrypointFiles
    if filesource.isArchive:
        if filesource.isTaxonomyPackage:  # if archive is also a taxonomy package, activate mappings
            filesource.loadTaxonomyPackageMappings()
        # HF note: a web api request to load a specific file from archive is ignored, is this right?
        del entrypointFiles[:]
        if reportPackage := filesource.reportPackage:
            assert isinstance(filesource.basefile, str)
            for report in reportPackage.reports or []:
                if report.isInline:
                    reportEntries = [{"file": f} for f in report.fullPathFiles]
                    ixdsDiscovered = False
                    for pluginXbrlMethod in filesource.hooks("InlineDocumentSet.Discovery"):
                        pluginXbrlMethod(filesource, reportEntries)
                        ixdsDiscovered = True
                    if not ixdsDiscovered and len(reportEntries) > 1:
                        raise RuntimeError(_("Loading error. Inline document set encountered. Enable 'InlineXbrlDocumentSet' plug-in to load this filing: {0}").format(filesource.url))
                    entrypointFiles.extend(reportEntries)
                elif not inlineOnly:
                    entrypointFiles.append({"file": report.fullPathPrimary})
        elif fallbackSelect:
            # attempt to find inline XBRL files before instance files, .xhtml before probing others (ESMA)
            urlsByType: dict[int, list[str]] = {}
            for _archiveFile in (filesource.dir or ()): # .dir might be none if IOerror
                filesource.select(_archiveFile)
                identifiedType = ModelDocumentType.identify(filesource, cast(str, filesource.url))
                if identifiedType in (ModelDocumentType.INSTANCE, ModelDocumentType.INLINEXBRL, ModelDocumentType.HTML):
                    urlsByType.setdefault(identifiedType, []).append(cast(str, filesource.url))
            # use inline instances, if any, else non-inline instances
            for identifiedType in ((ModelDocumentType.INLINEXBRL,) if inlineOnly else (ModelDocumentType.INLINEXBRL, ModelDocumentType.INSTANCE)):
                for url in urlsByType.get(identifiedType, []):
                    entrypointFiles.append({"file":url})
                if entrypointFiles:
                    if identifiedType == ModelDocumentType.INLINEXBRL:
                        for pluginXbrlMethod in filesource.hooks("InlineDocumentSet.Discovery"):
                            pluginXbrlMethod(filesource, entrypointFiles) # group into IXDS if plugin feature is available
                    break # found inline (or non-inline) entrypoint files, don't look for any other type
            # for ESEF non-consolidated xhtml documents accept an xhtml entry point
            if not entrypointFiles and not inlineOnly:
                for url in urlsByType.get(ModelDocumentType.HTML, []):
                    entrypointFiles.append({"file":url})
            if not entrypointFiles and filesource.taxonomyPackage is not None:
                # Looks like the type of values in the taxonomyPackage dict depends on the key
                entryPoints = cast(
                    dict[str, list[tuple[str | None, str, str]]],
                    filesource.taxonomyPackage.get('entryPoints', {})
                )
                for packageEntry in entryPoints.values():
                    for _resolvedUrl, remappedUrl, _closest in packageEntry:
                        entrypointFiles.append({"file": remappedUrl})


    elif os.path.isdir(cast(str, filesource.url)):
        del entrypointFiles[:] # clear list
        hasInline = False
        for _file in os.listdir(cast(str, filesource.url)):
            _path = os.path.join(cast(str, filesource.url), _file)
            if os.path.isfile(_path):
                identifiedType = ModelDocumentType.identify(filesource, _path)
                if identifiedType == ModelDocumentType.INLINEXBRL:
                    hasInline = True
                if identifiedType in (ModelDocumentType.INSTANCE, ModelDocumentType.INLINEXBRL):
                    entrypointFiles.append({"file":_path})
        if hasInline: # group into IXDS if plugin feature is available
            for pluginXbrlMethod in filesource.hooks("InlineDocumentSet.Discovery"):
                pluginXbrlMethod(filesource, entrypointFiles)

    return entrypointFiles
