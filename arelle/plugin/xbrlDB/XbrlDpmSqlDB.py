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
from arelle.ModelDocument import Type, create as createModelDocument
from arelle import Locale, ValidateXbrlDimensions
from arelle.ModelValue import qname, dateTime, DATEUNION
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlUtil import xmlstring, datetimeValue, addChild, addQnameValue, addProcessingInstruction
from arelle import XbrlConst
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from decimal import Decimal, InvalidOperation

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
                "dAvailableTable", "dFact", "dInstance",
                "dProcessingContext", "dProcessingFact",
                "mConcept", "mDomain", "mMember", "mModule", "mOwner",
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
            self.lockTables(("dAvailableTable", "dInstance",  "dFact", 
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
        # find primary model taxonomy of instance
        moduleId = None
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            for refDoc, ref in self.modelXbrl.modelDocument.referencesDocument.items():
                if refDoc.inDTS and ref.referenceType == "href":
                    table = self.getTable('mModule', 'ModuleID', 
                                          ('TaxonomyID', 'XBRLSchemaRef'), 
                                          ('XBRLSchemaRef',), 
                                          ((None, # taxonomy ID
                                            refDoc.uri
                                            ),),
                                          checkIfExisting=True,
                                          returnExistenceStatus=True)
                    for id, xbrlSchemaRef, existenceStatus in table:
                        moduleId = id
                        break
                    if moduleId:
                        break
        for cntx in self.modelXbrl.contexts.values():
            if cntx.isInstantPeriod:
                entityCode = cntx.entityIdentifier[1]
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
                              ((moduleId,
                                self.modelXbrl.uri,
                                None,
                                now,
                                "http://www.xbrl.org/lei",
                                entityCode, 
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
        for tableName in ("dFact", "dProcessingContext", "dProcessingFact"):
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName(tableName), instanceId), 
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
        contextSortedTypedDims = dict((cntx.id, dimKey(cntx, typedDim=True))
                                      for cntx in self.modelXbrl.contexts.values()
                                      if any(dim.isTyped for dim in cntx.qnameDims.values()))
        
        def met(fact):
            return "MET({})".format(fact.qname)
        
        def metDimKey(fact):
            key = met(fact)
            if fact.contextID in contextSortedDims:
                key += '|' + contextSortedDims[fact.contextID]
            return key
        
        def metDimTypedKey(fact):
            if fact.contextID in contextSortedTypedDims:
                key = met(fact)
                if fact.contextID in contextSortedTypedDims:
                    key += '|' + contextSortedTypedDims[fact.contextID]
                return key
            return None
                
            
        table = self.getTable("dProcessingContext", None,
                              ('InstanceID', 'ContextID', 'SortedDimensions', 'NotValid'),
                              ('InstanceID', 'ContextID'),
                              tuple((instanceId,
                                     cntxID,
                                     cntxDimKey,
                                     False
                                     )
                                    for cntxID, cntxDimKey in sorted(contextSortedDims.items())))
        
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
                    """ deprecated ver 7
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
                    """
                    pass
                else:
                    """ deprecated ver 7
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
                    """
                dFacts.append((instanceId,
                               metDimKey(f),
                               metDimTypedKey(f),
                               str(f.unit.measures[0][0]) if isNumeric and f.unit is not None and f.unit.isSingleMeasure else None,
                               f.decimals,
                               xValue if isNumeric else None,
                               xValue if isDateTime else None,
                               xValue if isBool else None,
                               xValue if isText else None
                            ))
                dProcessingFacts.append((instanceId,
                                         met(f),
                                         f.contextID if isNumeric else None,                                         
                                         xValue if isText or isBool else None,
                                         xValue if isNumeric else None,
                                         xValue if isDateTime else None,
                                         None))
        table = self.getTable("dFact", None,
                              ('InstanceID', 'DataPointSignature', 'DataPointSignatureWithValuesForWildcards', 
                               'Unit', 'Decimals',
                               'NumericValue', 'DateTimeValue', 'BooleanValue', 'TextValue'),
                              ('InstanceID', ),
                              dFacts)
        table = self.getTable("dProcessingFact", None,
                              ('InstanceID', 'Metric', 'ContextID', 
                               'ValueTxt', 'ValueDecimal', 'ValueDate',
                               'Error'),
                              ('InstanceID', ),
                              dProcessingFacts)
        
    def loadXbrlFromDB(self, loadDBsaveToFile):
        # load from database
        modelXbrl = self.modelXbrl
        
        # find instance in DB
        instanceURI = os.path.basename(loadDBsaveToFile)
        results = self.execute("SELECT InstanceID, ModuleID, EntityScheme, PeriodEndDateOrInstant"
                               " FROM dInstance WHERE FileName = '{}'"
                               .format(instanceURI))
        instanceId = moduleId = None
        for instanceId, moduleId, entId, datePerEnd in results:
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
            results = self.execute("""
SELECT DISTINCT mo.OwnerName AS Owner,
        CASE
             WHEN mo.OwnerId > do.OwnerId THEN mo.OwnerPrefix || '_' || do.OwnerPrefix 
             ELSE do.OwnerPrefix 
        END || '_' || d.DomainCode AS Prefix,
        mo.OwnerNamespace || '/dict/dom/' || CASE
             WHEN mo.OwnerId > do.OwnerId THEN do.OwnerPrefix || '_' || d.DomainCode 
             ELSE d.DomainCode 
        END AS Namespace
   FROM mMember m
        INNER JOIN mConcept mc
                ON mc.ConceptID = m.ConceptID
        INNER JOIN mOwner mo
                ON mo.OwnerID = mc.OwnerID
        INNER JOIN mDomain d
                ON d.ConceptID = m.DomainID
        INNER JOIN mConcept dc
                ON dc.ConceptID = d.ConceptID
        INNER JOIN mOwner do
                ON do.OwnerID = dc.OwnerID
  WHERE d.DomainCode != 'met'
UNION
SELECT DISTINCT do.OwnerName AS Owner,
                do.OwnerPrefix || '_typ' AS Prefix,
                do.OwnerNamespace || '/dict/typ' AS Namespace
           FROM mDomain d
                INNER JOIN mConcept dc
                        ON dc.ConceptID = d.ConceptID
                INNER JOIN mOwner do
                        ON do.OwnerID = dc.OwnerID
          WHERE d.IsTypedDomain = 1
UNION
SELECT do.OwnerName AS Owner,
       do.OwnerPrefix || '_' || d.DomainCode AS Prefix,
       mo.OwnerNamespace || '/dict/met' AS Namespace
  FROM mMember m
       INNER JOIN mConcept mc
               ON mc.ConceptID = m.ConceptID
       INNER JOIN mOwner mo
               ON mo.OwnerID = mc.OwnerID
       INNER JOIN mDomain d
               ON d.ConceptID = m.DomainID
       INNER JOIN mConcept dc
               ON dc.ConceptID = d.ConceptID
       INNER JOIN mOwner do
               ON do.OwnerID = dc.OwnerID
 WHERE d.DomainCode = 'met'
UNION
SELECT DISTINCT dimo.OwnerName AS Owner,
                dimo.OwnerPrefix || '_dim' AS Prefix,
                dimo.OwnerNamespace || '/dict/dim' AS Namespace
           FROM mDimension dim
                INNER JOIN mConcept dimc
                        ON dimc.ConceptID = dim.ConceptID
                INNER JOIN mOwner dimo
                        ON dimo.OwnerID = dimc.OwnerID
UNION
SELECT 'Common' AS Owner,
       '' AS Prefix,
       'http://www.xbrl.org/2003/instance' AS Namespace
UNION
SELECT 'Common' AS Owner,
       'iso4217' AS Prefix,
       'http://www.xbrl.org/2003/iso4217' AS Namespace
UNION
SELECT 'Common' AS Owner,
       'link' AS Prefix,
       'http://www.xbrl.org/2003/linkbase' AS Namespace
UNION
SELECT 'Common' AS Owner,
       'find' AS Prefix,
       'http://www.eurofiling.info/xbrl/ext/filing-indicators' AS Namespace
UNION
SELECT 'Common' AS Owner,
       'xbrldi' AS Prefix,
       'http://xbrl.org/2006/xbrldi' AS Namespace
UNION
SELECT 'Common' AS Owner,
       'xlink' AS Prefix,
       'http://www.w3.org/1999/xlink' AS Namespace;
            """)
            
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
        """ deprecated ver 7
        result = self.execute("SELECT VariableId, VariableKey FROM DataPointVariable WHERE VariableId in ({})"
                              .format(', '.join(fact[2]
                                                for fact in factsTbl
                                                if fact[2])))
        dimsTbl = dict((varId, varKey)
                       for varId, varKey in result)
        """
        
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
                cntxId = 'c{}'.format(len(cntxTbl) + 1)
                cntxTbl[cntxKey] = cntxId
                qnameDims = {}
                for dim in dims.split('|'):
                    dQn, sep, dVal = dim[:-1].partition('(')
                    dimQname = qname(dQn, prefixedNamespaces)
                    if dVal.startswith('<'): # typed dim
                        mem = typedDimElt(dVal)
                    else:
                        mem = qname(dVal, prefixedNamespaces)
                    qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "scenario")
                    
                modelXbrl.createContext("http://www.xbrl.org/lei",
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
