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
   
macOS
   # plug in installs dynamically
   
   # to store into DB from instance:
   arelleCmdLine -f "/Users/hermf/Documents/mvsl/projects/EIOPA/xbrt/13. XBRL Instance Documents/1_instance_md_ars_123456789.xbrl" --store-to-XBRL-DB ",,,,/Users/hermf/temp/DPM.db,90,sqliteDpmDB" --plugins xbrlDB
   
   # to load from DB and save to instance:
   arelleCmdLine -f "/Users/hermf/temp/instance_md_qrs_123456789.xbrl" --load-from-XBRL-DB ",,,,/Users/hermf/Documents/mvsl/projects/EIOPA/xbrt/3. DPM Database/DPM_DB/DPM_release_ver7_clean.db,90,sqliteDpmDB" --plugins xbrlDB

windows
   rem be sure plugin is installed
   arelleCmdLine --plugin "+xbrlDB|show"
   arelleCmdLine -f http://sec.org/somewhere/some.rss -v --store-to-XBRL-DB "myserver.com,portnumber,pguser,pgpasswd,database,timeoutseconds"

'''

import time, datetime, os, re
from collections import defaultdict
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle import Locale, ValidateXbrlDimensions
from arelle.ModelValue import qname, dateTime, DATEUNION, dateunionDate, DateTime
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlUtil import xmlstring, datetimeValue, DATETIME_MAXYEAR, dateunionValue, addChild, addQnameValue, addProcessingInstruction
from arelle import XbrlConst, XmlValidate
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from decimal import Decimal, InvalidOperation

qnFindFilingIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFindFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")
decimalsPattern = re.compile("^(-?[0-9]+|INF)$")

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, loadDBsaveToFile=None, loadInstanceId=None,
                 streamingState=None, streamedFacts=None,
                 **kwargs):
    if getattr(modelXbrl, "blockDpmDBrecursion", False):
        return None
    result = None
    xbrlDbConn = None
    try:
        if streamingState == "acceptFacts":
            # streaming mode, setup instance using context and dimensions
            xbrlDbConn = modelXbrl.streamingConnection
            if xbrlDbConn.instanceId is None:
                if not xbrlDbConn.insertInstanceToDB():
                    return False
            result = xbrlDbConn.insertDataPointsToDB()
        elif streamingState == "finish":
            xbrlDbConn = modelXbrl.streamingConnection
            xbrlDbConn.finishInsertXbrlToDB()
            del modelXbrl.streamingConnection # dereference in case of exception during closing
            xbrlDbConn.close()
        else:
            xbrlDbConn = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
            xbrlDbConn.verifyTables()
            if streamingState == "start":
                result = xbrlDbConn.startInsertXbrlToDB()
                modelXbrl.streamingConnection = xbrlDbConn
            elif loadDBsaveToFile:
                # load modelDocument from database saving to file
                result = xbrlDbConn.loadXbrlFromDB(loadDBsaveToFile, loadInstanceId)
                xbrlDbConn.close()
            else:
                # non-streaming complete insertion of XBRL document(s) to DB
                xbrlDbConn.insertXbrlToDB(rssItem=rssItem)
                xbrlDbConn.close()
                result = True
    except DpmDBException as ex:
        modelXbrl.error(ex.code, ex.message) # exception __repr__ includes message
        if xbrlDbConn is not None:
            try:
                xbrlDbConn.close(rollback=True)
            except Exception as ex2:
                pass
    except Exception as ex:
        if xbrlDbConn is not None:
            try:
                xbrlDbConn.close(rollback=True)
            except Exception as ex2:
                pass
        raise # reraise original exception with original traceback 
    return result   
    
def isDBPort(host, port, timeout=10, product="postgres"):
    return isSqlConnection(host, port, timeout)

XBRLDBTABLES = {
                "dAvailableTable", "dFact", "dFilingIndicator", "dInstance",
                # "dProcessingContext", "dProcessingFact",
                "mConcept", "mDomain", "mMember", "mModule", "mOwner", "mTemplateOrTable",
                }

EMPTYSET = set()

def dimValKey(cntx, typedDim=False, behaveAsTypedDims=EMPTYSET, restrictToDims=None):
    return '|'.join(sorted("{}({})".format(dim.dimensionQname,
                                           dim.memberQname if dim.isExplicit and dim not in behaveAsTypedDims
                                           else dim.memberQname if typedDim and not dim.isTyped
                                           else "nil" if typedDim and dim.typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1")
                                           else xmlstring(dim.typedMember, stripXmlns=True) if typedDim
                                           else '*' )
                           for dim in cntx.qnameDims.values()
                           if not restrictToDims or str(dim.dimensionQname) in restrictToDims))
def dimNameKey(cntx):
    return '|'.join(sorted("{}".format(dim.dimensionQname)
                           for dim in cntx.qnameDims.values()))

def met(fact):
    return "MET({})".format(fact.qname)

# key for use in dFact with * for dim that behaves as or is typed
def metDimAllKey(fact, behaveAsTypedDims=EMPTYSET):
    key = met(fact)
    cntx = fact.context
    if cntx.qnameDims:
        key += '|' + dimValKey(cntx, behaveAsTypedDims=behaveAsTypedDims)
    return key

# key for use in dFact only when there's a dim that behaves as or is typed
def metDimTypedKey(fact, behaveAsTypedDims=EMPTYSET):
    cntx = fact.context
    if True: # HF change: any(dimQname in behaveAsTypedDims for dimQname in cntx.qnameDims):
        key = met(fact) + '|' + dimValKey(cntx, typedDim=True, behaveAsTypedDims=behaveAsTypedDims)
        return key
    return None

# key for use in dAvailable where mem and typed values show up
def metDimValKey(cntx, typedDim=False, behaveAsTypedDims=EMPTYSET, restrictToDims=EMPTYSET):
    if "MET" in restrictToDims:
        key = "MET({})|".format(restrictToDims["MET"])
    else:
        key = ""
    key += dimValKey(cntx, typedDim=typedDim, behaveAsTypedDims=behaveAsTypedDims, restrictToDims=restrictToDims)
    return key
        
def metDimNameKey(fact, cntx):
    key = met(fact)
    if cntx.qnameDims:
        key += '|' + dimNameKey(cntx)
    return key

class DpmDBException(XPDBException):
    pass

class XbrlSqlDatabaseConnection(SqlDbConnection):
    def verifyTables(self):
        missingTables = XBRLDBTABLES - self.tablesInDB()
        if missingTables and missingTables != {"sequences"}:
            raise XPDBException("sqlDB:MissingTables",
                                _("The following tables are missing: %(missingTableNames)s"),
                                missingTableNames=', '.join(t for t in sorted(missingTables))) 
            
    def insertXbrlToDB(self, rssItem):
        try:
            self.startInsertXbrlToDB()
            self.insertInstanceToDB()
            self.insertDataPointsToDB()
            self.finishInsertXbrlToDB()
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise
        
    def startInsertXbrlToDB(self):
        self.instanceId = None; # instance not yet set up (streaming mode)
        
        # must also have default dimensions loaded
        from arelle import ValidateXbrlDimensions
        ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)
        
        # must have a valid XBRL instance or document
        if self.modelXbrl.modelDocument is None:
            raise DpmDBException("xpgDB:MissingXbrlDocument",
                                _("No XBRL instance or schema loaded for this filing.")) 
        
        # at this point we determine what's in the database and provide new tables
        # requires locking most of the table structure
        self.lockTables(("dAvailableTable", "dInstance",  "dFact", "dFilingIndicator",
                         # "dProcessingContext", "dProcessingFact"
                         ), isSessionTransaction=True)
        
        self.dropTemporaryTable()
        self.startedAt = time.time()
    
    def insertInstanceToDB(self):
        now = datetime.datetime.now()
        # find primary model taxonomy of instance
        self.modelXbrl.profileActivity()
        self.moduleId = None
        self.availableTableRows = defaultdict(set) # index (tableID, zDimVal) = set of yDimVals 
        self.dFilingIndicators = set()
        self.metricsForFilingIndicators = set()
        self.signaturesForFilingIndicators = defaultdict(list)

        _instanceSchemaRef = "(none)"
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            for refDoc, ref in self.modelXbrl.modelDocument.referencesDocument.items():
                if refDoc.inDTS and ref.referenceType == "href":
                    if self.moduleId is None:
                        _instanceSchemaRef = refDoc.uri
                        result = self.execute("SELECT ModuleID FROM mModule WHERE XBRLSchemaRef = '{}'"
                                              .format(refDoc.uri))
                        for moduleId in result:
                            self.moduleId = moduleId[0] # only column in row returned
                            break
                    else:
                        self.modelXbrl.error("sqlDB:multipeSchemaRefs",
                                             _("Loading XBRL DB: Multiple schema files referenced: %(schemaRef)s"),
                                             modelObject=self.modelXbrl, schemaRef=refDoc.uri)
        if not self.moduleId:
            raise DpmDBException("xpgDB:MissingModuleEntry",
                    _("A ModuleID could not be found in table mModule for instance schemaRef {0}.")
                    .format(_instanceSchemaRef)) 
        self.modelXbrl.profileActivity("dpmDB 01. Get ModuleID for instance schema", minTimeToShow=0.0)
        periodInstantDate = None
        entityIdentifier = ('', '') # scheme, identifier
        self.cntxDates = set()
        self.entityIdentifiers = set()
        for cntx in self.modelXbrl.contexts.values():
            if cntx.isInstantPeriod:
                entityIdentifier = cntx.entityIdentifier[1]
                periodInstantDate = cntx.endDatetime.date() - datetime.timedelta(1)  # convert to end date
                self.cntxDates.add(cntx.endDatetime) # for error checks
                self.entityIdentifiers.add(entityIdentifier)
                break
        if not periodInstantDate:
            return False # needed context not yet available
        entityCurrency = None
        for unit in self.modelXbrl.units.values():
            if unit.isSingleMeasure and unit.measures[0] and unit.measures[0][0].namespaceURI == XbrlConst.iso4217:
                entityCurrency = unit.measures[0][0].localName
                break
        if not entityCurrency:
            self.modelXbrl.error("sqlDB:entityCurrencyWarning",
                                 _("Loading XBRL DB: Instance does not have a currency unit."),
                                 modelObject=self.modelXbrl)
        table = self.getTable('dInstance', 'InstanceID', 
                              ('ModuleID', 'FileName', 'CompressedFileBlob',
                               'Timestamp', 'EntityScheme', 'EntityIdentifier', 'PeriodEndDateOrInstant',
                               'EntityName', 'EntityCurrency'), 
                              ('FileName',), 
                              ((self.moduleId,
                                os.path.basename(self.modelXbrl.uri),
                                None,
                                now,
                                entityIdentifier[0],
                                entityIdentifier[1], 
                                periodInstantDate, 
                                None, 
                                entityCurrency
                                ),),
                              checkIfExisting=True)
        for id, fileName in table:
            self.instanceId = id
            break
        self.modelXbrl.profileActivity("dpmDB 02. Store into dInstance", minTimeToShow=0.0)
        self.showStatus("deleting prior data points of this instance")
        for tableName in ("dFact", "dFilingIndicator", "dAvailableTable"):
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName(tableName), self.instanceId), 
                         close=False, fetch=False)
        self.modelXbrl.profileActivity("dpmDB 03. Delete prior data points of this instance", minTimeToShow=0.0)
            
        self.showStatus("obtaining mapping table information")
        result = self.execute("SELECT MetricAndDimensions, TableID FROM mTableDimensionSet WHERE ModuleID = {}"
                              .format(self.moduleId))
        self.tableIDs = set()
        self.metricAndDimensionsTableId = defaultdict(set)
        for metricAndDimensions, tableID in result:
            self.tableIDs.add(tableID)
            self.metricAndDimensionsTableId[metricAndDimensions].add(tableID)
        self.modelXbrl.profileActivity("dpmDB 04. Get TableDimensionSet for Module", minTimeToShow=0.0)
            
        result = self.execute("SELECT TableID, YDimVal, ZDimVal FROM mTable WHERE TableID in ({})"
                              .format(', '.join(str(i) for i in sorted(self.tableIDs))))
        self.yDimVal = defaultdict(dict)
        self.zDimVal = defaultdict(dict)
        for tableID, yDimVals, zDimVals in result:
            for tblDimVal, dimVals in ((self.yDimVal, yDimVals), (self.zDimVal, zDimVals)):
                if dimVals:
                    for dimVal in dimVals.split('|'):
                        dim, sep, val = dimVal.partition('(')
                        tblDimVal[tableID][dim] = val[:-1]
        self.modelXbrl.profileActivity("dpmDB 05. Get YZ DimVals for Table", minTimeToShow=0.0)

        self.showStatus("insert data points")
        return True
    
    def loadAllowedMetricsAndDims(self):
        self.filingIndicators = ', '.join("'{}'".format(filingIndicator)
                                           for filingIndicator in self.dFilingIndicators)
        # check metrics encountered for filing indicators found
        results = self.execute(
            "select distinct mem.MemberXBRLCode "
             "from mTemplateOrTable tott "
             "inner join mTemplateOrTable tottv on tottv.ParentTemplateOrTableID = tott.TemplateOrTableID "
             "   and tott.TemplateOrTableCode in ({0}) "
             "inner join mTemplateOrTable totbt on totbt.ParentTemplateOrTableID = tottv.TemplateOrTableID "
             "inner join mTemplateOrTable totat on totat.ParentTemplateOrTableID = totbt.TemplateOrTableID "
             "inner join mTaxonomyTable tt on tt.AnnotatedTableID = totat.TemplateOrTableID "
             "inner join mTableAxis ta on ta.TableID = tt.TableID "
             "inner join mAxisOrdinate ao on ao.AxisID = ta.AxisID "
             "inner join mOrdinateCategorisation oc on oc.OrdinateID = ao.OrdinateID AND (oc.Source = 'MD' or oc.Source is null) "
             "inner join mMember mem on mem.MemberID = oc.MemberID "
             "inner join mMetric met on met.CorrespondingMemberID = mem.MemberID "
             "inner join mModuleBusinessTemplate mbt on mbt.BusinessTemplateID = tottv.TemplateOrTableID "
             "   and mbt.ModuleID = {1} "
             .format(self.filingIndicators, self.moduleId))
        self.metricsForFilingIndicators = set(r[0] for r in results)
        
        results = self.execute(
             "select distinct tc.DatapointSignature "
             "from mTemplateOrTable tott "
             "inner join mTemplateOrTable tottv on tottv.ParentTemplateOrTableID = tott.TemplateOrTableID "
             "  and tott.TemplateOrTableCode in ( {0} ) "
             "inner join mTemplateOrTable totbt on totbt.ParentTemplateOrTableID = tottv.TemplateOrTableID "
             "inner join mTemplateOrTable totat on totat.ParentTemplateOrTableID = totbt.TemplateOrTableID "
             "inner join mTaxonomyTable tt on tt.AnnotatedTableID = totat.TemplateOrTableID "
             "inner join mTableCell tc on tc.TableID = tt.TableID and (tc.IsShaded = 0 or tc.IsShaded is null) "
             "inner join mModuleBusinessTemplate mbt on mbt.BusinessTemplateID = tottv.TemplateOrTableID "
             "  and mbt.ModuleID = {1} "
             .format(self.filingIndicators, self.moduleId))
        
        self.signaturesForFilingIndicators = defaultdict(list)
        for dpSig in results:
            _met, _sep, dims = dpSig[0].partition("|")
            _dimVals = {}
            for _dimVal in dims.split("|"):
                _dim, _sep, _val  = _dimVal.partition("(")
                _dimVals[_dim] = _val[:-1]
            self.signaturesForFilingIndicators[_met[4:-1]].append(_dimVals)
            
    def dFactValue(self, dFact):
        for v in dFact[4:7]:
            if v is not None:
                return v
        return None

    def validateFactSignature(self, dpmSignature, fact): # omit fact if checking at end
        _met, _sep, _dimVals = dpmSignature.partition("|")
        _metQname = _met[4:-1]
        if _metQname not in self.metricsForFilingIndicators:
            if isinstance(fact, ModelFact):
                self.modelXbrl.error("sqlDB:factQNameError",
                                     _("Loading XBRL DB: Fact QName not allowed for filing indicators %(qname)s, contextRef %(context)s, value: %(value)s"),
                                     modelObject=fact, dpmSignature=dpmSignature, qname=fact.qname, context=fact.contextID, value=fact.value)
            elif isinstance(fact, (tuple,list)): # from database dFact record
                self.modelXbrl.error("sqlDB:factQNameError",
                                     _("Loading XBRL DB: Fact QName not allowed for filing indicators %(qname)s, value: %(value)s"),
                                     modelObject=self.modelXbrl, dpmSignature=dpmSignature, qname=_metQname, value=self.dFactValue(fact))
        else:
            _dimVals = dict((_dim,_val[:-1])
                            for _dimVal in _dimVals.split("|")
                            for _dim, _sep, _val in (_dimVal.partition("("),))
            _dimSigs = self.signaturesForFilingIndicators.get(_metQname)
            _sigMatched = False
            _missingDims = _differentDims = _extraDims = set()
            _closestMatch = 9999
            _closestMatchSig = None
            if _dimSigs:
                for _dimSig in _dimSigs: # alternate signatures valid for member
                    _lenDimSig = len(_dimSig)
                    _lenDimVals = len(_dimVals)
                    _differentDimCount = abs(_lenDimSig - _lenDimVals)
                    _differentDims = set(_dim
                                         for _dim, _val in _dimVals.items()
                                         if _dim in _dimSig and _dimSig[_dim] not in ("*", _val))
                    _difference = _differentDimCount + len(_differentDims)
                    if _difference == 0:
                        _sigMatched = True
                        break
                    if _difference < _closestMatch:
                        _missingDims = _DICT_SET(_dimSig.keys()) - _DICT_SET(_dimVals.keys())
                        _extraDims = _DICT_SET(_dimVals.keys()) - _DICT_SET(_dimSig.keys())
                        _closestMatchDiffDims = _differentDims
                        _closestMatchSig = _dimSig
                        _closestMatch = _difference
                if not _sigMatched:
                    _missings = ",".join("{}({})".format(_dim,_closestMatchSig[_dim]) for _dim in _missingDims) or "none"
                    _extras = ",".join("{}({})".format(_dim,_dimVals[_dim]) for _dim in _extraDims) or "none"
                    _diffs = ",".join("dim: {} fact: {} DPMsig: {}".format(_dim, _dimVals[_dim], _closestMatchSig[_dim])  
                                      for _dim in _closestMatchDiffDims) or "none"
                    if isinstance(fact, ModelFact):
                        self.modelXbrl.error("sqlDB:factDimensionsError",
                                             _("Loading XBRL DB: Fact dimensions not allowed for filing indicators %(qname)s, contextRef %(context)s, value: %(value)s; "
                                               "Extra dimensions of fact: %(extra)s, missing dimensions of fact: %(missing)s, different dimensions of fact: %(different)s"),
                                             modelObject=fact, dpmSignature=dpmSignature, qname=fact.qname, context=fact.contextID, value=fact.value,
                                             extra=_extras, missing=_missings, different=_diffs)
                    elif isinstance(fact, (tuple,list)): # from database dFact record
                        self.modelXbrl.error("sqlDB:factDimensionsError",
                                             _("Loading XBRL DB: Fact dimensions not allowed for filing indicators %(qname)s, value: %(value)s; "
                                               "Extra dimensions of fact: %(extra)s, missing dimensions of fact: %(missing)s, different dimensions of fact: %(different)s"),
                                             modelObject=self.modelXbrl, dpmSignature=dpmSignature, qname=_metQname, value=self.dFactValue(fact),
                                             extra=_extras, missing=_missings, different=_diffs)

    def insertDataPointsToDB(self):
        instanceId = self.instanceId

        dFacts = []
        dFactHashes = {}
        for f in self.modelXbrl.facts:
            cntx = f.context
            concept = f.concept
            isNumeric = isBool = isDateTime = isText = False
            isInstant = None
            if concept is not None:
                if concept.isNumeric:
                    isNumeric = True
                    if f.precision:
                        self.modelXbrl.error("sqlDB:factPrecisionError",
                                             _("Loading XBRL DB: Fact contains a precision attribute %(qname)s, precision %(precision)s, context %(context)s, value %(value)s"),
                                             modelObject=f, qname=f.qname, context=f.contextID, value=f.value, precision=f.precision)
                else:
                    baseXbrliType = concept.baseXbrliType
                    if baseXbrliType == "booleanItemType":
                        isBool = True
                    elif baseXbrliType == "dateTimeItemType": # also is dateItemType?
                        isDateTime = True
                if f.isNil:
                    xValue = None
                else:
                    xValue = f.xValue
                    if isinstance(xValue, DateTime) and xValue.dateOnly:
                        xValue = dateunionDate(xValue)
                isInstant = concept.periodType == "instant"
            else:
                if f.isNil:
                    xValue = None
                else:
                    xValue = f.value
                    c = f.qname.localName[0]
                    if c in ('m', 'p', 'i'):
                        isNumeric = True
                        # not validated, do own xValue
                        try:
                            if c == 'i':
                                valuePattern = XmlValidate.integerPattern
                            else:
                                valuePattern = XmlValidate.decimalPattern
                            if valuePattern.match(xValue) is None:
                                self.modelXbrl.error("sqlDB:factValueError",
                                                     _("Loading XBRL DB: Fact %(qname)s, context %(context)s, value lexical error: %(value)s"),
                                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                            else:
                                xValue = Decimal(xValue)
                        except InvalidOperation:
                            xValue = Decimal('NaN')
                        if f.unit is None:
                            self.modelXbrl.error("sqlDB:factUnitError",
                                                 _("Loading XBRL DB: Fact missing unit %(qname)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                        if f.precision:
                            self.modelXbrl.error("sqlDB:factPrecisionError",
                                                 _("Loading XBRL DB: Fact contains a precision attribute %(qname)s, precision %(precision)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value, precision=f.precision)
                        elif not f.decimals or not decimalsPattern.match(f.decimals):
                            self.modelXbrl.error("sqlDB:factDecimalsError",
                                                 _("Loading XBRL DB: Fact contains an invalid decimals attribute %(qname)s, decimals %(decimals)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value, decimals=f.decimals)
                    else:
                        if c == 'd':
                            isDateTime = True
                            try:
                                xValue = dateTime(xValue, type=DATEUNION, castException=ValueError)
                                if xValue.dateOnly:
                                    xValue = dateunionDate(xValue)
                            except ValueError:
                                self.modelXbrl.error("sqlDB:factValueError",
                                                     _("Loading XBRL DB: Fact %(qname)s, context %(context)s, value: %(value)s"),
                                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                        elif c == 'b':
                            isBool = True
                            xValue = xValue.strip()
                            if xValue in ("true", "1"):  
                                xValue = True
                            elif xValue in ("false", "0"): 
                                xValue = False
                            else:
                                self.modelXbrl.error("sqlDB:factValueError",
                                                     _("Loading XBRL DB: Fact %(qname)s, context %(context)s, value: %(value)s"),
                                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                        if f.unit is not None:
                            self.modelXbrl.error("sqlDB:factUnitError",
                                                 _("Loading XBRL DB: Fact is non-numeric but has a unit %(qname)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                        if f.precision:
                            self.modelXbrl.error("sqlDB:factPrecisionError",
                                                 _("Loading XBRL DB: Fact contains a precision attribute %(qname)s, precision %(precision)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value, precision=f.precision)
                        elif f.decimals:
                            self.modelXbrl.error("sqlDB:factDecimalsError",
                                                 _("Loading XBRL DB: Fact is non-numeric but contains a decimals attribute %(qname)s, decimals %(decimals)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value, decimals=f.decimals)
                isInstant = f.qname.localName[1:2] == 'i'
                
            isText = not (isNumeric or isBool or isDateTime) # 's' or 'u' type
            if f.qname == qnFindFilingIndicators:
                if cntx is not None:
                    self.modelXbrl.error("sqlDB:filingIndicatorsContextError",
                                         _("Loading XBRL DB: Filing indicators tuple has a context, contextRef %(context)s"),
                                         modelObject=f, context=f.contextID)
                for filingIndicator in f.modelTupleFacts:
                    if filingIndicator.qname == qnFindFilingIndicator:
                        self.dFilingIndicators.add(filingIndicator.textValue.strip())
                        if filingIndicator.context is None:
                            self.modelXbrl.error("sqlDB:filingIndicatorContextError",
                                                 _("Loading XBRL DB: Filing indicator fact missing a context, value %(value)s"),
                                                 modelObject=filingIndicator, value=filingIndicator.value)
                self.loadAllowedMetricsAndDims() # reload metrics
            elif cntx is None: 
                self.modelXbrl.error("sqlDB:factContextError",
                                     _("Loading XBRL DB: Fact missing %(qname)s, contextRef %(context)s, value: %(value)s"),
                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
            else:
                # find which explicit dimensions act as typed
                behaveAsTypedDims = set()
                zDimValues = {}
                tableID = None
                for tableID in self.metricAndDimensionsTableId.get(metDimNameKey(f, cntx), ()):
                    yDimVals = self.yDimVal[tableID]
                    zDimVals = self.zDimVal[tableID]
                    for dimQname in cntx.qnameDims.keys():
                        dimStr = str(dimQname)
                        #if (dimStr in zDimVals and zDimVals[dimStr] == "*" or
                        #    dimStr in yDimVals and yDimVals[dimStr] == "*"):
                        #    behaveAsTypedDims.add(dimQname)
                    zDimKey = (metDimValKey(cntx, typedDim=True, behaveAsTypedDims=behaveAsTypedDims, restrictToDims=zDimVals)
                               or None)  # want None if no dimVal Z key
                    yDimKey = metDimValKey(cntx, typedDim=True, behaveAsTypedDims=behaveAsTypedDims, restrictToDims=yDimVals)
                    self.availableTableRows[tableID,zDimKey].add(yDimKey)
                    break
                _dataPointSignature = metDimTypedKey(f, behaveAsTypedDims)
                # self.validateFactSignature(_dataPointSignature, f)
                # validate signatures at end
                        
                _factHash = (instanceId, _dataPointSignature)
                if _factHash in dFactHashes and any(dF[0] == instanceId and dF[1] == _dataPointSignature
                                                    for dF in dFacts):
                    otherF = dFactHashes[_factHash]
                    self.modelXbrl.error("sqlDB:factDuplicate",
                                         _("Loading XBRL DB: Fact is a duplicate %(qname)s, contextRef %(context)s, value: %(value)s, other contextRef %(context2)s, other value %(value2)s"),
                                         modelObject=(f,otherF), qname=f.qname, context=f.contextID, value=f.value,
                                         context2=otherF.contextID, value2=otherF.value)
                else:
                    dFactHashes[_factHash] = f
                    dFacts.append((instanceId,
                                   _dataPointSignature,
                                   str(f.unit.measures[0][0]) if isNumeric and f.unit is not None and f.unit.isSingleMeasure else None,
                                   f.decimals,
                                   xValue if isNumeric else None,
                                   xValue if isDateTime else None,
                                   xValue if isBool else None,
                                   xValue if isText else None
                                ))
                ''' deprecated
                dProcessingFacts.append((instanceId,
                                         met(f),
                                         f.contextID if isNumeric else None,                                         
                                         xValue if isText or isBool else None,
                                         xValue if isNumeric else None,
                                         xValue if isDateTime else None,
                                         None))
                '''
            if cntx is not None:
                if getattr(cntx, "xValid", XmlValidate.UNKNOWN) == XmlValidate.UNKNOWN: # no validation, such as skipDTS and no streaming
                    cntx.xValid = XmlValidate.NONE # prevent detecting as UNKNOWN
                    if cntx.isInstantPeriod:
                        if cntx.instantDatetime in (None, DATETIME_MAXYEAR):
                            self.modelXbrl.error("sqlDB:contextDatesError",
                                                 _("Loading XBRL DB: Context has invalid instant date: %(context)s"),
                                                 modelObject=cntx, context=cntx.id)
                    elif cntx.isStartEndPeriod:
                        if cntx.startDatetime in (None, DATETIME_MAXYEAR):
                            self.modelXbrl.error("sqlDB:contextDatesError",
                                                 _("Loading XBRL DB: Context has invalid start date: %(context)s"),
                                                 modelObject=cntx, context=cntx.id)
                        if cntx.endDatetime in (None, DATETIME_MAXYEAR):
                            self.modelXbrl.error("sqlDB:contextDatesError",
                                                 _("Loading XBRL DB: Context has invalid end date: %(context)s"),
                                                 modelObject=cntx, context=cntx.id)
                if cntx.isInstantPeriod and cntx.endDatetime not in self.cntxDates:
                    self.modelXbrl.error("sqlDB:contextDatesError",
                                         _("Loading XBRL DB: Context has different date: %(context)s, date %(value)s"),
                                         modelObject=cntx, context=cntx.id, value=dateunionValue(cntx.endDatetime, subtractOneDay=True))
                    self.cntxDates.add(cntx.endDatetime)
                if cntx.entityIdentifier[1] not in self.entityIdentifiers:
                    self.modelXbrl.error("sqlDB:factContextError",
                                     _("Loading XBRL DB: Context has different entity identifier: %(context)s %(value)s"),
                                     modelObject=cntx, context=cntx.id, value=cntx.entityIdentifier[1])
                    self.entityIdentifiers.add(cntx.entityIdentifier[1])
                if cntx.isStartEndPeriod and isInstant:
                    self.modelXbrl.error("sqlDB:factContextError",
                                     _("Loading XBRL DB: Instant metric %(qname)s has start end context: %(context)s"),
                                     modelObject=f, qname=f.qname, context=f.contextID)
                    

        # check for fact duplicates
        duplicates = self.getTable("dFact", None,
                                   ('InstanceID', 
                                    'DataPointSignature', 
                                    'Unit', 'Decimals',
                                    'NumericValue', 'DateTimeValue', 'BooleanValue', 'TextValue'),
                                   ('InstanceID', 'DataPointSignature' ),
                                   dFacts,
                                   returnMatches=True, insertIfNotMatched=False)
        if duplicates:
            dupDpSigs = set(_dpSig for _instID, _dpSig in duplicates)
            for dFact in dFacts:
                dpSig = dFact[1]
                if dpSig in dupDpSigs:
                    metric, _sep, _dims = dpSig.partition('|')
                    metricPrefixedName = metric.partition('(')[2][:-1]
                    self.modelXbrl.error("sqlDB:factDuplicate",
                                         _("Loading XBRL DB: Fact is a duplicate %(qname)s, value=%(value)s"),
                                         modelObject=self.modelXbrl, qname=metricPrefixedName,
                                         value=(dFact[5] or dFact[6] or dFact[7] or dFact[4]))  # num last so zero isn't or'ed as bool false
        else:
            # insert non-duplicate facts
            self.getTable("dFact", None,
                          ('InstanceID', 
                           'DataPointSignature', 
                           'Unit', 'Decimals',
                           'NumericValue', 'DateTimeValue', 'BooleanValue', 'TextValue'),
                          ('InstanceID', ),
                          dFacts,
                          returnMatches=False)
        return True
        
    def finishInsertXbrlToDB(self):
        self.modelXbrl.profileActivity("dpmDB 06. Build facts table for bulk DB update", minTimeToShow=0.0)

        # check filing indicators after facts loaded
        result = self.execute("SELECT InstanceID, DataPointSignature, Unit, Decimals, NumericValue, DateTimeValue, BooleanValue, TextValue " 
                              "FROM dFact WHERE dFact.InstanceID = '{}'"
                              .format(self.instanceId))
        for dFact in result:
            self.validateFactSignature(dFact[1], dFact)
        # availableTable processing
        # get filing indicator template IDs
        if not self.dFilingIndicators:
            self.modelXbrl.error("sqlDB:NoFilingIndicators",
                                 _("No filing indicators were present in the instance"),
                                 modelObject=self.modelXbrl) 
        else:
            results = self.execute("SELECT mToT2.TemplateOrTableCode, mToT2.TemplateOrTableID "
                                   "  FROM mModuleBusinessTemplate mBT, mTemplateOrTable mToT, mTemplateOrTable mToT2 "
                                   "  WHERE mBT.ModuleID = {0} AND"
                                   "        mToT.TemplateOrTableID = mBT.BusinessTemplateID AND"
                                   "        mToT.ParentTemplateOrTableID = mToT2.TemplateOrTableID AND"
                                   "        mToT2.TemplateOrTableCode in ({1})"
                                   .format(self.moduleId, self.filingIndicators))
            filingIndicatorCodeIDs = dict((code, id) for code, id in results)
            self.modelXbrl.profileActivity("dpmDB 07. Get business template filing indicator for module", minTimeToShow=0.0)
            
            if _DICT_SET(filingIndicatorCodeIDs.keys()) != self.dFilingIndicators:
                self.modelXbrl.error("sqlDB:MissingFilingIndicators",
                                     _("The filing indicator IDs were not found for codes %(missingFilingIndicatorCodes)s"),
                                     modelObject=self.modelXbrl,
                                     missingFilingIndicatorCodes=','.join(self.dFilingIndicators - _DICT_SET(filingIndicatorCodeIDs.keys()))) 
    
            self.getTable("dFilingIndicator", None,
                          ("InstanceID", "BusinessTemplateID"),
                          ("InstanceID", "BusinessTemplateID"),
                          ((self.instanceId,
                            filingIndicatorCodeId)
                           for filingIndicatorCodeId in sorted(filingIndicatorCodeIDs.values())),
                          returnMatches=False)
        self.modelXbrl.profileActivity("dpmDB 08. Store dFilingIndicators", minTimeToShow=0.0)
        ''' deprecated
        table = self.getTable("dProcessingFact", None,
                              ('InstanceID', 'Metric', 'ContextID', 
                               'ValueTxt', 'ValueDecimal', 'ValueDate',
                               'Error'),
                              ('InstanceID', ),
                              dProcessingFacts)
        '''
        self.getTable("dAvailableTable", None,
                      ('InstanceID', 'TableID', 'ZDimVal', "NumberOfRows"), 
                      ('InstanceID', 'TableID', 'ZDimVal'),
                      ((self.instanceId,
                        availTableKey[0], # table Id
                        availTableKey[1], # zDimVal
                        len(setOfYDimVals))
                       for availTableKey, setOfYDimVals in self.availableTableRows.items()),
                      returnMatches=False)
        self.modelXbrl.profileActivity("dpmDB 10. Bulk store dAvailableTable", minTimeToShow=0.0)

        self.modelXbrl.profileStat(_("XbrlSqlDB: instance insertion"), time.time() - self.startedAt)
        startedAt = time.time()
        self.showStatus("Committing entries")
        self.commit()
        self.modelXbrl.profileStat(_("XbrlSqlDB: insertion committed"), time.time() - startedAt)
        self.showStatus("DB insertion completed", clearAfter=5000)
                
    def loadXbrlFromDB(self, loadDBsaveToFile, loadInstanceId):
        # load from database
        modelXbrl = self.modelXbrl
        
        # find instance in DB
        self.showStatus("finding instance in database")
        if loadInstanceId and loadInstanceId.isnumeric():
            # use instance ID to get instance
            results = self.execute("SELECT InstanceID, ModuleID, EntityScheme, EntityIdentifier, PeriodEndDateOrInstant"
                                   " FROM dInstance WHERE InstanceID = {}"
                                   .format(loadInstanceId))
        else:
            # use filename to get instance
            instanceURI = os.path.basename(loadDBsaveToFile)
            results = self.execute("SELECT InstanceID, ModuleID, EntityScheme, EntityIdentifier, PeriodEndDateOrInstant"
                                   " FROM dInstance WHERE FileName = '{}'"
                                   .format(instanceURI))
        instanceId = moduleId = None
        for instanceId, moduleId, entScheme, entId, datePerEnd in results:
            break
        if not instanceId:
            raise DpmDBException("sqlDB:MissingInstance",
                    _("The instance was not found in table dInstance: %(instanceURI)s"),
                    instanceURI = instanceURI) 
            

        # find module in DB        
        self.showStatus("finding module in database")
        results = self.execute("SELECT XbrlSchemaRef FROM mModule WHERE ModuleID = {}".format(moduleId))
        xbrlSchemaRef = None
        for result in results:
            xbrlSchemaRef = result[0]
            break
        
        if not xbrlSchemaRef:
            raise DpmDBException("sqlDB:MissingDTS",
                    _("The module in mModule, corresponding to the instance, was not found for %(instanceURI)s"),
                    instanceURI = instanceURI) 
            
        if modelXbrl.skipDTS:
            # find prefixes and namespaces in DB
            results = self.execute("SELECT * FROM [vwGetNamespacesPrefixes]")            
            dpmPrefixedNamespaces = dict((prefix, namespace)
                                         for owner, prefix, namespace in results)
            
        # create the instance document and resulting filing
        modelXbrl.blockDpmDBrecursion = True
        modelXbrl.modelDocument = createModelDocument(modelXbrl, 
                                                      Type.INSTANCE,
                                                      loadDBsaveToFile,
                                                      schemaRefs=[xbrlSchemaRef],
                                                      isEntry=True)
        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults 
        
        addProcessingInstruction(modelXbrl.modelDocument.xmlRootElement, 
                                 'xbrl-streamable-instance', 
                                 'version="1.0" contextBuffer="1"')

        # add roleRef and arcroleRef (e.g. for footnotes, if any, see inlineXbrlDocue)
        
        # filing indicator code IDs
        # get filing indicators
        results = self.execute("SELECT mToT.TemplateOrTableCode "
                               "  FROM dFilingIndicator dFI, mTemplateOrTable mToT "
                               "  WHERE dFI.InstanceID = {} AND mTot.TemplateOrTableID = dFI.BusinessTemplateID"
                               .format(instanceId))
        filingIndicatorCodes = [code[0] for code in results]
        
        if filingIndicatorCodes:
            modelXbrl.createContext(entScheme,
                        entId,
                        'instant',
                        None,
                        datePerEnd,
                        None, # no dimensional validity checking (like formula does)
                        {}, [], [],
                        id='c')
            filingIndicatorsTuple = modelXbrl.createFact(qnFindFilingIndicators, validate=False)
            for filingIndicatorCode in filingIndicatorCodes:
                modelXbrl.createFact(qnFindFilingIndicator, 
                                     parent=filingIndicatorsTuple,
                                     attributes={"contextRef": "c"}, 
                                     text=filingIndicatorCode, validate=False)
            XmlValidate.validate(modelXbrl, filingIndicatorsTuple) # must validate after contents are created

        # get typed dimension elements
        results = self.execute("SELECT dim.DimensionXBRLCode, "
                               "       owndom.OwnerPrefix || '_typ:' || dom.DomainCode"
                               "  FROM mDimension dim"
                               "       INNER JOIN mDomain dom"
                               "               ON dom.DomainID = dim.DomainID"
                               "       INNER JOIN mConcept condom"
                               "               ON condom.ConceptID = dom.ConceptID"
                               "       INNER JOIN mOwner owndom"
                               "               ON owndom.OwnerID = condom.OwnerID"
                               " WHERE dim.IsTypedDimension = 1")
        typedDimElts = dict((dimQn,eltQn) for dimQn,eltQn in results)
        
        # facts in this instance
        self.showStatus("finding data points in database")
        factsTbl = self.execute("SELECT DataPointSignature, " 
                                " Unit, Decimals, NumericValue, DateTimeValue, BooleanValue, TextValue "
                                "FROM dFact WHERE InstanceID = {} "
                                "ORDER BY substr(DataPointSignature, instr(DataPointSignature,'|') + 1)"
                                .format(instanceId))
        
        # results tuple: factId, dec, varId, dpKey, entId, datePerEnd, unit, numVal, dateVal, boolVal, textVal

        # get typed dimension values
        prefixedNamespaces = modelXbrl.prefixedNamespaces
        prefixedNamespaces["iso4217"] = XbrlConst.iso4217
        prefixedNamespaces["xbrli"] = XbrlConst.xbrli
        if modelXbrl.skipDTS:
            prefixedNamespaces.update(dpmPrefixedNamespaces) # for skipDTS this is always needed
        
        cntxTbl = {} # index by d
        unitTbl = {}
        
        def typedDimElt(s):
            # add xmlns into s for known qnames
            tag, angleBrkt, rest = s[1:].partition('>')
            text, angleBrkt, rest = rest.partition("<")
            qn = qname(tag, prefixedNamespaces)
            # a modelObject xml element is needed for all of the instance functions to manage the typed dim
            return addChild(modelXbrl.modelDocument, qn, text=text, appendChild=False)
        
        def nilTypedDimElt(dimQn):
            qn = qname(typedDimElts[dimQn], prefixedNamespaces)
            return addChild(modelXbrl.modelDocument, qn, appendChild=False, attributes={XbrlConst.qnXsiNil:"true"})
        
        # contexts and facts
        self.showStatus("creating XBRL output contexts, units, and facts")
        for dpSig, unit, dec, numVal, dateVal, boolVal, textVal in factsTbl:
            metric, _sep, dims = dpSig.partition('|')
            metricPrefixedName = metric.partition('(')[2][:-1]
            conceptQn = qname(metricPrefixedName, prefixedNamespaces)
            if conceptQn is None:
                self.modelXbrl.error("sqlDB:InvalidFactConcept",
                                     _("A concept definition is not found for metric %(concept)s of datapoint signature %(dpsignature)s"),
                                     modelObject=self.modelXbrl, concept=metricPrefixedName, dpsignature=dpSig)
                continue  # ignore DTS-based loading of invalid concept QName
            concept = modelXbrl.qnameConcepts.get(conceptQn)
            isNumeric = isBool = isDateTime = isQName = isText = False
            if concept is not None:
                if concept.isNumeric:
                    isNumeric = True
                else:
                    baseXbrliType = concept.baseXbrliType
                    if baseXbrliType == "booleanItemType":
                        isBool = True
                    elif baseXbrliType in ("dateTimeItemType", "dateItemType"): # also is dateItemType?
                        isDateTime = True
                    elif baseXbrliType == "QNameItemType":
                        isQName = True
            else:
                c = conceptQn.localName[0]
                if c in ('m', 'p', 'i'):
                    isNumeric = True
                elif c == 'd':
                    isDateTime = True
                elif c == 'b':
                    isBool = True
                elif c == 'e':
                    isQName = True
            isText = not (isNumeric or isBool or isDateTime or isQName) # 's' or 'u' type
            if isinstance(datePerEnd, _STR_BASE):
                datePerEnd = datetimeValue(datePerEnd, addOneDay=True)
            cntxKey = (dims, entId, datePerEnd)
            if cntxKey in cntxTbl:
                cntxId = cntxTbl[cntxKey]
            else:
                cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                cntxTbl[cntxKey] = cntxId
                qnameDims = {}
                if dims:
                    for dim in dims.split('|'):
                        dQn, sep, dVal = dim[:-1].partition('(')
                        dimQname = qname(dQn, prefixedNamespaces)
                        if dVal.startswith('<'):
                            mem = typedDimElt(dVal)  # typed dim
                        elif dVal == "nil":
                            mem = nilTypedDimElt(dQn)
                        else:
                            mem = qname(dVal, prefixedNamespaces) # explicit dim (even if treat-as-typed)
                        qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "scenario")
                    
                modelXbrl.createContext(entScheme,
                                        entId,
                                        'instant',
                                        None,
                                        datePerEnd,
                                        None, # no dimensional validity checking (like formula does)
                                        qnameDims, [], [],
                                        id=cntxId)
            if isNumeric and unit:
                if unit in unitTbl:
                    unitId = unitTbl[unit]
                else:
                    unitQn = qname(unit, prefixedNamespaces)
                    unitId = 'u{}'.format(unitQn.localName)
                    unitTbl[unit] = unitId
                    modelXbrl.createUnit([unitQn], [], id=unitId)
            else:
                unitId = None
            attrs = {"contextRef": cntxId}
            if isNumeric:
                if unitId:
                    attrs["unitRef"] = unitId
                if isinstance(numVal, _NUM_TYPES):
                    if dec is not None and len(dec) > 0:
                        if isinstance(dec, float): # must be an integer
                            dec = int(dec)
                        elif isinstance(dec, _STR_BASE) and '.' in dec:
                            dec = dec.partition('.')[0] # drop .0 from any SQLite string
                        attrs["decimals"] = str(dec)  # somehow it is float from the database
                    num = roundValue(numVal, None, dec) # round using reported decimals
                    if dec is None or dec == "INF":  # show using decimals or reported format
                        dec = abs(Decimal(str(numVal)).as_tuple().exponent)
                    else: # max decimals at 28
                        try:
                            dec = max( min(int(float(dec)), 28), -28) # 2.7 wants short int, 3.2 takes regular int, don't use _INT here
                        except ValueError:
                            dec = 0
                    text = Locale.format(Locale.C_LOCALE, "%.*f", (dec, num)) # culture-invariant locale
                else:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
            elif isDateTime:
                if isinstance(dateVal, (str, datetime.date)):
                    text = str(dateVal)
                else:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
            elif isBool:
                if isinstance(boolVal, _NUM_TYPES):
                    text = 'false' if boolVal == 0 else 'true'
                elif isinstance(boolVal, _STR_BASE) and len(boolVal) > 0:
                    text = 'true' if boolVal.lower() in ('t', 'true', '1') else 'false'
                else:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
            else: # text or QName
                if textVal is not None and (textVal or not isQName):
                    if isQName: # declare namespace
                        addQnameValue(modelXbrl.modelDocument, qname(textVal, prefixedNamespaces))
                    text = textVal
                else:
                    attrs[XbrlConst.qnXsiNil] = "true"
                    text = None
            modelXbrl.createFact(conceptQn, attributes=attrs, text=text)
            
        # add footnotes if any
        
        # save to file
        self.showStatus("saving XBRL instance")
        modelXbrl.saveInstance(overrideFilepath=loadDBsaveToFile)
        self.showStatus(_("Saved extracted instance"), 5000)
        return modelXbrl.modelDocument
