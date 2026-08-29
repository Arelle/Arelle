'''
See COPYRIGHT.md for copyright information.

Opening a loaded XBRL Model in the ixbrl-viewer, as the last step of the desktop workflow:
load -> validate -> Tk views -> view the report against its source document.

The viewer has two load paths and this uses the second one. Its own GUI launch
(``iXBRLViewerPlugin.guiRun``) builds a viewer *document* from a legacy inline ModelXbrl and
refuses anything whose modelDocument type is not INLINEXBRL. A compiled model is not that,
and does not need it: the viewer's XbrlModel overlay takes a *plain* document plus an OIM
model, given as ``?xbrlModel=<model>`` on the viewer URL, and resolves the document from the
model's own ``documentInfo.sourceMappings``. So the work here is staging -- put the model, the
document and the viewer bundle in one directory, serve it, and open it.

Where that directory goes follows Arelle's existing convention (EDGAR/render/__init__.py
``setProcessingFolder`` + the reportsFolder resolution): a subdirectory of the directory
holding the entry file, or -- when the entry file is inside a zip, report package or taxonomy
package -- a sibling of the archive, because FileSource.basefile is the archive's own path.
A read-only location falls back to the web cache directory for that URL, and then to a temp
directory.
'''
import os, shutil, tempfile, webbrowser

from arelle import PluginManager

from .SaveModel import saveFiles

# Subdirectory name for the staged viewer. "out" is what Arelle's EDGAR renderer uses for its
# GUI viewer output (reportsFolder="out" if showViewer); the CLI default there is "Reports".
DEFAULT_VIEWER_FOLDER = "out"

# Config keys (cntlr.config), so the desktop behaviour is settable without a rebuild.
CONFIG_LAUNCH_ON_LOAD = "xbrlModelViewerLaunchOnLoad"
CONFIG_VIEWER_FOLDER = "xbrlModelViewerFolder"

STUB_NAME = "ixbrlviewer.html"
MODEL_SUFFIX = "-model.json"

_STUB_HTML = '''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><meta charset="UTF-8"/><title>XBRL Model Viewer</title></head>
  <body><script src="{script}"></script></body>
</html>
'''


# Config key for an explicit bundle location, for a viewer checkout Arelle does not load as a
# plugin (a developer build, or a bundle shipped on its own).
CONFIG_BUNDLE_DIR = "xbrlModelViewerBundleDir"

# Path of the built bundle within an iXBRLViewerPlugin checkout or installation.
_BUNDLE_SUBPATH = ("viewer", "dist")
_BUNDLE_SCRIPT = "ixbrlviewer.js"


def _bundleDirIfBuilt(pluginDir):
    """pluginDir/viewer/dist if it holds a built ixbrlviewer.js, else None."""
    if not pluginDir:
        return None
    bundleDir = os.path.join(pluginDir, *_BUNDLE_SUBPATH)
    return bundleDir if os.path.isfile(os.path.join(bundleDir, _BUNDLE_SCRIPT)) else None


def viewerBundleDir(cntlr=None):
    """Directory holding the built ixbrlviewer.js and its webpack chunks, or None.

    Looked for in three places, and nothing is imported to make it appear -- without a built
    viewer bundle there is no viewer to launch, and that is reported rather than worked around:

      1. the CONFIG_BUNDLE_DIR setting, which may name either the plugin directory or the
         dist directory itself;
      2. the loaded iXBRLViewerPlugin module (Arelle loads it under that top-level name);
      3. the plugin configuration, whose moduleURL locates the checkout even when the plugin
         itself failed to load -- its GUI launch imports bottle, which the XBRL Model viewer
         path does not need until it actually serves.
    """
    import sys
    configured = (cntlr.config.get(CONFIG_BUNDLE_DIR) if getattr(cntlr, "config", None) else None)
    if configured:
        if os.path.isfile(os.path.join(configured, _BUNDLE_SCRIPT)):
            return configured
        found = _bundleDirIfBuilt(configured)
        if found:
            return found
    module = sys.modules.get("iXBRLViewerPlugin")
    if module is not None and getattr(module, "__file__", None):
        found = _bundleDirIfBuilt(os.path.dirname(module.__file__))
        if found:
            return found
    try:
        for moduleInfo in (PluginManager.pluginConfig.get("modules") or {}).values():
            moduleUrl = moduleInfo.get("moduleURL") or ""
            if "iXBRLViewer" in moduleUrl or "ixbrl-viewer" in moduleUrl:
                found = _bundleDirIfBuilt(moduleUrl if os.path.isdir(moduleUrl)
                                          else os.path.dirname(moduleUrl))
                if found:
                    return found
    except (AttributeError, KeyError):
        pass
    return None


def viewerOutputFolder(cntlr, modelXbrl, folderName=DEFAULT_VIEWER_FOLDER):
    """The directory to stage the viewer into, by Arelle's existing convention (see header)."""
    fileSource = getattr(modelXbrl, "fileSource", None)
    base = None
    if fileSource is not None and getattr(fileSource, "isOpen", False):
        # basefile is the ARCHIVE's own path for a zip / report package, so its dirname puts
        # the staged folder beside the archive rather than trying to write inside it.
        base = os.path.dirname(getattr(fileSource, "basefile", None) or "")
    if not base:
        url = getattr(fileSource, "url", None) or getattr(modelXbrl, "uri", None) or ""
        for separatorMethod in PluginManager.pluginClassMethods("InlineDocumentSet.Url.Separator"):
            url = url.partition(separatorMethod())[0]  # trim an inline document set suffix
        base = os.path.dirname(url)
    for candidate in (base, _cacheDirFor(cntlr, base)):
        if candidate and os.path.isdir(candidate) and os.access(candidate, os.W_OK | os.X_OK):
            folder = os.path.join(candidate, folderName)
            os.makedirs(folder, exist_ok=True)
            return folder
    return tempfile.mkdtemp(prefix="XbrlModelViewer_")


def _cacheDirFor(cntlr, url):
    """The web cache directory holding url, for an entry point loaded from the web (or from a
       read-only location), or None."""
    if not url:
        return None
    try:
        return cntlr.webCache.urlToCacheFilepath(url)
    except Exception:
        return None


def sourceDocumentUrls(compMdl):
    """{sourceName: [url, ...]} of the source documents the model's facts are located in.

    Taken from each module's parsed _sourceMappings. A report entry point binds its
    sourceMapping to the ARCHIVE when it was loaded from one, so that the report package's
    catalog remappings apply and the whole document set is discovered -- an archive is not a
    document, so the recorded entry URL replaces it, expanded to the documents it names.
    """
    from .FactPipeline import reportDocumentUrls
    urls = {}
    for module in compMdl.xbrlModels.values():
        for sm in getattr(module, "_sourceMappings", None) or ():
            sourceName = str(sm.sourceName) if getattr(sm, "sourceName", None) is not None else None
            url = getattr(sm, "url", None)
            if not url:
                continue
            urls[sourceName] = reportDocumentUrls(compMdl, url)
    return urls


def hasViewableSource(compMdl):
    """Whether this model has something for the viewer to render facts against.

    Two conditions, both necessary: a sourceMapping naming a document, and at least one fact
    value located in it. A model with neither is a taxonomy, not a report, and opening a viewer
    on it would show an empty document with no way to tell why.
    """
    if not sourceDocumentUrls(compMdl):
        return False
    for module in compMdl.xbrlModels.values():
        for fact in getattr(module, "facts", None) or ():
            for factValue in getattr(fact, "factValues", None) or ():
                if getattr(factValue, "valueSources", None) or getattr(factValue, "valueAnchors", None):
                    return True
    return False


def stageDocument(cntlr, url, folder):
    """Copy one source document into folder and return its basename, or None.

    Read through Arelle's FileSource / WebCache rather than the filesystem: the URL may name a
    member of an archive, or a document that only exists in the web cache.
    """
    from arelle import FileSource
    basename = os.path.basename(url.split("?", 1)[0].split("#", 1)[0])
    if not basename:
        return None
    destination = os.path.join(folder, basename)
    try:
        fileSource = FileSource.openFileSource(url, cntlr)
        try:
            with fileSource.file(url, binary=True)[0] as fh:
                data = fh.read()
        finally:
            fileSource.close()
    except Exception:
        try:
            filepath = cntlr.webCache.getfilename(url)
            if not filepath or not os.path.isfile(filepath):
                return None
            with open(filepath, "rb") as fh:
                data = fh.read()
        except Exception:
            return None
    if os.path.abspath(destination) != os.path.abspath(url):
        with open(destination, "wb") as fh:
            fh.write(data)
    return basename


def stageViewerBundle(folder, bundleDir):
    """Copy the viewer bundle into folder and return the script's filename.

    The build is code-split, so the lazily loaded chunks (``<id>.ixbrlviewer.js``) must travel
    with the entry script; copying only ixbrlviewer.js gives a viewer that loads and then
    fails to open a document, with the cause visible only in the browser console.
    """
    scriptName = "ixbrlviewer.js"
    for name in os.listdir(bundleDir):
        if name.endswith(".js") or name.endswith(".js.LICENSE.txt"):
            shutil.copy2(os.path.join(bundleDir, name), os.path.join(folder, name))
    return scriptName


def stageForViewer(cntlr, compMdl, folder, saveMode="full"):
    """Write model, document(s) and viewer bundle into folder. Returns the viewer URL path
       (stub + query), or None with the reason already reported."""
    bundleDir = viewerBundleDir(cntlr)
    if bundleDir is None:
        cntlr.addToLog(_("The XBRL Model viewer needs the iXBRL Viewer plugin and its built "
                         "bundle (viewer/dist/ixbrlviewer.js). Activate the plugin, or run "
                         "'npm run font && npm run prod' in the ixbrl-viewer repository."),
                       messageCode="arelle:xbrlModelViewerUnavailable", level="ERROR")
        return None
    documentUrls = sourceDocumentUrls(compMdl)
    stagedNames = {}
    for sourceName, urls in documentUrls.items():
        # Every document of the set is staged so that a link between them resolves in the
        # served directory; the sourceName binds to the first, which is the one the viewer
        # opens. (The loader records one sourceMapping per report today -- per-document
        # sourceMappings for a multi-document IXDS are still a TODO in LoadInlineFacts.)
        for url in urls:
            basename = stageDocument(cntlr, url, folder)
            if basename is not None and sourceName not in stagedNames:
                stagedNames[sourceName] = basename
    if not stagedNames:
        cntlr.addToLog(_("The model names no source document that could be staged, so there is "
                         "nothing for the viewer to render the facts against."),
                       messageCode="arelle:xbrlModelViewerNoDocument", level="ERROR")
        return None
    # The model is written with sourceMappings naming the staged copies, so the viewer resolves
    # the document from the model itself and the staged directory is self-contained.
    modelName = os.path.splitext(next(iter(stagedNames.values())))[0] + MODEL_SUFFIX
    saveFiles(cntlr, compMdl, os.path.join(folder, modelName), saveMode=saveMode,
              sourceUrlRewrite=lambda sourceName, url: stagedNames.get(sourceName))
    scriptName = stageViewerBundle(folder, bundleDir)
    with open(os.path.join(folder, STUB_NAME), "w", encoding="utf-8") as fh:
        fh.write(_STUB_HTML.format(script=scriptName))
    return "{}?xbrlModel={}".format(STUB_NAME, modelName)


class XbrlModelLocalViewer:
    """Serves the staged folder. Deliberately a thin subclass built at call time so that
       arelle.LocalViewer (and bottle) are imported only when a viewer is actually launched."""

    @staticmethod
    def build(folder):
        from arelle.LocalViewer import LocalViewer
        from bottle import static_file

        class _Viewer(LocalViewer):
            def getLocalFile(self, file, relpath, request):
                if file is None:
                    return None
                report, _, name = file.partition("/")
                root = self.reportsFolders[int(report)] if report.isnumeric() else self.reportsFolders[0]
                if not report.isnumeric():
                    name = file
                return static_file(name, root=root, headers=self.noCacheHeaders)

        return _Viewer("XBRL Model Viewer", folder)


def launchViewer(cntlr, compMdl, saveMode="full"):
    """Stage and open the loaded model in the ixbrl-viewer. Returns the opened URL, or None."""
    folder = viewerOutputFolder(cntlr, compMdl,
                                cntlr.config.get(CONFIG_VIEWER_FOLDER, DEFAULT_VIEWER_FOLDER)
                                if getattr(cntlr, "config", None) else DEFAULT_VIEWER_FOLDER)
    viewerPath = stageForViewer(cntlr, compMdl, folder, saveMode=saveMode)
    if viewerPath is None:
        return None
    localhost = XbrlModelLocalViewer.build(folder).init(cntlr, folder)
    if not localhost:
        return None
    url = "{}/{}".format(localhost, viewerPath)
    cntlr.addToLog(_("Opening the XBRL Model viewer: %(url)s"),
                   messageArgs={"url": url}, messageCode="arelle:xbrlModelViewerOpened")
    webbrowser.open(url)
    return url
