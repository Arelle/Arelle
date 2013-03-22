'''
xbrlDB is an interface to XBRL databases.

Two implementations are provided:

(1) the XBRL Public Database schema for Postgres, published by XBRL US.

(2) an graph database, based on the XBRL Abstract Model PWD 2.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
and does not apply to the XBRL US Database schema and description.

'''

import time, os, io, sys
from arelle.Locale import format_string
from .XbrlPublicPostgresDB import insertIntoDB as insertIntoPostgresDB, isDBPort as isPostgresPort
from .XbrlSemanticGraphDB import insertIntoDB as insertIntoRexsterDB, isDBPort as isRexsterPort

def xbrlDBmenuEntender(cntlr, menu):
    
    def storeIntoDBMenuCommand():
        # save DTS menu item has been invoked
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No XBRL instance or taxonomy is loaded.")
            return
        from arelle.DialogUserPassword import askDatabase
        # (user, password, host, port, database)
        priorDBconnection = cntlr.config.get("xbrlDBconnection", None)
        dbConnection = askDatabase(cntlr.parent, priorDBconnection)
        if dbConnection:
            host, port, user, password, db = dbConnection
            # identify server
            if isPostgresPort(host, port):
                insertIntoDB = insertIntoPostgresDB
            elif isRexsterPort(host, port):
                insertIntoDB = insertIntoRexsterDB
            else:
                from tkinter import messagebox
                messagebox.showwarning(_("Unable to determine server type!"),
                                       _("Probing host {0} port {1} unable to determine server type.")
                                       .format(host, port),
                                       parent=cntlr.parent)
                return
            cntlr.config["xbrlDBconnection"] = dbConnection
            cntlr.saveConfig()
        else:  # action cancelled
            return

        def backgroundStoreIntoDB():
            try: 
                startedAt = time.time()
                insertIntoDB(cntlr.modelManager.modelXbrl, 
                             host=host, port=port, user=user, password=password, database=db)
                cntlr.addToLog(format_string(cntlr.modelManager.locale, 
                                            _("stored to database in %.2f secs"), 
                                            time.time() - startedAt))
            except Exception as ex:
                import traceback
                cntlr.addToLog(
                    _("[xpDB:exception] Loading XBRL DB: %(exception)s: %(error)s \n%(traceback)s") % 
                    {"exception": ex.__class__.__name__,
                     "error": str(ex),
                     "exc_info": True,
                     "traceback": traceback.format_tb(sys.exc_info()[2])})
        import threading
        thread = threading.Thread(target=backgroundStoreIntoDB)
        thread.daemon = True
        thread.start()
            
    # Extend menu with an item for the savedts plugin
    menu.add_command(label="Store to XBRL DB", 
                     underline=0, 
                     command=storeIntoDBMenuCommand)

def xbrlDBcommandLineOptionExtender(parser):
    # extend command line options to import sphinx files into DTS for validation
    parser.add_option("--store-to-XBRL-DB", 
                      action="store", 
                      dest="storeToXbrlDb", 
                      help=_("Store into XBRL DB.  "
                             "Provides connection string. "))

def xbrlDBCommandLineUtilityRun(cntlr, options):
    # update or replace loaded instance/DTS in xbrlDB
    pass
    
def xbrlDBdialogRssWatchDBconnection(dialog, frame, row, options, cntlr, openFileImage, openDatabaseImage):
    from tkinter import PhotoImage, N, S, E, W
    try:
        from tkinter.ttk import Button
        from tkinter.simpledialog import askstring
    except ImportError:
        from ttk import Button
    from arelle.CntlrWinTooltip import ToolTip
    from arelle.UiUtil import gridCell, label
    # add sphinx formulas to RSS dialog
    def enterConnectionString():
        from arelle.DialogUserPassword import askDatabase
        # (user, password, host, port, database)
        db = askDatabase(cntlr.parent, dialog.cellDBconnection.value.split(',') if dialog.cellDBconnection.value else None)
        if db:
            dbConnectionString = ','.join(db)
            dialog.options["xbrlDBconnection"] = dbConnectionString 
            dialog.cellDBconnection.setValue(dbConnectionString)
        else:  # deleted
            dialog.options.pop("xbrlDBconnection", "")  # remove entry
    label(frame, 1, row, "DB Connection:")
    dialog.cellDBconnection = gridCell(frame,2, row, options.get("xbrlDBconnection",""))
    ToolTip(dialog.cellDBconnection, text=_("Enter an XBRL Database (Postgres) connection string.  "
                                           "E.g., pg://dbuser:dbpassword@dbhost:port.  "), wraplength=240)
    enterDBconnectionButton = Button(frame, image=openDatabaseImage, width=12, command=enterConnectionString)
    enterDBconnectionButton.grid(row=row, column=3, sticky=W)
    
def xbrlDBdialogRssWatchValidateChoices(dialog, frame, row, options, cntlr):
    from arelle.UiUtil import checkbox
    dialog.checkboxes += (
       checkbox(frame, 2, row, 
                "Store into XBRL Database", 
                "storeInXbrlDB"),
    )
    
def xbrlDBrssWatchHasWatchAction(rssWatchOptions):
    return rssWatchOptions.get("xbrlDBconnection") and rssWatchOptions.get("storeInXbrlDB")
    
def xbrlDBrssDoWatchAction(modelXbrl, rssWatchOptions, rssItem):
    dbConnectionString = rssWatchOptions.get("xbrlDBconnection")
    if dbConnectionString:
        db = dbConnectionString.split(',')
        from .XbrlPublicPostgresDB import insertIntoDB
        insertIntoDB(modelXbrl, 
                     host=db[0], port=db[1], user=db[2], password=db[3], database=db[4],
                     rssItem=rssItem)
        
 
__pluginInfo__ = {
    'name': 'XBRL Database',
    'version': '0.9',
    'description': "This plug-in implements the XBRL Public Postgres and Abstract Model Graph Databases.  ",
    'license': 'Apache-2 (Arelle plug-in), BSD license (pg8000 library)',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved,\n'
                'uses: pg8000, Copyright (c) 2007-2009, Mathieu Fenniak (XBRL Public Postgres DB)',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': xbrlDBmenuEntender,
    'CntlrCmdLine.Options': xbrlDBcommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': xbrlDBCommandLineUtilityRun,
    'DialogRssWatch.FileChoices': xbrlDBdialogRssWatchDBconnection,
    'DialogRssWatch.ValidateChoices': xbrlDBdialogRssWatchValidateChoices,
    'RssWatch.HasWatchAction': xbrlDBrssWatchHasWatchAction,
    'RssWatch.DoWatchAction': xbrlDBrssDoWatchAction,
}