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

'''

import os, io, re, time
from math import isnan, isinf
from pg8000 import DBAPI
from pg8000.errors import CursorClosedError, ConnectionClosedError
from arelle.ModelDtsObject import ModelConcept, ModelResource
from arelle.ModelValue import qname, datetime
from arelle.ValidateXbrlCalcs import roundValue
from arelle import XbrlConst

TRACESQLFILE = None
#TRACESQLFILE = r"c:\temp\sqltrace.log"  # uncomment to trace SQL on connection (very big file!!!)

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None,
                 rssItem=None):
    db = None
    try:
        db = XbrlPublicPostgresDatabaseConnection(modelXbrl, user, password, host, port, database)
        db.verifyTables()
        db.insertXbrl(rssItem=rssItem)
        db.close()
    except Exception as ex:
        if db is not None:
            try:
                db.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback    
    
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

class XPDBException(Exception):
    def __init__(self, code, message, **kwargs ):
        self.code = code
        self.message = message
        self.kwargs = kwargs
        self.args = ( self.__repr__(), )
    def __repr__(self):
        return _('[{0}] exception: {1}').format(self.code, self.message % self.kwargs)
            


class XbrlPublicPostgresDatabaseConnection():
    def __init__(self, modelXbrl, user, password, host, port, database):
        self.modelXbrl = modelXbrl
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        self.conn = DBAPI.connect(user=user, password=password, host=host, 
                                  port=int(port) if port else None, 
                                  database=database)
        self.tableColTypes = {}
        
    def close(self, rollback=False):
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
            raise XPDBException("xpDB:MissingTables",
                                _("The following tables are missing: %(missingTableNames)s"),
                                missingTableNames=', '.join(t for t in sorted(missingTables))) 
            
    def execute(self, sql, commit=False, close=True, fetch=True):
        cursor = self.cursor
        cursor.execute(sql)
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
            result = self.execute('DROP SEQUENCE %s' % sequence[0],
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
        for sql in sqlstatements:
            if 'CREATE TABLE' in sql or 'CREATE SEQUENCE' in sql:
                statusMsg, sep, rest = sql.strip().partition('\n')
                self.showStatus(statusMsg[0:50])
                result = self.execute(sql, close=False, commit=False, fetch=False)
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
                                              datetime if typename in ("date","timestamp") else  # ModelValue.datetime !!! not python class
                                              str))
                                             for name, fulltype in colTypes
                                             for typename in (fulltype.partition(' ')[0],))
        return self.tableColTypes[table]
    
    def getTable(self, table, idCol, newCols, matchCols, data, commit=False, comparisonOperator='='):
        # note: comparison by = will never match NULL fields
        # use 'IS NOT DISTINCT FROM' to match nulls, but this is not indexed and verrrrry slooooow
        if not data or not newCols or not matchCols:
            # nothing can be done, just return
            return () # place breakpoint here to debug
        returningCols = []
        if idCol: # idCol is the first returned column if present
            returningCols.append(idCol)
        for matchCol in matchCols:
            returningCols.append(matchCol)
        colTypeFunctions = self.columnTypeFunctions(table)
        try:
            colTypeCast = tuple(colTypeFunctions[colName][0] for colName in newCols)
            colTypeFunction = tuple(colTypeFunctions[colName][1] for colName in returningCols)
        except KeyError as err:
            raise XPDBException("xpDB:MissingColumnDefinition",
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
                    colValues.append("'" + str(col).replace("'","''").replace('%', '%%') + "'")
            if not rowValues:  # first row
                for i, cast in enumerate(colTypeCast):
                    if cast:
                        colValues[i] = colValues[i] + cast
            rowValues.append("(" + ", ".join(colValues) + ")")
        values = ", \n".join(rowValues)
        # insert new rows, return id and cols of new and existing rows
        # use IS NOT DISTINCT FROM instead of = to compare NULL usefully
        sql = '''
WITH row_values (%(newCols)s) AS (
  VALUES %(values)s
  ), insertions AS (
  INSERT INTO %(table)s (%(newCols)s)
  SELECT %(newCols)s
  FROM row_values v
  WHERE NOT EXISTS (SELECT 1 
                    FROM %(table)s x 
                    WHERE %(match)s)
  RETURNING %(returningCols)s
)
(  SELECT %(x_returningCols)s
   FROM %(table)s x JOIN row_values v ON (%(match)s)
) UNION ( 
   SELECT %(returningCols)s
   FROM insertions
);''' %     {"table": table,
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
        return tuple(tuple(None if colValue == "NULL" or colValue is None else
                           colTypeFunction[i](colValue)  # convert to int, datetime, etc
                           for i, colValue in enumerate(row))
                     for row in tableRows)
        
    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)
            
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
                                  ('accepted_timestamp', 'entity_id', 'filing_accession_number'), 
                                  ((rssItem.acceptanceDatetime,
                                    True,
                                    rssItem.filingDate,
                                    rssItem.cikNumber,
                                    rssItem.companyName,
                                    self.modelXbrl.modelDocument.creationSoftwareComment,
                                    rssItem.assignedSic,
                                    rssItem.htmlUrl,
                                    rssItem.url,
                                    rssItem.accessionNumber),))
            for id, timestamp, cik, accessionNbr in table:
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
                              ('uri',), 
                              tuple((uri,) 
                                    for uri in uris))
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
                              ('namespace', 'local_name'), 
                              tuple((qn.namespaceURI, qn.localName) 
                                    for qn in qnames))
        self.qnameId = dict((qname(ns, ln), id)
                            for id, ns, ln in table)
                     
    def insertNamespaces(self):
        self.showStatus("insert namespaces")
        table = self.getTable('namespace', 'namespace_id', 
                              ('uri', 'is_base', 'taxonomy_version_id'), 
                              ('uri',), 
                              tuple((uri, True, 0) 
                                    for uri in self.disclosureSystem.baseTaxonomyNamespaces))
        self.namespaceId = dict((uri, id)
                                for id, uri in table)
        
    def insertDocuments(self):
        self.showStatus("insert documents")
        table = self.getTable('document', 'document_id', 
                              ('document_uri',), 
                              ('document_uri',), 
                              tuple((docUri,) 
                                    for docUri in self.modelXbrl.urlDocs.keys()))
        self.documentIds = dict((uri, id)
                                for id, uri in table)
        
    def insertCustomArcroles(self):
        self.showStatus("insert arcrole types")
        arcroleTypesByIds = dict(((self.documentIds[arcroleType.modelDocument.uri],
                                   self.uriId[arcroleType.arcroleURI]), # key on docId, uriId
                                  arcroleType) # value is roleType object
                                 for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                 for arcroleType in arcroleTypes)
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
                              for roleType in roleTypes)
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
        table = self.getTable('element', 'element_id', 
                              ('qname_id', 'datatype_qname_id', 'xbrl_base_datatype_qname_id', 'balance_id',
                               'period_type_id', 'substitution_group_qname_id', 'abstract', 'nillable',
                               'document_id', 'is_numeric', 'is_monetary'), 
                              ('qname_id',), 
                              tuple((self.qnameId[concept.qname],
                                     self.qnameId.get(concept.typeQname), # may be None
                                     self.qnameId.get(concept.baseXbrliTypeQname), # may be None
                                     {'debit':1, 'credit':2, None:None}[concept.balance],
                                     {'instant':1, 'duration':2, 'forever':3, None:0}[concept.periodType],
                                     self.qnameId.get(concept.substitutionGroupQname), # may be None
                                     concept.isAbstract, 
                                     concept.isNillable,
                                     self.documentIds[concept.modelDocument.uri],
                                     concept.isNumeric,
                                     concept.isMonetary)
                                    for concept in self.modelXbrl.qnameConcepts.values()))
        self.elementId = dict((qnameId, id)  # indexed by qnameId, not by qname value
                              for id, qnameId in table)
        
    def insertResources(self):
        self.showStatus("insert resources")
        table = self.getTable('resource', 'resource_id', 
                              ('role_uri_id', 'qname_id', 'document_id', 'document_line_number', 'document_column_number'), 
                              ('role_uri_id', 'qname_id', 'document_id', 'document_line_number', 'document_column_number'), 
                              tuple((self.uriId[resource.role],
                                     self.qnameId[resource.qname],
                                     self.documentIds[resource.modelDocument.uri],
                                     resource.sourceline,
                                     0)
                                    for arcrole in (XbrlConst.conceptLabel, XbrlConst.conceptReference)
                                    for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships
                                    for resource in (rel.fromModelObject, rel.toModelObject)
                                    if isinstance(resource, ModelResource)))
        self.resourceId = dict(((roleId, qnId, docId, line, offset), id)
                               for id, roleId, qnId, docId, line, offset in table)
    
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
                if rel not in visited:
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

        def conceptId(concept):
            if isinstance(concept, ModelConcept):
                self.elementId.get(self.qnameId.get(concept.qname))
            else:
                return None            
        def resourceId(resource):
            if isinstance(resource, ModelResource):
                return self.resourceId.get((self.uriId[resource.role],
                                            self.qnameId[resource.qname],
                                            self.documentIds[resource.modelDocument.uri],
                                            resource.sourceline, 0))
            else:
                return 0            
        
        table = self.getTable('relationship', 'relationship_id', 
                              ('network_id', 'from_element_id', 'to_element_id', 'reln_order', 
                               'from_resource_id', 'to_resource_id', 'calculation_weight', 
                               'tree_sequence', 'tree_depth', 'preferred_label_role_uri_id'), 
                              ('network_id', 'tree_sequence'), 
                              tuple((networkId,
                                     conceptId(rel.fromModelObject.qname), # may be None
                                     conceptId(rel.toModelObject.qname), # may be None
                                     dbNum(rel.order),
                                     resourceId(rel.fromModelObject.qname), # may be None
                                     resourceId(rel.toModelObject.qname), # may be None
                                     dbNum(rel.weight), # none if no weight
                                     sequence,
                                     depth,
                                     self.qnameId.get(rel.preferredLabel))
                                    for rel, sequence, depth, networkId in dbRels))

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
                               dim.typedMember.innerText if dim.isTyped else None))
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
                                     self.elementId.get(self.qnameId.get(fact.qname)),
                                     roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric else None,
                                     fact.value,
                                     fact.id,
                                     fact.xAttributes['precision'].xValue if ('precision' in fact.xAttributes and isinstance(fact.xAttributes['precision'].xValue,int)) else None,
                                     fact.xAttributes['decimals'].xValue if ('decimals' in fact.xAttributes and isinstance(fact.xAttributes['decimals'].xValue,int)) else None,
                                     'precision' in fact.xAttributes and fact.xAttributes['precision'].xValue == 'INF',
                                     'decimals' in fact.xAttributes and fact.xAttributes['decimals'].xValue == 'INF',
                                     )
                                    for fact in self.modelXbrl.facts))
        # hashes
