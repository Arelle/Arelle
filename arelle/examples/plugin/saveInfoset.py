'''
Save SKOS is an example of a plug-in to both GUI menu and command line/web service
that will save the concepts a DTS into an RDF file.

(c) Copyright 2012 Mark V Systems Limited, All rights reserved.
'''

def generateInfoset(dts, infosetFile):
    if dts.fileSource.isArchive:
        return
    import os, io
    from arelle import XmlUtil, XbrlConst
    from arelle.ValidateXbrlCalcs import inferredPrecision, inferredDecimals            
    
    XmlUtil.setXmlns(dts.modelDocument, "ptv", "http://www.xbrl.org/2003/ptv")
    
    numFacts = 0
    
    for fact in dts.facts:
        if fact.concept.periodType:
            fact.set("{http://www.xbrl.org/2003/ptv}periodType", fact.concept.periodType)
        if fact.concept.balance:
            fact.set("{http://www.xbrl.org/2003/ptv}balance", fact.concept.balance)
        if fact.isNumeric:
            fact.set("{http://www.xbrl.org/2003/ptv}decimals", str(inferredDecimals(fact)))
            fact.set("{http://www.xbrl.org/2003/ptv}precision", str(inferredPrecision(fact)))
        numFacts += 1

    fh = open(infosetFile, "w", encoding="utf-8")
    XmlUtil.writexml(fh, dts.modelDocument.xmlDocument, encoding="utf-8")
    fh.close()
    
    dts.info("info:saveInfoset",
             _("Infoset of %(entryFile)s has %(numberOfFacts)s facts in infoset file %(infosetOutputFile)s."),
             modelObject=dts,
             entryFile=dts.uri, numberOfFacts=numFacts, infosetOutputFile=infosetFile)

def saveInfosetMenuEntender(cntlr, menu):
    # Extend menu with an item for the save infoset plugin
    menu.add_command(label="Save infoset", 
                     underline=0, 
                     command=lambda: saveInfosetMenuCommand(cntlr) )

def saveInfosetMenuCommand(cntlr):
    # save Infoset menu item has been invoked
    from arelle.ModelDocument import Type
    if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None or cntlr.modelManager.modelXbrl.modelDocument.type != Type.INSTANCE:
        cntlr.addToLog("No instance loaded.")
        return

        # get file name into which to save log file while in foreground thread
    infosetFile = cntlr.uiFileDialog("save",
            title=_("arelle - Save infoset file"),
            initialdir=cntlr.config.setdefault("infosetFileDir","."),
            filetypes=[(_("Infoset file .xml"), "*.xml")],
            defaultextension=".xml")
    if not infosetFile:
        return False
    import os
    cntlr.config["infosetFileDir"] = os.path.dirname(infosetFile)
    cntlr.saveConfig()

    try: 
        generateInfoset(cntlr.modelManager.modelXbrl, infosetFile)
    except Exception as ex:
        dts = cntlr.modelManager.modelXbrl
        dts.error("exception",
            _("Infoset generation exception: %(error)s"), error=ex,
            modelXbrl=dts,
            exc_info=True)

def saveInfosetCommandLineOptionExtender(parser):
    # extend command line options with a save DTS option
    parser.add_option("--save-infoset", 
                      action="store", 
                      dest="infosetFile", 
                      help=_("Save instance infoset in specified file, or to send testcase infoset out files to out directory specify 'generateOutFiles'."))

def saveInfosetCommandLineXbrlLoaded(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    from arelle.ModelDocument import Type
    if options.infosetFile and options.infosetFile == "generateOutFiles" and modelXbrl.modelDocument.type in (Type.TESTCASESINDEX, Type.TESTCASE):
        cntlr.modelManager.generateInfosetOutFiles = True

def saveInfosetCommandLineXbrlRun(cntlr, options, modelXbrl):
    # extend XBRL-loaded run processing for this option
    if options.infosetFile and options.infosetFile != "generateOutFiles":
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No taxonomy loaded.")
            return
        generateInfoset(cntlr.modelManager.modelXbrl, options.infosetfile)
        
def validateInfoset(dts, infosetFile):
    if getattr(dts.modelManager, 'generateInfosetOutFiles', False):
        generateInfoset(dts, 
                        # normalize file to instance
                        dts.modelManager.cntlr.webCache.normalizeUrl(infosetFile, dts.uri))


__pluginInfo__ = {
    'name': 'Save Infoset (Instance)',
    'version': '0.9',
    'description': "This plug-in adds a feature to output instance infoset.  "
                    "(Does not offset infoset hrefs and schemaLocations for directory offset from DTS.) ",
    'license': 'Apache-2',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2012 Mark V Systems Limited, All rights reserved.',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': saveInfosetMenuEntender,
    'CntlrCmdLine.Options': saveInfosetCommandLineOptionExtender,
    'CntlrCmdLine.Xbrl.Loaded': saveInfosetCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': saveInfosetCommandLineXbrlRun,
    'Validate.Infoset': validateInfoset,
}
