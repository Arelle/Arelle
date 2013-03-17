'''
xbrlPublicDB is an example of a relational database interface for Arelle, based on the
XBRL US Public Database.  It may be loaded by Arelle's RSS feed, or from an opened
DTS by interactive or command line/web service mode.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
and does not apply to the XBRL US Database schema and description.

The XBRL US Database schema and description is (c) Copyright XBRL US 2011, The 
resulting database may contain data from SEC interactive data filings (or any other XBRL
instance documents and DTS) in a relational model. Mark V Systems conveys neither 
rights nor license for the database schema.
 
The XBRL US Database and this code is intended for Postgres.  XBRL-US uses Postgres 8.4, 
Arelle uses 9.1, via Python DB API 2.0 interface.

Information for the 'official' XBRL US-maintained database (this schema, containing SEC filings):
    Database Name: edgar_db 
    Database engine: Postgres version 8.4 
    \Host: public.xbrl.us 
    Port: 5432

'''

import time, os, io, sys
from arelle.Locale import format_string

def xbrlDBmenuEntender(cntlr, menu):
    
    def storeIntoDBMenuCommand():
        # save DTS menu item has been invoked
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No XBRL instance or taxonomy is loaded.")
            return
        from arelle.DialogUserPassword import askDatabase
        # (user, password, host, port, database)
        db = askDatabase(cntlr.parent, cntlr.config.get("xbrlDBconnection", None))
        if db:
            cntlr.config["xbrlDBconnection"] = db
            cntlr.saveConfig()
        else:  # action cancelled
            return

        def backgroundStoreIntoDB():
            try: 
                startedAt = time.time()
                from .XbrlPublicPostgresDB import insertIntoDB
                insertIntoDB(cntlr.modelManager.modelXbrl, 
                             host=db[0], port=db[1], user=db[2], password=db[3], database=db[4])
                cntlr.addToLog(format_string(cntlr.modelManager.locale, 
                                            _("stored to database in %.2f secs"), 
                                            time.time() - startedAt))
            except Exception as ex:
                import traceback
                cntlr.addToLog(
                    _("[xpDB:exception] XBRL Database Exception: %(error)s \n%(traceback)s") % 
                    {"error": str(ex),
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
    'name': 'XBRL Public Database',
    'version': '0.9',
    'description': "This plug-in implements the XBRL Public Postgres and Abstract Model Graph Databases.  ",
    'license': 'Apache-2 (Arelle plug-in), BSD license (pg8000 and Bulbs libraries)',
    'author': 'Mark V Systems Limited',
    'copyright': '(c) Copyright 2013 Mark V Systems Limited, All rights reserved,\n'
                'uses libraries: pg8000, Copyright (c) 2007-2009, Mathieu Fenniak (XBRL Public Postgres DB), and \n'
                'and Bulbs, Copyright (c) 2012 James Thornton (XBRL Abstract Model Graph DB)',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': xbrlDBmenuEntender,
    'CntlrCmdLine.Options': xbrlDBcommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': xbrlDBCommandLineUtilityRun,
    'DialogRssWatch.FileChoices': xbrlDBdialogRssWatchDBconnection,
    'DialogRssWatch.ValidateChoices': xbrlDBdialogRssWatchValidateChoices,
    'RssWatch.HasWatchAction': xbrlDBrssWatchHasWatchAction,
    'RssWatch.DoWatchAction': xbrlDBrssDoWatchAction,
}