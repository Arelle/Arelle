'''
Save DTS is an example of a plug-in to both GUI menu and command line/web service
that will save the files of a DTS into a zip file.

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''
import os
def package(dts, rootdir=None):
    if dts.fileSource.isArchive:
        return
    import os
    from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED 
    try:
        import zlib
        compression = ZIP_DEFLATED
    except ImportError:
        compression = ZIP_STORED
        dts.info("info:packageDTS",
                 _("Python's zlib module is not available, output is not compressed."),
                 modelObject=dts)
    entryFilename = dts.fileSource.url
    files = sorted(dts.urlDocs.keys())
    if rootdir is None:
        rootdir = commondir(files)
    pkgFilename = entryFilename + ".zip"
    with ZipFile(pkgFilename, 'w', compression) as zipFile:
        numFiles = 0
        for fileUri in files:
            if fileUri.startswith(rootdir):
                numFiles += 1
                f = fileUri[len(rootdir):]
                zipFile.write(fileUri, f)
            elif not (fileUri.startswith('http://') or fileUri.startswith('https://')):
                dts.warning("packageDTS",
                            _("File `%(file)s` was not included in the ZIP because it is not in root directory `%(dir)s`. Use option --root-dir if needed."),
                            file=fileUri, dir=rootdir)
    dts.info("info:packageDTS",
             _("DTS of `%(entryFile)s` has %(numberOfFiles)s files packaged into `%(packageOutputFile)s`"),
             modelObject=dts,
             entryFile=os.path.basename(entryFilename), numberOfFiles=numFiles, packageOutputFile=pkgFilename)

def saveDtsMenuEntender(cntlr, menu):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save DTS in a package",
                     underline=0,
                     command=lambda: saveDtsMenuCommand(cntlr))

def saveDtsMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return
    package(cntlr.modelManager.modelXbrl)

def saveDtsCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--package-dts",
                      action="store_true",
                      dest="packageDTS",
                      help=_("Package the DTS into a zip file"))
    parser.add_option("--root-dir",
                      action="store",
                      dest="rootDir",
                      help=_("Root directory of the entry point. This influences the nested directories in the ZIP. By default it is the base directory of the entry point."))

def saveDtsCommandLineXbrlRun(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    if options.packageDTS:
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        package(cntlr.modelManager.modelXbrl, options.rootDir)

def commondir(paths):
    """
    :param paths: a list of paths
    :returns: The common directory root shared by all paths
    """
    # assert paths is not empty
    from functools import reduce
    list_dir = [d.split(os.sep) for d in paths if not(d.startswith('http://') or d.startswith('https://'))]
    min_len = reduce(min, (len(d) for d in list_dir))
    pivot = list_dir[0]
    for i in range(min_len):
        for d in list_dir:
            if pivot[i] != d[i]:
                return os.sep.join(pivot[:i])
    return os.path.dirname(paths[0])

__pluginInfo__ = {
    'name': 'Save DTS',
    'version': '1.0',
    'description': "This plug-in adds a feature to package the whole DTS into a zip archive. "
                   "Note that remote files are not included in the package. "
                   "Python's zlib module is used for compression (if available).",
    'license': 'Apache-2',
    'author': 'R\u00e9gis D\u00e9camps',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveDtsMenuEntender,
    'CntlrCmdLine.Options': saveDtsCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveDtsCommandLineXbrlRun,
}
