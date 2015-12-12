'''
Save DTS is an example of a plug-in to both GUI menu and command line/web service
that will save the files of a DTS into a zip file.

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

def package(dts):
    if dts.fileSource.isArchive:
        return
    import os
    from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED 
    from arelle.UrlUtil import isHttpUrl
    try:
        import zlib
        compression = ZIP_DEFLATED
    except ImportError:
        compression = ZIP_STORED
        dts.info("info:packageDTS",
                 _("Python's zlib module is not available, output is not compressed."),
                 modelObject=dts)
    entryFilename = dts.fileSource.url
    pkgFilename = entryFilename + ".zip"
    with ZipFile(pkgFilename, 'w', compression) as zipFile:
        numFiles = 0
        for fileUri in sorted(dts.urlDocs.keys()):
            if not isHttpUrl(fileUri):
                numFiles += 1
                # this has to be a relative path because the hrefs will break
                zipFile.write(fileUri, os.path.basename(fileUri))
    dts.info("info:packageDTS",
             _("DTS of %(entryFile)s has %(numberOfFiles)s files packaged into %(packageOutputFile)s."),
             modelObject=dts,
             entryFile=entryFilename, numberOfFiles=numFiles, packageOutputFile=pkgFilename)

def saveDtsMenuEntender(cntlr, menu, *args, **kwargs):
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Save DTS in a package", 
                     underline=0, 
                     command=lambda: saveDtsMenuCommand(cntlr) )

def saveDtsMenuCommand(cntlr):
    # save DTS menu item has been invoked
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
        cntlr.addToLog("No taxonomy loaded.")
        return
    package(cntlr.modelManager.modelXbrl)

def saveDtsCommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options with a save DTS option
    parser.add_option("--package-dts", 
                      action="store_true", 
                      dest="packageDTS", 
                      help=_("Package the DTS into a zip file"))

def saveDtsCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "packageDTS", False):
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        package(cntlr.modelManager.modelXbrl)


__pluginInfo__ = {
    'name': 'Save DTS',
    'version': '0.9',
    'description': "This plug-in adds a feature to package the whole DTS into a zip archive. "
                   "Note that remote files are not included in the package. "
                   "Python's zlib module is used for compression (if avaliable).",
    'license': 'Apache-2',
    'author': 'R\u00e9gis D\u00e9camps',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveDtsMenuEntender,
    'CntlrCmdLine.Options': saveDtsCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Run': saveDtsCommandLineXbrlRun,
}
