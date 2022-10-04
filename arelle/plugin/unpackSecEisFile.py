'''
Unpack SEC EIS File is an example of a plug-in to the GUI menu
that will save the unpacked contents of an SEC EIS File in a directory.

See COPYRIGHT.md for copyright information.
'''
from arelle.Version import authorLabel, copyrightLabel

def unpackEIS(cntlr, eisFile, unpackToDir):
    from arelle.FileSource import openFileSource
    filesource = openFileSource(eisFile, cntlr, checkIfXmlIsEis=True)
    if not filesource.isArchive:
        cntlr.addToLog("[info:unpackEIS] Not recognized as an EIS file: " + eisFile)
        return
    import os, io

    unpackedFiles = []

    for file in filesource.dir:
        fIn, encoding = filesource.file(os.path.join(eisFile,file))
        with open(os.path.join(unpackToDir, file), "w", encoding=encoding) as fOut:
            fOut.write(fIn.read())
            unpackedFiles.append(file)
        fIn.close()

    cntlr.addToLog("[info:unpackEIS] Unpacked files " + ', '.join(unpackedFiles))

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
            cntlr.addToLog("[arelle:exception] Unpack EIS exception: " + str(ex));
    menu.add_command(label="Unpack SEC EIS File",
                     underline=0,
                     command=lambda: askUnpackDirectory() )

__pluginInfo__ = {
    'name': 'Unpack SEC EIS File',
    'version': '0.9',
    'description': "This plug-in unpacks the contents of an SEC EIS file.",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': unpackSecEisMenuEntender,
}
