'''
XbrlPublicPostgresDB.py implements a relational database interface for Arelle, based
on the XBRL US Public Database.  The database schema is described by "XBRL US Public Database",
published by XBRL US, 2011.  This is a syntactic representation of XBRL information. 

This module provides the execution context for saving a dts and assession in 
XBRL Public Database Tables.  It may be loaded by Arelle'sRSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).
and does not apply to the XBRL US Database schema and description.

The XBRL US Database schema and description is (c) Copyright XBRL US 2011, The 
resulting database may contain data from SEC interactive data filings (or any other XBRL
instance documents and DTS) in a relational model. Mark V Systems conveys neither 
rights nor license for the database schema.
 
The XBRL US Database and this code is intended for Postgres.  XBRL-US uses Postgres 8.4, 
Arelle uses 9.1, via Python DB API 2.0 interface, using the pg8000 library.

Information for the 'official' XBRL US-maintained database (this schema, containing SEC filings):
    Database Name: edgar_db 
    Database engine: Postgres version 8.4 
    \Host: public.xbrl.us 
    Port: 5432

to use from command line:

linux
   # be sure plugin is installed
   arelleCmdLine --plugin '+xbrlDB|show'
   arelleCmdLine -f http://sec.org/somewhere/some.rss -v --store-to-XBRL-DB 'myserver.com,portnumber,pguser,pgpasswd,database,timeoutseconds'
   
windows
   rem be sure plugin is installed
   arelleCmdLine --plugin "+xbrlDB|show"
   arelleCmdLine -f http://sec.org/somewhere/some.rss -v --store-to-XBRL-DB "myserver.com,portnumber,pguser,pgpasswd,database,timeoutseconds"

'''

import os, sys, io, re, time, datetime
from math import isnan, isinf
from pg8000 import DBAPI
from pg8000.errors import CursorClosedError, ConnectionClosedError, InterfaceError, ProgrammingError
import socket
from arelle.ModelDocument import Type
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.ModelValue import qname, dateTime
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlUtil import elementFragmentIdentifier
from arelle import UrlUtil, XbrlConst

TRACESQLFILE = None
#TRACESQLFILE = r"c:\temp\sqltrace.log"  # uncomment to trace SQL on connection (very big file!!!)

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 rssItem=None):
    xpgdb = None
    try:
        xpgdb = XbrlPostgresDatabaseConnection(modelXbrl, user, password, host, port, database, timeout)
        xpgdb.verifyTables()
        xpgdb.insertXbrl(rssItem=rssItem)
        xpgdb.close()
    except Exception as ex:
        if xpgdb is not None:
            try:
                xpgdb.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback    
    
def isDBPort(host, port, timeout=10):
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
    
XBRLDBTABLES = {
                "fact", "fact_aug",
                "entity",
                "entity_name_history",
                "unit", "unit_measure", 
                "context", "context_aug", "context_dimension",
                "accession", "accession_document_association", "accession_element", "accession_timestamp",
                "attribute_value",
                "custom_role_type",
                "uri",
                "document",
                "qname",
                "taxonomy", "taxonomy_version", "namespace",
                "element", "element_attribute", "element_attribute_value_association",
                "network", "relationship",
                "custom_arcrole_type", "custom_arcrole_used_on", "custom_role_used_on",
                "label_resource",
                "reference_part", "reference_part_type", "reference_resource",
                "resource",
                "enumeration_arcrole_cycles_allowed",
                "enumeration_element_balance",
                "enumeration_element_period_type",
                "enumeration_unit_measure_location",
                "industry", "industry_level",
                "industry_structure",
                "query_log",
                "sic_code", 
                }

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

class XPDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)
            


class XbrlPostgresDatabaseConnection():
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
        
    def verifyTables(self):
        missingTables = XBRLDBTABLES - self.tablesInDB()
        # if no tables, initialize database
        if missingTables == XBRLDBTABLES:
            self.create()
            missingTables = XBRLDBTABLES - self.tablesInDB()
        if missingTables:
            raise XPDBException("xpgDB:MissingTables",
                                _("The following tables are missing: %(missingTableNames)s"),
                                missingTableNames=', '.join(t for t in sorted(missingTables))) 
            
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
            if cursor.rowcount > 0:
                cursor.fetchall()  # must get anyway
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
        
    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)
                        
            # find pre-existing documents in server database
            self.identifyPreexistingDocuments()
            self.identifyConceptsUsed()
            
            startedAt = time.time()
            self.insertAccession(rssItem)
            self.insertUris()
            self.insertQnames()
            self.insertNamespaces()
            self.insertDocuments()
            self.insertCustomArcroles()
            self.insertCustomRoles()
            self.insertElements()
            self.insertResources()
            self.insertNetworks()
            self.modelXbrl.profileStat(_("XbrlPublicDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertFacts()
            self.modelXbrl.profileStat(_("XbrlPublicDB: instance insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.showStatus("Committing entries")
            self.commit()
            self.modelXbrl.profileStat(_("XbrlPublicDB: insertion committed"), time.time() - startedAt)
            self.showStatus("DB insertion completed", clearAfter=5000)
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise
        
    def insertAccession(self, rssItem):
        if rssItem is None:
            self.accessionId = int(time.time())    # only available if entered from an SEC filing
        else:
            self.accessionId = "(TBD)"
            self.showStatus("insert accession")
            table = self.getTable('accession', 'accession_id', 
                                  ('accepted_timestamp', 'is_most_current', 'filing_date','entity_id', 
                                   'entity_name', 'creation_software', 'standard_industrial_classification', 
                                   'sec_html_url', 'entry_url', 'filing_accession_number'), 
                                  ('filing_accession_number',), 
                                  ((rssItem.acceptanceDatetime,
                                    True,
                                    rssItem.filingDate or datetime.datetime.min,  # NOT NULL
                                    rssItem.cikNumber or 0,  # NOT NULL
                                    rssItem.companyName,
                                    self.modelXbrl.modelDocument.creationSoftwareComment,
                                    rssItem.assignedSic or -1,  # NOT NULL
                                    rssItem.htmlUrl,
                                    rssItem.url,
                                    rssItem.accessionNumber or 'UNKNOWN'  # NOT NULL
                                    ),),
                                  checkIfExisting=True)
            for id, filing_accession_number in table:
                self.accessionId = id
                break
        
    def insertUris(self):
        uris = (_DICT_SET(self.modelXbrl.namespaceDocs.keys()) |
                _DICT_SET(self.modelXbrl.arcroleTypes.keys()) |
                _DICT_SET(XbrlConst.standardArcroleCyclesAllowed.keys()) |
                _DICT_SET(self.modelXbrl.roleTypes.keys()) |
                XbrlConst.standardRoles)
        self.showStatus("insert uris")
        table = self.getTable('uri', 'uri_id', 
                              ('uri',), 
                              ('uri',), # indexed match cols
                              tuple((uri,) 
                                    for uri in uris),
                              checkIfExisting=True)
        self.uriId = dict((uri, id)
                          for id, uri in table)
                     
    def insertQnames(self):
        qnames = (_DICT_SET(self.modelXbrl.qnameConcepts.keys()) |
                  _DICT_SET(self.modelXbrl.qnameAttributes.keys()) |
                  _DICT_SET(self.modelXbrl.qnameTypes.keys()) |
                  set(measure
                      for unit in self.modelXbrl.units.values()
                      for measures in unit.measures
                      for measure in measures))
        self.showStatus("insert qnames")
        table = self.getTable('qname', 'qname_id', 
                              ('namespace', 'local_name'), 
                              ('namespace', 'local_name'), # indexed match cols
                              tuple((qn.namespaceURI, qn.localName) 
                                    for qn in qnames),
                              checkIfExisting=True)
        self.qnameId = dict((qname(ns, ln), id)
                            for id, ns, ln in table)
                     
    def insertNamespaces(self):
        self.showStatus("insert namespaces")
        if self.disclosureSystem.baseTaxonomyNamespaces:
            # use only base taxonomy namespaces in disclosure system
            namespaceUris = self.disclosureSystem.baseTaxonomyNamespaces
        else:
            # use all namespace URIs
            namespaceUris = self.modelXbrl.namespaceDocs.keys()
        table = self.getTable('namespace', 'namespace_id', 
                              ('uri', 'is_base', 'taxonomy_version_id', 'prefix'), 
                              ('uri',), # indexed matchcol
                              tuple((uri, True, 0, self.disclosureSystem.standardPrefixes.get(uri,None)) 
                                    for uri in namespaceUris),
                              checkIfExisting=True)
        self.namespaceId = dict((uri, id)
                                for id, uri in table)
        
    def identifyPreexistingDocuments(self):
        self.existingDocumentIds = {}
        docUris = set()
        for modelDocument in self.modelXbrl.urlDocs.values():
            if modelDocument.type == Type.SCHEMA:
                docUris.add(dbStr(modelDocument.uri))
        if docUris:
            results = self.execute("SELECT document_id, document_uri FROM document WHERE document_uri IN (" +
                                   ', '.join(docUris) + ");")
            self.existingDocumentIds = dict((docUri,docId) for docId, docUri in results)
        
    def identifyConceptsUsed(self):
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]

        
        conceptsUsed = set(f.qname for f in self.modelXbrl.factsInInstance)
        
        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                conceptsUsed.add(dim.dimensionQname)
                if dim.isExplicit:
                    conceptsUsed.add(dim.memberQname)
                else:
                    conceptsUsed.add(dim.typedMember.qname)
        for defaultDim, defaultDimMember in self.modelXbrl.qnameDimensionDefaults.items():
            conceptsUsed.add(defaultDim)
            conceptsUsed.add(defaultDimMember)
        for relationshipSetKey in self.relationshipSets:
            relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
            for rel in relationshipSet.modelRelationships:
                if isinstance(rel.fromModelObject, ModelConcept):
                    conceptsUsed.add(rel.fromModelObject)
                if isinstance(rel.toModelObject, ModelConcept):
                    conceptsUsed.add(rel.toModelObject)
        for qn in (XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit):
            conceptsUsed.add(self.modelXbrl.qnameConcepts[qn])
        
        conceptsUsed -= {None}  # remove None if in conceptsUsed
        self.conceptsUsed = conceptsUsed
        
    def insertDocuments(self):
        self.showStatus("insert documents")
        table = self.getTable('document', 'document_id', 
                              ('document_uri',), 
                              ('document_uri',), 
                              set((docUri,) 
                                  for docUri in self.modelXbrl.urlDocs.keys()
                                  if docUri not in self.existingDocumentIds),
                              checkIfExisting=True)
        self.documentIds = dict((uri, id)
                                for id, uri in table)
        self.documentIds.update(self.existingDocumentIds)
        table = self.getTable('accession_document_association', 'accession_document_association_id', 
                              ('accession_id','document_id'), 
                              ('document_id',), 
                              tuple((self.accessionId, docId) 
                                    for docId in self.documentIds.values()))
        
    def insertCustomArcroles(self):
        self.showStatus("insert arcrole types")
        arcroleTypesByIds = dict(((self.documentIds[arcroleType.modelDocument.uri],
                                   self.uriId[arcroleType.arcroleURI]), # key on docId, uriId
                                  arcroleType) # value is roleType object
                                 for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                 for arcroleType in arcroleTypes
                                 if arcroleType.modelDocument.uri not in self.existingDocumentIds)
        table = self.getTable('custom_arcrole_type', 'custom_arcrole_type_id', 
                              ('document_id', 'uri_id', 'definition', 'cycles_allowed'), 
                              ('document_id', 'uri_id'), 
                              tuple((arcroleTypeIDs[0], # doc Id
                                     arcroleTypeIDs[1], # uri Id
                                     arcroleType.definition, 
                                     {'any':1, 'undirected':2, 'none':3}[arcroleType.cyclesAllowed])
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()))
        table = self.getTable('custom_arcrole_used_on', 'custom_arcrole_used_on_id', 
                              ('custom_arcrole_type_id', 'qname_id'), 
                              ('custom_arcrole_type_id', 'qname_id'), 
                              tuple((id, self.qnameId[usedOn])
                                    for id, docid, uriid in table
                                    for usedOn in arcroleTypesByIds[(docid,uriid)].usedOns))
        
    def insertCustomRoles(self):
        self.showStatus("insert role types")
        roleTypesByIds = dict(((self.documentIds[roleType.modelDocument.uri],
                                self.uriId[roleType.roleURI]), # key on docId, uriId
                               roleType) # value is roleType object
                              for roleTypes in self.modelXbrl.roleTypes.values()
                              for roleType in roleTypes
                              if roleType.modelDocument.uri not in self.existingDocumentIds)
        table = self.getTable('custom_role_type', 'custom_role_type_id', 
                              ('document_id', 'uri_id', 'definition'), 
                              ('document_id', 'uri_id'), 
                              tuple((roleTypeIDs[0], # doc Id
                                     roleTypeIDs[1], # uri Id
                                     roleType.definition) 
                                    for roleTypeIDs, roleType in roleTypesByIds.items()))
        table = self.getTable('custom_role_used_on', 'custom_role_used_on_id', 
                              ('custom_role_type_id', 'qname_id'), 
                              ('custom_role_type_id', 'qname_id'), 
                              tuple((id, self.qnameId[usedOn])
                                    for id, docid, uriid in table
                                    for usedOn in roleTypesByIds[(docid,uriid)].usedOns))
        
    def insertElements(self):
        self.showStatus("insert elements")
        
        filingDocumentConcepts = set()
        existingDocumentUsedConcepts = set()
        for concept in self.modelXbrl.qnameConcepts.values():
            if concept.modelDocument.uri not in self.existingDocumentIds:
                filingDocumentConcepts.add(concept)
            elif concept in self.conceptsUsed:
                existingDocumentUsedConcepts.add(concept)
                
        table = self.getTable('element', 'element_id', 
                              ('qname_id', 'datatype_qname_id', 'xbrl_base_datatype_qname_id', 'balance_id',
                               'period_type_id', 'substitution_group_qname_id', 'abstract', 'nillable',
                               'document_id', 'is_numeric', 'is_monetary'), 
                              ('qname_id',), 
                              tuple((self.qnameId[concept.qname],
                                     self.qnameId.get(concept.typeQname), # may be None
                                     self.qnameId.get(concept.baseXbrliTypeQname
                                                      if not isinstance(concept.baseXbrliTypeQname, list)
                                                      else concept.baseXbrliTypeQname[0]
                                                      ), # may be None or may be a list for a union
                                     {'debit':1, 'credit':2, None:None}[concept.balance],
                                     {'instant':1, 'duration':2, 'forever':3, None:0}[concept.periodType],
                                     self.qnameId.get(concept.substitutionGroupQname), # may be None
                                     concept.isAbstract, 
                                     concept.isNillable,
                                     self.documentIds[concept.modelDocument.uri],
                                     concept.isNumeric,
                                     concept.isMonetary)
                                    for concept in filingDocumentConcepts)
                             )
        self.elementId = dict((qnameId, elementId)  # indexed by qnameId, not by qname value
                              for elementId, qnameId in table)
        
        # get existing element IDs
        if existingDocumentUsedConcepts:
            conceptQnameIds = []
            for concept in existingDocumentUsedConcepts:
                conceptQnameIds.append(str(self.qnameId[concept.qname]))
            results = self.execute("SELECT element_id, qname_id FROM element WHERE qname_id IN (" +
                                   ', '.join(conceptQnameIds) + ");")
            for elementId, qnameId in results:
                self.elementId[qnameId] = elementId
        
    def conceptElementId(self, concept):
        if isinstance(concept, ModelConcept):
            return self.elementId.get(self.qnameId.get(concept.qname))
        else:
            return None 
                   
    def insertResources(self):
        self.showStatus("insert resources")
        # deduplicate resources (may be on multiple arcs)
        # note that lxml has no column numbers, use objectIndex as pseudo-column number
        uniqueResources = dict(((self.documentIds[resource.modelDocument.uri],
                                 resource.sourceline,
                                 resource.objectIndex), resource)
                               for arcrole in (XbrlConst.conceptLabel, XbrlConst.conceptReference)
                               for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships
                               if rel.fromModelObject is not None and rel.toModelObject is not None
                               for resource in (rel.fromModelObject, rel.toModelObject)
                               if isinstance(resource, ModelResource))
        table = self.getTable('resource', 'resource_id', 
                              ('role_uri_id', 'qname_id', 'document_id', 'document_line_number', 'document_column_number'), 
                              ('document_id', 'document_line_number', 'document_column_number'), 
                              tuple((self.uriId[resource.role],
                                     self.qnameId[resource.qname],
                                     self.documentIds[resource.modelDocument.uri],
                                     resource.sourceline,
                                     resource.objectIndex)
                                    for resource in uniqueResources.values()),
                              checkIfExisting=True)
        self.resourceId = dict(((docId, line, offset), id)
                               for id, docId, line, offset in table)
        
        self.showStatus("insert labels")
        table = self.getTable('label_resource', 'resource_id', 
                              ('resource_id', 'label', 'xml_lang'), 
                              ('resource_id',), 
                              tuple((self.resourceId[self.documentIds[resource.modelDocument.uri],
                                                     resource.sourceline,
                                                     resource.objectIndex],
                                     resource.textValue,
                                     resource.xmlLang)
                                    for arcrole in (XbrlConst.conceptLabel, XbrlConst.conceptReference)
                                    for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships
                                    if rel.fromModelObject is not None and rel.toModelObject is not None
                                    for resource in (rel.fromModelObject, rel.toModelObject)
                                    if isinstance(resource, ModelResource) and XbrlConst.isLabelRole(resource.role)),
                              checkIfExisting=True)
    
    def insertNetworks(self):
        self.showStatus("insert networks")
        table = self.getTable('network', 'network_id', 
                              ('accession_id', 'extended_link_qname_id', 'extended_link_role_uri_id', 
                               'arc_qname_id', 'arcrole_uri_id', 'description'), 
                              ('accession_id', 'extended_link_qname_id', 'extended_link_role_uri_id', 
                               'arc_qname_id', 'arcrole_uri_id'), 
                              tuple((self.accessionId,
                                     self.qnameId[linkqname],
                                     self.uriId[ELR],
                                     self.qnameId[arcqname],
                                     self.uriId[arcrole],
                                     None if ELR in XbrlConst.standardRoles else
                                     self.modelXbrl.roleTypes[ELR][0].definition)
                                    for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                    if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")))
        self.networkId = dict(((accId, linkQnId, linkRoleId, arcQnId, arcRoleId), id)
                              for id, accId, linkQnId, linkRoleId, arcQnId, arcRoleId in table)
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        dbRels = []
        
        def walkTree(rels, seq, depth, relationshipSet, visited, dbRels, networkId):
            for rel in rels:
                if rel not in visited and rel.toModelObject is not None:
                    visited.add(rel)
                    dbRels.append((rel, seq, depth, networkId))
                    seq += 1
                    seq = walkTree(relationshipSet.fromModelObject(rel.toModelObject), seq, depth+1, relationshipSet, visited, dbRels, networkId)
                    visited.remove(rel)
            return seq
        
        for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys():
            if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
                networkId = self.networkId[(self.accessionId,
                                            self.qnameId[linkqname],
                                            self.uriId[ELR],
                                            self.qnameId[arcqname],
                                            self.uriId[arcrole])]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), dbRels, networkId)

        def resourceResourceId(resource):
            if isinstance(resource, ModelResource):
                return self.resourceId.get((self.documentIds[resource.modelDocument.uri],
                                            resource.sourceline, 0))
            else:
                return None     
        
        table = self.getTable('relationship', 'relationship_id', 
                              ('network_id', 'from_element_id', 'to_element_id', 'reln_order', 
                               'from_resource_id', 'to_resource_id', 'calculation_weight', 
                               'tree_sequence', 'tree_depth', 'preferred_label_role_uri_id'), 
                              ('network_id', 'tree_sequence'), 
                              tuple((networkId,
                                     self.conceptElementId(rel.fromModelObject), # may be None
                                     self.conceptElementId(rel.toModelObject), # may be None
                                     dbNum(rel.order),
                                     resourceResourceId(rel.fromModelObject), # may be None
                                     resourceResourceId(rel.toModelObject), # may be None
                                     dbNum(rel.weight), # none if no weight
                                     sequence,
                                     depth,
                                     self.qnameId.get(rel.preferredLabel))
                                    for rel, sequence, depth, networkId in dbRels
                                    if rel.fromModelObject is not None and rel.toModelObject is not None))

    def insertFacts(self):
        accsId = self.accessionId
        self.showStatus("insert facts")
        # units
        table = self.getTable('unit', 'unit_id', 
                              ('accession_id', 'unit_xml_id'), 
                              ('accession_id', 'unit_xml_id'), 
                              tuple((accsId,
                                     unitId)
                                    for unitId in self.modelXbrl.units.keys()))
        self.unitId = dict(((_accsId, xmlId), id)
                           for id, _accsId, xmlId in table)
        # measures
        table = self.getTable('unit_measure', 'unit_measure_id', 
                              ('unit_id', 'qname_id', 'location_id'), 
                              ('qname_id', 'location_id'), 
                              tuple((self.unitId[(accsId,unit.id)],
                                     self.qnameId[measure],
                                     1 if (not unit.measures[1]) else (i + 1))
                                    for unit in self.modelXbrl.units.values()
                                    for i in range(2)
                                    for measure in unit.measures[i]))
        #table = self.getTable('enumeration_measure_location', 'enumeration_measure_location_id', 
        #                      ('description',), 
        #                      ('description',),
        #                      (('measure',), ('numerator',), ('denominator',)))
        # context
        table = self.getTable('context', 'context_id', 
                              ('accession_id', 'period_start', 'period_end', 'period_instant', 'specifies_dimensions', 'context_xml_id', 'entity_scheme', 'entity_identifier'), 
                              ('accession_id', 'context_xml_id'), 
                              tuple((accsId,
                                     cntx.startDatetime if cntx.isStartEndPeriod else None,
                                     cntx.endDatetime if cntx.isStartEndPeriod else None,
                                     cntx.instantDatetime if cntx.isInstantPeriod else None,
                                     bool(cntx.qnameDims),
                                     cntx.id,
                                     cntx.entityIdentifier[0],
                                     cntx.entityIdentifier[1])
                                    for cntx in self.modelXbrl.contexts.values()))
        self.cntxId = dict(((_accsId, xmlId), id)
                           for id, _accsId, xmlId in table)
        # context_dimension
        values = []
        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                values.append((self.cntxId[(accsId,cntx.id)],
                               self.qnameId[dim.dimensionQname],
                               self.qnameId.get(dim.memberQname), # may be None
                               self.qnameId.get(dim.typedMember.qname) if dim.isTyped else None,
                               False, # not default
                               dim.contextElement == "segment",
                               dim.typedMember.stringValue if dim.isTyped else None))
            for dimQname, memQname in self.modelXbrl.qnameDimensionDefaults.items():
                if dimQname not in cntx.qnameDims:
                    values.append((self.cntxId[(accsId,cntx.id)],
                                   self.qnameId[dimQname],
                                   self.qnameId[memQname],
                                   None,
                                   True, # is default
                                   True, # ambiguous and irrelevant for the XDT model
                                   None))
        table = self.getTable('context_dimension', 'context_dimension_id', 
                              ('context_id', 'dimension_qname_id', 'member_qname_id', 'typed_qname_id', 'is_default', 'is_segment', 'typed_text_content'), 
                              ('dimension_qname_id',), 
                              values)
        # facts
        table = self.getTable('fact', 'fact_id', 
                              ('accession_id', 'context_id', 'unit_id', 'element_id', 'effective_value', 'fact_value', 
                               'xml_id', 'precision_value', 'decimals_value', 
                               'is_precision_infinity', 'is_decimals_infinity', ), 
                              ('accession_id', 'context_id', 'unit_id', 'element_id', 'fact_value'), 
                              tuple((accsId,
                                     self.cntxId.get((accsId,fact.contextID)),
                                     self.unitId.get((accsId,fact.unitID)),
                                     self.conceptElementId(fact.concept),
                                     roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric else None,
                                     fact.value,
                                     elementFragmentIdentifier(fact),
                                     fact.xAttributes['precision'].xValue if ('precision' in fact.xAttributes and isinstance(fact.xAttributes['precision'].xValue,int)) else None,
                                     fact.xAttributes['decimals'].xValue if ('decimals' in fact.xAttributes and isinstance(fact.xAttributes['decimals'].xValue,int)) else None,
                                     'precision' in fact.xAttributes and fact.xAttributes['precision'].xValue == 'INF',
                                     'decimals' in fact.xAttributes and fact.xAttributes['decimals'].xValue == 'INF',
                                     )
                                    for fact in self.modelXbrl.facts))
        # hashes
