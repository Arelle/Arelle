'''
xbrlDB is an interface to XBRL databases.

Two implementations are provided:

(1) the XBRL Public Database schema for Postgres, published by XBRL US.

(2) an graph database, based on the XBRL Abstract Model PWD 2.

See COPYRIGHT.md for copyright information.
(Does not apply to the XBRL US Database schema and description.)

'''

import time, os, io, sys, logging
from arelle.Locale import format_string
from arelle.Version import authorLabel, copyrightLabel
from .XbrlPublicPostgresDB import insertIntoDB as insertIntoPostgresDB, isDBPort as isPostgresPort
from .XbrlSemanticSqlDB import insertIntoDB as insertIntoSemanticSqlDB, isDBPort as isSemanticSqlPort
from .XbrlOpenSqlDB import insertIntoDB as insertIntoOpenSqlDB
from .XbrlSemanticGraphDB import insertIntoDB as insertIntoRexsterDB, isDBPort as isRexsterPort
from .XbrlSemanticRdfDB import insertIntoDB as insertIntoRdfDB, isDBPort as isRdfPort
from .XbrlSemanticJsonDB import insertIntoDB as insertIntoJsonDB, isDBPort as isJsonPort
from .XbrlDpmSqlDB import insertIntoDB as insertIntoDpmDB, isDBPort as isDpmPort

dbTypes = {
    "postgres": insertIntoPostgresDB,
    "mssqlSemantic": insertIntoSemanticSqlDB,
    "mysqlSemantic": insertIntoSemanticSqlDB,
    "orclSemantic": insertIntoSemanticSqlDB,
    "pgSemantic": insertIntoSemanticSqlDB,
    "sqliteSemantic": insertIntoSemanticSqlDB,
    "sqliteDpmDB": insertIntoDpmDB,
    "pgOpenDB": insertIntoOpenSqlDB,
    "rexster": insertIntoRexsterDB,
    "rdfDB": insertIntoRdfDB,
    "json": insertIntoJsonDB
    }

dbProduct = {
    "postgres": "postgres",
    "mssqlSemantic": "mssql",
    "mysqlSemantic": "mysql",
    "orclSemantic": "orcl",
    "pgSemantic": "postgres",
    "pgOpenDB": "postgres",
    "sqliteSemantic": "sqlite",
    "sqliteDpmDB": "sqlite",
    "rexster": None,
    "rdfDB": None,
    "json": None
    }

_loadFromDBoptions = None  # only set for load, vs store operation
_storeIntoDBoptions = None
_schemaRefSubstitutions = None # for DPM database

def xbrlDBmenuEntender(cntlr, menu, *args, **kwargs):

    def storeIntoDBMenuCommand():
        # save DTS menu item has been invoked
        if cntlr.modelManager is None or cntlr.modelManager.modelXbrl is None:
            cntlr.addToLog("No XBRL instance or taxonomy is loaded.")
            return
        from arelle.DialogUserPassword import askDatabase
        # (user, password, host, port, database)
        priorDBconnection = cntlr.config.get("xbrlDBconnection", None)
        dbConnection = askDatabase(cntlr.parent, priorDBconnection)
        if not dbConnection: # action cancelled
            return

        def backgroundStoreIntoDB():
            try:
                host, port, user, password, db, timeout, dbType = dbConnection
                product = None
                if timeout and timeout.isdigit():
                    timeout = int(timeout)
                # identify server
                if dbType in dbTypes:
                    insertIntoDB = dbTypes[dbType]
                    product = dbProduct[dbType]
                else:
                    cntlr.addToLog(_("Probing host {0} port {1} to determine server database type.")
                                   .format(host, port))
                    if isPostgresPort(host, port):
                        dbType = "postgres"
                        insertIntoDB = insertIntoPostgresDB
                    elif isSemanticSqlPort(host, port):
                        dbType = "pgSemantic"
                        insertIntoDB = insertIntoPostgresDB
                    elif isRexsterPort(host, port):
                        dbType = "rexster"
                        insertIntoDB = insertIntoRexsterDB
                    elif isRdfPort(host, port, db):
                        dbType = "rdfDB"
                        insertIntoDB = insertIntoRdfDB
                    elif isJsonPort(host, port, db):
                        dbType = "json"
                        insertIntoDB = insertIntoJsonDB
                    else:
                        cntlr.addToLog(_("Unable to determine server type!\n  ") +
                                       _("Probing host {0} port {1} unable to determine server type.")
                                               .format(host, port))
                        cntlr.config["xbrlDBconnection"] = (host, port, user, password, db, timeout, '') # forget type
                        cntlr.saveConfig()
                        return
                    cntlr.addToLog(_("Database type {} identified.").format(dbType))
                cntlr.config["xbrlDBconnection"] = (host, port, user, password, db, timeout, dbType)
                cntlr.saveConfig()
                startedAt = time.time()
                insertIntoDB(cntlr.modelManager.modelXbrl,
                             host=host, port=port, user=user, password=password, database=db, timeout=timeout,
                             product=product)
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
                cntlr.config["xbrlDBconnection"] = (host, port, user, password, db, timeout, '') # forget type
                cntlr.saveConfig()
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

def storeIntoDB(dbConnection, modelXbrl, rssItem=None, **kwargs):
    host = port = user = password = db = timeout = dbType = None
    if isinstance(dbConnection, (list, tuple)): # variable length list
        if len(dbConnection) > 0: host = dbConnection[0]
        if len(dbConnection) > 1: port = dbConnection[1]
        if len(dbConnection) > 2: user = dbConnection[2]
        if len(dbConnection) > 3: password = dbConnection[3]
        if len(dbConnection) > 4: db = dbConnection[4]
        if len(dbConnection) > 5 and dbConnection[5] and dbConnection[5].isdigit():
            timeout = int(dbConnection[5])
        if len(dbConnection) > 6: dbType = dbConnection[6]

    startedAt = time.time()
    product = None
    if dbType in dbTypes:
        insertIntoDB = dbTypes[dbType]
        product = dbProduct[dbType]
    elif isPostgresPort(host, port):
        insertIntoDB = insertIntoPostgresDB
    elif isSemanticSqlPort(host, port):
        insertIntoDB = insertIntoSemanticSqlDB
    elif isRexsterPort(host, port):
        insertIntoDB = insertIntoRexsterDB
    elif isRdfPort(host, port, db):
        insertIntoDB = insertIntoRdfDB
    elif isJsonPort(host, port, db):
        insertIntoDB = insertIntoJsonDB
    else:
        modelXbrl.modelManager.addToLog('Server at "{0}:{1}" is not recognized to be either a Postgres or a Rexter service.'.format(host, port))
        return
    result = insertIntoDB(modelXbrl, host=host, port=port, user=user, password=password, database=db, timeout=timeout, product=product, rssItem=rssItem, **kwargs)
    if kwargs.get("logStoredMsg", result): # if false/None result and no logStoredMsg parameter then skip the message
        modelXbrl.modelManager.addToLog(format_string(modelXbrl.modelManager.locale,
                              _("stored to database in %.2f secs"),
                              time.time() - startedAt), messageCode="info", file=modelXbrl.uri)
    return result

def xbrlDBcommandLineOptionExtender(parser, *args, **kwargs):
    # extend command line options to store to database
    parser.add_option("--store-to-XBRL-DB",
                      action="store",
                      dest="storeIntoXbrlDb",
                      help=_("Store into XBRL DB.  "
                             "Provides connection string: host,port,user,password,database[,timeout[,{postgres|rexster|rdfDB}]]. "
                             "Autodetects database type unless 7th parameter is provided.  "))
    parser.add_option("--load-from-XBRL-DB",
                      action="store",
                      dest="loadFromXbrlDb",
                      help=_("Load from XBRL DB.  "
                             "Provides connection string: host,port,user,password,database[,timeout[,{postgres|rexster|rdfDB}]]. "
                             "Specifies DB parameters to load and optional file to save XBRL into.  "))

    logging.getLogger("arelle").addHandler(LogToDbHandler())

def xbrlDBCommandLineXbrlLoaded(cntlr, options, modelXbrl, entrypoint, *args, **kwargs):
    from arelle.ModelDocument import Type
    if modelXbrl.modelDocument.type == Type.RSSFEED and getattr(options, "storeIntoXbrlDb", False):
        modelXbrl.xbrlDBconnection = options.storeIntoXbrlDb.split(",")
        # for semantic SQL database check for loaded filings
        if (len(modelXbrl.xbrlDBconnection) > 7 and
            modelXbrl.xbrlDBconnection[6] in ("mssqlSemantic","mysqlSemantic","orclSemantic",
                                              "pgSemantic","sqliteSemantic","pgOpenDB") and
            modelXbrl.xbrlDBconnection[7] == "skipLoadedFilings"):
            # specify reloading of cached source documents (may have been corrupted originally or refiled)
            modelXbrl.reloadCache = True
            storeIntoDB(modelXbrl.xbrlDBconnection, modelXbrl, entrypoint=entrypoint, rssObject=modelXbrl.modelDocument)

def xbrlDBCommandLineXbrlRun(cntlr, options, modelXbrl, entrypoint, *args, **kwargs):
    from arelle.ModelDocument import Type
    if (modelXbrl.modelDocument.type not in (Type.RSSFEED, Type.TESTCASE, Type.REGISTRYTESTCASE) and
        getattr(options, "storeIntoXbrlDb", False) and
        not getattr(modelXbrl, "xbrlDBprocessedByStreaming", False)):
        dbConnection = options.storeIntoXbrlDb.split(",")
        storeIntoDB(dbConnection, modelXbrl, entrypoint=entrypoint)

def xbrlDBvalidateRssItem(val, modelXbrl, rssItem, *args, **kwargs):
    if hasattr(val.modelXbrl, 'xbrlDBconnection'):
        storeIntoDB(val.modelXbrl.xbrlDBconnection, modelXbrl, rssItem)

def xbrlDBtestcaseVariationXbrlLoaded(val, modelXbrl, *args, **kwargs):
    if _storeIntoDBoptions:
        return storeIntoDB(_storeIntoDBoptions.split(','), modelXbrl)

def xbrlDBdialogRssWatchDBconnection(*args, **kwargs):
    try:
        from .DialogRssWatchExtender import dialogRssWatchDBextender
        dialogRssWatchDBextender(*args, **kwargs)
    except ImportError:
        pass

def xbrlDBdialogRssWatchValidateChoices(dialog, frame, row, *args, **kwargs):
    from arelle.UiUtil import checkbox
    dialog.checkboxes += (
       checkbox(frame, 2, row,
                "Store into XBRL Database",
                "storeIntoXbrlDb"),
    )

def xbrlDBrssWatchHasWatchAction(rssWatchOptions, *args, **kwargs):
    return rssWatchOptions.get("xbrlDBconnection") and rssWatchOptions.get("storeIntoXbrlDB")

def xbrlDBrssDoWatchAction(modelXbrl, rssWatchOptions, rssItem, *args, **kwargs):
    dbConnectionString = rssWatchOptions.get("xbrlDBconnection")
    if dbConnectionString:
        dbConnection = dbConnectionString.split(',')
        storeIntoDB(dbConnection, modelXbrl)

def xbrlDBLoaderSetup(cntlr, options, *args, **kwargs):
    global _loadFromDBoptions, _storeIntoDBoptions, _schemaRefSubstitutions
    # set options to load from DB (instead of load from XBRL and store in DB)
    _loadFromDBoptions = getattr(options, "loadFromXbrlDb", None)
    _storeIntoDBoptions = getattr(options, "storeIntoXbrlDb", None)
    _schemaRefSubstitutions = None
    if _storeIntoDBoptions:
        dbConnection = _storeIntoDBoptions.split(',')
        if len(dbConnection) > 7 and dbConnection[6] == "sqliteDpmDB":
            for extraArg in dbConnection[7:]:
                argName, _sep, argValue = extraArg.partition("=")
                if argName == "schemaRefSubstitutions":
                    _schemaRefSubstitutions = dict(_keyVal.split(":")[0:2] for _keyVal in argValue.split(";"))

def xbrlDBLoader(modelXbrl, mappedUri, filepath, *args, **kwargs):
    # check if big instance and has header with an initial incomplete tree walk (just 2 elements
    if not _loadFromDBoptions:
        return None

    # load from DB and save XBRL in filepath, returning modelDocument
    extraArgs = {"loadDBsaveToFile": filepath, "logStoredMsg": False}
    dbConnection = _loadFromDBoptions.split(',')
    if len(dbConnection) > 7:
        for extraArg in dbConnection[7:]:
            argName, _sep, argValue = extraArg.partition("=")
            extraArgs[argName] = argValue
    return storeIntoDB(dbConnection, modelXbrl, **extraArgs)

def xbrlDBmodelXbrlInit(modelXbrl, *args, **kwargs):
        modelXbrl.xbrlDBprocessedByStreaming = False

def xbrlDBstartStreaming(modelXbrl, *args, **kwargs):
    if _storeIntoDBoptions:
        return storeIntoDB(_storeIntoDBoptions.split(','), modelXbrl, streamingState="start", logStoredMsg=False)

def xbrlDBstreamingFacts(modelXbrl, modelFacts, *args, **kwargs):
    if _storeIntoDBoptions:
        return storeIntoDB(_storeIntoDBoptions.split(','), modelXbrl, streamingState="acceptFacts", streamedFacts=modelFacts, logStoredMsg=False)

def xbrlDBfinishStreaming(modelXbrl, *args, **kwargs):
    if _storeIntoDBoptions:
        modelXbrl.xbrlDBprocessedByStreaming = True
        return storeIntoDB(_storeIntoDBoptions.split(','), modelXbrl, streamingState="finish", logStoredMsg=False)

def modelDocumentInstanceSchemaRefRewriter(modelDocument, url, *args, **kwargs):
    if _schemaRefSubstitutions:
        for _from, _to in _schemaRefSubstitutions.items():
            url = url.replace(_from, _to) # for DPM db substitutions
    return url

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
    'description': "This plug-in implements the XBRL Public Postgres, Abstract Model and DPM Databases.  ",
    'license': 'Apache-2 (Arelle plug-in), BSD license (pg8000 library)',
    'author': authorLabel,
    'copyright': f'{copyrightLabel} \n'
                'uses: cx_Oracle Copyright (c) 2007-2012, Anthony Tuininga. All rights reserved (Oracle DB), \n'
                '           (and)Copyright (c) 2001-2007, Computronix (Canada) Ltd., Edmonton, Alberta, Canada. All rights reserved, \n'
                '      pg8000, Copyright (c) 2007-2009, Mathieu Fenniak (Postgres DB), \n'
                '      pyodbc, no copyright, Michael Kleehammer (MS SQL), \n'
                '      PyMySQL, Copyright (c) 2010, 2013 PyMySQL contributors (MySQL DB), and\n'
                '      rdflib, Copyright (c) 2002-2012, RDFLib Team (RDF DB)',
    # classes of mount points (required)
    'CntlrWinMain.Menu.Tools': xbrlDBmenuEntender,
    'CntlrCmdLine.Options': xbrlDBcommandLineOptionExtender,
    'CntlrCmdLine.Utility.Run': xbrlDBLoaderSetup,
    'CntlrCmdLine.Xbrl.Loaded': xbrlDBCommandLineXbrlLoaded,
    'CntlrCmdLine.Xbrl.Run': xbrlDBCommandLineXbrlRun,
    'DialogRssWatch.FileChoices': xbrlDBdialogRssWatchDBconnection,
    'DialogRssWatch.ValidateChoices': xbrlDBdialogRssWatchValidateChoices,
    'ModelDocument.PullLoader': xbrlDBLoader,
    'RssWatch.HasWatchAction': xbrlDBrssWatchHasWatchAction,
    'RssWatch.DoWatchAction': xbrlDBrssDoWatchAction,
    'ModelXbrl.Init': xbrlDBmodelXbrlInit,
    'Streaming.Start': xbrlDBstartStreaming,
    'Streaming.Facts': xbrlDBstreamingFacts,
    'Streaming.Finish': xbrlDBfinishStreaming,
    'Validate.RssItem': xbrlDBvalidateRssItem,
    'TestcaseVariation.Xbrl.Loaded': xbrlDBtestcaseVariationXbrlLoaded,
    'ModelDocument.InstanceSchemaRefRewriter': modelDocumentInstanceSchemaRefRewriter
}
