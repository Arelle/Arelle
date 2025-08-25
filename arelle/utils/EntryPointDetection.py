"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from arelle import (
    ModelDocument,
    PluginManager, FileSource, PackageManager,
)
from arelle.UrlUtil import isHttpUrl
from arelle.typing import TypeGetText

_: TypeGetText

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr


@dataclass(frozen=True)
class EntrypointParseResult:
    success: bool
    entrypointFiles: list[dict[str, Any]]
    filesource: FileSource | None


def parseEntrypointFileInput(cntlr: Cntlr, entrypointFile: str | None, sourceZipStream=None, fallbackSelect=True) -> EntrypointParseResult:
    # entrypointFile may be absent (if input is a POSTED zip or file name ending in .zip)
    #    or may be a | separated set of file names
    _entryPoints = []
    _checkIfXmlIsEis = cntlr.modelManager.disclosureSystem and cntlr.modelManager.disclosureSystem.validationType == "EFM"
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


def filesourceEntrypointFiles(filesource, entrypointFiles=None, inlineOnly=False, fallbackSelect=True):
    if entrypointFiles is None:
        entrypointFiles = []
    for pluginXbrlMethod in PluginManager.pluginClassMethods("FileSource.EntrypointFiles"):
        resultEntrypointFiles = pluginXbrlMethod(filesource, inlineOnly)
        if resultEntrypointFiles is not None:
            del entrypointFiles[:]  # clear list
            entrypointFiles.extend(resultEntrypointFiles)
            return entrypointFiles
    if filesource.isArchive:
        if filesource.isTaxonomyPackage:  # if archive is also a taxonomy package, activate mappings
            filesource.loadTaxonomyPackageMappings()
        # HF note: a web api request to load a specific file from archive is ignored, is this right?
        del entrypointFiles[:] # clear out archive from entrypointFiles
        if reportPackage := filesource.reportPackage:
            assert isinstance(filesource.basefile, str)
            for report in reportPackage.reports or []:
                if report.isInline:
                    reportEntries = [{"file": f} for f in report.fullPathFiles]
                    ixdsDiscovered = False
                    for pluginXbrlMethod in PluginManager.pluginClassMethods("InlineDocumentSet.Discovery"):
                        pluginXbrlMethod(filesource, reportEntries)
                        ixdsDiscovered = True
                    if not ixdsDiscovered and len(reportEntries) > 1:
                        raise RuntimeError(_("Loading error. Inline document set encountered. Enable 'InlineXbrlDocumentSet' plug-in to load this filing: {0}").format(filesource.url))
                    entrypointFiles.extend(reportEntries)
                elif not inlineOnly:
                    entrypointFiles.append({"file": report.fullPathPrimary})
        elif fallbackSelect:
            # attempt to find inline XBRL files before instance files, .xhtml before probing others (ESMA)
            urlsByType = {}
            for _archiveFile in (filesource.dir or ()): # .dir might be none if IOerror
                filesource.select(_archiveFile)
                identifiedType = ModelDocument.Type.identify(filesource, filesource.url)
                if identifiedType in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL, ModelDocument.Type.HTML):
                    urlsByType.setdefault(identifiedType, []).append(filesource.url)
            # use inline instances, if any, else non-inline instances
            for identifiedType in ((ModelDocument.Type.INLINEXBRL,) if inlineOnly else (ModelDocument.Type.INLINEXBRL, ModelDocument.Type.INSTANCE)):
                for url in urlsByType.get(identifiedType, []):
                    entrypointFiles.append({"file":url})
                if entrypointFiles:
                    if identifiedType == ModelDocument.Type.INLINEXBRL:
                        for pluginXbrlMethod in PluginManager.pluginClassMethods("InlineDocumentSet.Discovery"):
                            pluginXbrlMethod(filesource, entrypointFiles) # group into IXDS if plugin feature is available
                    break # found inline (or non-inline) entrypoint files, don't look for any other type
            # for ESEF non-consolidated xhtml documents accept an xhtml entry point
            if not entrypointFiles and not inlineOnly:
                for url in urlsByType.get(ModelDocument.Type.HTML, []):
                    entrypointFiles.append({"file":url})
            if not entrypointFiles and filesource.taxonomyPackage is not None:
                for packageEntry in filesource.taxonomyPackage.get('entryPoints', {}).values():
                    for _resolvedUrl, remappedUrl, _closest in packageEntry:
                        entrypointFiles.append({"file": remappedUrl})


    elif os.path.isdir(filesource.url):
        del entrypointFiles[:] # clear list
        hasInline = False
        for _file in os.listdir(filesource.url):
            _path = os.path.join(filesource.url, _file)
            if os.path.isfile(_path):
                identifiedType = ModelDocument.Type.identify(filesource, _path)
                if identifiedType == ModelDocument.Type.INLINEXBRL:
                    hasInline = True
                if identifiedType in (ModelDocument.Type.INSTANCE, ModelDocument.Type.INLINEXBRL):
                    entrypointFiles.append({"file":_path})
        if hasInline: # group into IXDS if plugin feature is available
            for pluginXbrlMethod in PluginManager.pluginClassMethods("InlineDocumentSet.Discovery"):
                pluginXbrlMethod(filesource, entrypointFiles)

    return entrypointFiles
