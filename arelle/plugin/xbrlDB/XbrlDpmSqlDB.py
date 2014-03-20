'''
XbrlDpmEbaDB.py implements an SQL database interface for Arelle, based
on the DPM EBA database.  This is a semantic data points modeling 
representation of EBA's XBRL information architecture. 

This module may save directly to a Postgres, MySQL, SEQLite, MSSQL, or Oracle server.

This module provides the execution context for saving a dts and instances in 
XBRL SQL database.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

Example dialog or command line parameters for operation:

    host:  the supporting host for SQL Server
    port:  the host port of server
    user, password:  if needed for server
    database:  the top level path segment for the SQL Server
    timeout: 
    

(c) Copyright 2014 Mark V Systems Limited, California US, All rights reserved.  
Mark V copyright applies to this software, which is licensed according to the terms of Arelle(r).


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

import time, datetime, logging
from arelle.ModelDocument import Type
from arelle.ModelDtsObject import ModelConcept, ModelType, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl
from arelle.ModelDocument import ModelDocument
from arelle.ModelValue import (qname, qnameEltPfxName, qnameClarkName, 
                               dateTime, DATE, DATETIME, DATEUNION)
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlValidate import UNVALIDATED, VALID
from arelle.XmlUtil import elementFragmentIdentifier, xmlstring
from arelle import XbrlConst
from arelle.UrlUtil import ensureUrl
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from .tableFacts import tableFacts
from .primaryDocumentFacts import loadPrimaryDocumentFacts
from collections import defaultdict
from decimal import Decimal, InvalidOperation

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None):
    xbrlDbConn = None
    try:
        xbrlDbConn = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
        xbrlDbConn.verifyTables()
        xbrlDbConn.insertXbrl(rssItem=rssItem)
        xbrlDbConn.close()
    except Exception as ex:
        if xbrlDbConn is not None:
            try:
                xbrlDbConn.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback    
    
def isDBPort(host, port, timeout=10, product="postgres"):
    return isSqlConnection(host, port, timeout)

XBRLDBTABLES = {
                "dAvailableTable", "dCloseTableFact", "dOpenTableSheetsRow",
                "dProcessingContext", "dProcessingFact"
                }



class XbrlSqlDatabaseConnection(SqlDbConnection):
    def verifyTables(self):
        missingTables = XBRLDBTABLES - self.tablesInDB()
        if missingTables and missingTables != {"sequences"}:
            raise XPDBException("sqlDB:MissingTables",
                                _("The following tables are missing: %(missingTableNames)s"),
                                missingTableNames=', '.join(t for t in sorted(missingTables))) 
            
    def insertXbrl(self, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)
            
            # must have a valid XBRL instance or document
            if self.modelXbrl.modelDocument is None:
                raise XPDBException("xpgDB:MissingXbrlDocument",
                                    _("No XBRL instance or schema loaded for this filing.")) 
            
            # at this point we determine what's in the database and provide new tables
            # requires locking most of the table structure
            self.lockTables(("dAvailableTable", "dCloseFactTable", "dOpenTableSheetsRow",
                             "dProcessingContext", "dProcessingFact"))
            
            self.dropTemporaryTable()
 
            startedAt = time.time()
            self.insertInstance()
            self.insertDataPoints()
            self.modelXbrl.profileStat(_("XbrlSqlDB: instance insertion"), time.time() - startedAt)
            
            startedAt = time.time()
            self.showStatus("Committing entries")
            self.commit()
            self.modelXbrl.profileStat(_("XbrlSqlDB: insertion committed"), time.time() - startedAt)
            self.showStatus("DB insertion completed", clearAfter=5000)
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise
    
    def insertInstance(self):
        now = datetime.datetime.now()
        entityCode = periodInstantDate = None
        for cntx in self.modelXbrl.contexts.values():
            if cntx.isInstantPeriod:
                entityCode = cntx.entityIdentifier[1]
                periodInstantDate = cntx.endDatetime.date() - datetime.timedelta(1)  # convert to end date
        table = self.getTable('Instance', 'InstanceID', 
                              ('ModuleID', 'FileName', 'CompressedFileBlob',
                               'Date', 'EntityCode', 'EntityName', 'Period',
                               'EntityInternalName', 'EntityCurrency'), 
                              ('ModuleID',), 
                              ((int(time.time()),
                                self.modelXbrl.uri,
                                None,
                                now,
                                entityCode, 
                                None, 
                                periodInstantDate, 
                                None, 
                                None
                                ),),
                              checkIfExisting=True,
                              returnExistenceStatus=True)
        for id, moduleID, existenceStatus in table:
            self.instanceId = id
            self.instancePreviouslyInDB = existenceStatus
            break
 
    def insertDataPoints(self):
        instanceId = self.instanceId
        if self.instancePreviouslyInDB:
            self.showStatus("deleting prior data points of this report")
            # remove prior facts
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName("dCloseTableFact"), instanceId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName("dOpenTableSheetsRow"), instanceId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName("dProcessingContext"), instanceId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName("dProcessingFact"), instanceId), 
                         close=False, fetch=False)
        self.showStatus("insert data points")
        # contexts
        def dimKey(cntx, typedDim=False):
            return '|'.join(sorted("{}({})".format(dim.dimensionQname,
                                                   dim.memberQname if dim.isExplicit 
                                                   else xmlstring(dim.typedMember, stripXmlns=True) if typedDim
                                                   else '*' )
                                   for dim in cntx.qnameDims.values()))
        contextSortedDims = dict((cntx.id, dimKey(cntx))
                                 for cntx in self.modelXbrl.contexts.values()
                                 if cntx.qnameDims)
        
        def met(fact):
            return "MET({})".format(fact.qname)
        
        def metDimKey(fact):
            key = met(fact)
            if fact.contextID in contextSortedDims:
                key += '|' + contextSortedDims[fact.contextID]
            return key
            
        table = self.getTable("dProcessingContext", None,
                              ('InstanceID', 'ContextID', 'SortedDimensions', 'NotValid'),
                              ('InstanceID', 'ContextID'),
                              tuple((instanceId,
                                     cntxID,
                                     cntxDimKey,
                                     False
                                     )
                                    for cntxID, cntxDimKey in contextSortedDims.items()))
        
        # contexts with typed dimensions
        
        # dCloseFactTable
        dCloseTableFacts = []
        dProcessingFacts = []
        dFacts = []
        for f in self.modelXbrl.factsInInstance:
            cntx = f.context
            concept = f.concept
            isNumeric = isBool = isDateTime = isText = False
            if concept is not None:
                if concept.isNumeric:
                    isNumeric = True
                else:
                    baseXbrliType = concept.baseXbrliType
                    if baseXbrliType == "booleanItemType":
                        isBool = True
                    elif baseXbrliType == "dateTimeItemType": # also is dateItemType?
                        isDateTime = True
                xValue = f.xValue
            else:
                if f.isNil:
                    xValue = None
                else:
                    xValue = f.value
                    c = f.qname.localName[0]
                    if c == 'm':
                        isNumeric = True
                        # not validated, do own xValue
                        try:
                            xValue = Decimal(xValue)
                        except InvalidOperation:
                            xValue = Decimal('NaN')
                    elif c == 'd':
                        isDateTime = True
                        try:
                            xValue = dateTime(xValue, type=DATEUNION, castException=ValueError)
                        except ValueError:
                            pass
                    elif c == 'b':
                        isBool = True
                        xValue = xValue.strip()
                        if xValue in ("true", "1"):  
                            xValue = True
                        elif xValue in ("false", "0"): 
                            xValue = False
                
            isText = not (isNumeric or isBool or isDateTime)
            if cntx is not None:
                if any(dim.isTyped for dim in cntx.qnameDims.values()):
                    # typed dim in fact
                    dFacts.append((f.decimals,
                                   # factID auto generated (?)
                                   None,
                                   metDimKey(f),
                                   instanceId,
                                   cntx.entityIdentifier[1],
                                   cntx.endDatetime.date() - datetime.timedelta(1),
                                   f.unitID,
                                   xValue if isNumeric else None,
                                   xValue if isDateTime else None,
                                   xValue if isBool else None,
                                   xValue if isText else None
                                   ))
                else:
                    # no typed dim in fact
                    dFacts.append((f.decimals,
                                   # factID auto generated (?)
                                   None,
                                   metDimKey(f),
                                   instanceId,
                                   cntx.entityIdentifier[1],
                                   cntx.endDatetime.date() - datetime.timedelta(1),
                                   f.unitID,
                                   xValue if isNumeric else None,
                                   xValue if isDateTime else None,
                                   xValue if isBool else None,
                                   xValue if isText else None
                                   ))
                    dCloseTableFacts.append((instanceId,
                                              metDimKey(f),
                                              f.unitID,
                                              f.decimals,
                                              xValue if isNumeric else None,
                                              xValue if isDateTime else None,
                                              xValue if isBool else None,
                                              xValue if isText else None,
                                              None
                                              ))
                dProcessingFacts.append((instanceId,
                                         met(f),
                                         cntx.id,
                                         f.value,
                                         f.decimals,
                                         cntx.endDatetime.date() - datetime.timedelta(1),
                                         None))
        table = self.getTable("Fact", "FactID",
                              ("Decimals", "VariableID", "DataPointKey",
                               "InstanceID", "EntityID", "DatePeriodEnd", "Unit",
                               'NumericValue', 'DateTimeValue', 'BoolValue', 'TextValue'),
                              ("InstanceID", ),
                              dFacts)
        table = self.getTable("dCloseTableFact", None,
                              ('InstanceID', 'MetricDimMem', 'Unit', 'Decimals',
                               'NumericValue', 'DateTimeValue', 'BoolValue', 'TextValue',
                               'InstanceIdMetricDimMemHash'),
                              ('InstanceID', ),
                              dCloseTableFacts)
        table = self.getTable("dProcessingFact", None,
                              ('InstanceID', 'Metric', 'ContextID', 
                               'ValueTxt', 'ValueDecimal', 'ValueDate',
                               'Error'),
                              ('InstanceID', ),
                              dProcessingFacts)

