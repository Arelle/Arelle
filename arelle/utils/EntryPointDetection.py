import os

from arelle import (
    ModelDocument,
    PluginManager,
)


def filesourceEntrypointFiles(filesource, entrypointFiles=None, inlineOnly=False):
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
        else:
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
