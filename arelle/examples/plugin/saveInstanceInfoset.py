'''
Save Instance Infoset is an example of a plug-in to both GUI menu and command line/web service
that will save facts decorated with ptv:periodType, ptv:balance, ptv:decimals and ptv:precision (inferred).

See COPYRIGHT.md for copyright information.
'''
from arelle.Version import authorLabel, copyrightLabel

def generateInstanceInfoset(dts, instanceInfosetFile):
    if dts.fileSource.isArchive:
        return
    import os, io
    from arelle import XmlUtil, XbrlConst
    from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals

    XmlUtil.setXmlns(dts.modelDocument, "ptv", "http://www.xbrl.org/2003/ptv")

    numFacts = 0

    for fact in dts.facts:
        try:
            if fact.concept.periodType:
                fact.set("{http://www.xbrl.org/2003/ptv}periodType", fact.concept.periodType)
            if fact.concept.balance:
                fact.set("{http://www.xbrl.org/2003/ptv}balance", fact.concept.balance)
            if fact.isNumeric and not fact.isNil:
                fact.set("{http://www.xbrl.org/2003/ptv}decimals", str(inferredDecimals(fact)))
                fact.set("{http://www.xbrl.org/2003/ptv}precision", str(inferredPrecision(fact)))
            numFacts += 1
        except Exception as err:
            dts.error("saveInfoset.exception",
                     _("Facts exception %(fact)s %(value)s %(error)s."),
                     modelObject=fact, fact=fact.qname, value=fact.effectiveValue, error = err)

    fh = open(instanceInfosetFile, "w", encoding="utf-8")
    XmlUtil.writexml(fh, dts.modelDocument.xmlDocument, encoding="utf-8")
    fh.close()

    dts.info("info:saveInstanceInfoset",
             _("Instance infoset of %(entryFile)s has %(numberOfFacts)s facts in infoset file %(infosetOutputFile)s."),
             modelObject=dts,
             entryFile=dts.uri, numberOfFacts=numFacts, infosetOutputFile=instanceInfosetFile)

def saveInstanceInfosetMenuEntender(cntlr, menu):
    # Extend menu with an item for the save infoset plugin
    menu.add_command(label="Save infoset",
                     underline=0,
                     command=lambda: saveInstanceInfosetMenuCommand(cntlr) )

def saveInstanceInfosetMenuCommand(cntlr):
    # save Infoset menu item has been invoked
    from arelle.ModelDocument import Type
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or cntlr.modelManager.modelXbrl.modelDocument.type != Type.INSTANCE:
        cntlr.addToLog("No instance loaded.")
        return

        # get file name into which to save log file while in foreground thread
    instanceInfosetFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save instance infoset file"),
            initialdir=cntlr.config.setdefault("infosetFileDir","."),
            filetypes=[(_("Infoset file .xml"), "*.xml")],
            defaultextension=".xml")
    if not instanceInfosetFile:
        return False
    import os
    cntlr.config["infosetFileDir"] = os.path.dirname(instanceInfosetFile)
    cntlr.saveConfig()

    try:
        generateInstanceInfoset(cntlr.modelManager.modelXbrl, instanceInfosetFile)
    except Exception as ex:
        dts = cntlr.modelManager.modelXbrl
        dts.error("exception",
            _("Instance infoset generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveInstanceInfosetCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--save-instance-infoset",
                      action="store",
                      dest="instanceInfosetFile",
                      help=_("Save instance infoset in specified file, or to send testcase infoset out files to out directory specify 'generateOutFiles'."))

def saveInstanceInfosetCommandLineXbrlLoaded(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    from arelle.ModelDocument import Type
    if getattr(options, "instanceInfosetFile", None) and options.infosetFile == "generateOutFiles" and modelXbrl.modelDocument.type in (Type.TESTCASESINDEX, Type.TESTCASE):
        cntlr.modelManager.generateInfosetOutFiles = True

def saveInstanceInfosetCommandLineXbrlRun(cntlr, options, modelXbrl, *args, **kwargs):
    # extend XBRL-loaded run processing for this option
    if getattr(options, "instanceInfosetFile", None) and options.instanceInfosetFile != "generateOutFiles":
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        generateInstanceInfoset(cntlr.modelManager.modelXbrl, options.instanceInfosetFile)

def validateInstanceInfoset(dts, instanceInfosetFile):
    if getattr(dts.modelManager, 'generateInfosetOutFiles', False):
        generateInstanceInfoset(dts,
                        # normalize file to instance
                        dts.modelManager.cntlr.webCache.normalizeUrl(instanceInfosetFile, dts.uri))


__pluginInfo__ = {
    'name': 'Save Instance Infoset (PTV)',
    'version': '0.9',
    'description': "This plug-in adds a feature to output an instance \"ptv\" infoset.  "
                    "(Does not offset infoset hrefs and schemaLocations for directory offset from DTS.) "
                    "The ptv infoset is the source instance with facts having ptv:periodType, ptv:balance (where applicable), ptv:decimals and ptv:precision (inferred).  ",
    'license': 'Apache-2',
    'author': authorLabel,
    'copyright': copyrightLabel,
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveInstanceInfosetMenuEntender,
    'CntlrCmdLine.Options': saveInstanceInfosetCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': saveInstanceInfosetCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': saveInstanceInfosetCommandLineXbrlRun,
    'Validate.Infoset': validateInstanceInfoset,
}
