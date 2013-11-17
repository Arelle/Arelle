'''
This module provides database interfaces to postgres SQL

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
'''
import sys, os, io, time, re, datetime
from math import isnan, isinf
from arelle.ModelValue import dateTime
import socket
from pg8000 import DBAPI
from pg8000.errors import (CursorClosedError, ConnectionClosedError, ProgrammingError,
                           InterfaceError, ProgrammingError)


TRACESQLFILE = None
TRACESQLFILE = r"c:\temp\sqltrace.log"  # uncomment to trace SQL on connection (very big file!!!)


def pyBoolFromDbBool(str):
    return str in ("TRUE", "t")

def pyNoneFromDbNULL(str):
    return None

def dbNum(num):
    if isinstance(num, (int,float)):
        if isinf(num) or isnan(num):
            return None  # not legal in SQL
        return num
    return None 

def dbStr(s):
    return "'" + str(s).replace("'","''").replace('%', '%%') + "'"

def isSqlConnection(host, port, timeout=10):
    # determine if postgres port
    t = 2
    while t < timeout:
        try:
            DBAPI.connect(user='', host=host, port=int(port or 5432), socket_timeout=t)
        except ProgrammingError:
            return True # success, this is really a postgres socket, wants user name
        except InterfaceError:
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
    def __init__(self, modelXbrl, user, password, host, port, database, timeout):
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        self.conn = DBAPI.connect(user=user, password=password, host=host, 
                                  port=int(port or 5432), 
                                  database=database, 
                                  socket_timeout=timeout or 60)
        self.tableColTypes = {}
        self.accessionId = "(None)"
                
    def close(self, rollback=False):
        try:
            self.closeCursor()
            if rollback:
                self.rollback()
            self.conn.close()
            self.__dict__.clear() # dereference everything
        except Exception as ex:
            self.__dict__.clear() # dereference everything
            if sys.version[0] >= '3':
                raise ex.with_traceback(ex.__traceback__)
            else:
                raise ex
        
    @property
    def isClosed(self):
        return not bool(self.__dict__)  # closed when dict is empty
    
    def showStatus(self, msg, clearAfter=None):
        self.modelXbrl.modelManager.showStatus(msg, clearAfter)
        
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
        except (AttributeError, CursorClosedError, ConnectionClosedError):
            if hasattr(self, '_cursor'):
                del self._cursor
        
    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        try:
            self.conn.rollback()
        except (ConnectionClosedError):
            pass
        
    def execute(self, sql, commit=False, close=True, fetch=True):
        cursor = self.cursor
        try:
            cursor.execute(sql)
        except ProgrammingError as ex:  # something wrong with SQL
            if TRACESQLFILE:
                with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                    fh.write("\n\n>>> EXCEPTION Programming Error {}\n sql {}\n"
                             .format(str(ex), sql))
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
    
    def create(self):
        # drop tables
        startedAt = time.time()
        self.showStatus("Dropping prior tables")
        for table in self.tablesInDB():
            result = self.execute('DROP TABLE %s' % table[0],
                                  close=False, commit=False, fetch=False)
        self.showStatus("Dropping prior sequences")
        for sequence in self.sequencesInDB():
            result = self.execute('DROP SEQUENCE %s' % sequence,
                                  close=False, commit=False, fetch=False)
        self.modelXbrl.profileStat(_("XbrlPublicDB: drop prior tables"), time.time() - startedAt)
                    
        startedAt = time.time()
        with io.open(os.path.dirname(__file__) + os.sep + "xbrlPublicPostgresDB.ddl", 
                     'rt', encoding='utf-8') as fh:
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
                i += len(dollarescape)
                stmt += dollarescape + sql[j:i]
                # problem with driver and $$ statements, skip them (for now)
                stmt = ''
        for i, sql in enumerate(sqlstatements):
            if any(cmd in sql
                   for cmd in ('CREATE TABLE', 'CREATE SEQUENCE', 'INSERT INTO',
                               'CREATE INDEX', 'CREATE UNIQUE INDEX' # 'ALTER TABLE ONLY'
                               )):
                statusMsg, sep, rest = sql.strip().partition('\n')
                self.showStatus(statusMsg[0:50])
                result = self.execute(sql, close=False, commit=False, fetch=False)
                """
                if TRACESQLFILE:
                    with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                        fh.write("\n\n>>> ddl {0}: \n{1} \n\n>>> result: \n{2}\n"
                                 .format(i, sql, result))
                        fh.write(sql)
                """
        # fixed tables
        self.getTable('enumeration_arcrole_cycles_allowed', 'enumeration_arcrole_cycles_allowed_id', 
                      ('description',), ('description',),
                      (('any',), ('undirected',), ('none',)))
        self.getTable('enumeration_element_balance', 'enumeration_element_balance_id', 
                      ('description',), ('description',),
                      (('credit',), ('debit',)))
        self.getTable('enumeration_element_period_type', 'enumeration_element_period_type_id', 
                      ('description',), ('description',),
                      (('instant',), ('duration',), ('forever',)))
        self.showStatus("")
        self.conn.commit()
        self.modelXbrl.profileStat(_("XbrlPublicDB: create tables"), time.time() - startedAt)
        self.closeCursor()
        
    def databasesInDB(self):
        return self.execute("SELECT datname FROM pg_database;")
    
    def dropAllTablesInDB(self):
        # drop all tables (clean out database)
        self.execute("drop schema public cascade;")
        self.execute("create schema public;", commit=True)
        
    def tablesInDB(self):
        return set(tableRow[0]
                   for tableRow in 
                   self.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';"))
    
    def sequencesInDB(self):
        return set(sequenceRow[0]
                   for sequenceRow in
                   self.execute("SELECT c.relname FROM pg_class c WHERE c.relkind = 'S';"))
    
    def columnTypeFunctions(self, table):
        if table not in self.tableColTypes:
            colTypes = self.execute("SELECT c.column_name, c.data_type "
                                    "FROM information_schema.columns c "
                                    "WHERE c.table_name = '%s' "
                                    "ORDER BY c.ordinal_position;" % table)
            self.tableColTypes[table] = dict((name, 
                                              # (type cast, conversion function)
                                              ('::' + typename if typename in # takes first word of full type
                                                    {"integer", "smallint", "int", "bigint",
                                                     "real", "numeric",
                                                     "int2", "int4", "int8", "float4", "float8",
                                                     "boolean", "date", "timestamp"}
                                               else "::double precision" if fulltype.startswith("double precision") 
                                               else '',
                                              int if typename in ("integer", "smallint", "int", "bigint") else
                                              float if typename in ("double precision", "real", "numeric") else
                                              pyBoolFromDbBool if typename == "boolean" else
                                              dateTime if typename in ("date","timestamp") else  # ModelValue.datetime !!! not python class
                                              str))
                                             for name, fulltype in colTypes
                                             for typename in (fulltype.partition(' ')[0],))
        return self.tableColTypes[table]
    
    def getTable(self, table, idCol, newCols=None, matchCols=None, data=None, commit=False, comparisonOperator='=', checkIfExisting=False):
        # generate SQL
        # note: comparison by = will never match NULL fields
        # use 'IS NOT DISTINCT FROM' to match nulls, but this is not indexed and verrrrry slooooow
        if not data or not newCols or not matchCols:
            # nothing can be done, just return
            return () # place breakpoint here to debug
        returningCols = []
        if idCol: # idCol is the first returned column if present
            returningCols.append(idCol)
        for matchCol in matchCols:
            if matchCol not in returningCols: # allow idCol to be specified or default assigned
                returningCols.append(matchCol)
        colTypeFunctions = self.columnTypeFunctions(table)
        try:
            colTypeCast = tuple(colTypeFunctions[colName][0] for colName in newCols)
            colTypeFunction = tuple(colTypeFunctions[colName][1] for colName in returningCols)
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
                    colValues.append(dbStr(col))
            if not rowValues:  # first row
                for i, cast in enumerate(colTypeCast):
                    if cast:
                        colValues[i] = colValues[i] + cast
            rowValues.append("(" + ", ".join(colValues) + ")")
        values = ", \n".join(rowValues)
        # insert new rows, return id and cols of new and existing rows
        # use IS NOT DISTINCT FROM instead of = to compare NULL usefully
        sql = ('''
WITH row_values (%(newCols)s) AS (
  VALUES %(values)s
  ), insertions AS (
  INSERT INTO %(table)s (%(newCols)s)
  SELECT %(newCols)s
  FROM row_values v''' + ('''
  WHERE NOT EXISTS (SELECT 1 
                    FROM %(table)s x 
                    WHERE %(match)s)''' if checkIfExisting else '') + '''
  RETURNING %(returningCols)s
)
(''' + ('''
   SELECT %(x_returningCols)s
   FROM %(table)s x JOIN row_values v ON (%(match)s)
) UNION ( ''' if checkIfExisting else '') + '''
   SELECT %(returningCols)s
   FROM insertions
);''') %     {"table": table,
             "idCol": idCol,
             "newCols": ', '.join(newCols),
             "returningCols": ', '.join(returningCols),
             "x_returningCols": ', '.join('x.{0}'.format(c) for c in returningCols),
             "match": ' AND '.join('x.{0} {1} v.{0}'.format(col, comparisonOperator) 
                                for col in matchCols),
             "values": values
             }
        if TRACESQLFILE:
            with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> accession {0} table {1} sql length {2} row count {3}\n"
                         .format(self.accessionId, table, len(sql), len(data)))
                fh.write(sql)
        tableRows = self.execute(sql,commit=commit, close=False)

        if TRACESQLFILE:
            with io.open(TRACESQLFILE, "a", encoding='utf-8') as fh:
                fh.write("\n\n>>> accession {0} table {1} result row count {2}\n{3}\n"
                         .format(self.accessionId, table, len(tableRows), '\n'.join(str(r) for r in tableRows)))
        return tuple(tuple(None if colValue == "NULL" or colValue is None else
                           colTypeFunction[i](colValue)  # convert to int, datetime, etc
                           for i, colValue in enumerate(row))
                     for row in tableRows)
        
