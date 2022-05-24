'''
Unpack SEC EIS File can be used from GUI, Command Line or Web Service
to save the unpacked files within an SEC EDGAR EIS Submission into a directory.
The submission archive has an .eis extension or an .xml extension.

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.

Unpacks an SEC EIS file into specified directory.

To run from GUI:
    tools->Unpack SEC EIS File

To run from command line, loading formula linkbase and saving formula syntax files:

  python3.x arelleCmdLine.py 
    --plugins unpackSecEisFile
    --sec-eis-file {sourceEisFilePath}
    --unpack-sec-eis-file-dir {directoryIntoWhichToSaveUnpackedFiles}
'''
import os, logging

def unpackEIS(cntlr, eisFile, unpackToDir):
    from arelle.FileSource import openFileSource
    filesource = openFileSource(eisFile, cntlr, checkIfXmlIsEis=True)
    if not filesource.isArchive:
        cntlr.addToLog("Not recognized as an EIS file: " + eisFile, messageCode="arelle:unpackEisFileError", level=logging.ERROR)
        return
    import os, io
    
    unpackedFiles = []
    
    for file in filesource.dir:
        fIn, encoding = filesource.file(os.path.join(eisFile,file))
        with open(os.path.join(unpackToDir, file), "w", encoding=encoding) as fOut:
            fOut.write(fIn.read())
            unpackedFiles.append(file)
        fIn.close()
                
    cntlr.addToLog("Unpacked files " + ', '.join(unpackedFiles), messageCode="arelle:unpackEis", level=logging.INFO)

def unpackSecEisMenuEntender(cntlr, menu, *args, **kwargs):
    def askUnpackDirectory():
        eisFile = cntlr.uiFileDialog("open",
                                     title=_("arelle - Open SEC EIS file"),
                                     initialdir=cntlr.config.setdefault("openSecEisFileDir","."),
                                     filetypes=[(_("Compressed EIS file .eis"), "*.eis"), (_("Uncompressed EIS file .xml"), "*.xml")],
                                     defaultextension=".eis")
        if not eisFile:
            return
        from tkinter.filedialog import askdirectory
        unpackToDir = askdirectory(parent=cntlr.parent,
                                   initialdir=cntlr.config.setdefault("unpackSecEisFileDir","."),
                                   title='Please select a directory for unpacked EIS Contents')
        import os
        cntlr.config["openSecEisFileDir"] = os.path.dirname(eisFile)
        cntlr.config["unpackSecEisFileDir"] = unpackToDir
        cntlr.saveConfig()
        try: 
            unpackEIS(cntlr, eisFile, unpackToDir)
        except Exception as ex:
            cntlr.addToLog("Unpack EIS exception: " + str(ex), messageCode="arelle:unpackEisException", level=logging.ERROR);
    menu.add_command(label="Unpack SEC EIS File", 
                     underline=0, 
                     command=lambda: askUnpackDirectory() )

def unpackSecEisCommandLineOptionExtender(parser, *args, **kwargs):
    parser.add_option("--sec-eis-file", 
                      action="store", 
                      dest="secEisFile", 
                      help=_("SEC EIS file to be unpacked."))
    parser.add_option("--unpack-sec-eis-file-dir", 
                      action="store", 
                      dest="unpackSecEisFileDir", 
                      help=_("Save unpacked files into specified directory."))

def unpackSecEisCommandLineUtilityRun(cntlr, options, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "secEisFile", False)  and getattr(options, "unpackSecEisFileDir", False):
        try:
            os.makedirs(options.unpackSecEisFileDir, exist_ok=True) # ensure out dir exists
            unpackEIS(cntlr, options.secEisFile, options.unpackSecEisFileDir)
        except Exception as ex:
            cntlr.addToLog("Unpack EIS exception: " + str(ex), messageCode="arelle:unpackEisException", level=logging.ERROR);


__pluginInfo__ = {
    'name': 'Unpack SEC EIS File',
    'version': '0.9',
    'description': "This plug-in unpacks the contents of an SEC EIS file.",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': unpackSecEisMenuEntender,
    'CntlrCmdLine.Options': unpackSecEisCommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': unpackSecEisCommandLineUtilityRun,
}
