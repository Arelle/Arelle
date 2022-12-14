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


See COPYRIGHT.md for copyright information.


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

concrete example:
   python3.4 arelleCmdLine.py -f "/Users/hermf/Documents/mvsl/projects/EIOPA/xbrt/13. XBRL Instance Documents/1.5.2 (generated with DPM Architect)/arg.xbrl"  --formula none --store-to-XBRL-DB ",,,,/users/hermf/temp/DBtest5.xbrt,90,sqliteDpmDB" --internetConnectivity offline --skipDT --plugins logging/dpmSignature.pyS

'''

import time, datetime, os, re
from collections import defaultdict
from arelle.HashUtil import Md5Sum
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle import Locale, ValidateXbrlDimensions
from arelle.ModelValue import qname, QName, dateTime, DATE, dateunionDate, DateTime
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlUtil import xmlstring, datetimeValue, DATETIME_MAXYEAR, dateunionValue, addChild, addQnameValue, addProcessingInstruction
from arelle import XbrlConst
from arelle.XmlValidate import UNKNOWN, NONE as xmlValidateNONE, INVALID, VALID
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from decimal import Decimal, InvalidOperation
from numbers import Number
from _ctypes import _memset_addr

qnFindFilingIndicators = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:fIndicators")
qnFindFilingIndicator = qname("{http://www.eurofiling.info/xbrl/ext/filing-indicators}find:filingIndicator")
decimalsPattern = re.compile("^(-?[0-9]+|INF)$")
sigDimPattern = re.compile(r"([^(]+)[(]([^\[)]*)(\[([0-9;]+)\])?[)]")
schemaRefDatePattern = re.compile(r".*/([0-9]{4}-[01][0-9]-[0-3][0-9])/mod.*")
ONE = Decimal("1")
ONE00 = Decimal("1.00")
ONE0000 = Decimal("1.0000")

def insertIntoDB(modelXbrl,
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, loadDBsaveToFile=None, loadInstanceId=None,
                 streamingState=None, streamedFacts=None, schemaRefSubstitutions=None,
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
                if not xbrlDbConn.insertInstanceToDB(isStreaming=True):
                    return False
            result = xbrlDbConn.insertDataPointsToDB(streamedFacts, isStreaming=True)
        elif streamingState == "finish":
            xbrlDbConn = modelXbrl.streamingConnection
            if xbrlDbConn.isClosed:  # may have closed due to exception
                xbrlDbConn.finishInsertXbrlToDB()
            del modelXbrl.streamingConnection # dereference in case of exception during closing
            xbrlDbConn.close()
        else:
            xbrlDbConn = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
            xbrlDbConn.verifyTables()
            if schemaRefSubstitutions:
                xbrlDbConn.schemaRefSubstitutions = dict(_keyVal.split(":")[0:2] for _keyVal in schemaRefSubstitutions.split(";"))
            else:
                xbrlDbConn.schemaRefSubstitutions = None
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
                "dFact", "dFilingIndicator", "dInstance",
                # "dAvailableTable", "dProcessingContext", "dProcessingFact",
                "mConcept", "mDomain", "mMember", "mModule", "mOwner", "mTemplateOrTable",
                }

EMPTYSET = set()

def dimValKey(cntx, typedDim=False, behaveAsTypedDims=EMPTYSET, restrictToDims=None):
    return '|'.join(sorted("{}({})".format(dim.dimensionQname,
                                           dim.memberQname if dim.isExplicit and dim not in behaveAsTypedDims
                                           else dim.memberQname if typedDim and not dim.isTyped
                                           else "<{}/>".format(dim.typedMember.qname)
                                                 if typedDim and dim.typedMember.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1")
                                           # else xmlstring(dim.typedMember, stripXmlns=True) if typedDim
                                           # use corrected prefix in typedMember.qname and compatible with native c# implementation
                                           else "<{0}>{1}</{0}>".format(dim.typedMember.qname,dim.typedMember.stringValue) if typedDim
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
            self.insertInstanceToDB(isStreaming=False)
            self.insertDataPointsToDB(self.modelXbrl.facts, isStreaming=False)
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
        self.lockTables(("dInstance",  "dFact", "dFilingIndicator",
                         # "dAvailableTable", "dProcessingContext", "dProcessingFact"
                         ), isSessionTransaction=True)

        self.dropTemporaryTable()
        self.startedAt = time.time()

    def insertInstanceToDB(self, isStreaming=False):
        now = datetime.datetime.now()
        # find primary model taxonomy of instance
        self.modelXbrl.profileActivity()
        self.moduleId = None
        self.numFactsInserted = 0
        self.availableTableRows = defaultdict(set) # index (tableID, zDimVal) = set of yDimVals
        self.dFilingIndicators = {} # index qName, value filed (boolean)
        self.filedFilingIndicators = None # comma separated list of positive filing indicators
        self.filingIndicatorReportsFacts = {} # index by filing indicator to be reported, value = True if it has any facts reported
        self.metricsForFilingIndicators = defaultdict(set) # index (metric) of which filing indicators contains metric
        self.signaturesForFilingIndicators = defaultdict(list)
        self.entityCurrency = None
        self.tableIDs = set()
        self.metricAndDimensionsTableId = defaultdict(set)

        _instanceSchemaRef = "(none)"
        if self.modelXbrl.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL):
            for refDoc, ref in self.modelXbrl.modelDocument.referencesDocument.items():
                if refDoc.inDTS and "href" in ref.referenceTypes:
                    if self.moduleId is None:
                        _instanceSchemaRef = _schemaRef = refDoc.uri
                        # perform schemaRef substitutions
                        if self.schemaRefSubstitutions:
                            for _from, _to in self.schemaRefSubstitutions.items():
                                _schemaRef = _schemaRef.replace(_from, _to)
                        result = self.execute("SELECT ModuleID FROM mModule WHERE XBRLSchemaRef = '{}'"
                                              .format(_schemaRef))
                        for moduleId in result:
                            self.moduleId = moduleId[0] # only column in row returned
                            break
                        _match = schemaRefDatePattern.match(_instanceSchemaRef)
                        if _match:
                            self.isEIOPAfullVersion = _match.group(1) > "2015-02-28"
                            self.isEIOPA_2_0_1 = _match.group(1) >= "2015-10-21"
                            break
                    else:
                        self.modelXbrl.error(("EBA.1.5","EIOPA.S.1.5.a"),
                                             _("Loading XBRL DB: Multiple schema files referenced: %(schemaRef)s"),
                                             modelObject=self.modelXbrl, schemaRef=refDoc.uri)
        if not self.moduleId:
            raise DpmDBException(("EBA.1.5","EIOPA.S.1.5.a"),
                    _("A ModuleID could not be found in table mModule for instance schemaRef {0}.")
                    .format(_instanceSchemaRef))
        self.modelXbrl.profileActivity("dpmDB 01. Get ModuleID for instance schema", minTimeToShow=2.0)
        periodInstantDate = None
        entityIdentifier = ''
        entityScheme = ''
        self.cntxDates = set()
        self.entityIdentifiers = set() # set of entity identifiers
        for cntx in self.modelXbrl.contexts.values():
            if cntx.isInstantPeriod:
                entityScheme, entityIdentifier = cntx.entityIdentifier
                periodInstantDate = cntx.endDatetime.date() - datetime.timedelta(1)  # convert to end date
                self.cntxDates.add(cntx.endDatetime) # for error checks
                self.entityIdentifiers.add(entityIdentifier)
                break
        if not periodInstantDate:
            return False # needed context not yet available
        # in streaming mode entity Currency may not be available yet, if so do it later when storing fact
        for unit in self.modelXbrl.units.values():
            if unit.isSingleMeasure and unit.measures[0] and unit.measures[0][0].namespaceURI == XbrlConst.iso4217:
                self.entityCurrency = unit.measures[0][0].localName
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
                                entityScheme,
                                entityIdentifier,
                                periodInstantDate,
                                None,
                                self.entityCurrency
                                ),),
                              checkIfExisting=True)
        for id, fileName in table:
            self.instanceId = id
            break
        self.modelXbrl.profileActivity("dpmDB 02. Store into dInstance", minTimeToShow=2.0)
        self.showStatus("deleting prior data points of this instance")
        for tableName in ("dFact", "dFilingIndicator", "dInstanceLargeDimensionMember"): # , "dAvailableTable",
            self.execute("DELETE FROM {0} WHERE {0}.InstanceID = {1}"
                         .format( self.dbTableName(tableName), self.instanceId),
                         close=False, fetch=False)
        self.modelXbrl.profileActivity("dpmDB 03. Delete prior data points of this instance", minTimeToShow=2.0)

        self.showStatus("obtaining mapping table information")
        '''
        result = self.execute("SELECT MetricAndDimensions, TableID FROM mTableDimensionSet WHERE ModuleID = {}"
                              .format(self.moduleId))
        for metricAndDimensions, tableID in result:
            self.tableIDs.add(tableID)
            self.metricAndDimensionsTableId[metricAndDimensions].add(tableID)
        '''
        self.modelXbrl.profileActivity("dpmDB 04. Get TableDimensionSet for Module", minTimeToShow=2.0)

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

        '''
        # get qnames of percent items
        result = self.execute("SELECT mem.MemberXbrlCode from mMetric met, mMember mem "
                              "WHERE met.DataType = 'Percent' AND mem.MemberCode like 'pi%' "
                              "AND mem.MemberId = met.CorrespondingMemberId")
        self.percentMetrics = {p[0] for p in result}
        '''

        # get typed dimension domain element qnames
        result = self.execute("SELECT dim.DimensionXBRLCode, ( '[<]' || dom.DomainXBRLCode || '[>]' || "
                              " CASE WHEN dom.DataType = 'Integer' THEN '\\d+' ELSE '.+' END || " # HF change string dim from \\S+ to .+
                              " '[<][/]' || dom.DomainXBRLCode || '[>]'  "
                              " || '|[<]' || dom.DomainXBRLCode || '/>' )" # removed: ' xsi:nil=''true''
                              "FROM mDimension dim, mDomain dom "
                              "WHERE dim.IsTypedDimension AND dim.DomainID = dom.DomainID")
        self.typedDimensionDomain = dict((dim,re.compile(dom)) for dim, dom in result)

        # get large dimension ids & qnames
        result = self.execute("SELECT dim.DimensionXBRLCode, dim.DimensionId "
                              "FROM mModuleLargeDimension mld, mDimension dim "
                              " WHERE mld.ModuleId = {} AND dim.DimensionId = mld.DimensionId"
                              .format(self.moduleId))
        self.largeDimensionIds = dict((_dimQname, _dimId) for _dimQname, _dimId in result)

        self.largeDimensionMemberIds = defaultdict(dict)

        # get explicit dimension domain element qnames
        result = self.execute("SELECT dim.DimensionXBRLCode, mem.MemberXBRLCode, mem.MemberId "
                              "FROM mDomain dom "
                              "left outer join mHierarchy h on h.DomainID = dom.DomainID "
                              "left outer join mHierarchyNode hn on hn.HierarchyID = h.HierarchyID "
                              "left outer join mMember mem on mem.MemberID = hn.MemberID "
                              "inner join mDimension dim on dim.DomainID = dom.DomainID and not dim.isTypedDimension")
        self.explicitDimensionDomain = defaultdict(set)
        self.domainHiearchyMembers = {}
        for _dim, _memQn, _memId in result:
            if _memQn:
                self.explicitDimensionDomain[_dim].add(_memQn)
                if _dim in self.largeDimensionIds:
                    self.largeDimensionMemberIds[_dim][_memQn] = _memId

        # get enumeration element values
        result = self.execute("select mem.MemberXBRLCode, enum.MemberXBRLCode from mMetric met "
                              "inner join mMember mem on mem.MemberID = met.CorrespondingMemberID "
                              "inner join mHierarchyNode hn on hn.HierarchyID = met.ReferencedHierarchyID "
                              "inner join mMember enum on enum.MemberID = hn.MemberID "
                              "where (hn.IsAbstract is null or hn.IsAbstract = 0) "
                              "      and case when met.HierarchyStartingMemberID is not null then "
                              "        (hn.Path like '%'||ifnull(met.HierarchyStartingMemberID,'')||'%' "
                              "            or (hn.MemberID = ifnull(met.HierarchyStartingMemberID,'') and 1 = ifnull(met.IsStartingMemberIncluded,0))) "
                              "        else 1 end")
        self.enumElementValues = defaultdict(set)
        for _elt, _enum in result:
            self.enumElementValues[_elt].add(_enum)

        self.showStatus("insert data points, " +
                        ("streaming" if isStreaming else "non-streaming"))

        # find dpm canonical prefixes and namespaces in DB
        results = self.execute("SELECT * FROM [vwGetNamespacesPrefixes]")
        self.dpmNsPrefix = dict((namespace, prefix)
                                for owner, prefix, namespace in results)

        # get S.2.18.c (a) metrics with dec >= 2 accuracy
        results = self.execute("select distinct mem.MemberXBRLCode from mOrdinateCategorisation oc "
                               "inner join mAxisOrdinate ao on ao.OrdinateID = oc.OrdinateID "
                               "inner join mTableAxis ta on ta.AxisID = ao.AxisID "
                               "inner join mTable t on t.TableID = ta.TableID "
                               "inner join mMember mem on mem.MemberID = oc.MemberID "
                               "inner join mMetric met on met.CorrespondingMemberID = mem.MemberID and met.DataType = 'Monetary' "
                               "where (t.TableCode like 'S.06.02%' or t.TableCode like 'SE.06.02%' or t.TableCode like 'S.08.01%' or t.TableCode like 'S.08.02%' or t.TableCode like 'S.11.01%' or t.TableCode like 'E.01.01%') and mem.MemberXBRLCode not like 's2hd_met%' "
                               "order by t.TableCode;")
        self.s_2_18_c_a_Metrics = set(mem for mem in results)
        return True

    def correctQnamePrefix(self, qn):
        if qn.prefix != self.dpmNsPrefix[qn.namespaceURI]:
            qn.prefix = self.dpmNsPrefix[qn.namespaceURI]

    def correctFactQnamePrefixes(self, f, xValue):
        self.correctQnamePrefix(f.qname)
        cntx = f.context
        if cntx is not None and not getattr(cntx, "_cntxPrefixesCorrected", False):
            for dim in cntx.qnameDims.values():
                self.correctQnamePrefix(dim.dimensionQname)
                if dim.isExplicit:
                    self.correctQnamePrefix(dim.memberQname)
                else:
                    self.correctQnamePrefix(dim.typedMember.qname)
            cntx._cntxPrefixesCorrected = True
        if isinstance(xValue, QName):
            self.correctQnamePrefix(xValue)

    def loadAllowedMetricsAndDims(self):
        self.filedFilingIndicators = ', '.join("'{}'".format(_filingIndicator)
                                               for _filingIndicator, _filed in self.dFilingIndicators.items()
                                               if _filed)
        self.allFilingIndicators = ', '.join("'{}'".format(_filingIndicator)
                                             for _filingIndicator, _filed in self.dFilingIndicators.items())
        # check metrics encountered for filing indicators found
        results = self.execute(
            "select distinct mem.MemberXBRLCode, tott.TemplateOrTableCode "
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
             .format(self.filedFilingIndicators, self.moduleId))
        for r in results:
            self.metricsForFilingIndicators[r[0]].add(r[1])

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
             .format(self.filedFilingIndicators, self.moduleId))

        self.signaturesForFilingIndicators = defaultdict(list)
        for dpSig in results:
            _met, _sep, dims = dpSig[0].partition("|")
            _dimVals = {}
            for _dimVal in dims.split("|"):
                _dimSigMatch = sigDimPattern.match(_dimVal)
                if _dimSigMatch:
                    _dim, _sig, _hierTerm, _hier = _dimSigMatch.groups()
                    _dimVals[_dim] = (_sig, _hier)
            self.signaturesForFilingIndicators[_met[4:-1]].append(_dimVals)
        pass

    def dFactValue(self, dFact):
        for v in dFact[4:7]:
            if v is not None:
                return v
        return None

    def dHierarchyMembers(self, hierarchyKey):
        if hierarchyKey in self.domainHiearchyMembers:
            return self.domainHiearchyMembers[hierarchyKey]
        _hierarchies = hierarchyKey.split(";")
        if len(_hierarchies) == 1:
            results = self.execute(
                "select mem.MemberXBRLCode from mHierarchyNode hn "
                "inner join mMember mem on mem.MemberID = hn.MemberID "
                "where hn.HierarchyID = {0} and hn.IsAbstract != 1"
                 .format(_hierarchies[0]))
        elif len(_hierarchies) == 3:
            results = self.execute(
                "select distinct mem.MemberXBRLCode from mHierarchyNode hn "
                "left outer join mHierarchyNode hn2 on hn2.ParentMemberID = hn.MemberID and hn2.HierarchyID = hn.HierarchyID "
                "left outer join mHierarchyNode hn3 on hn3.ParentMemberID = hn2.MemberID and hn3.HierarchyID = hn.HierarchyID "
                "left outer join mHierarchyNode hn4 on hn4.ParentMemberID = hn3.MemberID and hn4.HierarchyID = hn.HierarchyID "
                "inner join mMember mem on mem.MemberID = hn.MemberID or mem.MemberID = hn2.MemberID or mem.MemberID = hn3.MemberID or mem.MemberID = hn4.MemberID "
                "where hn.HierarchyID = {0} and hn.MemberID = {1} "
                 .format(_hierarchies[0], _hierarchies[1]))
        else:
            results = () # empty tuple
        _mems = [_memrow[0] for _memrow in results] # tuple of select fields per member found
        self.domainHiearchyMembers[hierarchyKey] = _mems
        return _mems

    def validateFactSignature(self, dpmSignature, fact): # omit fact if checking at end
        _met, _sep, _dimVals = dpmSignature.partition("|")
        _metQname = _met[4:-1]
        if not self.filedFilingIndicators:
            pass # validate/EBA provides error messages when no positive filing indicators
        elif _metQname not in self.metricsForFilingIndicators:
            if isinstance(fact, ModelFact):
                self.modelXbrl.error(("EBA.1.7.1", "EIOPA.1.7.1"),
                                     _("Loading XBRL DB: Fact QName not allowed for filing indicators %(qname)s, contextRef %(context)s, value: %(value)s"),
                                     modelObject=fact, dpmSignature=dpmSignature, qname=fact.qname, context=fact.contextID, value=fact.value)
            elif isinstance(fact, (tuple,list)): # from database dFact record
                self.modelXbrl.error(("EBA.1.7.1", "EIOPA.1.7.1"),
                                     _("Loading XBRL DB: Fact QName not allowed for filing indicators %(qname)s, value: %(value)s"),
                                     modelObject=self.modelXbrl, dpmSignature=dpmSignature, qname=_metQname, value=self.dFactValue(fact))
        else:
            _dimVals = dict((_dim,_val[:-1])
                            for _dimVal in _dimVals.split("|")
                            for _dim, _sep, _val in (_dimVal.partition("("),))
            _dimSigs = self.signaturesForFilingIndicators.get(_metQname) # value is (mem, hier)
            _largeDimIdMemIds = set()
            _sigMatched = False
            _missingDims = _differentDims = _extraDims = set()
            _closestMatch = 9999
            _closestMatchSig = None
            if _dimSigs and _dimSigs[0]: # don't pass [{}]
                for _dimSig in _dimSigs: # alternate signatures valid for member
                    _lenDimVals = len(_dimVals)
                    _lenDimSig = sum(1
                                     for _dim, _valHier in _dimSig.items()
                                     if _valHier[0] != "*?" or _dim in _dimVals)
                    _differentDims = set(_dim
                                         for _dim, _val in _dimVals.items()
                                         if _dim in _dimSig and _dimSig[_dim][0] not in ("*", "*?", _val))
                    _differentDimCount = abs(_lenDimSig - _lenDimVals)
                    _difference = _differentDimCount + len(_differentDims)
                    if _difference == 0:
                        # check * dimensions
                        _largeDimIdMemIds.clear()
                        for _dim, _val in _dimVals.items():
                            _sigVal, _sigHier = _dimSig.get(_dim, (None,None))
                            if _sigVal in ("*", "*?"):
                                if _dim in self.explicitDimensionDomain:
                                    if _sigHier:
                                        _dimMems = self.dHierarchyMembers(_sigHier)
                                        # print("trying to match {} to {}".format(_val,_dimMems))
                                    else:
                                        _dimMems = self.explicitDimensionDomain[_dim]
                                    if _val not in _dimMems:
                                        _difference += 1
                                        _differentDims.add(_dim)
                                elif _dim in self.typedDimensionDomain:
                                    if not self.typedDimensionDomain[_dim].match(_val):
                                        _difference += 1
                                        _differentDims.add(_dim)
                            try:
                                _largeDimIdMemIds.add((self.largeDimensionIds[_dim], self.largeDimensionMemberIds[_dim][_val]))
                            except KeyError:
                                pass
                        if _difference == 0:
                            _sigMatched = True
                            #print ("successful match {}".format(_dimSig))   # debug successful match
                            break
                    if _difference < _closestMatch:
                        _extraDims = dimVals.keys() - _dimSig.keys()
                        _missingDims = set(_dim
                                           for _dim, _val in _dimSig.items()
                                           if _dim not in _dimVals and _val != "*?")
                        _closestMatchDiffDims = _differentDims
                        _closestMatchSig = _dimSig
                        _closestMatch = _difference
                if _sigMatched:
                    self.largeDimIdMemIds |= _largeDimIdMemIds
                else:
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
            for _filingIndicator in self.metricsForFilingIndicators[_metQname]:
                if _filingIndicator in self.filingIndicatorReportsFacts:
                    self.filingIndicatorReportsFacts[_filingIndicator] = True

    def insertDataPointsToDB(self, facts, isStreaming=False):
        instanceId = self.instanceId
        if instanceId is None:
            return # cannot proceed with insertion

        dFacts = []
        dFactHashes = {}
        skipDTS = self.modelXbrl.skipDTS
        for f in facts: # facts may be a batch of streamed facts
            cntx = f.context
            concept = f.concept
            c = f.qname.localName[0]
            isNumeric = isBool = isDateTime = isText = False
            isInstant = None
            isValid = skipDTS or f.xValid >= VALID
            if concept is not None:
                if concept.isNumeric:
                    isNumeric = True
                    if f.precision:
                        self.modelXbrl.error("sqlDB:factPrecisionError",
                                             _("Loading XBRL DB: Fact contains a precision attribute %(qname)s, precision %(precision)s, context %(context)s, value %(value)s"),
                                             modelObject=f, qname=f.qname, context=f.contextID, value=f.value, precision=f.precision)
                        isValid = False
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
                    if c in ('m', 'p', 'i', 'r'):
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
                                xValue = None
                                isValid = False
                            else:
                                if c == 'i':
                                    xValue = int(xValue)
                                else:
                                    xValue = Decimal(xValue)
                        except InvalidOperation:
                            xValue = Decimal('NaN')
                        except ValueError:
                            xValue = None
                        if f.unit is None:
                            self.modelXbrl.error("sqlDB:factUnitError",
                                                 _("Loading XBRL DB: Fact missing unit %(qname)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                            isValid = False
                        if f.precision:
                            self.modelXbrl.error("sqlDB:factPrecisionError",
                                                 _("Loading XBRL DB: Fact contains a precision attribute %(qname)s, precision %(precision)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value, precision=f.precision)
                            isValid = False
                        elif not f.decimals or not decimalsPattern.match(f.decimals):
                            self.modelXbrl.error("sqlDB:factDecimalsError",
                                                 _("Loading XBRL DB: Fact contains an invalid decimals attribute %(qname)s, decimals %(decimals)s, context %(context)s, value %(value)s"),
                                                 modelObject=f, qname=f.qname, context=f.contextID, value=f.value, decimals=f.decimals)
                            isValid = False
                    else:
                        if c == 'd':
                            isDateTime = True
                            try:
                                xValue = dateTime(xValue, type=DATE, castException=ValueError)
                                if xValue.dateOnly:
                                    xValue = dateunionDate(xValue)
                            except ValueError:
                                self.modelXbrl.error("sqlDB:factValueError",
                                                     _("Loading XBRL DB: Fact %(qname)s, context %(context)s, value: %(value)s"),
                                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                                xValue = None
                                isValid = False
                        elif c in ('b', 't'):
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
                                xValue = None
                                isValid = False
                        elif c == 'e':
                            fQn = str(f.qname)
                            if fQn in self.enumElementValues and xValue not in self.enumElementValues[fQn]:
                                self.modelXbrl.error("sqlDB:factValueError",
                                                     _("Loading XBRL DB: Fact %(qname)s, context %(context)s, value: %(value)s"),
                                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
                                isValid = False
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
            if c == 'm' and not self.entityCurrency and f.unit is not None and f.unit.measures[0][0].namespaceURI == XbrlConst.iso4217:
                self.entityCurrency = f.unit.measures[0][0].localName
                self.execute("UPDATE dInstance SET EntityCurrency='{}' WHERE InstanceID={}"
                              .format(self.entityCurrency, self.instanceId))
            isText = not (isNumeric or isBool or isDateTime) # 's' or 'u' type
            if f.qname == qnFindFilingIndicators:
                if cntx is not None:
                    self.modelXbrl.error("sqlDB:filingIndicatorsContextError",
                                         _("Loading XBRL DB: Filing indicators tuple has a context, contextRef %(context)s"),
                                         modelObject=f, context=f.contextID)
                for filingIndicator in f.modelTupleFacts:
                    if filingIndicator.qname == qnFindFilingIndicator:
                        _filingIndicator = filingIndicator.textValue.strip()
                        _filed = filingIndicator.get("{http://www.eurofiling.info/xbrl/ext/filing-indicators}filed", "true") in ("true", "1")
                        if _filingIndicator in self.dFilingIndicators: # duplicate filing indicator
                            if _filed: # take positive value if duplicate
                                self.dFilingIndicators[_filingIndicator] = _filed
                        else:
                            self.dFilingIndicators[_filingIndicator] = _filed
                        if _filed:
                            self.filingIndicatorReportsFacts[_filingIndicator] = False
                        if filingIndicator.context is None:
                            self.modelXbrl.error("sqlDB:filingIndicatorContextError",
                                                 _("Loading XBRL DB: Filing indicator fact missing a context, value %(value)s"),
                                                 modelObject=filingIndicator, value=filingIndicator.value)
                self.loadAllowedMetricsAndDims() # reload metrics
            elif f.qname == qnFindFilingIndicator:
                continue # ignore root-level filing indicators, reported by validate/EBA
            elif cntx is None:
                self.modelXbrl.error("sqlDB:factContextError",
                                     _("Loading XBRL DB: Fact missing %(qname)s, contextRef %(context)s, value: %(value)s"),
                                     modelObject=f, qname=f.qname, context=f.contextID, value=f.value)
            else:
                # find which explicit dimensions act as typed
                behaveAsTypedDims = set()
                '''
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
                '''
                self.correctFactQnamePrefixes(f, xValue)
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
                elif isValid:
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
                if getattr(cntx, "xValid", UNKNOWN) == UNKNOWN: # no validation, such as skipDTS and no streaming
                    cntx.xValid = xmlValidateNONE # prevent detecting as UNKNOWN
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
                ''' moved to validate/EBA
                if cntx.isInstantPeriod and cntx.endDatetime not in self.cntxDates:
                    self.modelXbrl.error(("EBA.2.13","EIOPA.2.13"),
                                         _("Loading XBRL DB: Context has different date: %(context)s, date %(value)s"),
                                         modelObject=cntx, context=cntx.id, value=dateunionValue(cntx.endDatetime, subtractOneDay=True))
                    self.cntxDates.add(cntx.endDatetime)
                if cntx.entityIdentifier[1] not in self.entityIdentifiers:
                    self.modelXbrl.error(("EBA.2.9","EIOPA.2.9"),
                                     _("Loading XBRL DB: Context has different entity identifier: %(context)s %(value)s"),
                                     modelObject=cntx, context=cntx.id, value=cntx.entityIdentifier[1])
                    self.entityIdentifiers.add(cntx.entityIdentifier[1])
                '''
                if cntx.isStartEndPeriod and isInstant:
                    self.modelXbrl.error("sqlDB:factContextError",
                                     _("Loading XBRL DB: Instant metric %(qname)s has start end context: %(context)s"),
                                     modelObject=f, qname=f.qname, context=f.contextID)

        if not isStreaming:
            self.showStatus("Loading XBRL Instance {}, non-streaming, storing {} facts"
                            .format(os.path.basename(self.modelXbrl.uri),
                                    len(dFacts)))

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
            iFact = 0
            while iFact < len(dFacts):
                dFact = dFacts[iFact]
                dpSig = dFact[1]
                if dpSig in dupDpSigs:
                    metric, _sep, _dims = dpSig.partition('|')
                    metricPrefixedName = metric.partition('(')[2][:-1]
                    self.modelXbrl.error("sqlDB:factDuplicate",
                                         _("Loading XBRL DB: Fact is a duplicate %(qname)s, value=%(value)s"),
                                         modelObject=self.modelXbrl, qname=metricPrefixedName,
                                         value=(dFact[5] or dFact[6] or dFact[7] or dFact[4]))  # num last so zero isn't or'ed as bool false
                    del dFact[iFact]
                else:
                    iFact += 1
        # insert non-duplicate facts
        self.getTable("dFact", None,
                      ('InstanceID',
                       'DataPointSignature',
                       'Unit', 'Decimals',
                       'NumericValue', 'DateTimeValue', 'BooleanValue', 'TextValue'),
                      ('InstanceID', ),
                      dFacts,
                      returnMatches=False)

        factsInserted = self.numFactsInserted + len(dFacts)
        if not isStreaming:
            self.showStatus("Loading XBRL Instance {}, non-streaming, stored {} facts"
                            .format(os.path.basename(self.modelXbrl.uri),
                                    len(dFacts)))
        elif (self.numFactsInserted % 100) + len(dFacts) >= 100:
            self.showStatus("Loading XBRL Instance {}, streaming, at fact {}"
                            .format(os.path.basename(self.modelXbrl.uri),
                                    factsInserted))
        self.numFactsInserted = factsInserted
        return True  # True causes streaming to be able to dereference facts

    def finishInsertXbrlToDB(self):
        if self.instanceId is None:
            return

        self.modelXbrl.profileActivity("dpmDB 06. Build facts table for bulk DB update", minTimeToShow=2.0)

        # check filing indicators after facts loaded
        result = self.execute("SELECT InstanceID, DataPointSignature, Unit, Decimals, NumericValue, DateTimeValue, BooleanValue, TextValue "
                              "FROM dFact WHERE dFact.InstanceID = '{}'"
                              .format(self.instanceId))

        self.largeDimIdMemIds = set()
        for dFact in result:
            self.validateFactSignature(dFact[1], dFact)

        # large Dimension Member Ids
        if self.largeDimIdMemIds:
            self.getTable("dInstanceLargeDimensionMember", None,
                          ('InstanceID', 'DimensionID', 'MemberID'),
                          ('InstanceID', ),
                          ((self.instanceId, _dimId, _memId)
                           for _dimId, _memId in self.largeDimIdMemIds),
                          returnMatches=False)

        # availableTable processing
        # get filing indicator template IDs
        if self.dFilingIndicators: # missing and all false check in EBA/EIOPA validation
            results = self.execute("SELECT mToT2.TemplateOrTableCode, mToT2.TemplateOrTableID "
                                   "  FROM mModuleBusinessTemplate mBT, mTemplateOrTable mToT, mTemplateOrTable mToT2 "
                                   "  WHERE mBT.ModuleID = {0} AND"
                                   "        mToT.TemplateOrTableID = mBT.BusinessTemplateID AND"
                                   "        mToT.ParentTemplateOrTableID = mToT2.TemplateOrTableID AND"
                                   "        mToT2.TemplateOrTableCode in ({1})"
                                   .format(self.moduleId, self.allFilingIndicators))
            filingIndicatorCodeIDs = dict((code, id) for code, id in results)
            self.modelXbrl.profileActivity("dpmDB 07. Get business template filing indicator for module", minTimeToShow=2.0)

            if filingIndicatorCodeIDs.keys() != self.dFilingIndicators.keys():
                missingIndicators = set(filingIndicatorCodeIDs.keys() - self.dFilingIndicators.keys())
                if missingIndicators:
                    self.modelXbrl.error(("EBA.1.6","EIOPA.1.6.a"),
                                         _("The filing indicator IDs were not found for codes %(missingFilingIndicatorCodes)s"),
                                         modelObject=self.modelXbrl,
                                         missingFilingIndicatorCodes=','.join(missingIndicators))
                extraneousIndicators = self.dFilingIndicators.keys() - filingIndicatorCodeIDs.keys()
                if extraneousIndicators:
                    self.modelXbrl.error(("EIOPA.S.1.7.a"),
                                         _("The filing indicator IDs were not in scope for module %(missingFilingIndicatorCodes)s"),
                                         modelObject=self.modelXbrl,
                                         missingFilingIndicatorCodes=','.join(extraneousIndicators))

            self.getTable("dFilingIndicator", None,
                          ("InstanceID", "BusinessTemplateID", "Filed"),
                          ("InstanceID", "BusinessTemplateID"),
                          ((self.instanceId,
                            filingIndicatorCodeId,
                            self.dFilingIndicators.get(filingIndicatorCode))
                           for filingIndicatorCode, filingIndicatorCodeId in sorted(filingIndicatorCodeIDs.items())),
                          returnMatches=False)
            unreportedFilingIndicators = set(_filingIndicator
                                             for _filingIndicator, _isReported in self.filingIndicatorReportsFacts.items()
                                             if not _isReported)
            if unreportedFilingIndicators:
                self.modelXbrl.error(("EIOPA.1.7.b"),
                                     _("The filing indicator must not indicate filed when not reported in instance %(unreportedFilingIndicators)s"),
                                     modelObject=self.modelXbrl,
                                     unreportedFilingIndicators=','.join(sorted(unreportedFilingIndicators)))
        self.modelXbrl.profileActivity("dpmDB 08. Store dFilingIndicators", minTimeToShow=2.0)
        ''' deprecated
        table = self.getTable("dProcessingFact", None,
                              ('InstanceID', 'Metric', 'ContextID',
                               'ValueTxt', 'ValueDecimal', 'ValueDate',
                               'Error'),
                              ('InstanceID', ),
                              dProcessingFacts)
        '''
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
        self.modelXbrl.profileActivity("dpmDB 10. Bulk store dAvailableTable", minTimeToShow=2.0)
        '''

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
                    _("The instance was not found in table dInstance: %(instanceURI)s")
                    .format(loadInstanceId or instanceURI))


        # find module in DB
        self.showStatus("finding module in database")
        results = self.execute("SELECT XbrlSchemaRef FROM mModule WHERE ModuleID = {}".format(moduleId))
        xbrlSchemaRef = None
        for result in results:
            xbrlSchemaRef = result[0]
            break

        if not xbrlSchemaRef:
            raise DpmDBException("sqlDB:MissingDTS",
                    _("The module in mModule, corresponding to the instance, was not found for {0}")
                    .format(instanceId or instanceURI))

        _match = schemaRefDatePattern.match(xbrlSchemaRef)
        if _match:
            self.isEIOPAfullVersion = _match.group(1) > "2015-02-28"
            self.isEIOPA_2_0_1 = _match.group(1) >= "2015-10-21"
        else:
            self.isEIOPAfullVersion = self.isEIOPA_2_0_1 = False

        if modelXbrl.skipDTS:
            # find prefixes and namespaces in DB
            results = self.execute("SELECT * FROM [vwGetNamespacesPrefixes]")
            dpmPrefixedNamespaces = dict((prefix, namespace)
                                         for owner, prefix, namespace in results)

        # output attributin {comment string}|{processing instruction attributes}
        outputAttribution = getattr(modelXbrl.modelManager, "outputAttribution", "").partition("|")
        if self.isEIOPA_2_0_1:
            outputAttributionPIargs = outputAttribution[2] or None
            outputAttributionComment = None
            outputDocumentEncoding = "UTF-8"
        else:
            outputAttributionComment = outputAttribution[0] or None
            outputAttributionPIargs = None
            outputDocumentEncoding = "utf-8"

        # create the instance document and resulting filing
        modelXbrl.blockDpmDBrecursion = True
        modelXbrl.modelDocument = createModelDocument(
              modelXbrl,
              Type.INSTANCE,
              loadDBsaveToFile,
              schemaRefs=[xbrlSchemaRef],
              isEntry=True,
              initialComment=outputAttributionComment,
              documentEncoding=outputDocumentEncoding)
        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults

        if outputAttributionPIargs:
            addProcessingInstruction(modelXbrl.modelDocument.xmlRootElement,
                                     'instance-generator',
                                     outputAttributionPIargs.replace("'",'"'),
                                     insertBeforeParentElement=True) # passed as ' to avoid cmd line quoting problem in windows
        addProcessingInstruction(modelXbrl.modelDocument.xmlRootElement,
                                 'xbrl-streamable-instance',
                                 'version="1.0" contextBuffer="1"')
        addProcessingInstruction(modelXbrl.modelDocument.xmlRootElement,
                                 'xbrl-facts-check',
                                 'version="0.8"')

        xbrlFactsCheckSum = Md5Sum()

        # add roleRef and arcroleRef (e.g. for footnotes, if any, see inlineXbrlDocue)

        cntxTbl = {} # index by d
        unitTbl = {}

        # filing indicator code IDs
        # get filing indicators
        results = self.execute("SELECT mToT.TemplateOrTableCode, dFI.Filed"
                               "  FROM dFilingIndicator dFI, mTemplateOrTable mToT "
                               "  WHERE dFI.InstanceID = {} AND mTot.TemplateOrTableID = dFI.BusinessTemplateID"
                               .format(instanceId))
        filingIndicatorCodes = dict((code[0], code[1]) for code in results)

        if filingIndicatorCodes:
            modelXbrl.createContext(entScheme,
                        entId,
                        'instant',
                        None,
                        datePerEnd,
                        None, # no dimensional validity checking (like formula does)
                        {}, [], [],
                        id='c')
            cntxKey = ("", entId, datePerEnd) # context key for no dimensions
            cntxTbl[cntxKey] = 'c'
            filingIndicatorsTuple = modelXbrl.createFact(qnFindFilingIndicators, validate=False)
            if filingIndicatorsTuple is None:
                raise DpmDBException("sqlDB:createTupleError",
                                     _("Unable to create filing indicators tuple, please check if schema file was loaded"))
            for filingIndicatorCode, filed in filingIndicatorCodes.items():
                attributes = {"contextRef": "c"}
                if filed is not None and not filed:
                    attributes["{http://www.eurofiling.info/xbrl/ext/filing-indicators}filed"] = "false"
                f = modelXbrl.createFact(qnFindFilingIndicator,
                                     parent=filingIndicatorsTuple,
                                     attributes=attributes,
                                     text=filingIndicatorCode, validate=False)
                if f is None:
                    raise DpmDBException("sqlDB:createFactError",
                                         _("Unable to create filing indicator, please check if schema file was loaded"))
                xbrlFactsCheckSum += f.md5sum
            XmlValidate.validate(modelXbrl, filingIndicatorsTuple) # must validate after contents are created
            xbrlFactsCheckSum += filingIndicatorsTuple.md5sum


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
        prefixedNamespaces[None] = XbrlConst.xbrli # createInstance expects default prefix for xbrli
        if modelXbrl.skipDTS:
            prefixedNamespaces.update(dpmPrefixedNamespaces) # for skipDTS this is always needed

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
            c = conceptQn.localName[0]
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
                if c in ('m', 'p', 'r', 'i'):
                    isNumeric = True
                elif c == 'd':
                    isDateTime = True
                elif c in ('b', 't'):
                    isBool = True
                elif c == 'e':
                    isQName = True
            isText = not (isNumeric or isBool or isDateTime or isQName) # 's' or 'u' type
            if isinstance(datePerEnd, str):
                datePerEnd = datetimeValue(datePerEnd, addOneDay=True)
            cntxKey = (dims, entId, datePerEnd)
            if cntxKey in cntxTbl:
                cntxId = cntxTbl[cntxKey]
            else:
                cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                qnameDims = {}
                if dims:
                    for dim in dims.split('|'):
                        dQn, sep, dVal = dim[:-1].partition('(')
                        dimQname = qname(dQn, prefixedNamespaces)
                        if dVal.startswith('<'):
                            if "/>" in dVal: # now <a:b/> is nil, was "xsi:nil='true'"
                                mem = nilTypedDimElt(dQn)
                            else:
                                mem = typedDimElt(dVal)  # typed dim
                        else:
                            mem = qname(dVal, prefixedNamespaces) # explicit dim (even if treat-as-typed)
                        qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "scenario")

                _cntx = modelXbrl.createContext(
                                        entScheme,
                                        entId,
                                        'instant',
                                        None,
                                        datePerEnd,
                                        None, # no dimensional validity checking (like formula does)
                                        qnameDims, [], [],
                                        id=cntxId)
                cntxTbl[cntxKey] = cntxId

            if isNumeric and unit:
                if unit in unitTbl:
                    unitId = unitTbl[unit]
                else:
                    unitQn = qname(unit, prefixedNamespaces)
                    unitId = 'u{}'.format(unitQn.localName)
                    _unit = modelXbrl.createUnit([unitQn], [], id=unitId)
                    unitTbl[unit] = unitId

            else:
                unitId = None
            attrs = {"contextRef": cntxId}
            if isNumeric:
                if unitId:
                    attrs["unitRef"] = unitId
                if isinstance(numVal, Number):
                    if dec is not None and len(dec) > 0:
                        if isinstance(dec, float): # must be an integer
                            dec = int(dec)
                        elif isinstance(dec, str) and '.' in dec:
                            dec = dec.partition('.')[0] # drop .0 from any SQLite string
                        attrs["decimals"] = str(dec)  # somehow it is float from the database
                    try:
                        text = str(numVal)
                        if c == 'm':
                            text = str(Decimal(text) + ONE00 - ONE) # force two decimals
                        elif c == 'p':
                            text = str(Decimal(text) + ONE0000 - ONE) # force four decimals
                        elif c == 'i':
                            text = str(int(numVal))
                    except Exception:
                        text = str(numVal)
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
                if isinstance(boolVal, Number):
                    text = 'false' if boolVal == 0 else 'true'
                elif isinstance(boolVal, str) and len(boolVal) > 0:
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
            f = modelXbrl.createFact(conceptQn, attributes=attrs, text=text)
            if f is None:
                raise DpmDBException("sqlDB:createFactError",
                                     _("Unable to create fact for concept {0} value {1}".format(conceptQn, text)))
            xbrlFactsCheckSum += f.md5sum
            #print ("f {} v {} c {} u {} f {} s {}".format(
            #        f.qname, f.value, f.context.md5sum, f.unit.md5sum, f.md5sum, xbrlFactsCheckSum))

        # add footnotes if any

        # save to file
        addProcessingInstruction(modelXbrl.modelDocument.xmlRootElement,
                                 'xbrl-facts-check',
                                 'sum-of-fact-md5s="{}"'.format(xbrlFactsCheckSum),
                                 insertBeforeChildElements=False) # add pi AFTER other elements

        # change schemaRef as needed
        if self.schemaRefSubstitutions:
            _xbrlSchemaRef = xbrlSchemaRef
            for _from, _to in self.schemaRefSubstitutions.items():
                xbrlSchemaRef = xbrlSchemaRef.replace(_from, _to)
            if _xbrlSchemaRef != xbrlSchemaRef:
                # change schemaRef in instance
                for schemaRefElt in modelXbrl.modelDocument.xmlRootElement.iter("{http://www.xbrl.org/2003/linkbase}schemaRef"):
                    if schemaRefElt.get("{http://www.w3.org/1999/xlink}href") == _xbrlSchemaRef:
                        schemaRefElt.set("{http://www.w3.org/1999/xlink}href", xbrlSchemaRef)


        self.showStatus("saving XBRL instance")
        modelXbrl.saveInstance(overrideFilepath=loadDBsaveToFile, encoding=outputDocumentEncoding)
        self.showStatus(_("Saved extracted instance"), 5000)
        return modelXbrl.modelDocument
