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

import time, datetime, os
from collections import defaultdict
from arelle.ModelDocument import Type, create as createModelDocument
from arelle import Locale, ValidateXbrlDimensions
from arelle.ModelValue import qname, dateTime, DATEUNION
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlUtil import xmlstring, datetimeValue, addChild, addQnameValue, addProcessingInstruction
from arelle import XbrlConst
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from decimal import Decimal, InvalidOperation

qnFindFilingIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFindFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")

def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, loadDBsaveToFile=None, **kwargs):
    if getattr(modelXbrl, "blockDpmDBrecursion", False):
        return None
    result = None
    xbrlDbConn = None
    try:
        xbrlDbConn = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
        xbrlDbConn.verifyTables()
        if loadDBsaveToFile:
            # load modelDocument from database saving to file
            result = xbrlDbConn.loadXbrlFromDB(loadDBsaveToFile)
        else:
            xbrlDbConn.insertXbrl(rssItem=rssItem)
        xbrlDbConn.close()
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
            self.lockTables(("dAvailableTable", "dInstance",  "dFact", "dFilingIndicator",
                             # "dProcessingContext", "dProcessingFact"
                             ))
            
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
        entityIdentifier = ('', '') # scheme, identifier
        periodInstantDate = None
        # find primary model taxonomy of instance
        self.moduleId = None
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            for refDoc, ref in self.modelXbrl.modelDocument.referencesDocument.items():
                if refDoc.inDTS and ref.referenceType == "href":
                    result = self.execute("SELECT ModuleID FROM mModule WHERE XBRLSchemaRef = '{}'"
                                          .format(refDoc.uri))
                    for moduleId in result:
                        self.moduleId = moduleId[0] # only column in row returned
                        break
                    if self.moduleId:
                        break
        for cntx in self.modelXbrl.contexts.values():
            if cntx.isInstantPeriod:
                entityIdentifier = cntx.entityIdentifier
                periodInstantDate = cntx.endDatetime.date() - datetime.timedelta(1)  # convert to end date
                break
        entityCurrency = None
        for unit in self.modelXbrl.units.values():
            if unit.isSingleMeasure and unit.measures[0] and unit.measures[0][0].namespaceURI == XbrlConst.iso4217:
                entityCurrency = unit.measures[0][0].localName
                break
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
 
    def insertDataPoints(self):
        instanceId = self.instanceId
        self.showStatus("deleting prior data points of this report")
        for tableName in ("dFact", "dFilingIndicator", "dAvailableTable"):
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName(tableName), instanceId), 
                         close=False, fetch=False)
            
        self.showStatus("obtaining mapping table information")
        result = self.execute("SELECT MetricAndDimensions, TableID FROM mTableDimensionSet WHERE ModuleID = {}"
                              .format(self.moduleId))
        tableIDs = set()
        metricAndDimensionsTableId = defaultdict(set)
        for metricAndDimensions, tableID in result:
            tableIDs.add(tableID)
            metricAndDimensionsTableId[metricAndDimensions].add(tableID)
            
        result = self.execute("SELECT TableID, YDimVal, ZDimVal FROM mTable WHERE TableID in ({})"
                              .format(', '.join(str(i) for i in sorted(tableIDs))))
        yDimVal = defaultdict(dict)
        zDimVal = defaultdict(dict)
        for tableID, yDimVals, zDimVals in result:
            for tblDimVal, dimVals in ((yDimVal, yDimVals), (zDimVal, zDimVals)):
                if dimVals:
                    for dimVal in dimVals.split('|'):
                        dim, sep, val = dimVal.partition('(')
                        tblDimVal[tableID][dim] = val[:-1]

        availableTableRows = defaultdict(set) # index (tableID, zDimVal) = set of yDimVals 
               
        self.showStatus("insert data points")
        # contexts
        emptySet = set()
        def dimValKey(cntx, typedDim=False, behaveAsTypedDims=emptySet, restrictToDims=None):
            return '|'.join(sorted("{}({})".format(dim.dimensionQname,
                                                   dim.memberQname if dim.isExplicit and dim not in behaveAsTypedDims
                                                   else dim.memberQname if typedDim and not dim.isTyped
                                                   else xmlstring(dim.typedMember, stripXmlns=True) if typedDim
                                                   else '*' )
                                   for dim in cntx.qnameDims.values()
                                   if not restrictToDims or str(dim.dimensionQname) in restrictToDims))
        def dimNameKey(cntx):
            return '|'.join(sorted("{}".format(dim.dimensionQname)
                                   for dim in cntx.qnameDims.values()))
        contextSortedAllDims = dict((cntx.id, dimValKey(cntx))  # has (*) for typed dim
                                    for cntx in self.modelXbrl.contexts.values()
                                    if cntx.qnameDims)
        contextSortedTypedDims = dict((cntx.id, dimValKey(cntx, typedDim=True)) # typed dims with value only if typed
                                      for cntx in self.modelXbrl.contexts.values()
                                      if any(dim.isTyped for dim in cntx.qnameDims.values()))
        contextSortedDimNames = dict((cntx.id, dimNameKey(cntx))
                                     for cntx in self.modelXbrl.contexts.values()
                                     if cntx.qnameDims)
        
        def met(fact):
            return "MET({})".format(fact.qname)
        
        # key for use in dFact with * for dim that behaves as or is typed
        def metDimAllKey(fact, behaveAsTypedDims=emptySet):
            key = met(fact)
            cntx = fact.context
            if cntx.qnameDims:
                key += '|' + dimValKey(cntx, behaveAsTypedDims=behaveAsTypedDims)
            return key
        
        # key for use in dFact only when there's a dim that behaves as or is typed
        def metDimTypedKey(fact, behaveAsTypedDims=emptySet):
            cntx = fact.context
            if any(dimQname in behaveAsTypedDims for dimQname in cntx.qnameDims):
                key = met(fact) + '|' + dimValKey(cntx, typedDim=True, behaveAsTypedDims=behaveAsTypedDims)
                return key
            return None
        
        # key for use in dAvailable where mem and typed values show up
        def metDimValKey(cntx, typedDim=False, behaveAsTypedDims=emptySet, restrictToDims=emptySet):
            if "MET" in restrictToDims:
                key = "MET({})|".format(restrictToDims["MET"])
            else:
                key = ""
            key += dimValKey(cntx, typedDim=typedDim, behaveAsTypedDims=behaveAsTypedDims, restrictToDims=restrictToDims)
            return key
                
        def metDimNameKey(fact):
            key = met(fact)
            if fact.contextID in contextSortedDimNames:
                key += '|' + contextSortedDimNames[fact.contextID]
            return key
        
        ''' deprecated
        table = self.getTable("dProcessingContext", None,
                              ('InstanceID', 'ContextID', 'SortedDimensions', 'NotValid'),
                              ('InstanceID', 'ContextID'),
                              tuple((instanceId,
                                     cntxID,
                                     cntxDimKey,
                                     False
                                     )
                                    for cntxID, cntxDimKey in sorted(contextSortedAllDims.items())))
        '''
        
        # contexts with typed dimensions
        
        # dCloseFactTable
        dFilingIndicators = set()
        # dProcessingFacts = []
        dFacts = []
        for f in self.modelXbrl.facts:
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
            if f.qname == qnFindFilingIndicators:
                for filingIndicator in f.modelTupleFacts:
                    if filingIndicator.qname == qnFindFilingIndicator:
                        dFilingIndicators.add(filingIndicator.textValue.strip())
            elif cntx is not None:
                # find which explicit dimensions act as typed
                behaveAsTypedDims = set()
                zDimValues = {}
                tableID = None
                for tableID in metricAndDimensionsTableId.get(metDimNameKey(f), ()):
                    yDimVals = yDimVal[tableID]
                    zDimVals = zDimVal[tableID]
                    for dimQname in cntx.qnameDims.keys():
                        dimStr = str(dimQname)
                        if (dimStr in zDimVals and zDimVals[dimStr] == "*" or
                            dimStr in yDimVals and yDimVals[dimStr] == "*"):
                            behaveAsTypedDims.add(dimQname)
                    zDimKey = (metDimValKey(cntx, typedDim=True, behaveAsTypedDims=behaveAsTypedDims, restrictToDims=zDimVals)
                               or None)  # want None if no dimVal Z key
                    yDimKey = metDimValKey(cntx, typedDim=True, behaveAsTypedDims=behaveAsTypedDims, restrictToDims=yDimVals)
                    availableTableRows[tableID,zDimKey].add(yDimKey)
                    break
                dFacts.append((instanceId,
                               metDimAllKey(f, behaveAsTypedDims),
                               metDimTypedKey(f, behaveAsTypedDims),
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
                
                # availableTable processing
        # get filing indicator template IDs
        results = self.execute("SELECT mToT.TemplateOrTableCode, mToT.TemplateOrTableID "
                               "  FROM mModuleBusinessTemplate mBT, mTemplateOrTable mToT "
                               "  WHERE mBT.ModuleID = {0} AND"
                               "        mToT.TemplateOrTableID = mBT.BusinessTemplateID AND"
                               "        mToT.TemplateOrTableCode in ({1})"
                               .format(self.moduleId,
                                       ', '.join("'{}'".format(filingIndicator)
                                                 for filingIndicator in dFilingIndicators)))
        filingIndicatorCodeIDs = dict((code, id) for code, id in results)
        
        if _DICT_SET(filingIndicatorCodeIDs.keys()) != dFilingIndicators:
            self.modelXbrl.error("sqlDB:MissingFilingIndicators",
                                 _("The filing indicator IDs not found for codes %(missingFilingIndicatorCodes)"),
                                 modelObject=self.modelXbrl,
                                 missingFilingIndicatorCodes=','.join(dFilingIndicators - _DICT_SET(filingIndicatorCodeIDs.keys()))) 

        self.getTable("dFilingIndicator", None,
                      ("InstanceID", "BusinessTemplateID"),
                      ("InstanceID", "BusinessTemplateID"),
                      ((instanceId,
                        filingIndicatorCodeId)
                       for filingIndicatorCodeId in sorted(filingIndicatorCodeIDs.values())))

        
        self.getTable("dFact", None,
                      ('InstanceID', 'DataPointSignature', 'DataPointSignatureWithValuesForWildcards', 
                       'Unit', 'Decimals',
                       'NumericValue', 'DateTimeValue', 'BooleanValue', 'TextValue'),
                      ('InstanceID', ),
                      dFacts)
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
                      ((instanceId,
                        availTableKey[0], # table Id
                        availTableKey[1], # zDimVal
                        len(setOfYDimVals))
                       for availTableKey, setOfYDimVals in availableTableRows.items()))
        
    def loadXbrlFromDB(self, loadDBsaveToFile):
        # load from database
        modelXbrl = self.modelXbrl
        
        # find instance in DB
        instanceURI = os.path.basename(loadDBsaveToFile)
        results = self.execute("SELECT InstanceID, ModuleID, EntityScheme, EntityIdentifier, PeriodEndDateOrInstant"
                               " FROM dInstance WHERE FileName = '{}'"
                               .format(instanceURI))
        instanceId = moduleId = None
        for instanceId, moduleId, entScheme, entId, datePerEnd in results:
            break

        # find module in DB        
        results = self.execute("SELECT XbrlSchemaRef FROM mModule WHERE ModuleID = {}".format(moduleId))
        xbrlSchemaRef = None
        for result in results:
            xbrlSchemaRef = result[0]
            break
        
        if not instanceId or not xbrlSchemaRef:
            raise XPDBException("sqlDB:MissingDTS",
                    _("The instance and module were not found for %(instanceURI)"),
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
            filingIndicatorsTuple = modelXbrl.createFact(qnFindFilingIndicators)
            for filingIndicatorCode in filingIndicatorCodes:
                modelXbrl.createFact(qnFindFilingIndicator, 
                                     parent=filingIndicatorsTuple,
                                     attributes={"contextRef": "c"}, 
                                     text=filingIndicatorCode)

        
        # facts in this instance
        factsTbl = self.execute("SELECT DataPointSignature, DataPointSignatureWithValuesForWildcards,"
                                " Unit, Decimals, NumericValue, DateTimeValue, BooleanValue, TextValue "
                                "FROM dFact WHERE InstanceID = {} "
                                "ORDER BY substr(CASE WHEN DataPointSignatureWithValuesForWildcards IS NULL "
                                "                          THEN DataPointSignature"
                                "                          ELSE DataPointSignatureWithValuesForWildcards"
                                "                END, instr(DataPointSignature,'|') + 1)"
                                .format(instanceId))
        
        # results tuple: factId, dec, varId, dpKey, entId, datePerEnd, unit, numVal, dateVal, boolVal, textVal

        # get typed dimension values
        prefixedNamespaces = modelXbrl.prefixedNamespaces
        prefixedNamespaces["iso4217"] = XbrlConst.iso4217
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
        
        # contexts and facts
        for dpSig, dpSigTypedDims, unit, dec, numVal, dateVal, boolVal, textVal in factsTbl:
            metric, sep, dims = (dpSigTypedDims or dpSig).partition('|')
            conceptQn = qname(metric.partition('(')[2][:-1], prefixedNamespaces)
            concept = modelXbrl.qnameConcepts.get(conceptQn)
            isNumeric = isBool = isDateTime = isQName = isText = False
            if concept is not None:
                if concept.isNumeric:
                    isNumeric = True
                else:
                    baseXbrliType = concept.baseXbrliType
                    if baseXbrliType == "booleanItemType":
                        isBool = True
                    elif baseXbrliType == "dateTimeItemType": # also is dateItemType?
                        isDateTime = True
                    elif baseXbrliType == "QNameItemType":
                        isQName = True
            else:
                c = conceptQn.localName[0]
                if c == 'm':
                    isNumeric = True
                elif c == 'd':
                    isDateTime = True
                elif c == 'b':
                    isBool = True
                elif c == 'e':
                    isQName = True
            isText = not (isNumeric or isBool or isDateTime or isQName)
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
            if unit:
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
            if unitId:
                attrs["unitRef"] = unitId
            if dec is not None:
                if isinstance(dec, float): # must be an integer
                    dec = int(dec)
                elif isinstance(dec, _STR_BASE) and '.' in dec:
                    dec = dec.partition('.')[0] # drop .0 from any SQLite string
                attrs["decimals"] = str(dec)  # somehow it is float from the database
            if False: # fact.isNil:
                attrs[XbrlConst.qnXsiNil] = "true"
                text = None
            elif numVal is not None:
                num = roundValue(numVal, None, dec) # round using reported decimals
                if dec is None or dec == "INF":  # show using decimals or reported format
                    dec = len(numVal.partition(".")[2])
                else: # max decimals at 28
                    dec = max( min(int(float(dec)), 28), -28) # 2.7 wants short int, 3.2 takes regular int, don't use _INT here
                text = Locale.format(self.modelXbrl.locale, "%.*f", (dec, num))
            elif dateVal is not None:
                text = dateVal
            elif boolVal is not None:
                text = 'true' if boolVal.lower() in ('t', 'true', '1') else 'false'
            else:
                if isQName: # declare namespace
                    addQnameValue(modelXbrl.modelDocument, qname(textVal, prefixedNamespaces))
                text = textVal
            modelXbrl.createFact(conceptQn, attributes=attrs, text=text)
            
        # add footnotes if any
        
        # save to file
        modelXbrl.saveInstance(overrideFilepath=loadDBsaveToFile)
        modelXbrl.modelManager.showStatus(_("Saved extracted instance"), 5000)
        return modelXbrl.modelDocument
