'''
XbrlOpenSqlDB.py implements an SQL database interface for Arelle, based
on a concrete realization of the Open Information Model and Abstract Model Model PWD 2.0.  
This is a semantic representation of XBRL Open Information Model (instance) and
XBRL Abstract Model (DTS) information. 

This module may save directly to a Postgres, MySQL, SQLite, MSSQL, or Oracle server.

This module provides the execution context for saving a dts and instances in 
XBRL SQL database.  It may be loaded by Arelle's RSS feed, or by individual
DTS and instances opened by interactive or command line/web service mode.

Example dialog or command line parameters for operation:

    host:  the supporting host for SQL Server
    port:  the host port of server
    user, password:  if needed for server
    database:  the top level path segment for the SQL Server
    timeout: 
    

(c) Copyright 2013 Mark V Systems Limited, California US, All rights reserved.  
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
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlValidate import collapseWhitespacePattern, UNVALIDATED, VALID
from arelle.XmlUtil import elementChildSequence, xmlstring
from arelle import XbrlConst
from arelle.UrlUtil import authority, ensureUrl
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from .tableFacts import tableFacts
from .entityInformation import loadEntityInformation
from .primaryDocumentFacts import loadPrimaryDocumentFacts
from collections import defaultdict


def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None, **kwargs):
    xbrlDbConn = None
    try:
        xbrlDbConn = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
        if "rssObject" in kwargs: # initialize batch
            xbrlDbConn.initializeBatch(kwargs["rssObject"])
        else:
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
                "filing", "report",
                "document", "referenced_documents",
                "concept", "enumeration", "data_type", "role_type", "arcrole_type",
                "resource", "relationship_set", "root", "relationship",
                "fact", "footnote", "entity_identifier", "period", "unit", "unit_measure", "aspect_value_set",
                "message", "message_reference",
                "industry", "industry_level", "industry_structure",
                }



class XbrlSqlDatabaseConnection(SqlDbConnection):
    def verifyTables(self):
        missingTables = XBRLDBTABLES - self.tablesInDB()
        # if no tables, initialize database
        if missingTables == XBRLDBTABLES:
            self.create({"mssql": "xbrlOpenDBMSSql.sql",
                         "mysql": "xbrlOpenDBMySql.ddl",
                         "sqlite": "xbrlOpenSqlDBSQLite.ddl",
                         "orcl": "xbrlOpenSqlDBOracle.sql",
                         "postgres": "xbrlOpenSqlDBPostgres.ddl"}[self.product])
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
            
            # get logging entries (needed to find which concepts to identify)
            self.loggingEntries = []
            for handler in logging.getLogger("arelle").handlers:
                if hasattr(handler, "dbHandlerLogEntries"):
                    self.loggingEntries = handler.dbHandlerLogEntries()
                    break
                
            # must have a valid XBRL instance or document
            if self.modelXbrl.modelDocument is None:
                raise XPDBException("xpgDB:MissingXbrlDocument",
                                    _("No XBRL instance or schema loaded for this filing.")) 
            
            # obtain supplementaion entity information
            self.entityInformation = loadEntityInformation(self.modelXbrl, rssItem)
            # identify table facts (table datapoints) (prior to locked database transaction
            self.tableFacts = tableFacts(self.modelXbrl)  # for EFM & HMRC this is ( (roleType, table_code, fact) )
            loadPrimaryDocumentFacts(self.modelXbrl, rssItem, self.entityInformation) # load primary document facts for SEC filing
            self.identifyTaxonomyRelSetsOwner()
                        
            # at this point we determine what's in the database and provide new tables
            # requires locking most of the table structure
            self.lockTables(('filing', 'report', 'document', 'referenced_documents'),
                            isSessionTransaction=True) # lock for whole transaction
            
            # find pre-existing documents in server database
            self.identifyPreexistingDocuments()
            self.identifyConceptsUsed()
            
            self.dropTemporaryTable()
            startedAt = time.time()
            self.syncSequences = True # for data base types that don't explicity handle sequences
            self.insertFiling(rssItem)
            self.modelXbrl.profileStat(_("XbrlSqlDB: Filing insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDocuments()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Documents insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertConcepts()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Concepts insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertArcroleTypes()
            self.insertRoleTypes()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Role Types insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertResources()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Resources insertion"), time.time() - startedAt)
            startedAt = time.time()
            # self.modelXbrl.profileStat(_("XbrlSqlDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertFacts()
            self.modelXbrl.profileStat(_("XbrlSqlDB: instance insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertRelationships() # must follow data points for footnote relationships
            self.modelXbrl.profileStat(_("XbrlSqlDB: Relationships insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertValidationResults()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Validation results insertion"), time.time() - startedAt)
            
            startedAt = time.time()
            self.showStatus("Committing entries")
            self.commit()
            self.modelXbrl.profileStat(_("XbrlSqlDB: insertion committed"), time.time() - startedAt)
            self.showStatus("DB insertion completed", clearAfter=5000)
        except Exception as ex:
            self.showStatus("DB insertion failed due to exception", clearAfter=5000)
            raise
            
    def identifyTaxonomyRelSetsOwner(self):
        # walk down referenced document set from instance to find 'lowest' taxonomy relationship set ownership
        instanceReferencedDocuments = set()
        instanceDocuments = set()
        inlineXbrlDocSet = None
        for mdlDoc in self.modelXbrl.urlDocs.values():
            if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
                instanceDocuments.add(mdlDoc)
                for refDoc, ref in mdlDoc.referencesDocument.items():
                    if refDoc.inDTS and ref.referenceType in ("href", "import", "include"):
                        instanceReferencedDocuments.add(refDoc)
            elif mdlDoc.type == Type.INLINEXBRLDOCUMENTSET:
                inlineXbrlDocSet = mdlDoc
        if len(instanceReferencedDocuments) > 1:
            # filing must own the taxonomy set
            if len(instanceDocuments) == 1:
                self.taxonomyRelSetsOwner = instanceDocuments.pop()
            elif inlineXbrlDocSet is not None:  # manifest for inline docs can own the rel sets
                self.taxonomyRelSetsOwner = inlineXbrlDocSet
            else: # no single instance, pick the entry poin doct
                self.taxonomyRelSetsOwner = self.modelXbrl.modelDocument # entry document (instance or inline doc set)
        elif len(instanceReferencedDocuments) == 1:
            self.taxonomyRelSetsOwner = instanceReferencedDocuments.pop()
        elif self.modelXbrl.modelDocument.type == Type.SCHEMA:
            self.taxonomyRelSetsOwner = self.modelXbrl.modelDocument 
        else:
            self.taxonomyRelSetsOwner = self.modelXbrl.modelDocument
        instanceReferencedDocuments.clear() # dereference
        instanceDocuments.clear()
        
        # check whether relationship_set is completely in instance or part/all in taxonomy
        self.arcroleInInstance = {}
        self.arcroleHasResource = {}
        for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys():
            if ELR is None and linkqname is None and arcqname is None and not arcrole.startswith("XBRL-"):
                inInstance = False
                hasResource = False
                for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                    if (not inInstance and
                        rel.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL) and
                        any(isinstance(tgtObj, ModelObject) and tgtObj.modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL)
                            for tgtObj in (rel.fromModelObject, rel.toModelObject))):
                        inInstance = True
                    if not hasResource and any(isinstance(resource, ModelResource)
                                               for resource in (rel.fromModelObject, rel.toModelObject)):
                        hasResource = True
                    if inInstance and hasResource:
                        break;
                self.arcroleInInstance[arcrole] = inInstance
                self.arcroleHasResource[arcrole] = hasResource
                
    def initializeBatch(self, rssObject):
        results = self.execute("SELECT filing_number, accepted_timestamp FROM filing")
        existingFilings = dict((filingNumber, timestamp) 
                               for filingNumber, timestamp in results) # timestamp is a string
        for rssItem in rssObject.rssItems:
            if (rssItem.accessionNumber in existingFilings and
                rssItem.acceptanceDatetime == existingFilings[rssItem.accessionNumber]):
                rssItem.skipRssItem = True
        
                                     
    def insertFiling(self, rssItem):
        now = datetime.datetime.now()
        entityInfo = self.entityInformation
        def rssItemGet(propertyName):
            if rssItem is not None:
                return getattr(rssItem, propertyName, None)
            return None
        self.showStatus("insert filing")
        LEI = None
        entity_comparator = ('legal_entity_number', 'file_number') if LEI else ('file_number',)
        table = self.getTable('filing', 'filing_id', 
                              ('filing_number', 
                               'legal_entity_number', 
                               'reference_number', # CIK
                               'standard_industry_code',
                               'tax_number',
                               'form_type', 
                               'accepted_timestamp', 'is_most_current', 'filing_date',
                               'creation_software', 
                               'authority_html_url', 
                               'entry_url',
                               'fiscal_year',
                               'fiscal_period',
                               'name_at_filing',
                               'legal_state_at_filing',
                               'restatement_index',
                               'period_index',
                               'first_5_comments',
                               'zip_url',
                               'file_number',
                               'phone',
                               'phys_addr1', 'phys_addr2', 'phys_city', 'phys_state', 'phys_zip', 'phys_country',
                               'mail_addr1', 'mail_addr2', 'mail_city', 'mail_state', 'mail_zip', 'mail_country',
                               'fiscal_year_end',
                               'filer_category',
                               'public_float',
                               'trading_symbol'), 
                              entity_comparator, # cannot compare None = None if LEI is absent, always False
                              ((rssItemGet("accessionNumber") or entityInfo.get("accession-number") or str(int(time.time())),  # NOT NULL
                                LEI, 
                                rssItemGet("cikNumber") or entityInfo.get("cik"),
                                rssItemGet("assignedSic") or entityInfo.get("assigned-sic") or -1,
                                entityInfo.get("irs-number"),
                                rssItemGet("formType") or entityInfo.get("form-type"),
                                rssItemGet("acceptanceDatetime") or entityInfo.get("acceptance-datetime") or now,
                                True,
                                rssItemGet("filingDate") or entityInfo.get("filing-date") or now,  # NOT NULL
                                self.modelXbrl.modelDocument.creationSoftware,
                                rssItemGet("htmlUrl") or entityInfo.get("primary-document-url"),
                                rssItemGet("url") or entityInfo.get("instance-url"),
                                None, #'fiscal_year',
                                None, #'fiscal_period',
                                rssItemGet("companyName") or entityInfo.get("conformed-name"),
                                entityInfo.get("state-of-incorporation"),
                                None, #'restatement_index',
                                None, #'period_index',
                                None, #'first_5_comments',
                                None, #'zip_url',
                                rssItemGet("fileNumber") or entityInfo.get("file-number")  or str(int(time.time())),
                                entityInfo.get("business-address.phone"),
                                entityInfo.get("business-address.street1"),
                                entityInfo.get("business-address.street2"),
                                entityInfo.get("business-address.city"),
                                entityInfo.get("business-address.state"),
                                entityInfo.get("business-address.zip"),
                                countryOfState.get(entityInfo.get("business-address.state")),
                                entityInfo.get("mail-address.street1"),
                                entityInfo.get("mail-address.street2"),
                                entityInfo.get("mail-address.city"),
                                entityInfo.get("mail-address.state"),
                                entityInfo.get("mail-address.zip"),
                                countryOfState.get(entityInfo.get("mail-address.state")),
                                rssItemGet("fiscalYearEnd") or entityInfo.get("fiscal-year-end"),
                                entityInfo.get("filer-category"),
                                entityInfo.get("public-float"),
                                entityInfo.get("trading-symbol")
                                ),),
                              checkIfExisting=True,
                              returnExistenceStatus=True)
        if LEI:
            for id, _LEI, filing_number, existenceStatus in table:
                self.filingId = id
                self.filingPreviouslyInDB = existenceStatus
                break
        else:
            for id, filing_number, existenceStatus in table:
                self.filingId = id
                self.filingPreviouslyInDB = existenceStatus
                break
        self.showStatus("insert report")
        table = self.getTable('report', 'report_id', 
                              ('filing_id', ), 
                              ('filing_id',), 
                              ((self.filingId,
                                ),),
                              checkIfExisting=True,
                              returnExistenceStatus=True)
        for id, foundFilingId, existenceStatus in table:
            self.reportId = id
            self.filingPreviouslyInDB = existenceStatus
            break
        
    def isSemanticDocument(self, modelDocument):
        if modelDocument.type == Type.SCHEMA:
            # must include document items taxonomy even if not in DTS
            return modelDocument.inDTS or modelDocument.targetNamespace == "http://arelle.org/doc/2014-01-31"
        return modelDocument.type in (Type.INSTANCE, Type.INLINEXBRL, Type.LINKBASE)       
        
    def identifyPreexistingDocuments(self):
        self.existingDocumentIds = {}
        self.urlDocs = {}
        docUris = set()
        for modelDocument in self.modelXbrl.urlDocs.values():
            url = ensureUrl(modelDocument.uri)
            self.urlDocs[url] = modelDocument
            if self.isSemanticDocument(modelDocument):
                docUris.add(self.dbStr(url))
        if docUris:
            results = self.execute("SELECT document_id, document_url FROM {} WHERE document_url IN ({})"
                                   .format(self.dbTableName("document"),
                                           ', '.join(docUris)))
            self.existingDocumentIds = dict((self.urlDocs[docUrl],docId) 
                                            for docId, docUrl in results)
            
            # identify whether taxonomyRelsSetsOwner is existing
            self.isExistingTaxonomyRelSetsOwner = (
                self.taxonomyRelSetsOwner.type not in (Type.INSTANCE, Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET) and
                self.taxonomyRelSetsOwner in self.existingDocumentIds)
                 
    def identifyConceptsUsed(self):
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]

        
        conceptsUsed = set(f.concept
                           for f in self.modelXbrl.factsInInstance)
        
        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                conceptsUsed.add(dim.dimension)
                if dim.isExplicit:
                    conceptsUsed.add(dim.member)
                else:
                    conceptsUsed.add(self.modelXbrl.qnameConcepts[dim.typedMember.qname])
        for defaultDimQn, defaultDimMemberQn in self.modelXbrl.qnameDimensionDefaults.items():
            conceptsUsed.add(self.modelXbrl.qnameConcepts[defaultDimQn])
            conceptsUsed.add(self.modelXbrl.qnameConcepts[defaultDimMemberQn])
        for relationshipSetKey in self.relationshipSets:
            relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
            for rel in relationshipSet.modelRelationships:
                if isinstance(rel.fromModelObject, ModelConcept):
                    conceptsUsed.add(rel.fromModelObject)
                if isinstance(rel.toModelObject, ModelConcept):
                    conceptsUsed.add(rel.toModelObject)
                    
        try:
            for qn in (XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit):
                conceptsUsed.add(self.modelXbrl.qnameConcepts[qn])
        except KeyError:
            pass # no DTS

        for roleTypes in (self.modelXbrl.roleTypes.values(), self.modelXbrl.arcroleTypes.values()):
            for roleUriTypes in roleTypes:
                for roleType in roleUriTypes:
                    for qn in roleType.usedOns:
                        if qn in self.modelXbrl.qnameConcepts: # qname may be undefined or invalid and still 2.1 legal
                            conceptsUsed.add(self.modelXbrl.qnameConcepts[qn])
                        
        # add concepts referenced by logging entries
        for logEntry in self.loggingEntries:
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                if isinstance(modelObject, ModelConcept) and modelObject.modelDocument.inDTS:
                    conceptsUsed.add(modelObject)

        # add substitution groups
        conceptsUsed |= set(concept.substitutionGroup
                            for concept in conceptsUsed
                            if concept is not None)
        
        conceptsUsed -= {None}  # remove None if in conceptsUsed
        self.conceptsUsed = conceptsUsed
    
        typesUsed = set()
        def typeUsed(modelType):
            if modelType is not None and modelType.modelDocument.inDTS: # exclude nonDTS types (schema, etc)
                typesUsed.add(modelType)
                typesDerivedFrom = modelType.typeDerivedFrom
                if isinstance(typesDerivedFrom, list): # union derivation
                    for typeDerivedFrom in typesDerivedFrom:
                        if typeDerivedFrom not in typesUsed:
                            typeUsed(typeDerivedFrom)
                else: # single derivation
                    if typesDerivedFrom is not None and typesDerivedFrom not in typesUsed:
                        typeUsed(typesDerivedFrom)
                    
        for concept in conceptsUsed:
            modelType = concept.type
            if modelType is not None:
                if modelType not in typesUsed:
                    typeUsed(modelType)
        self.typesUsed = typesUsed
        
    def insertDocuments(self):
        self.showStatus("insert documents")
        table = self.getTable('document', 'document_id', 
                              ('document_url', 'document_type', 'namespace'), 
                              ('document_url',), 
                              set((ensureUrl(docUrl),
                                   Type.typeName[mdlDoc.type],
                                   mdlDoc.targetNamespace) 
                                  for docUrl, mdlDoc in self.modelXbrl.urlDocs.items()
                                  if mdlDoc not in self.existingDocumentIds and 
                                     self.isSemanticDocument(mdlDoc)),
                              checkIfExisting=True)
        self.documentIds = dict((self.urlDocs[url], id)
                                for id, url in table)
        self.documentIds.update(self.existingDocumentIds)

        referencedDocuments = set()
        # instance documents are filing references
        # update report with document references
        for mdlDoc in self.modelXbrl.urlDocs.values():
            if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
                referencedDocuments.add( (self.reportId, self.documentIds[mdlDoc] ))
            if mdlDoc in self.documentIds:
                for refDoc, ref in mdlDoc.referencesDocument.items():
                    if refDoc.inDTS and ref.referenceType in ("href", "import", "include") \
                       and refDoc in self.documentIds:
                        referencedDocuments.add( (self.documentIds[mdlDoc], self.documentIds[refDoc] ))
        
        table = self.getTable('referenced_documents', 
                              None, # no id column in this table 
                              ('object_id','document_id'), 
                              ('object_id','document_id'), 
                              referencedDocuments,
                              checkIfExisting=True)
        
        instDocId = instSchemaDocId = agencySchemaDocId = stdSchemaDocId = None
        mdlDoc = self.modelXbrl.modelDocument
        if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
            instDocId = self.documentIds[mdlDoc]
            # referenced doc may be extension schema
            for refDoc, ref in mdlDoc.referencesDocument.items():
                if refDoc.inDTS and ref.referenceType == "href" and refDoc in self.documentIds:
                    instSchemaDocId = self.documentIds[refDoc]
                    break
        elif mdlDoc.type == Type.SCHEMA:
            instDocSchemaDocId = self.documentIds[mdlDoc]
        for mdlDoc in self.modelXbrl.urlDocs.values():
            if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
                referencedDocuments.add( (self.reportId, self.documentIds[mdlDoc] ))
            if mdlDoc in self.documentIds:
                for refDoc, ref in mdlDoc.referencesDocument.items():
                    if refDoc.inDTS and ref.referenceType in ("href", "import", "include") \
                       and refDoc in self.documentIds:
                        if refDoc.type == Type.SCHEMA:
                            nsAuthority = authority(refDoc.targetNamespace, includeScheme=False)
                            nsPath = refDoc.targetNamespace.split('/')
                            if len(nsPath) > 2:
                                if ((nsAuthority in ("fasb.org", "xbrl.us") and nsPath[-2] == "us-gaap") or
                                    (nsAuthority == "xbrl.ifrs.org" and nsPath[-1] in ("ifrs", "ifrs-full", "ifrs-smes"))):
                                    stdSchemaDocId = self.documentIds[refDoc]
                                elif (nsAuthority == "xbrl.sec.gov" and nsPath[-2] == "rr"):
                                    agencySchemaDocId = self.documentIds[refDoc]
        
        
        self.updateTable("report",
                         ("report_id", "report_data_doc_id", "report_schema_doc_id", "agency_schema_doc_id", "standard_schema_doc_id"),
                         ((self.reportId, instDocId, instSchemaDocId, agencySchemaDocId, stdSchemaDocId),)
                        )

        
    def insertConcepts(self):
        self.showStatus("insert concepts")
        
        # determine new filing documents and types they use
        filingDocumentConcepts = set()
        existingDocumentUsedConcepts = set()
        for concept in self.modelXbrl.qnameConcepts.values():
            if concept.modelDocument not in self.existingDocumentIds:
                filingDocumentConcepts.add(concept)
                filingDocumentConceptType = concept.type
                if filingDocumentConceptType is not None and filingDocumentConceptType not in self.typesUsed:
                        self.typesUsed.add(filingDocumentConceptType)
            elif concept in self.conceptsUsed:
                existingDocumentUsedConcepts.add(concept)
                
        filingDocumentTypes = set()
        existingDocumentUsedTypes = set()
        for modelType in self.modelXbrl.qnameTypes.values():
            if modelType.modelDocument not in self.existingDocumentIds:
                filingDocumentTypes.add(modelType)
            elif modelType in self.typesUsed:
                existingDocumentUsedTypes.add(modelType)

                
        # get existing element IDs
        self.typeQnameId = {}
        if existingDocumentUsedTypes:
            typeQnameIds = []
            table = self.getTable('data_type', 'data_type_id', 
                                  ('document_id', 'qname',), 
                                  ('document_id', 'qname',), 
                                  tuple((self.documentIds[modelType.modelDocument],
                                         modelType.qname.clarkNotation)
                                        for modelType in existingDocumentUsedTypes
                                        if modelType.modelDocument in self.documentIds),
                                  checkIfExisting=True,
                                  insertIfNotMatched=False)
            for typeId, docId, qn in table:
                self.typeQnameId[qname(qn)] = typeId
        
        table = self.getTable('data_type', 'data_type_id', 
                              ('document_id', 'xml_id', 'xml_child_seq',
                               'qname', 'name', 'base_type', 'derived_from_type_id'), 
                              ('document_id', 'qname',), 
                              tuple((self.documentIds[modelType.modelDocument],
                                     modelType.id,
                                     elementChildSequence(modelType),
                                     modelType.qname.clarkNotation,
                                     modelType.name,
                                     modelType.baseXsdType,
                                     self.typeQnameId.get(modelType.typeDerivedFrom)
                                     if isinstance(modelType.typeDerivedFrom, ModelType) else None)
                                    for modelType in filingDocumentTypes
                                    if modelType.modelDocument in self.documentIds)
                             )
        for typeId, docId, qn in table:
            self.typeQnameId[qname(qn)] = typeId
        
        updatesToDerivedFrom = set()
        for modelType in filingDocumentTypes:
            if isinstance(modelType.typeDerivedFrom, ModelType):
                typeDerivedFrom = modelType.typeDerivedFrom
                if (typeDerivedFrom in filingDocumentTypes and
                    modelType.qname in self.typeQnameId and
                    typeDerivedFrom.qname in self.typeQnameId):
                    updatesToDerivedFrom.add( (self.typeQnameId[modelType.qname], 
                                               self.typeQnameId[typeDerivedFrom.qname]) )
        # update derivedFrom's of newly added types
        if updatesToDerivedFrom:
            self.updateTable('data_type', 
                             ('data_type_id', 'derived_from_type_id'),
                             updatesToDerivedFrom)
            
        existingDocumentUsedTypes.clear() # dereference
        filingDocumentTypes.clear() # dereference
                
        self.conceptQnameId = {}
        
        # get existing element IDs
        if existingDocumentUsedConcepts:
            table = self.getTable('concept', 'concept_id', 
                                  ('document_id', 'qname',), 
                                  ('document_id', 'qname',), 
                                  tuple((self.documentIds[concept.modelDocument],
                                         concept.qname.clarkNotation)
                                        for concept in existingDocumentUsedConcepts
                                        if concept.modelDocument in self.documentIds),
                                  checkIfExisting=True,
                                  insertIfNotMatched=False)
            for conceptId, docId, qn in table:
                self.conceptQnameId[qname(qn)] = conceptId
                
        concepts = []
        for concept in filingDocumentConcepts:
            niceType  = concept.niceType
            if niceType is not None and len(niceType) > 128:
                niceType = niceType[:128]
            if concept.modelDocument in self.documentIds:
                concepts.append((self.documentIds[concept.modelDocument],
                                concept.id,
                                elementChildSequence(concept),
                                concept.qname.clarkNotation,
                                concept.name,
                                self.typeQnameId.get(concept.typeQname),
                                niceType[:128] if niceType is not None else None,
                                self.conceptQnameId.get(concept.substitutionGroupQname),
                                concept.balance,
                                concept.periodType,
                                concept.isAbstract, 
                                concept.isNillable,
                                concept.isNumeric,
                                concept.isMonetary,
                                concept.isTextBlock))
        table = self.getTable('concept', 'concept_id', 
                              ('document_id', 'xml_id', 'xml_child_seq',
                               'qname', 'name', 'datatype_id', 'base_type', 'substitution_group_concept_id',  
                               'balance', 'period_type', 'abstract', 'nillable',
                               'is_numeric', 'is_monetary', 'is_text_block'), 
                              ('document_id', 'qname'), 
                              concepts
                             )
        for conceptId, docId, qn in table:
            self.conceptQnameId[qname(qn)] = conceptId
            
        updatesToSubstitutionGroup = set()
        for concept in filingDocumentConcepts:
            if concept.substitutionGroup in filingDocumentConcepts and concept.modelDocument in self.documentIds:
                updatesToSubstitutionGroup.add( (self.conceptQnameId[concept.qname], 
                                                 self.conceptQnameId.get(concept.substitutionGroupQname)) )
        # update derivedFrom's of newly added types
        if updatesToSubstitutionGroup:
            self.updateTable('concept', 
                             ('concept_id', 'substitution_group_concept_id'),
                             updatesToSubstitutionGroup)
            
        # enumerations
        # TBD
            
        filingDocumentConcepts.clear() # dereference
        existingDocumentUsedConcepts.clear() # dereference
                   
    def insertArcroleTypes(self):
        self.showStatus("insert arcrole types")
        # add existing arcrole types
        arcroleTypesByIds = set((self.documentIds[arcroleType.modelDocument],
                                 arcroleType.roleURI) # key on docId, uriId
                                for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                for arcroleType in arcroleTypes
                                if arcroleType.modelDocument in self.existingDocumentIds)
        table = self.getTable('arcrole_type', 'arcrole_type_id', 
                              ('document_id', 'arcrole_uri'), 
                              ('document_id', 'arcrole_uri'), 
                              tuple((arcroleTypeIDs[0], # doc Id
                                     arcroleTypeIDs[1] # uri Id
                                     ) 
                                    for arcroleTypeIDs in arcroleTypesByIds),
                              checkIfExisting=True,
                              insertIfNotMatched=False)
        self.arcroleTypeIds = {}
        for arcroleId, docId, uri in table:
            self.arcroleTypeIds[(docId, uri)] = arcroleId

        # added document arcrole type        
        arcroleTypesByIds = dict(((self.documentIds[arcroleType.modelDocument],
                                   arcroleType.arcroleURI), # key on docId, uriId
                                  arcroleType) # value is roleType object
                                 for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                 for arcroleType in arcroleTypes
                                 if arcroleType.modelDocument not in self.existingDocumentIds)
        table = self.getTable('arcrole_type', 'arcrole_type_id', 
                              ('document_id', 'xml_id', 'xml_child_seq', 'arcrole_uri', 'cycles_allowed', 'definition'), 
                              ('document_id', 'arcrole_uri'), 
                              tuple((arcroleTypeIDs[0], # doc Id
                                     arcroleType.id,
                                     elementChildSequence(arcroleType),
                                     arcroleType.arcroleURI,
                                     arcroleType.cyclesAllowed,
                                     arcroleType.definition)
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()))
        
        for arcroleId, docId, uri in table:
            self.arcroleTypeIds[(docId, uri)] = arcroleId
            
        table = self.getTable('used_on', 
                              None, # no record id in this table  
                              ('object_id', 'concept_id'), 
                              ('object_id', 'concept_id'), 
                              tuple((self.arcroleTypeIds[(arcroleTypeIDs[0], arcroleType.arcroleURI)], 
                                     self.conceptQnameId[usedOnQn])
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()
                                    for usedOnQn in arcroleType.usedOns
                                    if usedOnQn in self.conceptQnameId),
                              checkIfExisting=True)
        
    def insertRoleTypes(self):
        self.showStatus("insert role types")
        # add existing role types
        roleTypesByIds = set((self.documentIds[roleType.modelDocument],
                              roleType.roleURI) # key on docId, uriId
                              for roleTypes in self.modelXbrl.roleTypes.values()
                              for roleType in roleTypes
                              if roleType.modelDocument in self.existingDocumentIds)
        table = self.getTable('role_type', 'role_type_id', 
                              ('document_id', 'role_uri'), 
                              ('document_id', 'role_uri'), 
                              tuple((roleTypeIDs[0], # doc Id
                                     roleTypeIDs[1] # uri Id
                                     ) 
                                    for roleTypeIDs in roleTypesByIds),
                              checkIfExisting=True,
                              insertIfNotMatched=False)
        self.roleTypeIds = {}
        for roleId, docId, uri in table:
            self.roleTypeIds[(docId, uri)] = roleId
        
        # new document role types
        roleTypesByIds = dict(((self.documentIds[roleType.modelDocument],
                                roleType.roleURI), # key on docId, uriId
                               roleType) # value is roleType object
                              for roleTypes in self.modelXbrl.roleTypes.values()
                              for roleType in roleTypes
                              if roleType.modelDocument not in self.existingDocumentIds)
        table = self.getTable('role_type', 'role_type_id', 
                              ('document_id', 'xml_id', 'xml_child_seq', 'role_uri', 'definition'), 
                              ('document_id', 'role_uri'), 
                              tuple((roleTypeIDs[0], # doc Id
                                     roleType.id,
                                     elementChildSequence(roleType),
                                     roleTypeIDs[1], # uri Id
                                     roleType.definition) 
                                    for roleTypeIDs, roleType in roleTypesByIds.items()))
        for roleId, docId, uri in table:
            self.roleTypeIds[(docId, uri)] = roleId
            
            
        table = self.getTable('used_on', 
                              None, # no record id in this table  
                              ('object_id', 'concept_id'), 
                              ('object_id', 'concept_id'), 
                              tuple((self.roleTypeIds[(roleTypeIDs[0], roleType.roleURI)], 
                                     self.conceptQnameId[usedOnQn])
                                    for roleTypeIDs, roleType in roleTypesByIds.items()
                                    for usedOnQn in roleType.usedOns
                                    if usedOnQn in self.conceptQnameId),
                              checkIfExisting=True)
        
    def insertResources(self):
        self.showStatus("insert resources")
        # deduplicate resources (may be on multiple arcs)
        arcroles = [arcrole
                    # check whether relationship_set is completely in instance or part/all in taxonomy
                    for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                    if ELR is None and linkqname is None and arcqname is None and not arcrole.startswith("XBRL-")
                       and self.arcroleHasResource[arcrole]
                       and (self.arcroleInInstance[arcrole] or not self.isExistingTaxonomyRelSetsOwner)]
        # note that lxml has no column numbers, use objectIndex as pseudo-column number
        uniqueResources = dict(((self.documentIds[resource.modelDocument],
                                 resource.objectIndex), resource)
                               for arcrole in arcroles
                               for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships
                               if rel.fromModelObject is not None and rel.toModelObject is not None
                               for resource in (rel.fromModelObject, rel.toModelObject)
                               if isinstance(resource, ModelResource))
        table = self.getTable('resource', 'resource_id', 
                              ('document_id', 'xml_id', 'xml_child_seq', 'qname', 'role', 'value', 'xml_lang'), 
                              ('document_id', 'xml_child_seq'), 
                              tuple((self.documentIds[resource.modelDocument],
                                     resource.id,
                                     elementChildSequence(resource),
                                     resource.qname.clarkNotation,
                                     resource.role,
                                     resource.textValue,
                                     resource.xmlLang)
                                    for resource in uniqueResources.values()),
                              checkIfExisting=True)
        self.resourceId = dict(((docId, xml_child_seq), id)
                               for id, docId, xml_child_seq in table)
        uniqueResources.clear()
        
                
    def modelObjectId(self, modelObject):
        if isinstance(modelObject, ModelConcept):
            return self.conceptQnameId.get(modelObject.qname)
        elif isinstance(modelObject, ModelType):
            return self.conceptTypeIds.get(modelObject.qname)
        elif isinstance(modelObject, ModelResource):
            return self.resourceId.get((self.documentIds[modelObject.modelDocument],
                                        elementChildSequence(modelObject)))
        elif isinstance(modelObject, ModelFact):
            return self.factId.get((self.documentIds[modelObject.modelDocument],
                                   elementChildSequence(modelObject)))
        else:
            return None 
    
    def insertRelationships(self):
        self.showStatus("insert relationship sets")
        table = self.getTable('relationship_set', 'relationship_set_id', 
                              ('document_id', 'link_role', 'arc_role', 'link_qname', 'arc_qname'), 
                              ('document_id', 'link_role', 'arc_role', 'link_qname', 'arc_qname'), 
                              tuple((self.documentIds[self.modelXbrl.modelDocument if self.arcroleInInstance[arcrole]
                                                      else self.taxonomyRelSetsOwner],
                                     ELR,
                                     arcrole,
                                     linkqname.clarkNotation,
                                     arcqname.clarkNotation)
                                    for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                    if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")
                                           and (not self.isExistingTaxonomyRelSetsOwner or self.arcroleInInstance[arcrole])))
        self.relSetId = dict(((linkRole, arcRole, lnkQn, arcQn), id)
                             for id, document_id, linkRole, arcRole, lnkQn, arcQn in table)
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        dbRels = []
        
        def walkTree(rels, seq, depth, relationshipSet, visited, dbRels, relSetId):
            for rel in rels:
                if rel not in visited and isinstance(rel.toModelObject, ModelObject):
                    visited.add(rel)
                    dbRels.append((rel, seq, depth, relSetId))
                    seq += 1
                    seq = walkTree(relationshipSet.fromModelObject(rel.toModelObject), seq, depth+1, relationshipSet, visited, dbRels, relSetId)
                    visited.remove(rel)
            return seq
        
        for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys():
            if (ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")
                and (not self.isExistingTaxonomyRelSetsOwner or self.arcroleInInstance[arcrole])):
                relSetId = self.relSetId[(ELR,
                                          arcrole,
                                          linkqname.clarkNotation,
                                          arcqname.clarkNotation)]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), dbRels, relSetId)

        def resourceResourceId(resource):
            if isinstance(resource, ModelResource):
                return self.resourceId.get((self.documentIds[resource.modelDocument],
                                            resource.sourceline, 
                                            resource.objectIndex))
            else:
                return None     
        
        table = self.getTable('relationship', 'relationship_id', 
                              ('document_id', 'xml_id', 'xml_child_seq', 
                               'relationship_set_id', 'reln_order', 
                               'from_id', 'to_id', 'calculation_weight', 
                               'tree_sequence', 'tree_depth', 'preferred_label_role'), 
                              ('relationship_set_id', 'document_id', 'xml_child_seq'), 
                              tuple((self.documentIds[rel.modelDocument],
                                     rel.id,
                                     elementChildSequence(rel.arcElement),
                                     relSetId,
                                     self.dbNum(rel.order),
                                     self.modelObjectId(rel.fromModelObject),
                                     self.modelObjectId(rel.toModelObject),
                                     self.dbNum(rel.weight), # none if no weight
                                     sequence,
                                     depth,
                                     rel.preferredLabel)
                                    for rel, sequence, depth, relSetId in dbRels
                                    if isinstance(rel.fromModelObject, ModelObject) and isinstance(rel.toModelObject, ModelObject)))
        self.relationshipId = dict(((docId,xml_child_seq), relationshipId)
                                   for relationshipId, relSetId, docId, xml_child_seq in table)
        table = self.getTable('root', None, 
                              ('relationship_set_id', 'relationship_id'), 
                              ('relationship_set_id', 'relationship_id'), 
                              tuple((relSetId,
                                     self.relationshipId[self.documentIds[rel.modelDocument],
                                                         elementChildSequence(rel.arcElement)])
                                    for rel, sequence, depth, relSetId in dbRels
                                    if depth == 1 and
                                       isinstance(rel.fromModelObject, ModelObject) and isinstance(rel.toModelObject, ModelObject)))
        del dbRels[:]   # dererefence

    def insertFacts(self):
        reportId = self.reportId
        if self.filingPreviouslyInDB:
            self.showStatus("deleting prior facts of this report")
            # remove prior facts
            self.lockTables(("fact", "entity_identifier", "period", "unit_measure", "unit", 
                             "aspect_value_set", "aspect_value_report_set", # report_set is for id assignment
                             "footnote" "table_facts"))
            for _tableName, _id in (("entity_identifier", "entity_identifier_id"), 
                                    ("period", "period_id"), 
                                    ("unit", "unit_id"),
                                    ("unit_measure", "unit_id"),
                                    ("aspect_value_set", "aspect_value_set_id"),
                                    ("aspect_value_report_set", "aspect_value_set_id"),
                                    ("footnote", "fact_id")):
                self.execute("DELETE from {0} "
                             "USING {1} "
                             "WHERE {1}.report_id = {2} AND {0}.{3} = {1}.{3}" 
                             .format( self.dbTableName(_tableName), 
                                      self.dbTableName("fact"), 
                                      reportId, 
                                      _id), 
                             close=False, fetch=False)
            for _tableName in ("fact", "table_facts"):
                self.execute("DELETE FROM {0} WHERE {0}.report_id = {1}"
                             .format( self.dbTableName(_tableName), reportId), 
                             close=False, fetch=False)
        self.showStatus("insert data points")
        
        # must only store used contexts and units (as they are removed only by being used)
        contextsUsed = set()
        unitsUsed = {} # deduplicate by md5has
        for f in self.modelXbrl.factsInInstance:
            if f.context is not None:
                contextsUsed.add(f.context)
            if f.unit is not None:
                unitsUsed[f.unit.md5hash] = f.unit
                
        # units
        table = self.getTable('unit', 'unit_id', 
                              ('xml_id', 'xml_child_seq', 'measures_hash'), 
                              ('xml_id',), 
                              tuple((unit.id, # unit's xml_id
                                     elementChildSequence(unit),
                                     unit.md5hash)
                                    for unit in unitsUsed.values()))
        self.unitId = dict((_xmlId, id)
                           for id, _xmlId in table)
        # measures
        table = self.getTable('unit_measure', 
                              None, 
                              ('unit_id', 'qname', 'is_multiplicand'), 
                              ('unit_id', 'qname', 'is_multiplicand'), 
                              tuple((self.unitId[unit.id],
                                     measure.clarkNotation,
                                     i == 0)
                                    for unit in unitsUsed.values()
                                    for i in range(2)
                                    for measure in unit.measures[i]))
        table = self.getTable('entity_identifier', 'entity_identifier_id', 
                              ('scheme', 'identifier'), 
                              ('scheme', 'identifier'), 
                              set((cntx.entityIdentifier[0],
                                   cntx.entityIdentifier[1])
                                for cntx in contextsUsed)) # not shared across reports
        self.entityIdentifierId = dict(((entScheme, entIdent), id)
                                       for id, entScheme, entIdent in table)
        table = self.getTable('period', 'period_id', 
                              ('start_date', 'end_date', 'is_instant', 'is_forever'), 
                              ('start_date', 'end_date', 'is_instant', 'is_forever'), 
                              set((cntx.startDatetime if cntx.isStartEndPeriod else None,
                                   cntx.endDatetime if (cntx.isStartEndPeriod or cntx.isInstantPeriod) else None,
                                   cntx.isInstantPeriod,
                                   cntx.isForeverPeriod)
                                for cntx in contextsUsed)) # periods not shared across multiple instance/inline docs
        self.periodId = dict(((start, end, isInstant, isForever), id)
                             for id, start, end, isInstant, isForever in table)
        
        def cntxDimsSet(cntx):
            return frozenset((self.conceptQnameId[modelDimValue.dimensionQname],
                              self.conceptQnameId.get(modelDimValue.memberQname), # null if typed
                              modelDimValue.isTyped,
                              None if not modelDimValue.isTyped else ( # typed_value is null if not typed dimension
                              modelDimValue.typedMember.xValue.clarkNotation # if typed member is QName use clark name because QName is not necessarily a concept in the DTS
                                 if (modelDimValue.typedMember is not None and getattr(modelDimValue.typedMember, "xValid", UNVALIDATED) >= VALID and isinstance(QName,modelDimValue.typedMember.xValue))
                                 else modelDimValue.stringValue)) # otherwise typed member is string value of the typed member
                             for modelDimValue in cntx.qnameDims.values()
                             if modelDimValue.dimensionQname in self.conceptQnameId)
        
        cntxAspectValueSets = dict((cntx, cntxDimsSet(cntx))
                                   for cntx in contextsUsed)
        
        aspectValueSelections = set(aspectValueSelectionSet
                                    for cntx, aspectValueSelectionSet in cntxAspectValueSets.items()
                                    if aspectValueSelectionSet)
        # allocate an aspect_value_set_id for each aspect_value_set in report (independent of SQL of database)
        table = self.getTable('aspect_value_report_set', 'aspect_value_set_id', 
                              ('report_id', ), 
                              ('report_id', ), 
                              tuple((reportId,)
                                    for aspectValueSelection in aspectValueSelections)
                              )
        # assure we only get single entry per result (above gives cross product)
        table = self.execute("SELECT aspect_value_set_id, report_id from {0} "
                             "WHERE report_id = {1}"
                             .format(self.dbTableName("aspect_value_report_set"), reportId))
        aspectValueReportSets = dict((aspectValueSelections.pop(), id)
                                     for id, _reportId in table)
        
        cntxAspectValueSetId = dict((cntx, aspectValueReportSets[_cntxDimsSet])
                                    for cntx, _cntxDimsSet in cntxAspectValueSets.items()
                                    if _cntxDimsSet)
                                    
        table = self.getTable('aspect_value_set', 
                              None, 
                              ('aspect_value_set_id', 'aspect_concept_id', 'aspect_value_id', 'is_typed_value', 'typed_value'), 
                              ('aspect_value_set_id', ), 
                              tuple((aspectValueSetId, dimId, dimMbrId, isTyped, typedValue)
                                    for aspectValueSelection, aspectValueSetId in aspectValueReportSets.items()
                                    for dimId, dimMbrId, isTyped, typedValue in aspectValueSelection)
                              )
        
        del contextsUsed, unitsUsed # dereference objects

        # facts
        def insertFactSet(modelFacts, tupleFactId):
            facts = []
            for fact in modelFacts:
                if fact.concept is not None and getattr(fact, "xValid", UNVALIDATED) >= VALID and fact.qname is not None:
                    cntx = fact.context
                    documentId = self.documentIds[fact.modelDocument]
                    facts.append((reportId,
                                  documentId,
                                  fact.id, # fact's xml_id
                                  elementChildSequence(fact),
                                  fact.sourceline,
                                  tupleFactId, # tuple (parent) fact's database fact_id
                                  self.conceptQnameId.get(fact.qname),
                                  fact.contextID,
                                  self.entityIdentifierId.get((reportId, cntx.entityIdentifier[0], cntx.entityIdentifier[1]))
                                      if cntx is not None else None,
                                  self.periodId.get((reportId,
                                                cntx.startDatetime if cntx.isStartEndPeriod else None,
                                                cntx.endDatetime if (cntx.isStartEndPeriod or cntx.isInstantPeriod) else None,
                                                cntx.isInstantPeriod,
                                                cntx.isForeverPeriod)) if cntx is not None else None,
                                  cntxAspectValueSetId.get(cntx) if cntx is not None else None,
                                  self.unitId.get((reportId,fact.unit.md5hash)) if fact.unit is not None else None,
                                  fact.isNil,
                                  fact.precision,
                                  fact.decimals,
                                  roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric and not fact.isNil else None,
                                  fact.xmlLang if not fact.isNumeric and not fact.isNil else None,
                                  collapseWhitespacePattern.sub(' ', fact.value.strip()) if fact.value is not None else None,
                                  fact.value,
                                  ))
            table = self.getTable('fact', 'fact_id', 
                                  ('report_id', 'document_id', 'xml_id', 'xml_child_seq', 'source_line', 
                                   'tuple_fact_id',  # tuple
                                   'concept_id',
                                   'context_xml_id', 'entity_identifier_id', 'period_id', 'aspect_value_set_id', 'unit_id',
                                   'is_nil', 'precision_value', 'decimals_value', 'effective_value', 
                                   'language', 'normalized_string_value', 'value'), 
                                  ('document_id', 'xml_child_seq'), 
                                  facts)
            xmlIdFactId = dict(((docId, xml_child_seq), _factId)
                               for _factId, docId, xml_child_seq in table)
            self.factId.update(xmlIdFactId)
            for fact in modelFacts:
                if fact.isTuple:
                    try:
                        insertFactSet(fact.modelTupleFacts, 
                                      xmlIdFactId[(self.documentIds[fact.modelDocument],
                                                        elementChildSequence(fact))])
                    except KeyError:
                        self.modelXbrl.info("xpDB:warning",
                                            _("Loading XBRL DB: tuple's datapoint not found: %(tuple)s"),
                                            modelObject=fact, tuple=fact.qname)

        self.factId = {}
        insertFactSet(self.modelXbrl.facts, None)
        # hashes
        if self.tableFacts: # if any entries
            _tableFacts = []
            for roleType, tableCode, fact in self.tableFacts:
                try:
                    _tableFacts.append((reportId,
                                        self.roleTypeIds[(self.documentIds[roleType.modelDocument], 
                                                          roleType.roleURI)],
                                        tableCode,
                                        self.factId[(self.documentIds[fact.modelDocument],
                                                     elementChildSequence(fact))]))
                except KeyError:
                    # print ("missing table facts role or fact")
                    pass
            table = self.getTable('table_facts', None, 
                                  ('report_id', 'object_id', 'table_code', 'fact_id'), 
                                  ('report_id', 'object_id', 'fact_id'), 
                                  _tableFacts)
        
        # footnotes
        footnotesRelationshipSet = ModelRelationshipSet(self.modelXbrl, "XBRL-footnotes")
        try:
            s = None
            for fact in self.modelXbrl.factsInInstance:
                for footnoteRel in footnotesRelationshipSet.fromModelObject(fact):
                    toObj = footnoteRel.toModelObject
                    print("footnote text \"{}\" tail \"{}\"".format(toObj.text, toObj.tail))
                    if toObj is not None:
                        s = xmlstring(toObj, stripXmlns=True, contentsOnly=True, includeText=True)
        except TypeError:
            print ("footnote Error toObj={} s={}".format(toObj.text, s))
        table = self.getTable('footnote', None, 
                              ('fact_id', 'footnote_group', 'type', 'footnote_value_id', 'language', 'normalized_string_value', 'value'), 
                              ('fact_id', 'footnote_group', 'type', 'footnote_value_id', 'language', 'normalized_string_value', 'value'), 
                              tuple((self.factId[(self.documentIds[fact.modelDocument], elementChildSequence(fact))],
                                     footnoteRel.arcrole,
                                     None if isinstance(toObj, ModelFact) else toObj.role,
                                     self.factId[(self.documentIds[toObj.modelDocument], elementChildSequence(toObj))] if isinstance(toObj, ModelFact) else None,
                                     None if isinstance(toObj, ModelFact) else toObj.xmlLang,
                                     None if isinstance(toObj, ModelFact) else collapseWhitespacePattern.sub(' ', xmlstring(toObj, stripXmlns=True, contentsOnly=True, includeText=True)),
                                     None if isinstance(toObj, ModelFact) else xmlstring(toObj, stripXmlns=True, contentsOnly=True, includeText=True))
                                    for fact in self.modelXbrl.factsInInstance
                                    for footnoteRel in footnotesRelationshipSet.fromModelObject(fact)
                                    for toObj in (footnoteRel.toModelObject,)
                                    if toObj is not None)
                              )

    def insertValidationResults(self):
        reportId = self.reportId
        
        if self.filingPreviouslyInDB:
            self.showStatus("deleting prior messages of this report")
            # remove prior messages for this report
            self.lockTables(("message", "message_reference"))
            self.execute("DELETE from {0} "
                         "USING {1} "
                         "WHERE {1}.report_id = {2} AND {1}.message_id = {0}.message_id"
                         .format(self.dbTableName("message_reference"),
                                 self.dbTableName("message"),
                                 reportId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {} WHERE message.report_id = {}"
                         .format(self.dbTableName("message"),reportId), 
                         close=False, fetch=False)
        messages = []
        messageRefs = defaultdict(set) # direct link to objects
        for i, logEntry in enumerate(self.loggingEntries):
            sequenceInReport = i+1
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                # for now just find a concept
                objectId = None
                if isinstance(modelObject, ModelFact):
                    objectId = self.factId.get((self.documentIds.get(modelObject.modelDocument),
                                               elementChildSequence(modelObject)))
                elif isinstance(modelObject, ModelRelationship):
                    objectId = self.relSetId.get((modelObject.linkrole,
                                                  modelObject.arcrole,
                                                  modelObject.linkQname.clarkNotation,
                                                  modelObject.arcElement.qname.clarkNotation))
                elif isinstance(modelObject, ModelConcept):
                    objectId = self.conceptQnameId.get(modelObject.qname)
                elif isinstance(modelObject, ModelXbrl):
                    objectId = reportId
                elif hasattr(modelObject, "modelDocument"):
                    objectId = self.documentIds.get(modelObject.modelDocument)
                    
                if objectId is not None:
                    messageRefs[sequenceInReport].add(objectId)
                    
            messages.append((reportId,
                             sequenceInReport,
                             logEntry['code'],
                             logEntry['level'],
                             logEntry['message']['text']))
        if messages:
            self.showStatus("insert validation messages")
            table = self.getTable('message', 'message_id', 
                                  ('report_id', 'sequence_in_report', 'message_code', 'message_level', 'value'), 
                                  ('report_id', 'sequence_in_report'), 
                                  messages)
            messageIds = dict((sequenceInReport, messageId)
                              for messageId, _reportId, sequenceInReport in table)
            table = self.getTable('message_reference', None, 
                                  ('message_id', 'object_id'), 
                                  ('message_id', 'object_id'), 
                                  tuple((messageId, 
                                         objectId)
                                        for sequenceInReport, objectIds in messageRefs.items()
                                        for objectId in objectIds
                                        for messageId in (messageIds[sequenceInReport],)))
                        
countryOfState = {
    "AL": "US","AK": "US","AZ": "US","AR": "US","CA": "US","CO": "US", "CT": "US","DE": "US",
    "FL": "US","GA": "US","HI": "US","ID": "US","IL": "US","IN": "US","IA": "US","KS": "US",
    "KY": "US","LA": "US","ME": "US","MD": "US","MA": "US","MI": "US","MN": "US","MS": "US",
    "MO": "US","MT": "US","NE": "US","NV": "US","NH": "US","NJ": "US","NM": "US","NY": "US",
    "NC": "US","ND": "US","OH": "US","OK": "US","OR": "US","PA": "US","RI": "US","SC": "US",
    "SD": "US","TN": "US","TX": "US","UT": "US","VT": "US","VA": "US","WA": "US","WV": "US",
    "WI": "US","WY": "US","DC": "US","PR": "US","VI": "US","AS": "US","GU": "US","MP": "US",
    "AB": "CA","BC": "CA","MB": "CA","NB": "CA","NL": "CA","NS": "CA","ON": "CA","PE": "CA",
    "QC": "CA","SK": "CA","NT": "CA","NU": "CA","YT": "CA"}

