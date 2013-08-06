'''
xbrlDB is an interface to XBRL databases.

Two implementations are provided:

(1) the XBRL Public Database schema for Postgres, published by XBRL US.

(2) an graph database, based on the XBRL Abstract Model PWD 2.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
and does not apply to the XBRL US Database schema and description.

'''

import time, os, io, sys, logging
from arelle.Locale import format_string
from .XbrlPublicPostgresDB import insertIntoDB as insertIntoPostgresDB, isDBPort as isPostgresPort
from .XbrlSemanticGraphDB import insertIntoDB as insertIntoRexsterDB, isDBPort as isRexsterPort
from .XbrlSemanticRdfDB import insertIntoDB as insertIntoRdfDB, isDBPort as isRdfPort

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
            host, port, user, password, db, timeout = dbConnection
            if timeout and timeout.isdigit():
                timeout = int(timeout)
            # identify server
            if isPostgresPort(host, port):
                insertIntoDB = insertIntoPostgresDB
            elif isRexsterPort(host, port):
                insertIntoDB = insertIntoRexsterDB
            elif isRdfPort(host, port, db):
                insertIntoDB = insertIntoRdfDB
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
                             host=host, port=port, user=user, password=password, database=db, timeout=timeout)
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
    
    # add log handler
    logging.getLogger("arelle").addHandler(LogToDbHandler())    
    
def storeIntoDB(dbConnection, modelXbrl, rssItem=None):
    host = port = user = password = db = timeout = None
    if isinstance(dbConnection, (list, tuple)): # variable length list
        if len(dbConnection) > 0: host = dbConnection[0]
        if len(dbConnection) > 1: port = dbConnection[1]
        if len(dbConnection) > 2: user = dbConnection[2]
        if len(dbConnection) > 3: password = dbConnection[3]
        if len(dbConnection) > 4: db = dbConnection[4]
        if len(dbConnection) > 5 and dbConnection[5] and dbConnection[5].isdigit(): 
            timeout = int(dbConnection[5])

    startedAt = time.time()
    if isPostgresPort(host, port):
        insertIntoPostgresDB(modelXbrl, host=host, port=port, user=user, password=password, database=db, timeout=timeout, rssItem=rssItem)
    elif isRexsterPort(host, port):
        insertIntoRexsterDB(modelXbrl, host=host, port=port, user=user, password=password, database=db, timeout=timeout, rssItem=rssItem)
    elif isRdfPort(host, port, db):
        insertIntoRdfDB(modelXbrl, host=host, port=port, user=user, password=password, database=db, timeout=timeout, rssItem=rssItem)
    else:
        modelXbrl.modelManager.addToLog('Server at "{0}:{1}" is not recognized to be either a Postgres or a Rexter service.'.format(host, port))
        return
    modelXbrl.modelManager.addToLog(format_string(modelXbrl.modelManager.locale, 
                          _("stored to database in %.2f secs"), 
                          time.time() - startedAt), messageCode="info", file=modelXbrl.uri)

def xbrlDBcommandLineOptionExtender(parser):
    # extend command line options to import sphinx files into DTS for validation
    parser.add_option("--store-to-XBRL-DB", 
                      action="store", 
                      dest="storeToXbrlDb", 
                      help=_("Store into XBRL DB.  "
                             "Provides connection string: host,port,user,password,database[,timeout]. "))
    logging.getLogger("arelle").addHandler(LogToDbHandler())    

def xbrlDBCommandLineXbrlLoaded(cntlr, options, modelXbrl):
    from arelle.ModelDocument import Type
    if modelXbrl.modelDocument.type == Type.RSSFEED and getattr(options, "storeToXbrlDb", False):
        modelXbrl.xbrlDBconnection = options.storeToXbrlDb.split(",")
    
def xbrlDBCommandLineXbrlRun(cntlr, options, modelXbrl):
    from arelle.ModelDocument import Type
    if modelXbrl.modelDocument.type != Type.RSSFEED and getattr(options, "storeToXbrlDb", False):
        dbConnection = options.storeToXbrlDb.split(",")
        storeIntoDB(dbConnection, modelXbrl)
        
def xbrlDBvalidateRssItem(val, modelXbrl, rssItem):
    if hasattr(val.modelXbrl, 'xbrlDBconnection'):
        storeIntoDB(val.modelXbrl.xbrlDBconnection, modelXbrl, rssItem)
    
def xbrlDBdialogRssWatchDBconnection(*args, **kwargs):
    try:
        from .DialogRssWatchExtender import dialogRssWatchDBextender
        dialogRssWatchDBextender(*args, **kwargs)
    except ImportError:
        pass
    
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
        dbConnection = dbConnectionString.split(',')
        storeIntoDB(dbConnection, modelXbrl)

class LogToDbHandler(logging.Handler):
    def __init__(self):
        super(LogToDbHandler, self).__init__()
        self.logRecordBuffer = []
        
    def flush(self):
        del self.logRecordBuffer[:]
    
    def dbHandlerLogEntries(self, clear=True):
        entries = []
        for logRec in self.logRecordBuffer:
            message = { "text": self.format(logRec) }
            if logRec.args:
                for n, v in logRec.args.items():
                    message[n] = v
            entry = {"code": logRec.messageCode,
                     "level": logRec.levelname.lower(),
                     "refs": logRec.refs,
                     "message": message}
            entries.append(entry)
        if clear:
            del self.logRecordBuffer[:]
        return entries
    
    def emit(self, logRecord):
        self.logRecordBuffer.append(logRecord)
        
 
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
    'CntlrCmdLine.Xbrl.Loaded': xbrlDBCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': xbrlDBCommandLineXbrlRun,
    'DialogRssWatch.FileChoices': xbrlDBdialogRssWatchDBconnection,
    'DialogRssWatch.ValidateChoices': xbrlDBdialogRssWatchValidateChoices,
    'RssWatch.HasWatchAction': xbrlDBrssWatchHasWatchAction,
    'RssWatch.DoWatchAction': xbrlDBrssDoWatchAction,
    'Validate.RssItem': xbrlDBvalidateRssItem
}