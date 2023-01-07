'''
This module provides database interfaces to postgres SQL

See COPYRIGHT.md for copyright information.
'''
import sys, os, io, glob, time, datetime, socket, string, random
import regex as re
from math import isnan, isinf, isfinite
from decimal import Decimal
from arelle.ModelValue import dateTime
from arelle.PythonUtil import flattenSequence

TRACESQLFILE = None
#TRACESQLFILE = r"z:\temp\sqltraceWin.log"  # uncomment to trace SQL on connection (very big file!!!)
#TRACESQLFILE = "/Users/hermf/temp/sqltraceUnx.log"  # uncomment to trace SQL on connection (very big file!!!)

def noop(*args, **kwargs): return
class NoopException(Exception):
    pass
try:
    import pg8000
    hasPostgres = True
    pgConnect = pg8000.connect
    pgOperationalError = pg8000.OperationalError
    pgProgrammingError = pg8000.ProgrammingError
    pgInterfaceError = pg8000.InterfaceError
except ImportError:
    hasPostgres = False
    pgConnect = noop
    pgOperationalError = pgProgrammingError = pgInterfaceError = NoopException

try:
    import pymysql  # MIT License but not installed at GAE
    hasMySql = True
    mysqlConnect = pymysql.connect
    mysqlProgrammingError = pymysql.ProgrammingError
    mysqlInterfaceError = pymysql.InterfaceError
    mysqlInternalError = pymysql.InternalError
except ImportError:
    try :
        import MySQLdb  # LGPL License and used on GAE, Python 2.7 only
        hasMySql = True
        mysqlConnect = MySQLdb.connect
        mysqlProgrammingError = MySQLdb.ProgrammingError
        mysqlInterfaceError = MySQLdb.InterfaceError
        mysqlInternalError = MySQLdb.InternalError
    except ImportError:
        hasMySql = False
        mysqlConnect = noop
        mysqlProgrammingError = mysqlInterfaceError = mysqlInternalError = NoopException

try:
    # requires NLS_LANG to be UTF-8
    os.environ["NLS_LANG"] = ".UTF8"
    os.environ['ORA_NCHAR_LITERAL_REPLACE'] = 'TRUE'
    import cx_Oracle
    hasOracle = True
    oracleConnect = cx_Oracle.connect
    oracleDatabaseError = cx_Oracle.DatabaseError
    oracleInterfaceError = cx_Oracle.InterfaceError
    oracleNCLOB = cx_Oracle.NCLOB
except ImportError:
    # also requires "Oracle Instant Client"
    hasOracle = False
    oracleConnect = noop
    oracleDatabaseError = oracleInterfaceError = NoopException
    oracleCLOB = None

try:
    import pyodbc
    hasMSSql = True
    mssqlConnect = pyodbc.connect
    mssqlOperationalError = pyodbc.OperationalError
    mssqlProgrammingError = pyodbc.ProgrammingError
    mssqlInterfaceError = pyodbc.InterfaceError
    mssqlInternalError = pyodbc.InternalError
    mssqlDataError = pyodbc.DataError
    mssqlIntegrityError = pyodbc.IntegrityError
except ImportError:
    hasMSSql = False
    mssqlConnect = noop
    mssqlOperationalError = mssqlProgrammingError = mssqlInterfaceError = mssqlInternalError = \
        mssqlDataError = mssqlIntegrityError = NoopException

try:
    import sqlite3
    hasSQLite = True
    sqliteConnect = sqlite3.connect
    sqliteParseDecltypes = sqlite3.PARSE_DECLTYPES
    sqliteOperationalError = sqlite3.OperationalError
    sqliteProgrammingError = sqlite3.ProgrammingError
    sqliteInterfaceError = sqlite3.InterfaceError
    sqliteInternalError = sqlite3.InternalError
    sqliteDataError = sqlite3.DataError
    sqliteIntegrityError = sqlite3.IntegrityError
except ImportError:
    hasSQLite = False
    sqliteConnect = noop
    sqliteParseDecltypes = None
    sqliteOperationalError = sqliteProgrammingError = sqliteInterfaceError = sqliteInternalError = \
        sqliteDataError = sqliteIntegrityError = NoopException




def isSqlConnection(host, port, timeout=10, product=None):
    # determine if postgres port
    t = 2
    while t < timeout:
        try:
            if product == "postgres" and hasPostgres:
                pgConnect(user='', host=host, port=int(port or 5432), timeout=t)
            elif product == "mysql" and hasMySql:
                mysqlConnect(user='', host=host, port=int(port or 5432), socket_timeout=t)
            elif product == "orcl" and hasOracle:
                orclConnect = oracleConnect('{}/{}@{}:{}'
                                            .format("", "", host,
                                                    ":{}".format(port) if port else ""))
            elif product == "mssql" and hasMSSql:
                mssqlConnect(user='', host=host, socket_timeout=t)
            elif product == "sqlite" and hasSQLite:
                sqliteConnect("", t) # needs a database specified for this test
        except (pgProgrammingError, mysqlProgrammingError, oracleDatabaseError, sqliteProgrammingError):
            return True # success, this is really a postgres socket, wants user name
        except (pgInterfaceError, mysqlInterfaceError, oracleInterfaceError,
                mssqlOperationalError, mssqlInterfaceError, sqliteOperationalError, sqliteInterfaceError):
            return False # something is there but not postgres
        except socket.timeout:
            t = t + 2  # relax - try again with longer timeout
    return False

class XPDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)

class SqlDbConnection():
    def __init__(self, modelXbrl, user, password, host, port, database, timeout, product, **kwargs):
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        if product == "postgres":
            if not hasPostgres:
                raise XPDBException("xpgDB:MissingPostgresInterface",
                                    _("Postgres interface is not installed"))
            self.conn = pgConnect(user=user, password=password, host=host,
                                  port=int(port or 5432),
                                  database=database,
                                  timeout=timeout or 60)
            self.product = product
        elif product == "mysql":
            if not hasMySql:
                raise XPDBException("xpgDB:MissingMySQLInterface",
                                    _("MySQL interface is not installed"))
            self.conn = mysqlConnect(user=user, passwd=password, host=host,
                                     port=int(port or 5432),
                                     db=database,  # pymysql takes database or db but MySQLdb only takes db
                                     connect_timeout=timeout or 60,
                                     charset='utf8')
            self.product = product
        elif product == "orcl":
            if not hasOracle:
                raise XPDBException("xpgDB:MissingOracleInterface",
                                    _("Oracle interface is not installed"))
            self.conn = oracleConnect('{}/{}@{}{}'
                                            .format(user, password, host,
                                                    ":{}".format(port) if port else ""))
            # self.conn.paramstyle = 'named'
            self.product = product
        elif product == "mssql":
            if not hasMSSql:
                raise XPDBException("xpgDB:MissingMSSQLInterface",
                                    _("MSSQL server interface is not installed"))
            self.conn = mssqlConnect('DRIVER={{SQL Server Native Client 11.0}};SERVER={2};DATABASE={3};UID={0};PWD={1};CHARSET=UTF8'
                                      .format(user,
                                              password,
                                              host, # e.g., localhost\\SQLEXPRESS
                                              database))
            self.product = product
        elif product == "sqlite":
            if not hasSQLite:
                raise XPDBException("xpgDB:MissingSQLiteInterface",
                                    _("SQLite interface is not installed"))
            self.conn = sqliteConnect(database, (timeout or 60), detect_types=sqliteParseDecltypes)
            self.product = product
            self.syncSequences = False # for object_id coordination of autoincrement values
        else:
            self.product = None
        self.tableColTypes = {}
        self.tableColDeclaration = {}
        self.accessionId = "(None)"
        self.tempInputTableName = "input{}".format(os.getpid())

    def close(self, rollback=False):
        if not self.isClosed:
            try:
                self.closeCursor()
                if rollback:
                    self.rollback()
                self.conn.close()
                self.__dict__.clear() # dereference everything
            except Exception as ex:
                self.__dict__.clear() # dereference everything
                raise ex.with_traceback(ex.__traceback__)


    @property
    def isClosed(self):
        return not bool(self.__dict__)  # closed when dict is empty

    def showStatus(self, msg, clearAfter=None):
        if self.modelXbrl is not None:
            self.modelXbrl.modelManager.showStatus(msg, clearAfter)

    def pyStrFromDbStr(self, str):
        if self.product == "postgres":
            return str.replace("%%", "%")
        return str

    def pyBoolFromDbBool(self, str):
        return str in ("TRUE", "t", True)  # may be DB string or Python boolean (preconverted)

    def pyNoneFromDbNULL(self, str):
        return None

    def dbNum(self, num):
        if isinstance(num, (int,float)):
            if isinf(num) or isnan(num):
                return None  # not legal in SQL
            return num
        return None

    def dbStr(self, s):
        if self.product == "orcl":
            return "'" + str(s).replace("'","''") + "'"
        elif self.product == "mysql":
            return "N" + self.conn.escape(str(s))
        elif self.product == 'postgres':
            dollarString = '$string$'
            i = 0
            cleanString = str(s).replace('%', '%%')
            while dollarString in cleanString:
                i += 1
                if i > 100:
                    raise XPDBException("xpgDB:StringHandlingError",
                                _("Trying to generate random dollar quoted string tag, but cannot find one that is not in the string. Tried 100 times."),
                                table=table)
                dollarString = '$' + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(8)) + '$'
            return dollarString + cleanString + dollarString
        elif self.product == "sqlite":
            return "'" + str(s).replace("'","''") + "'"
        else:
            return "'" + str(s).replace("'","''").replace('%', '%%') + "'"

    def dbTableName(self, tableName):
        if self.product == "orcl":
            return '"' + tableName + '"'
        else:
            return tableName

    @property
    def cursor(self):
        try:
            return self._cursor
        except AttributeError:
            self._cursor = self.conn.cursor()
            return self._cursor

    def closeCursor(self):
        try:
            self._cursor.close()
            del self._cursor
        except (AttributeError,
                pgOperationalError,
                mysqlProgrammingError,
                oracleDatabaseError):
            if hasattr(self, '_cursor'):
                del self._cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        try:
            self.conn.rollback()
        except (pg8000.ConnectionClosedError):
            pass

    def dropTemporaryTable(self):
        if self.product == "orcl":
            self.execute("""
                BEGIN
                    EXECUTE IMMEDIATE 'drop table {}';
                    EXCEPTION WHEN OTHERS THEN NULL;
                END;
                """.format(self.tempInputTableName),
                close=True, commit=False, fetch=False, action="dropping temporary table")
        elif self.product == "mssql":
            self.execute("""
                IF OBJECT_ID('tempdb..#{0}', 'U') IS NOT NULL DROP TABLE "#{0}";
                """.format(self.tempInputTableName),
                close=True, commit=False, fetch=False, action="dropping temporary table")

    def lockTables(self, tableNames, isSessionTransaction=False):
        ''' lock for an entire transaction has isSessionTransaction=True, locks until commit
            some databases require locks per operation (such as MySQL), when isSessionTransaction=False
        '''
        if self.product in ("postgres", "orcl") and isSessionTransaction:
            result = self.execute('LOCK {} IN SHARE ROW EXCLUSIVE MODE'.format(', '.join(tableNames)),
                                  close=False, commit=False, fetch=False, action="locking table")
        elif self.product in ("mysql",):
            result = self.execute('LOCK TABLES {}'
                                  .format(', '.join(['{} WRITE'.format(t) for t in tableNames])),
                                  close=False, commit=False, fetch=False, action="locking table")
        elif self.product in ("sqlite",) and isSessionTransaction:
            result = self.execute('BEGIN TRANSACTION',
                                  close=False, commit=False, fetch=False, action="locking table")
        # note, there is no lock for MS SQL (as far as I could find)


    def unlockAllTables(self):
        if self.product in ("mysql",):
            result = self.execute('UNLOCK TABLES',
                                  close=False, commit=False, fetch=False, action="locking table")
        elif self.product in ("sqlite",):
            result = self.execute('COMMIT TRANSACTION',
                                  close=False, commit=False, fetch=False, action="locking table")

    def execute(self, sql, commit=False, close=True, fetch=True, params=None, action="execute"):
        cursor = self.cursor
        try:
            if isinstance(params, dict):
                cursor.execute(sql, **params)
            elif isinstance(params, (tuple,list)):
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
        except (pgProgrammingError,
                mysqlProgrammingError, mysqlInternalError,
                oracleDatabaseError,
                mssqlOperationalError, mssqlInterfaceError, mssqlDataError,
                mssqlProgrammingError, mssqlIntegrityError,
                sqliteOperationalError, sqliteInterfaceError, sqliteDataError,
                socket.timeout,
                ValueError) as ex:  # something wrong with SQL
            if TRACESQLFILE:
                with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                    fh.write("\n\n>>> EXCEPTION {} error {}\n sql {}\n"
                             .format(action, str(ex), sql))
            raise

        if fetch:
            result = cursor.fetchall()
        else:
            #if cursor.rowcount > 0:
            #    cursor.fetchall()  # must get anyway
            result = None
        if commit:
            self.conn.commit()
        if close:
            self.closeCursor()
        return result

    def create(self, ddlFiles, dropPriorTables=True): # ddl Files may be a sequence (or not) of file names, glob wildcards ok, relative ok
        if dropPriorTables:
            # drop tables
            startedAt = time.time()
            self.showStatus("Dropping prior tables")
            for table in self.tablesInDB():
                result = self.execute('DROP TABLE %s' % self.dbTableName(table),
                                      close=False, commit=False, fetch=False, action="dropping table")
            self.showStatus("Dropping prior sequences")
            for sequence in self.sequencesInDB():
                result = self.execute('DROP SEQUENCE %s' % sequence,
                                      close=False, commit=False, fetch=False, action="dropping sequence")
            self.modelXbrl.profileStat(_("XbrlPublicDB: drop prior tables"), time.time() - startedAt)

        startedAt = time.time()
        # process ddlFiles to make absolute and de-globbed
        _ddlFiles = []
        for ddlFile in flattenSequence(ddlFiles):
            if not os.path.isabs(ddlFile):
                ddlFile = os.path.join(os.path.dirname(__file__), ddlFile)
            for _ddlFile in glob.glob(ddlFile):
                _ddlFiles.append(_ddlFile)
        for ddlFile in _ddlFiles:
            with io.open(ddlFile, 'rt', encoding='utf-8') as fh:
                sql = fh.read().replace('%', '%%')
            # separate dollar-quoted bodies and statement lines
            sqlstatements = []
            def findstatements(start, end, laststatement):
                for line in sql[start:end].split('\n'):
                    stmt, comment1, comment2 = line.partition("--")
                    laststatement += stmt + '\n'
                    if ';' in stmt:
                        sqlstatements.append(laststatement)
                        laststatement = ''
                return laststatement
            stmt = ''
            i = 0
            patternDollarEsc = re.compile(r"([$]\w*[$])", re.DOTALL + re.MULTILINE)
            while i < len(sql):  # preserve $$ function body escaping
                match = patternDollarEsc.search(sql, i)
                if not match:
                    stmt = findstatements(i, len(sql), stmt)
                    sqlstatements.append(stmt)
                    break
                # found match
                dollarescape = match.group()
                j = match.end()
                stmt = findstatements(i, j, stmt)  # accumulate statements before match
                i = sql.find(dollarescape, j)
                if i > j: # found end of match
                    if self.product == "mysql":
                        # mysql doesn't want DELIMITER over the interface
                        stmt = sql[j:i]
                        i += len(dollarescape)
                    else:
                        # postgres and others want the delimiter in the sql sent
                        i += len(dollarescape)
                        stmt += sql[j:i]
                    sqlstatements.append(stmt)
                    # problem with driver and $$ statements, skip them (for now)
                    stmt = ''
            action = "executing ddl in {}".format(os.path.basename(ddlFile))
            for i, sql in enumerate(sqlstatements):
                if any(cmd in sql
                       for cmd in ('CREATE TABLE', 'CREATE SEQUENCE', 'INSERT INTO', 'CREATE TYPE',
                                   'CREATE FUNCTION',
                                   'DROP'
                                   'SET',
                                   'CREATE INDEX', 'CREATE UNIQUE INDEX', # 'ALTER TABLE ONLY'
                                   'CREATE VIEW', 'CREATE OR REPLACE VIEW', 'CREATE MATERIALIZED VIEW'
                                   )):
                    statusMsg, sep, rest = sql.strip().partition('\n')
                    self.showStatus(statusMsg[0:50])
                    result = self.execute(sql, close=False, commit=False, fetch=False, action=action)
                    if TRACESQLFILE:
                        with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                            fh.write("\n\n>>> ddl {0}: \n{1} \n\n>>> result: \n{2}\n"
                                     .format(i, sql, result))
                            fh.write(sql)
        self.showStatus("")
        self.conn.commit()
        self.modelXbrl.profileStat(_("XbrlPublicDB: create tables"), time.time() - startedAt)
        self.closeCursor()

    def databasesInDB(self):
        return self.execute({"postgres":"SELECT datname FROM pg_database;",
                             "mysql": "SHOW databases;",
                             "mssql": "SELECT name FROM master..sysdatabases",
                             "orcl": "SELECT DISTINCT OWNER FROM ALL_OBJECTS"
                             }[self.product],
                            action="listing tables in database")

    def dropAllTablesInDB(self):
        # drop all tables (clean out database)
        if self.product == "postgres":
            self.execute("drop schema public cascade")
            self.execute("create schema public;", commit=True, action="recreating schema")
        elif self.product in ("mysql", "mssql", "orcl"):
            for tableName in self.tablesInDB():
                self.execute("DROP TABLE {}".format( self.dbTableName(tableName) ),
                             action="dropping tables")

    def tablesInDB(self):
        return set(tableRow[0]
                   for tableRow in
                   self.execute({"postgres":"SELECT tablename FROM pg_tables WHERE schemaname = 'public';",
                                 "mysql": "SHOW tables;",
                                 "mssql": "SELECT name FROM sys.TABLES;",
                                 "orcl": "SELECT table_name FROM user_tables",
                                 "sqlite": "SELECT name FROM sqlite_master WHERE type='table';"
                                 }[self.product]))

    def sequencesInDB(self):
        try:
            return set(sequenceRow[0]
                       for sequenceRow in
                       self.execute({"postgres":"SELECT c.relname FROM pg_class c WHERE c.relkind = 'S';",
                                     "mysql": "SHOW triggers;",
                                     "mssql": "SELECT name FROM sys.triggers;",
                                     "orcl": "SHOW trigger_name FROM user_triggers"\
                                     }[self.product]))
        except KeyError:
            return set()

    def columnTypeFunctions(self, table):
        if table not in self.tableColTypes:
            if self.product == "orcl":
                colTypesResult = self.execute("SELECT column_name, data_type, data_precision, char_col_decl_length "
                                              "FROM user_tab_columns "
                                              "WHERE table_name = '{0}'"
                                              .format( table )) # table name is not " " quoted here
                colTypes = []
                for name, fulltype, dataPrecision, charColDeclLength in colTypesResult:
                    name = name.lower()
                    fulltype = fulltype.lower()
                    if fulltype in ("varchar", "varchar2"):
                        colDecl = "{}({})".format(fulltype, charColDeclLength)
                    elif fulltype == "number" and dataPrecision:
                        colDecl = "{}({})".format(fulltype, dataPrecision)
                    else:
                        colDecl = fulltype
                    colTypes.append( (name, fulltype, colDecl) )
                # print ("col types for {} = {} ".format(table, colTypes))
            elif self.product == "mssql":
                colTypesResult = self.execute("SELECT column_name, data_type, character_maximum_length "
                                              "FROM information_schema.columns "
                                              "WHERE table_name = '{0}'"
                                              .format( table )) # table name is not " " quoted here
                colTypes = []
                for name, fulltype, characterMaxLength in colTypesResult:
                    name = name.lower()
                    if fulltype in ("char", "varchar", "nvarchar"):
                        if characterMaxLength == -1:
                            characterMaxLength = "max"
                        colDecl = "{}({})".format(fulltype, characterMaxLength)
                    else:
                        colDecl = fulltype
                    colTypes.append( (name, fulltype, colDecl) )
                # print ("col types for {} = {} ".format(table, colTypes))
            elif self.product == "sqlite":
                colTypesResult = self.execute("PRAGMA table_info('{0}')"
                                              .format( table )) # table name is not " " quoted here
                colTypes = []
                for cid, name, type, notnull, dflt_value, pk in colTypesResult:
                    name = name.lower()
                    type = type.lower()
                    colTypes.append( (name, type, type) )
                # print ("col types for {} = {} ".format(table, colTypes))
            else:
                colTypes = self.execute("SELECT c.column_name, c.data_type, {0} "
                                            "FROM information_schema.columns c "
                                            "WHERE c.table_name = '{1}' "
                                            "ORDER BY c.ordinal_position;"
                                            .format('c.column_type' if self.product == 'mysql' else 'c.data_type',
                                                    self.dbTableName(table)))
            self.tableColTypes[table] = dict((name,
                                              # (type cast, conversion function)
                                              ('::' + typename if typename in # takes first word of full type
                                                    {"integer", "smallint", "int", "bigint",
                                                     "real", "numeric",
                                                     "int2", "int4", "int8", "float4", "float8",
                                                     "boolean", "date", "timestamp", "bytea", "json", "jsonb"}
                                               else "::double precision" if fulltype.startswith("double precision")
                                               else '',
                                              int if typename in ("integer", "smallint", "int", "bigint", "number") else
                                              float if typename in ("double precision", "real", "numeric") else
                                              self.pyBoolFromDbBool if typename in ("bit", "boolean") else
                                              dateTime if typename in ("date","timestamp") else  # ModelValue.datetime !!! not python class
                                              str))
                                             for name, fulltype, colDecl in colTypes
                                             for typename in (fulltype.partition(' ')[0],))
            if self.product in ('mysql', 'mssql', 'orcl', 'sqlite'):
                self.tableColDeclaration[table] = dict((name, colDecl)
                                                       for name, fulltype, colDecl in colTypes)

        return self.tableColTypes[table]

    def getTable(self, table, idCol, newCols=None, matchCols=None, data=None, commit=False,
                 comparisonOperator='=', checkIfExisting=False, insertIfNotMatched=True,
                 returnMatches=True, returnExistenceStatus=False):
        # generate SQL
        # note: comparison by = will never match NULL fields
        # use 'IS NOT DISTINCT FROM' to match nulls, but this is not indexed and verrrrry slooooow
        if not data or not newCols or not matchCols:
            # nothing can be done, just return
            return () # place breakpoint here to debug
        isOracle = self.product == "orcl"
        isMSSql = self.product == "mssql"
        isPostgres = self.product == "postgres"
        isSQLite = self.product == "sqlite"
        newCols = [newCol.lower() for newCol in newCols]
        matchCols = [matchCol.lower() for matchCol in matchCols]
        returningCols = []
        if idCol: # idCol is the first returned column if present
            returningCols.append(idCol.lower())
        for matchCol in matchCols:
            if matchCol not in returningCols: # allow idCol to be specified or default assigned
                returningCols.append(matchCol)
        colTypeFunctions = self.columnTypeFunctions(table)
        colDeclarations = self.tableColDeclaration.get(table)
        try:
            colTypeCast = tuple(colTypeFunctions[colName][0] for colName in newCols)
            colTypeFunction = [colTypeFunctions[colName][1] for colName in returningCols]
            if returnExistenceStatus:
                colTypeFunction.append(self.pyBoolFromDbBool) # existence is a boolean
        except KeyError as err:
            raise XPDBException("xpgDB:MissingColumnDefinition",
                                _("Table %(table)s column definition missing: %(missingColumnName)s"),
                                table=table, missingColumnName=str(err))
        rowValues = []
        rowLongValues = []  # contains None if no parameters, else {} parameter dict
        if isOracle:
            longColValues = {}
        else:
            longColValues = []
        for row in data:
            colValues = []
            for col in row:
                if isinstance(col, bool):
                    if isOracle or isMSSql or isSQLite:
                        colValues.append('1' if col else '0')
                    else:
                        colValues.append('TRUE' if col else 'FALSE')
                elif isinstance(col, int):
                    colValues.append(str(col))
                elif isinstance(col, float):
                    if isfinite(col):
                        colValues.append(str(col))
                    else:  # no NaN, INF, in SQL implementations (Postgres has it but not IEEE implementation)
                        colValues.append('NULL')
                elif isinstance(col, Decimal):
                    if col.is_finite():
                        colValues.append(str(col))
                    else:  # no NaN, INF, in SQL implementations (Postgres has it but not IEEE implementation)
                        colValues.append('NULL')
                elif isinstance(col, (datetime.date, datetime.datetime)) and self.product == "orcl":
                    colValues.append("DATE '{:04}-{:02}-{:02}'".format(col.year, col.month, col.day))
                elif isinstance(col, datetime.datetime) and (isMSSql or isSQLite):
                    colValues.append("'{:04}-{:02}-{:02} {:02}:{:02}:{:02}'".format(col.year, col.month, col.day, col.hour, col.minute, col.second))
                elif isinstance(col, datetime.date) and (isMSSql or isSQLite):
                    colValues.append("'{:04}-{:02}-{:02}'".format(col.year, col.month, col.day))
                elif col is None:
                    colValues.append('NULL')
                elif isinstance(col, str) and len(col) >= 4000 and (isOracle or isMSSql):
                    if isOracle:
                        colName = "col{}".format(len(colValues))
                        longColValues[colName] = col
                        colValues.append(":" + colName)
                    else:
                        longColValues.append(col)
                        colValues.append("?")
                elif isinstance(col, bytes) and isPostgres:
                    hexvals = "".join([hex(x)[2:] for x in col])
                    #get the hex values
                    hexvals = [hex(x)[2:] for x in col]
                    #fix up single digit values
                    for i in range(len(hexvals)):
                        if len(hexvals[i]) == 1:
                            hexvals[i] = "0" + hexvals[i]

                    colValues.append(r"E'\\x" + "".join(hexvals) + "'")
                    #colValues.append(r"E'\\x" + col.decode() + "'" )
                else:
                    colValues.append(self.dbStr(col))
            if not rowValues and isPostgres:  # first row
                for i, cast in enumerate(colTypeCast):
                    if cast:
                        colValues[i] = colValues[i] + cast
            rowColValues = ", ".join(colValues)
            rowValues.append("(" + rowColValues + ")" if not isOracle else rowColValues)
            if longColValues:
                rowLongValues.append(longColValues)
                if isOracle:
                    longColValues = {} # must be new instance of dict
                else:
                    longColValues = []
            else:
                rowLongValues.append(None)
        values = ", \n".join(rowValues)

        _table = self.dbTableName(table)
        _inputTableName = self.tempInputTableName
        if self.product == "postgres":
            # insert new rows, return id and cols of new and existing rows
            # use IS NOT DISTINCT FROM instead of = to compare NULL usefully
            sql = [(('''
WITH row_values (%(newCols)s) AS (
  VALUES %(values)s
  )''' + (''', insertions AS (
  INSERT INTO %(table)s (%(newCols)s)
  SELECT %(newCols)s
  FROM row_values v''' + ('''
  WHERE NOT EXISTS (SELECT 1
                    FROM %(table)s x
                    WHERE %(match)s)''' if checkIfExisting else '') + '''
  RETURNING %(returningCols)s
) ''' if insertIfNotMatched else '') + '''
(''' + (('''
   SELECT %(x_returningCols)s %(statusIfExisting)s
   FROM %(table)s x JOIN row_values v ON (%(match)s) ''' if checkIfExisting else '') + ('''
) UNION ( ''' if (checkIfExisting and insertIfNotMatched) else '') + ('''
   SELECT %(returningCols)s %(statusIfInserted)s
   FROM insertions''' if insertIfNotMatched else '')) + '''
);''') %        {"table": _table,
                 "idCol": idCol,
                 "newCols": ', '.join(newCols),
                 "returningCols": ', '.join(returningCols),
                 "x_returningCols": ', '.join('x.{0}'.format(c) for c in returningCols),
                 "match": ' AND '.join('x.{0} {1} v.{0}'.format(col, comparisonOperator)
                                    for col in matchCols),
                 "values": values,
                 "statusIfInserted": ", FALSE" if returnExistenceStatus else "",
                 "statusIfExisting": ", TRUE" if returnExistenceStatus else ""
                 }, None, True)]
        elif self.product == "mysql":
            sql = [("CREATE TEMPORARY TABLE %(inputTable)s ( %(inputCols)s );" %
                        {"inputTable": _inputTableName,
                         "inputCols": ', '.join('{0} {1}'.format(newCol, colDeclarations[newCol])
                                                for newCol in newCols)}, None, False),
                   ("INSERT INTO %(inputTable)s ( %(newCols)s ) VALUES %(values)s;" %
                        {"inputTable": _inputTableName,
                         "newCols": ', '.join(newCols),
                         "values": values}, None, False)]
            if insertIfNotMatched:
                if checkIfExisting:
                    _where = ('WHERE NOT EXISTS (SELECT 1 FROM %(table)s x WHERE %(match)s)' %
                              {"table": _table,
                               "match": ' AND '.join('x.{0} {1} i.{0}'.format(col, comparisonOperator)
                                                     for col in matchCols)})
                    _whereLock = (", %(table)s AS x READ" % {"table": _table})
                else:
                    _where = "";
                    _whereLock = ""
                sql.append( ("LOCK TABLES %(table)s WRITE %(whereLock)s" %
                             {"table": _table,
                              "whereLock": _whereLock}, None, False) )
                sql.append( ("INSERT INTO %(table)s ( %(newCols)s ) SELECT %(newCols)s FROM %(inputTable)s i %(where)s;" %
                                {"inputTable": _inputTableName,
                                 "table": _table,
                                 "newCols": ', '.join(newCols),
                                 "where": _where}, None, False) )
            elif returnMatches or returnExistenceStatus:
                sql.append( ("LOCK TABLES %(table)s READ" %
                             {"table": _table}, None, False) )
            # don't know how to get status if existing
            if returnMatches or returnExistenceStatus:
                sql.append( ("SELECT %(returningCols)s %(statusIfExisting)s from %(inputTable)s JOIN %(table)s ON ( %(match)s );" %
                                {"inputTable": _inputTableName,
                                 "table": _table,
                                 "newCols": ', '.join(newCols),
                                 "match": ' AND '.join('{0}.{2} = {1}.{2}'.format(_table,_inputTableName,col)
                                            for col in matchCols),
                                 "statusIfExisting": ", FALSE" if returnExistenceStatus else "",
                                 "returningCols": ', '.join('{0}.{1}'.format(_table,col)
                                                            for col in returningCols)}, None, True) )
            sql.append( ("DROP TEMPORARY TABLE %(inputTable)s;" %
                         {"inputTable": _inputTableName}, None, False) )
        elif self.product == "mssql":
            sql = [("CREATE TABLE #%(inputTable)s ( %(inputCols)s );" %
                        {"inputTable": _inputTableName,
                         "inputCols": ', '.join('{0} {1}'.format(newCol, colDeclarations[newCol])
                                                for newCol in newCols)}, None, False)]
            # break values insertion into 1000's each
            def insertMSSqlRows(i, j, params):
                sql.append(("INSERT INTO #%(inputTable)s ( %(newCols)s ) VALUES %(values)s;" %
                        {"inputTable": _inputTableName,
                         "newCols": ', '.join(newCols),
                         "values": ", ".join(rowValues[i:j])}, params, False))
            iMax = len(rowValues)
            i = 0
            while (i < iMax):
                for j in range(i, min(i+1000, iMax)):
                    if rowLongValues[j] is not None:
                        if j > i:
                            insertMSSqlRows(i, j, None)
                        insertMSSqlRows(j, j+1, rowLongValues[j])
                        i = j + 1
                        break
                if i < j+1 and i < iMax:
                    insertMSSqlRows(i, j+1, None)
                    i = j+1
            if insertIfNotMatched:
                sql.append(("MERGE INTO %(table)s USING #%(inputTable)s ON (%(match)s) "
                            "WHEN NOT MATCHED THEN INSERT (%(newCols)s) VALUES (%(values)s);" %
                            {"inputTable": _inputTableName,
                             "table": _table,
                             "newCols": ', '.join(newCols),
                             "match": ' AND '.join('{0}.{2} = #{1}.{2}'.format(_table,_inputTableName,col)
                                        for col in matchCols),
                             "values": ', '.join("#{0}.{1}".format(_inputTableName,newCol)
                                                 for newCol in newCols)}, None, False))
            if returnMatches or returnExistenceStatus:
                sql.append(# don't know how to get status if existing
                       ("SELECT %(returningCols)s %(statusIfExisting)s from #%(inputTable)s JOIN %(table)s ON ( %(match)s );" %
                            {"inputTable": _inputTableName,
                             "table": _table,
                             "newCols": ', '.join(newCols),
                             "match": ' AND '.join('{0}.{2} = #{1}.{2}'.format(_table,_inputTableName,col)
                                        for col in matchCols),
                             "statusIfExisting": ", 0" if returnExistenceStatus else "",
                             "returningCols": ', '.join('{0}.{1}'.format(_table,col)
                                                        for col in returningCols)}, None, True))
            sql.append(("DROP TABLE #%(inputTable)s;" %
                         {"inputTable": _inputTableName}, None, False))
        elif self.product == "orcl":
            sql = [("CREATE GLOBAL TEMPORARY TABLE %(inputTable)s ( %(inputCols)s )" %
                        {"inputTable": _inputTableName,
                         "inputCols": ', '.join('{0} {1}'.format(newCol, colDeclarations[newCol])
                                                for newCol in newCols)}, None, False)]
            # break values insertion into 1000's each
            def insertOrclRows(i, j, params):
                sql.append(("INSERT INTO %(inputTable)s ( %(newCols)s ) %(values)s" %
                        {"inputTable": _inputTableName,
                         "newCols": ', '.join(newCols),
                         "values": "\nUNION ALL".join(" SELECT {} FROM dual ".format(r)
                                                      for r in rowValues[i:j])}, params, False))
            iMax = len(rowValues)
            i = 0
            while (i < iMax):
                for j in range(i, min(i+1000, iMax)):
                    if rowLongValues[j] is not None:
                        if j > i:
                            insertOrclRows(i, j, None)
                        insertOrclRows(j, j+1, rowLongValues[j])
                        i = j + 1
                        break
                if i < j+1 and i < iMax:
                    insertOrclRows(i, j+1, None)
                    i = j+1
            if insertIfNotMatched:
                sql.append(("MERGE INTO %(table)s USING %(inputTable)s ON (%(match)s) "
                            "WHEN NOT MATCHED THEN INSERT (%(newCols)s) VALUES (%(values)s)" %
                            {"inputTable": _inputTableName,
                             "table": _table,
                             "newCols": ', '.join(newCols),
                             "match": ' AND '.join('{0}.{2} = {1}.{2}'.format(_table,_inputTableName,col)
                                        for col in matchCols),
                             "values": ', '.join("{0}.{1}".format(_inputTableName,newCol)
                                                 for newCol in newCols)}, None, False))
            if returnMatches or returnExistenceStatus:
                sql.append(# don't know how to get status if existing
                       ("SELECT %(returningCols)s %(statusIfExisting)s from %(inputTable)s JOIN %(table)s ON ( %(match)s )" %
                            {"inputTable": _inputTableName,
                             "table": _table,
                             "newCols": ', '.join(newCols),
                             "match": ' AND '.join('{0}.{2} = {1}.{2}'.format(_table,_inputTableName,col)
                                        for col in matchCols),
                             "statusIfExisting": ", 0" if returnExistenceStatus else "",
                             "returningCols": ', '.join('{0}.{1}'.format(_table,col)
                                                        for col in returningCols)}, None, True))
            sql.append(("DROP TABLE %(inputTable)s" %
                         {"inputTable": _inputTableName}, None, False))
        elif self.product == "sqlite":
            sql = [("CREATE TEMP TABLE %(inputTable)s ( %(inputCols)s );" %
                        {"inputTable": _inputTableName,
                         "inputCols": ', '.join('{0} {1}'.format(newCol, colDeclarations[newCol])
                                                for newCol in newCols)}, None, False)]
            # break values insertion into 1000's each
            def insertSQLiteRows(i, j, params):
                sql.append(("INSERT INTO %(inputTable)s ( %(newCols)s ) VALUES %(values)s;" %
                        {"inputTable": _inputTableName,
                         "newCols": ', '.join(newCols),
                         "values": ", ".join(rowValues[i:j])}, params, False))
            iMax = len(rowValues)
            i = 0
            while (i < iMax):
                for j in range(i, min(i+500, iMax)):
                    if rowLongValues[j] is not None:
                        if j > i:
                            insertSQLiteRows(i, j, None)
                        insertSQLiteRows(j, j+1, rowLongValues[j])
                        i = j + 1
                        break
                if i < j+1 and i < iMax:
                    insertSQLiteRows(i, j+1, None)
                    i = j+1
            if insertIfNotMatched:
                if checkIfExisting:
                    _where = ('WHERE NOT EXISTS (SELECT 1 FROM %(table)s x WHERE %(match)s)' %
                              {"table": _table,
                               "match": ' AND '.join('x.{0} {1} i.{0}'.format(col, comparisonOperator)
                                                     for col in matchCols)})
                else:
                    _where = "";
                sql.append( ("INSERT INTO %(table)s ( %(newCols)s ) SELECT %(newCols)s FROM %(inputTable)s i %(where)s;" %
                                {"inputTable": _inputTableName,
                                 "table": _table,
                                 "newCols": ', '.join(newCols),
                                 "where": _where}, None, False) )
            if returnMatches or returnExistenceStatus:
                sql.append(# don't know how to get status if existing
                       ("SELECT %(returningCols)s %(statusIfExisting)s from %(inputTable)s JOIN %(table)s ON ( %(match)s );" %
                            {"inputTable": _inputTableName,
                             "table": _table,
                             "newCols": ', '.join(newCols),
                             "match": ' AND '.join('{0}.{2} = {1}.{2}'.format(_table,_inputTableName,col)
                                        for col in matchCols),
                             "statusIfExisting": ", 0" if returnExistenceStatus else "",
                             "returningCols": ', '.join('{0}.{1}'.format(_table,col)
                                                        for col in returningCols)}, None, True))
            sql.append(("DROP TABLE %(inputTable)s;" %
                         {"inputTable": _inputTableName}, None, False))
            if insertIfNotMatched and self.syncSequences:
                sql.append( ("update sqlite_sequence "
                             "set seq = (select seq from sqlite_sequence where name = '%(table)s') "
                             "where name != '%(table)s';" %
                              {"table": _table}, None, False) )
        if TRACESQLFILE:
            with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> accession {0} table {1} sql length {2} row count {3}\n"
                         .format(self.accessionId, table, len(sql), len(data)))
                for sqlStmt, params, fetch in sql:
                    fh.write("\n    " + sqlStmt + "\n     {}".format(params if params else ""))
        tableRows = []
        for sqlStmt, params, fetch in sql:
            if params and isOracle:
                self.cursor.setinputsizes(**dict((name,oracleNCLOB) for name in params))

            #startTime = datetime.datetime.today()
            result = self.execute(sqlStmt,commit=commit, close=False, fetch=fetch, params=params)
            #endTime = datetime.datetime.today()

            if fetch and result:
                tableRows.extend(result)

            #hours, remainder = divmod((endTime - startTime).total_seconds(), 3600)
            #minutes, seconds = divmod(remainder, 60)
            #self.modelXbrl.info("info",_("%(now)s - Table %(tableName)s loaded in %(timeTook)s"),
            #                             now=str(datetime.datetime.today()),
            #                             tableName=table,
            #                             timeTook='%02.0f:%02.0f:%02.4f' % (hours, minutes, seconds))


        if TRACESQLFILE:
            with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> accession {0} table {1} result row count {2}\n{3}\n"
                         .format(self.accessionId, table, len(tableRows), '\n'.join(str(r) for r in tableRows)))
        return tuple(tuple(None if colValue == "NULL" or colValue is None else
                           colTypeFunction[i](colValue)  # convert to int, datetime, etc
                           for i, colValue in enumerate(row))
                     for row in tableRows)

    def updateTable(self, table, cols=None, data=None, commit=False):
        # generate SQL
        # note: comparison by = will never match NULL fields
        # use 'IS NOT DISTINCT FROM' to match nulls, but this is not indexed and verrrrry slooooow
        if not cols or not data:
            # nothing can be done, just return
            return () # place breakpoint here to debug
        isOracle = self.product == "orcl"
        isSQLite = self.product == "sqlite"
        idCol = cols[0]
        colTypeFunctions = self.columnTypeFunctions(table)
        colDeclarations = self.tableColDeclaration.get(table)
        try:
            colTypeCast = tuple(colTypeFunctions[colName][0] for colName in cols)
        except KeyError as err:
            raise XPDBException("xpgDB:MissingColumnDefinition",
                                _("Table %(table)s column definition missing: %(missingColumnName)s"),
                                table=table, missingColumnName=str(err))
        rowValues = []
        for row in data:
            colValues = []
            for col in row:
                if isinstance(col, bool):
                    colValues.append('TRUE' if col else 'FALSE')
                elif isinstance(col, (int,float)):
                    colValues.append(str(col))
                elif col is None:
                    colValues.append('NULL')
                else:
                    colValues.append(self.dbStr(col))
            if not rowValues and self.product == "postgres":  # first row
                for i, cast in enumerate(colTypeCast):
                    if cast:
                        colValues[i] = colValues[i] + cast
            rowColValues = ", ".join(colValues)
            if isOracle:
                rowValues.append(rowColValues)
            elif isSQLite:
                rowValues.append(colValues)
            else:
                rowValues.append("(" + rowColValues + ")")
        if not isOracle and not isSQLite:
            values = ", \n".join(rowValues)

        _table = self.dbTableName(table)
        _inputTableName = self.tempInputTableName
        if self.product == "postgres":
            # insert new rows, return id and cols of new and existing rows
            # use IS NOT DISTINCT FROM instead of = to compare NULL usefully
            sql = [('''
WITH input (%(valCols)s) AS ( VALUES %(values)s )
   UPDATE %(table)s t SET %(settings)s
   FROM input i WHERE i.%(idCol)s = t.%(idCol)s
;''') %         {"table": _table,
                 "idCol": idCol,
                 "valCols": ', '.join(col for col in cols),
                 "settings": ', '.join('{0} = i.{0}'.format(cols[i])
                                       for i, col in enumerate(cols)
                                       if i > 0),
                 "values": values}]

        elif self.product == "mysql":
            sql = ["CREATE TEMPORARY TABLE %(inputTable)s ( %(valCols)s );" %
                        {"inputTable": _inputTableName,
                         "valCols": ', '.join('{0} {1}'.format(col, colDeclarations[col])
                                              for col in cols)},
                   "INSERT INTO %(inputTable)s ( %(newCols)s ) VALUES %(values)s;" %
                        {"inputTable": _inputTableName,
                         "newCols": ', '.join(cols),
                         "values": values},
                   "LOCK TABLES %(inputTable)s AS i READ, %(table)s AS t WRITE;" %
                        {"inputTable": _inputTableName,
                         "table": _table},
                   "UPDATE %(inputTable)s i, %(table)s t SET %(settings)s WHERE i.%(idCol)s = t.%(idCol)s;" %
                        {"inputTable": _inputTableName,
                         "table": _table,
                         "idCol": idCol,
                         "settings": ', '.join('t.{0} = i.{0}'.format(cols[i])
                                               for i, col in enumerate(cols)
                                               if i > 0)},
                   "DROP TEMPORARY TABLE %(inputTable)s;" % {"inputTable": _inputTableName}]
        elif self.product == "mssql":
            sql = ["CREATE TABLE #%(inputTable)s ( %(valCols)s );" %
                        {"inputTable": _inputTableName,
                         "valCols": ', '.join('{0} {1}'.format(col, colDeclarations[col])
                                              for col in cols)}]
            # must break values insertion into 1000's each
            for i in range(0, len(rowValues), 950):
                values = ", \n".join(rowValues[i: i+950])
                sql.append("INSERT INTO #%(inputTable)s ( %(cols)s ) VALUES %(values)s;" %
                        {"inputTable": _inputTableName,
                         "cols": ', '.join(cols),
                         "values": values})
            sql.append("MERGE INTO %(table)s USING #%(inputTable)s ON (#%(inputTable)s.%(idCol)s = %(table)s.%(idCol)s) "
                       "WHEN MATCHED THEN UPDATE SET %(settings)s;" %
                        {"inputTable": _inputTableName,
                         "table": _table,
                         "idCol": idCol,
                         "settings": ', '.join('{0}.{2} = #{1}.{2}'.format(_table, _inputTableName, cols[i])
                                               for i, col in enumerate(cols)
                                               if i > 0)})
            sql.append("DROP TABLE #%(inputTable)s;" % {"inputTable": _inputTableName})
        elif self.product == "orcl":
            sql = ["CREATE GLOBAL TEMPORARY TABLE %(inputTable)s ( %(valCols)s )" %
                        {"inputTable": _inputTableName,
                         "valCols": ', '.join('{0} {1}'.format(col, colDeclarations[col])
                                              for col in cols)}]
            for i in range(0, len(rowValues), 500):
                sql.append(
                   "INSERT INTO %(inputTable)s ( %(cols)s ) %(values)s" %
                        {"inputTable": _inputTableName,
                         "cols": ', '.join(cols),
                         "values": "\nUNION ALL".join(" SELECT {} FROM dual ".format(r)
                                                      for r in rowValues[i:i+500])})
            sql.append("MERGE INTO %(table)s USING %(inputTable)s ON (%(inputTable)s.%(idCol)s = %(table)s.%(idCol)s) "
                       "WHEN MATCHED THEN UPDATE SET %(settings)s" %
                        {"inputTable": _inputTableName,
                         "table": _table,
                         "idCol": idCol,
                         "settings": ', '.join('{0}.{2} = {1}.{2}'.format(_table, _inputTableName, cols[i])
                                               for i, col in enumerate(cols)
                                               if i > 0)})
            sql.append("DROP TABLE %(inputTable)s" % {"inputTable": _inputTableName})
        elif self.product == "sqlite":
            sql = ["UPDATE %(table)s SET %(settings)s WHERE %(idCol)s = %(idVal)s;" %
                            {"table": _table,
                             "idCol": idCol,
                             "idVal": rowValue[0],
                             "settings": ', '.join('{0} = {1}'.format(col,rowValue[i])
                                                   for i, col in enumerate(cols)
                                                   if i > 0)}
                   for rowValue in rowValues]
        if TRACESQLFILE:
            with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> accession {0} table {1} sql length {2} row count {3}\n"
                         .format(self.accessionId, table, len(sql), len(data)))
                for sqlStmt in sql:
                    fh.write(sqlStmt)
        for sqlStmt in sql:
            self.execute(sqlStmt,commit=commit, fetch=False, close=False)
