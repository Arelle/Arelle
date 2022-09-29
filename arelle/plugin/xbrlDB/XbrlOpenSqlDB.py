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


See COPYRIGHT.md for copyright information.


to use from command line:

linux
   # be sure plugin is installed
   arelleCmdLine --plugin '+xbrlDB|show'
   arelleCmdLine -f http://sec.org/somewhere/some.rss -v --store-to-XBRL-DB 'myserver.com,portnumber,pguser,pgpasswd,database,timeoutseconds'

windows
   rem be sure plugin is installed
   arelleCmdLine --plugin "+xbrlDB|show"
   arelleCmdLine -f http://sec.org/somewhere/some.rss -v --store-to-XBRL-DB "myserver.com,portnumber,pguser,pgpasswd,database,timeoutseconds"

examples of arguments:
   store from instance into DB: -f "my_traditional_instance.xbrl" -v --plugins "xbrlDB" --store-to-XBRL-DB "localhost,8084,userid,passwd,open_db,90,pgOpenDB"
   store from OIM excel instance into DB: -f "my_oim_instance.xlsx" -v --plugins "loadFromOIM.py|xbrlDB" --store-to-XBRL-DB "localhost,8084,userid,passwd,open_db,90,pgOpenDB"
   load from DB save into instance: -f "output_instance.xbrl" --plugins "xbrlDB" --load-from-XBRL-DB "localhost,8084,userid,passwd,open_db,90,pgOpenDB,loadInstanceId=214147"
'''

import os, time, datetime, logging
from arelle.ModelDocument import Type, create as createModelDocument
from arelle.ModelDtsObject import ModelConcept, ModelType, ModelResource, ModelRelationship
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelXbrl import ModelXbrl
from arelle.ModelDocument import ModelDocument
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname, QName, dateTime, DATETIME
from arelle.ModelRelationshipSet import ModelRelationshipSet
from arelle.PluginManager import pluginClassMethods
from arelle.PrototypeInstanceObject import DimValuePrototype
from arelle.PythonUtil import flattenSequence
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlValidate import collapseWhitespacePattern, UNVALIDATED, VALID
from arelle.XmlUtil import elementChildSequence, xmlstring, addQnameValue, addChild
from arelle import XbrlConst, ValidateXbrlDimensions
from arelle.UrlUtil import authority, ensureUrl
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from .tableFacts import tableFacts
from .entityInformation import loadEntityInformation
from .primaryDocumentFacts import loadPrimaryDocumentFacts
from collections import defaultdict


def insertIntoDB(modelXbrl,
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 loadDBsaveToFile=None, loadInstanceId=None,
                 product=None, entrypoint=None, rssItem=None, **kwargs):
    if getattr(modelXbrl, "blockOpenDBrecursion", False):
        return None
    xbrlDbConn = None
    result = True
    try:
        xbrlDbConn = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
        if "rssObject" in kwargs: # initialize batch
            xbrlDbConn.initializeBatch(kwargs["rssObject"])
        else:
            xbrlDbConn.verifyTables()
            if loadDBsaveToFile:
                # load modelDocument from database saving to file
                result = xbrlDbConn.loadXbrlFromDB(loadDBsaveToFile, loadInstanceId)
            else:
                xbrlDbConn.insertXbrl(entrypoint=entrypoint, rssItem=rssItem)
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
                "submission", "filing", "report",
                "document", "referenced_documents",
                "element", "data_type", "enumeration", "role_type", "arcrole_type",
                "resource", "reference_part", "relationship_set", "root", "relationship",
                "fact", "footnote", "entity_identifier", "period", "unit", "unit_measure", "aspect_value_set",
                "message", "message_reference",
                }



class XbrlSqlDatabaseConnection(SqlDbConnection):
    def verifyTables(self):
        allExtTables = set()
        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.TableDDLFiles"):
            allExtTables |= pluginXbrlMethod(self)[0]
        coreAndExtTables = XBRLDBTABLES | allExtTables
        presentTables = self.tablesInDB()
        # check for missing core tables and missing ext tables separately, ext tables can  be added by ext use later
        # if no tables, initialize database
        if not (presentTables & XBRLDBTABLES): # no core tables at all, initialize core tables
            # may have glob wildcard characters
            self.create(os.path.join("sql", "open", {"mssql": "xbrlOpenMSSqlDB.sql",
                                                     "mysql": "xbrlOpenMySqlDB.ddl",
                                                     "sqlite": "xbrlOpenSQLiteDB.ddl",
                                                     "orcl": "xbrlOpenOracleDB.sql",
                                                     "postgres": "xbrlOpenPostgresDB.ddl"}[self.product]))
            presentTables.clear() # db is cleared
        # for this extension, add extension tables if any ext's tables are missing
        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.TableDDLFiles"):
            _extTables, _extDdlFiles = pluginXbrlMethod(self)
            if not (presentTables & _extTables):
                self.create(_extDdlFiles, dropPriorTables=False)

        missingTables = coreAndExtTables - self.tablesInDB()
        if missingTables and missingTables != {"sequences"}:
            raise XPDBException("sqlDB:MissingTables",
                                _("The following tables are missing: %(missingTableNames)s"),
                                missingTableNames=', '.join(t for t in sorted(missingTables)))

    def insertXbrl(self, entrypoint, rssItem):
        try:
            # must also have default dimensions loaded
            from arelle import ValidateXbrlDimensions
            ValidateXbrlDimensions.loadDimensionDefaults(self.modelXbrl)

            # get logging entries (needed to find which elements to identify)
            self.loggingEntries = []
            for handler in logging.getLogger("arelle").handlers:
                if hasattr(handler, "dbHandlerLogEntries"):
                    self.loggingEntries = handler.dbHandlerLogEntries()
                    break

            # must have a valid XBRL instance or document
            if self.modelXbrl.modelDocument is None:
                raise XPDBException("xpgDB:MissingXbrlDocument",
                                    _("No XBRL instance or schema loaded for this filing."))

            # obtain ext metadata
            self.metadata = loadEntityInformation(self.modelXbrl, entrypoint, rssItem)
            for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.Metadata"):
                pluginXbrlMethod(self, entrypoint, rssItem)
            # identify table facts (table datapoints) (prior to locked database transaction
            self.tableFacts = tableFacts(self.modelXbrl)  # for EFM & HMRC this is ( (roleType, table_code, fact) )
            loadPrimaryDocumentFacts(self.modelXbrl, rssItem, self.metadata) # load primary document facts for SEC filing
            self.identifyTaxonomyRelSetsOwner()

            # at this point we determine what's in the database and provide new tables
            # requires locking most of the table structure
            self.lockTables(('filing', 'report', 'document', 'referenced_documents'),
                            isSessionTransaction=True) # lock for whole transaction

            # find pre-existing documents in server database
            self.identifyPreexistingDocuments()
            self.identifyElementsUsed()

            self.dropTemporaryTable()
            startedAt = time.time()
            self.syncSequences = True # for data base types that don't explicity handle sequences

            # schema-only submission is not a filing
            if self.modelXbrl.modelDocument.type != Type.SCHEMA:
                self.insertFiling()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Filing insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDocuments()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Documents insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertElements()
            self.modelXbrl.profileStat(_("XbrlSqlDB: Elements insertion"), time.time() - startedAt)
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
            if self.modelXbrl.modelDocument.type != Type.SCHEMA:
                self.insertFacts()
            self.modelXbrl.profileStat(_("XbrlSqlDB: instance insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertRelationships() # must follow data points for footnote relationships
            self.modelXbrl.profileStat(_("XbrlSqlDB: Relationships insertion"), time.time() - startedAt)
            startedAt = time.time()
            if self.modelXbrl.modelDocument.type != Type.SCHEMA:
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
                    if refDoc.inDTS and ref.referenceTypes & {"href", "import", "include"}:
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
        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.InitializeBatch"):
            pluginXbrlMethod(self, rssObject)


    def insertFiling(self):
        now = datetime.datetime.now()
        self.showStatus("insert submission")
        table = self.getTable('submission', 'submission_pk',
                              ('accepted_timestamp',
                               'loaded_timestamp' ),
                              ('submission_pk', ),
                              ((self.metadata.get("acceptedTimestamp") or now, # not null
                                now),)
                              )
        for submissionId, in table:
            self.submissionId = submissionId
            break

        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.ExtSubmission"):
            existingFilingId = pluginXbrlMethod(self, now)

        self.showStatus("insert filing")
        self.filingPk = None
        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.ExistingFilingPk"):
            self.filingPk = pluginXbrlMethod(self)
            if self.filingPk:
                break
        if self.filingPk is None:
            table = self.getTable('filing', 'filing_pk',
                                  ('filer_id',
                                   ),
                                  ('filing_pk',),
                                  ((self.metadata.get("filerId"),
                                    ),),
                                  )
            for pk, in table:
                self.filingPk = pk
        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.ExtFiling"):
            existingFilingId = pluginXbrlMethod(self, now)
        self.showStatus("insert report")
        self.reportPk = None
        self.filingPreviouslyInDB = False
        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.ExistingReportPk"):
            self.reportPk = pluginXbrlMethod(self)
            if self.reportPk:
                self.filingPreviouslyInDB = True
                break
        if self.reportPk is None:
            table = self.getTable('report', 'report_pk',
                                  ('submission_fk',
                                   'filing_fk',
                                   'report_id'
                                   ),
                                  ('filing_fk',),
                                  ((self.submissionId,
                                    self.filingPk,
                                    self.metadata.get("reportId")
                                    ),)
                                  )
            for pk, foundFilingId in table:
                self.reportPk = pk
                break

        for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.ExtReport"):
            existingFilingId = pluginXbrlMethod(self, now)

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
            results = self.execute("SELECT document_pk, url FROM {} WHERE url IN ({})"
                                   .format(self.dbTableName("document"),
                                           ', '.join(docUris)))
            self.existingDocumentIds = dict((self.urlDocs[self.pyStrFromDbStr(docUrl)],docId)
                                            for docId, docUrl in results)

            # identify whether taxonomyRelsSetsOwner is existing
            self.isExistingTaxonomyRelSetsOwner = (
                self.taxonomyRelSetsOwner.type not in (Type.INSTANCE, Type.INLINEXBRL, Type.INLINEXBRLDOCUMENTSET) and
                self.taxonomyRelSetsOwner in self.existingDocumentIds)

    def identifyElementsUsed(self):
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]


        elementsUsed = set(f.concept
                           for f in self.modelXbrl.factsInInstance)

        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                elementsUsed.add(dim.dimension)
                if dim.isExplicit:
                    elementsUsed.add(dim.member)
                else:
                    elementsUsed.add(self.modelXbrl.qnameConcepts[dim.typedMember.qname])
        for defaultDimQn, defaultDimMemberQn in self.modelXbrl.qnameDimensionDefaults.items():
            elementsUsed.add(self.modelXbrl.qnameConcepts[defaultDimQn])
            elementsUsed.add(self.modelXbrl.qnameConcepts[defaultDimMemberQn])
        for relationshipSetKey in self.relationshipSets:
            relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
            for rel in relationshipSet.modelRelationships:
                if isinstance(rel.fromModelObject, ModelConcept):
                    elementsUsed.add(rel.fromModelObject)
                _toObj = rel.toModelObject
                if isinstance(_toObj, ModelConcept):
                    elementsUsed.add(_toObj)
                if relationshipSetKey[0] == XbrlConst.conceptReference and isinstance(_toObj, ModelResource):
                    for referencePart in _toObj.iterchildren():
                        if isinstance(referencePart,ModelObject):
                            elementsUsed.add(referencePart.elementDeclaration())

        try:
            for qn in (XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit):
                elementsUsed.add(self.modelXbrl.qnameConcepts[qn])
        except KeyError:
            pass # no DTS

        for roleTypes in (self.modelXbrl.roleTypes.values(), self.modelXbrl.arcroleTypes.values()):
            for roleUriTypes in roleTypes:
                for roleType in roleUriTypes:
                    for qn in roleType.usedOns:
                        if qn in self.modelXbrl.qnameConcepts: # qname may be undefined or invalid and still 2.1 legal
                            elementsUsed.add(self.modelXbrl.qnameConcepts[qn])

        # add concepts referenced by logging entries
        for logEntry in self.loggingEntries:
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                if isinstance(modelObject, ModelConcept) and modelObject.modelDocument.inDTS:
                    elementsUsed.add(modelObject)

        # add substitution groups
        elementsUsed |= set(element.substitutionGroup
                            for element in elementsUsed
                            if element is not None)

        elementsUsed -= {None}  # remove None if in elementsUsed
        self.elementsUsed = elementsUsed

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

        for element in elementsUsed:
            modelType = element.type
            if modelType is not None:
                if modelType not in typesUsed:
                    typeUsed(modelType)
        self.typesUsed = typesUsed

    def insertDocuments(self):
        self.showStatus("insert documents")
        table = self.getTable('document', 'document_pk',
                              ('url', 'type', 'namespace'),
                              ('url',),
                              set((ensureUrl(docUrl),
                                   Type.typeName[mdlDoc.type],
                                   mdlDoc.targetNamespace)
                                  for docUrl, mdlDoc in self.modelXbrl.urlDocs.items()
                                  if mdlDoc not in self.existingDocumentIds and
                                     self.isSemanticDocument(mdlDoc)),
                              checkIfExisting=True)
        self.documentIds = dict((self.urlDocs[self.pyStrFromDbStr(url)], id)
                                for id, url in table)
        self.documentIds.update(self.existingDocumentIds)

        referencedDocuments = set()
        # instance documents are filing references
        # update report with document references
        for mdlDoc in self.modelXbrl.urlDocs.values():
            if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
                referencedDocuments.add( (self.reportPk, self.documentIds[mdlDoc] ))
            if mdlDoc in self.documentIds:
                for refDoc, ref in mdlDoc.referencesDocument.items():
                    if refDoc.inDTS and ref.referenceTypes & {"href", "import", "include"} \
                       and refDoc in self.documentIds:
                        referencedDocuments.add( (self.documentIds[mdlDoc], self.documentIds[refDoc] ))

        table = self.getTable('referenced_documents',
                              None, # no id column in this table
                              ('object_fk','document_fk'),
                              ('object_fk','document_fk'),
                              referencedDocuments,
                              checkIfExisting=True)

        instDocId = instSchemaDocId = creationSoftware = None
        mdlDoc = self.modelXbrl.modelDocument
        if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
            instDocId = self.documentIds[mdlDoc]
            creationSoftware = mdlDoc.creationSoftware
            # referenced doc may be extension schema
            for refDoc, ref in mdlDoc.referencesDocument.items():
                if refDoc.inDTS and "href" in ref.referenceTypes and refDoc in self.documentIds:
                    instSchemaDocId = self.documentIds[refDoc]
                    break
        elif mdlDoc.type == Type.SCHEMA:
            instDocSchemaDocId = self.documentIds[mdlDoc]

        if hasattr(self, "reportPk"): # if this is a filing and report exists, update it
            for mdlDoc in self.modelXbrl.urlDocs.values():
                if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
                    referencedDocuments.add( (self.reportPk, self.documentIds[mdlDoc] ))
            self.updateTable("report",
                             ("report_pk", "report_data_doc_fk", 'creation_software',
                              "report_schema_doc_fk"),
                             ((self.reportPk, instDocId, creationSoftware,
                               instSchemaDocId),)
                            )
            for pluginXbrlMethod in pluginClassMethods("xbrlDB.Open.Ext.ExtReportUpdate"):
                existingFilingId = pluginXbrlMethod(self)


    def insertElements(self):
        self.showStatus("insert elements")

        # determine new filing documents and types they use
        filingDocumentElements = set()
        existingDocumentUsedElements = set()
        for element in self.modelXbrl.qnameConcepts.values():
            if element.modelDocument not in self.existingDocumentIds:
                filingDocumentElements.add(element)
                filingDocumentElementType = element.type
                if filingDocumentElementType is not None and filingDocumentElementType not in self.typesUsed:
                        self.typesUsed.add(filingDocumentElementType)
            elif element in self.elementsUsed:
                existingDocumentUsedElements.add(element)

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
            table = self.getTable('data_type', 'data_type_pk',
                                  ('document_fk', 'qname',),
                                  ('document_fk', 'qname',),
                                  tuple((self.documentIds[modelType.modelDocument],
                                         modelType.qname.clarkNotation)
                                        for modelType in existingDocumentUsedTypes
                                        if modelType.modelDocument in self.documentIds),
                                  checkIfExisting=True,
                                  insertIfNotMatched=False)
            for typeId, docId, qn in table:
                self.typeQnameId[qname(qn)] = typeId

        table = self.getTable('data_type', 'data_type_pk',
                              ('document_fk', 'xml_id', 'xml_child_seq',
                               'qname', 'name', 'base_type', 'derived_from_type_fk'),
                              ('document_fk', 'qname',),
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

        if any(modelType.facets.get("enumeration") # might be an empty enumeration dict
               for modelType in filingDocumentTypes
               if modelType.modelDocument in self.documentIds
               if modelType.facets is not None):
            # note: do we have to remove pre-existing facets for dataType if it was there before?
            table = self.getTable('enumeration',
                                  None, # no record id in this table
                                  ('data_type_fk', 'document_fk', 'value'),
                                  ('data_type_fk', 'document_fk'),
                                  tuple((self.typeQnameId[modelType.qname],
                                         self.documentIds[modelType.modelDocument],
                                         enumValue)
                                        for modelType in filingDocumentTypes
                                        if modelType.modelDocument in self.documentIds
                                        if modelType.facets is not None and "enumeration" in modelType.facets
                                        for enumValue in modelType.facets.get("enumeration"))
                                 )

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
                             ('data_type_pk', 'derived_from_type_fk'),
                             updatesToDerivedFrom)

        existingDocumentUsedTypes.clear() # dereference
        filingDocumentTypes.clear() # dereference

        self.elementQnameId = {}

        # get existing element IDs
        if existingDocumentUsedElements:
            table = self.getTable('element', 'element_pk',
                                  ('document_fk', 'qname',),
                                  ('document_fk', 'qname',),
                                  tuple((self.documentIds[element.modelDocument],
                                         element.qname.clarkNotation)
                                        for element in existingDocumentUsedElements
                                        if element.modelDocument in self.documentIds),
                                  checkIfExisting=True,
                                  insertIfNotMatched=False)
            for elementId, docId, qn in table:
                self.elementQnameId[qname(qn)] = elementId

        elements = []
        unreferencedDocumentsElements = []
        for element in filingDocumentElements:
            niceType  = element.niceType
            if niceType is not None and len(niceType) > 128:
                niceType = niceType[:128]
            if element.modelDocument in self.documentIds:
                elements.append((self.documentIds[element.modelDocument],
                                element.id,
                                elementChildSequence(element),
                                element.qname.clarkNotation,
                                element.name,
                                self.typeQnameId.get(element.typeQname),
                                niceType[:128] if niceType is not None else None,
                                self.elementQnameId.get(element.substitutionGroupQname),
                                element.balance,
                                element.periodType,
                                element.isAbstract,
                                element.isNillable,
                                element.isNumeric,
                                element.isMonetary,
                                element.isTextBlock))
            else:
                unreferencedDocumentsElements.append(element.qname)
        table = self.getTable('element', 'element_pk',
                              ('document_fk', 'xml_id', 'xml_child_seq',
                               'qname', 'name', 'datatype_fk', 'base_type', 'substitution_group_element_fk',
                               'balance', 'period_type', 'abstract', 'nillable',
                               'is_numeric', 'is_monetary', 'is_text_block'),
                              ('document_fk', 'qname'),
                              elements
                             )
        for elementId, docId, qn in table:
            self.elementQnameId[qname(qn)] = elementId

        if unreferencedDocumentsElements:
            results = self.execute("SELECT element_pk, qname FROM {} WHERE qname IN ({})"
                                   .format(self.dbTableName("element"),
                                           ', '.join(self.dbStr(qn.clarkNotation) for qn in unreferencedDocumentsElements)))
            for elementId, qn in results:
                self.elementQnameId[qname(qn)] = elementId

            # report on unmatched QNames
            unmatchedElements = set(qn for qn in unreferencedDocumentsElements if qn not in self.elementQnameId)
            if unmatchedElements:
                self.modelXbrl.info("xpDB:warning",
                                    _("Loading XBRL DB: Elements not found in DTS or database: %(unmatchedElements)s"),
                                    modelObject=self.modelXbrl,
                                    unmatchedElements=", ".join(sorted(str(qn) for qn in unmatchedElements)))

        updatesToSubstitutionGroup = set()
        for element in filingDocumentElements:
            if element.substitutionGroup in filingDocumentElements and element.modelDocument in self.documentIds:
                updatesToSubstitutionGroup.add( (self.elementQnameId[element.qname],
                                                 self.elementQnameId.get(element.substitutionGroupQname)) )
        # update derivedFrom's of newly added types
        if updatesToSubstitutionGroup:
            self.updateTable('element',
                             ('element_pk', 'substitution_group_element_fk'),
                             updatesToSubstitutionGroup)

        # enumerations
        # TBD

        filingDocumentElements.clear() # dereference
        existingDocumentUsedElements.clear() # dereference

    def insertArcroleTypes(self):
        self.showStatus("insert arcrole types")
        # add existing arcrole types
        arcroleTypesByIds = set((self.documentIds[arcroleType.modelDocument],
                                 arcroleType.roleURI) # key on docId, uriId
                                for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                for arcroleType in arcroleTypes
                                if arcroleType.modelDocument in self.existingDocumentIds)
        table = self.getTable('arcrole_type', 'arcrole_type_pk',
                              ('document_fk', 'arcrole_uri'),
                              ('document_fk', 'arcrole_uri'),
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
        table = self.getTable('arcrole_type', 'arcrole_type_pk',
                              ('document_fk', 'xml_id', 'xml_child_seq', 'arcrole_uri', 'cycles_allowed', 'definition'),
                              ('document_fk', 'arcrole_uri'),
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
                              ('object_fk', 'element_fk'),
                              ('object_fk', 'element_fk'),
                              tuple((self.arcroleTypeIds[(arcroleTypeIDs[0], arcroleType.arcroleURI)],
                                     self.elementQnameId[usedOnQn])
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()
                                    for usedOnQn in arcroleType.usedOns
                                    if usedOnQn in self.elementQnameId),
                              checkIfExisting=True)

    def insertRoleTypes(self):
        self.showStatus("insert role types")
        # add existing role types
        roleTypesByIds = set((self.documentIds[roleType.modelDocument],
                              roleType.roleURI) # key on docId, uriId
                              for roleTypes in self.modelXbrl.roleTypes.values()
                              for roleType in roleTypes
                              if roleType.modelDocument in self.existingDocumentIds)
        table = self.getTable('role_type', 'role_type_pk',
                              ('document_fk', 'role_uri'),
                              ('document_fk', 'role_uri'),
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
        table = self.getTable('role_type', 'role_type_pk',
                              ('document_fk', 'xml_id', 'xml_child_seq', 'role_uri', 'definition'),
                              ('document_fk', 'role_uri'),
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
                              ('object_fk', 'element_fk'),
                              ('object_fk', 'element_fk'),
                              tuple((self.roleTypeIds[(roleTypeIDs[0], roleType.roleURI)],
                                     self.elementQnameId[usedOnQn])
                                    for roleTypeIDs, roleType in roleTypesByIds.items()
                                    for usedOnQn in roleType.usedOns
                                    if usedOnQn in self.elementQnameId),
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
                               for resource in (rel.fromModelObject, rel.toModelObject)
                               if isinstance(resource, ModelResource))
        table = self.getTable('resource', 'resource_pk',
                              ('document_fk', 'xml_id', 'xml_child_seq', 'qname', 'role', 'value', 'xml_lang'),
                              ('document_fk', 'xml_child_seq'),
                              tuple((self.documentIds[resource.modelDocument],
                                     resource.id,
                                     elementChildSequence(resource),
                                     resource.qname.clarkNotation,
                                     resource.role,
                                     resource.stringValue,
                                     resource.xmlLang)
                                    for resource in uniqueResources.values()),
                              checkIfExisting=True)
        self.resourceId = dict(((docId, xml_child_seq), id)
                               for id, docId, xml_child_seq in table)

        # is there a need to delete prior-existing reference parts??
        if any(isinstance(referencePart,ModelObject)
               for resource in uniqueResources.values()
               for referencePart in resource.iterchildren()):
            table = self.getTable('reference_part',
                                  None, # no record id in this table
                                  ('resource_pk', 'document_fk', 'xml_child_seq', 'element_fk', 'value'),
                                  ('resource_pk', 'document_fk'),
                                  tuple((self.resourceId[(self.documentIds[resource.modelDocument], elementChildSequence(resource))],
                                         self.documentIds[resource.modelDocument],
                                         elementChildSequence(referencePart),
                                         self.elementQnameId.get(referencePart.qname), # null if element not in DB or referenced properly
                                         referencePart.textValue)
                                        for resource in uniqueResources.values()
                                        for referencePart in resource.iterchildren()
                                        if isinstance(referencePart,ModelObject)),
                                  checkIfExisting=True)
        uniqueResources.clear()


    def modelObjectId(self, modelObject):
        if isinstance(modelObject, ModelConcept):
            return self.elementQnameId.get(modelObject.qname)
        elif isinstance(modelObject, ModelType):
            return self.elementTypeIds.get(modelObject.qname)
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
        table = self.getTable('relationship_set', 'relationship_set_pk',
                              ('document_fk', 'link_role', 'arc_role', 'link_qname', 'arc_qname'),
                              ('document_fk', 'link_role', 'arc_role', 'link_qname', 'arc_qname'),
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

        table = self.getTable('relationship', 'relationship_pk',
                              ('document_fk', 'xml_id', 'xml_child_seq',
                               'relationship_set_fk', 'reln_order',
                               'from_fk', 'to_fk', 'calculation_weight',
                               'tree_sequence', 'tree_depth', 'preferred_label_role'),
                              ('relationship_set_fk', 'document_fk', 'xml_child_seq'),
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
                              ('relationship_set_fk', 'relationship_fk'),
                              ('relationship_set_fk', 'relationship_fk'),
                              tuple((relSetId,
                                     self.relationshipId[self.documentIds[rel.modelDocument],
                                                         elementChildSequence(rel.arcElement)])
                                    for rel, sequence, depth, relSetId in dbRels
                                    if depth == 1 and
                                       isinstance(rel.fromModelObject, ModelObject) and isinstance(rel.toModelObject, ModelObject)))
        del dbRels[:]   # dererefence

    def insertFacts(self):
        reportFk = self.reportPk
        if self.filingPreviouslyInDB:
            self.showStatus("deleting prior facts of this report")
            # remove prior facts
            self.lockTables(("fact", "entity_identifier", "period", "unit_measure", "unit",
                             "aspect_value_set", "aspect_value_report_set", # report_set is for id assignment
                             "footnote" "table_facts"))
            for _tableName, _st, _id, _sf in (("entity_identifier", "_pk", "entity_identifier", "_fk"),
                                              ("period", "_pk", "period", "_fk"),
                                              ("unit", "_pk", "unit", "_fk"),
                                              ("unit_measure", "_pk", "unit", "_fk"),
                                              ("aspect_value_report_set", "_pk", "aspect_value_set", "_fk"),
                                              ("aspect_value_set", "_fk", "aspect_value_set", "_fk"),
                                              ("footnote", "_fk", "fact", "_pk")):
                #print("DELETE from {0} "
                #             "USING {1} "
                #             "WHERE {1}.report_fk = {2} AND {0}.{3}{4} = {1}.{3}{5}"
                #             .format( self.dbTableName(_tableName),
                #                      self.dbTableName("fact"),
                #                      reportFk,
                #                      _id, _st, _sf))
                self.execute("DELETE from {0} "
                             "USING {1} "
                             "WHERE {1}.report_fk = {2} AND {0}.{3}{4} = {1}.{3}{5}"
                             .format( self.dbTableName(_tableName),
                                      self.dbTableName("fact"),
                                      reportFk,
                                      _id, _st, _sf),
                             close=False, fetch=False)
            for _tableName in ("fact", "table_facts"):
                self.execute("DELETE FROM {0} WHERE {0}.report_fk = {1}"
                             .format( self.dbTableName(_tableName), reportFk),
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
        table = self.getTable('unit', 'unit_pk',
                              ('xml_id', 'xml_child_seq', 'measures_hash'),
                              ('measures_hash',),
                              tuple((unit.id, # unit's xml_id
                                     elementChildSequence(unit),
                                     unit.md5hash)
                                    for unit in unitsUsed.values()))
        self.unitId = dict((_measuresHash, id)
                           for id, _measuresHash in table)
        # measures
        table = self.getTable('unit_measure',
                              None,
                              ('unit_pk', 'qname', 'is_multiplicand'),
                              ('unit_pk', 'qname', 'is_multiplicand'),
                              tuple((self.unitId[unit.md5hash],
                                     measure.clarkNotation,
                                     i == 0)
                                    for unit in unitsUsed.values()
                                    for i in range(2)
                                    for measure in unit.measures[i]))
        table = self.getTable('entity_identifier', 'entity_identifier_pk',
                              ('scheme', 'identifier'),
                              ('scheme', 'identifier'),
                              set((cntx.entityIdentifier[0],
                                   cntx.entityIdentifier[1])
                                for cntx in contextsUsed)) # not shared across reports
        self.entityIdentifierId = dict(((entScheme, entIdent), id)
                                       for id, entScheme, entIdent in table)
        table = self.getTable('period', 'period_pk',
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
            return frozenset((self.elementQnameId[modelDimValue.dimensionQname],
                              self.elementQnameId.get(modelDimValue.memberQname), # null if typed
                              modelDimValue.isTyped,
                              None if not modelDimValue.isTyped else ( # typed_value is null if not typed dimension
                              modelDimValue.typedMember.xValue.clarkNotation # if typed member is QName use clark name because QName is not necessarily a element in the DTS
                                 if (modelDimValue.typedMember is not None and getattr(modelDimValue.typedMember, "xValid", UNVALIDATED) >= VALID and isinstance(modelDimValue.typedMember.xValue,QName))
                                 else modelDimValue.stringValue)) # otherwise typed member is string value of the typed member
                             for modelDimValue in cntx.qnameDims.values()
                             if modelDimValue.dimensionQname in self.elementQnameId)

        cntxAspectValueSets = dict((cntx, cntxDimsSet(cntx))
                                   for cntx in contextsUsed)

        aspectValueSelections = set(aspectValueSelectionSet
                                    for cntx, aspectValueSelectionSet in cntxAspectValueSets.items()
                                    if aspectValueSelectionSet)
        # allocate an aspect_value_set_id for each aspect_value_set in report (independent of SQL of database)
        table = self.getTable('aspect_value_report_set', 'aspect_value_set_pk',
                              ('report_fk', ),
                              ('report_fk', ),
                              tuple((reportFk,)
                                    for aspectValueSelection in aspectValueSelections)
                              )
        # assure we only get single entry per result (above gives cross product)
        table = self.execute("SELECT aspect_value_set_pk, report_fk FROM {0} "
                             "WHERE report_fk = {1}"
                             .format(self.dbTableName("aspect_value_report_set"), reportFk))
        aspectValueReportSets = dict((aspectValueSelections.pop(), id)
                                     for id, _reportFk in table)

        cntxAspectValueSetId = dict((cntx, aspectValueReportSets[_cntxDimsSet])
                                    for cntx, _cntxDimsSet in cntxAspectValueSets.items()
                                    if _cntxDimsSet)

        table = self.getTable('aspect_value_set',
                              None,
                              ('aspect_value_set_fk', 'aspect_element_fk', 'aspect_value_fk', 'is_typed_value', 'typed_value'),
                              ('aspect_value_set_fk', ),
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
                    facts.append((reportFk,
                                  documentId,
                                  fact.id, # fact's xml_id
                                  elementChildSequence(fact),
                                  fact.sourceline,
                                  tupleFactId, # tuple (parent) fact's database fact_id
                                  self.elementQnameId.get(fact.qname),
                                  fact.contextID,
                                  self.entityIdentifierId.get((cntx.entityIdentifier[0], cntx.entityIdentifier[1]))
                                      if cntx is not None else None,
                                  self.periodId.get((
                                                cntx.startDatetime if cntx.isStartEndPeriod else None,
                                                cntx.endDatetime if (cntx.isStartEndPeriod or cntx.isInstantPeriod) else None,
                                                cntx.isInstantPeriod,
                                                cntx.isForeverPeriod)) if cntx is not None else None,
                                  cntxAspectValueSetId.get(cntx) if cntx is not None else None,
                                  self.unitId.get(fact.unit.md5hash) if fact.unit is not None else None,
                                  fact.isNil,
                                  fact.precision,
                                  fact.decimals,
                                  roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric and not fact.isNil else None,
                                  fact.xmlLang if not fact.isNumeric and not fact.isNil else None,
                                  collapseWhitespacePattern.sub(' ', fact.value.strip()) if fact.value is not None else None,
                                  fact.value,
                                  ))
            table = self.getTable('fact', 'fact_pk',
                                  ('report_fk', 'document_fk', 'xml_id', 'xml_child_seq', 'source_line',
                                   'tuple_fact_fk',  # tuple
                                   'element_fk',
                                   'context_xml_id', 'entity_identifier_fk', 'period_fk', 'aspect_value_set_fk', 'unit_fk',
                                   'is_nil', 'precision_value', 'decimals_value', 'effective_value',
                                   'language', 'normalized_string_value', 'value'),
                                  ('document_fk', 'xml_child_seq'),
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
                    _tableFacts.append((reportFk,
                                        self.roleTypeIds[(self.documentIds[roleType.modelDocument],
                                                          roleType.roleURI)],
                                        tableCode,
                                        self.factId[(self.documentIds[fact.modelDocument],
                                                     elementChildSequence(fact))]))
                except KeyError:
                    # print ("missing table facts role or fact")
                    pass
            table = self.getTable('table_facts', None,
                                  ('report_fk', 'object_fk', 'table_code', 'fact_fk'),
                                  ('report_fk', 'object_fk', 'fact_fk'),
                                  _tableFacts)

        # footnotes
        footnotesRelationshipSet = ModelRelationshipSet(self.modelXbrl, "XBRL-footnotes")
        table = self.getTable('footnote', None,
                              ('fact_fk', 'footnote_group', 'type', 'footnote_value_fk', 'language', 'normalized_string_value', 'value'),
                              ('fact_fk', 'footnote_group', 'type', 'footnote_value_fk', 'language', 'normalized_string_value', 'value'),
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
        reportFk = self.reportPk

        if self.filingPreviouslyInDB:
            self.showStatus("deleting prior messages of this report")
            # remove prior messages for this report
            self.lockTables(("message", "message_reference"))
            self.execute("DELETE from {0} "
                         "USING {1} "
                         "WHERE {1}.report_fk = {2} AND {1}.message_pk = {0}.message_fk"
                         .format(self.dbTableName("message_reference"),
                                 self.dbTableName("message"),
                                 reportFk),
                         close=False, fetch=False)
            self.execute("DELETE FROM {} WHERE message.report_fk = {}"
                         .format(self.dbTableName("message"),reportFk),
                         close=False, fetch=False)
        messages = []
        messageRefs = defaultdict(set) # direct link to objects
        for i, logEntry in enumerate(self.loggingEntries):
            sequenceInReport = i+1
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                # for now just find a element
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
                    objectId = self.elementQnameId.get(modelObject.qname)
                elif isinstance(modelObject, ModelXbrl):
                    objectId = reportFk
                elif hasattr(modelObject, "modelDocument"):
                    objectId = self.documentIds.get(modelObject.modelDocument)

                if objectId is not None:
                    messageRefs[sequenceInReport].add(objectId)

            messages.append((reportFk,
                             sequenceInReport,
                             logEntry['code'],
                             logEntry['level'],
                             logEntry['message']['text']))
        if messages:
            self.showStatus("insert validation messages")
            table = self.getTable('message', 'message_pk',
                                  ('report_fk', 'sequence_in_report', 'message_code', 'message_level', 'value'),
                                  ('report_fk', 'sequence_in_report'),
                                  messages)
            messageIds = dict((sequenceInReport, messageId)
                              for messageId, _reportFk, sequenceInReport in table)
            table = self.getTable('message_reference', None,
                                  ('message_fk', 'object_fk'),
                                  ('message_fk', 'object_fk'),
                                  tuple((messageId,
                                         objectId)
                                        for sequenceInReport, objectIds in messageRefs.items()
                                        for objectId in objectIds
                                        for messageId in (messageIds[sequenceInReport],)))

    def loadXbrlFromDB(self, loadDBsaveToFile, loadreportPk):
        # load from database
        modelXbrl = self.modelXbrl

        # find instance in DB
        self.showStatus("finding loadreportPk in database")
        if loadreportPk and loadreportPk.isnumeric():
            # use report ID to get specific report
            results = self.execute("SELECT r.report_pk, d.url FROM report r, document d "
                                   "WHERE r.report_pk = {} AND r.report_schema_doc_fk = d.document_fk"
                                   .format(loadreportPk))
        else:
            # use filename to get instance
            instanceURI = os.path.basename(loadDBsaveToFile)
            results = self.execute("SELECT r.report_pk, d.url FROM report r, document d "
                                   "WHERE r.report_schema_doc_fk = d.document_fk")
        for reportPk, xbrlSchemaRef in results:
            break
        if not reportPk:
            raise DpmDBException("sqlDB:MissingReport",
                    _("The report was not found in table report"))
        if not xbrlSchemaRef:
            raise DpmDBException("sqlDB:MissingSchemaRef",
                    _("The report schemaRef was not found in table report"))

        # create the instance document and resulting filing
        modelXbrl.blockOpenDBrecursion = True
        modelXbrl.modelDocument = createModelDocument(
              modelXbrl,
              Type.INSTANCE,
              loadDBsaveToFile,
              schemaRefs=[xbrlSchemaRef],
              isEntry=True,
              initialComment="Generated by Arelle(r) for Data Act project",
              documentEncoding="utf-8")
        ValidateXbrlDimensions.loadDimensionDefaults(modelXbrl) # needs dimension defaults

        prefixes = modelXbrl.prefixedNamespaces
        prefixes["iso4217"] = XbrlConst.iso4217
        prefixes["xbrli"] = XbrlConst.xbrli
        prefixes[None] = XbrlConst.xbrli # createInstance expects default prefix for xbrli
        # make prefixes reverse lookupable for qname function efficiency
        prefixes.update(dict((ns,prefix) for prefix, ns in prefixes.items()))

        # add roleRef and arcroleRef (e.g. for footnotes, if any, see inlineXbrlDocue)

        cntxTbl = {} # index by d
        unitTbl = {}


        # facts in this instance
        self.showStatus("finding facts in database")
        factsTbl = self.execute(_(
                               "SELECT f.fact_pk, fc.qname, f.value, f.decimals_value, "
                               "avd.qname AS dim_name, avm.qname AS mem_name, av.typed_value, "
                               "um.qname AS u_measure, um.is_multiplicand AS u_mul,p.start_date, p.end_date, p.is_instant, "
                               "ei.scheme, ei.identifier "
                               "FROM fact f "
                               "JOIN element fc ON f.element_fk = fc.element_pk "
                               "AND f.report_fk = {} "
                               "LEFT JOIN aspect_value_set av ON av.aspect_value_set_pk = f.aspect_value_set_fk "
                               "JOIN element avd ON av.aspect_element_fk = avd.element_pk "
                               "LEFT JOIN element avm ON av.aspect_value_fk = avm.element_pk "
                               "LEFT JOIN unit_measure um ON um.unit_pk = f.unit_fk "
                               "LEFT JOIN period p ON p.period_pk = f.period_fk "
                               "LEFT JOIN entity_identifier ei ON ei.entity_identifier_pk = f.entity_identifier_fk ")
                               .format(reportPk))
        prevId = None
        factRows = []
        cntxTbl = {}
        unitTbl = {}

        def storeFact():
            unitMul = set()
            unitDiv = set()
            dims = set()
            for _dbFactId, _qname, _value, _decimals, _dimQName, _memQName, _typedValue, \
                _unitMeasure, _unitIsMul, \
                _perStart, _perEnd, _perIsInstant, \
                _scheme, _identifier in factRows:
                if _unitMeasure:
                    if _unitIsMul:
                        unitMul.add(_unitMeasure)
                    else:
                        unitDiv.add(_unitMeasure)
                if _dimQName:
                    dims.add((_dimQName, _memQName, _typedValue))

            cntxKey = (_perStart, _perEnd, _perIsInstant, _scheme, _identifier) + tuple(sorted(dims))
            if cntxKey in cntxTbl:
                _cntx = cntxTbl[cntxKey]
            else:
                cntxId = 'c-{:02}'.format(len(cntxTbl) + 1)
                qnameDims = {}
                for _dimQn, _memQn, _dimVal in dims:
                    dimQname = qname(_dimQn, prefixes)
                    dimConcept = modelXbrl.qnameConcepts.get(dimQname)
                    if _memQn:
                        mem = qname(_memQn, prefixes) # explicit dim
                    elif dimConcept.isTypedDimension:
                        # a modelObject xml element is needed for all of the instance functions to manage the typed dim
                        mem = addChild(modelXbrl.modelDocument, dimConcept.typedDomainElement.qname, text=_dimVal, appendChild=False)
                    qnameDims[dimQname] = DimValuePrototype(modelXbrl, None, dimQname, mem, "segment")
                _cntx = modelXbrl.createContext(
                                        _scheme,
                                        _identifier,
                                        ("duration","instant")[_perIsInstant],
                                        None if _perIsInstant else dateTime(_perStart, type=DATETIME),
                                        dateTime(_perEnd, type=DATETIME),
                                        None, # no dimensional validity checking (like formula does)
                                        qnameDims, [], [],
                                        id=cntxId)
                cntxTbl[cntxKey] = _cntx


            if unitMul or unitDiv:
                unitKey = (tuple(sorted(unitMul)),tuple(sorted(unitDiv)))
                if unitKey in unitTbl:
                    unit = unitTbl[unitKey]
                else:
                    mulQns = [qname(u, prefixes) for u in sorted(unitMul) if u]
                    divQns = [qname(u, prefixes) for u in sorted(unitDiv) if u]
                    unitId = 'u-{:02}'.format(len(unitTbl) + 1)
                    for _measures in mulQns, divQns:
                        for _measure in _measures:
                            addQnameValue(modelXbrl.modelDocument, _measure)
                    unit = modelXbrl.createUnit(mulQns, divQns, id=unitId)
                    unitTbl[unitKey] = unit
            else:
                unit = None

            attrs = {"contextRef": _cntx.id}

            conceptQn = qname(_qname,prefixes)
            concept = modelXbrl.qnameConcepts.get(conceptQn)

            if _value is None or (
                len(_value) == 0 and concept.baseXbrliType not in ("string", "normalizedString", "token")):
                attrs[XbrlConst.qnXsiNil] = "true"
                text = None
            else:
                text = _value
            if concept.isNumeric:
                if unit is not None:
                    attrs["unitRef"] = unit.id
                if _decimals:
                    attrs["decimals"] = _decimals

            # is value a QName?
            if concept.baseXbrliType == "QName":
                addQnameValue(modelXbrl.modelDocument, qname(text.strip(), prefixes))

            f = modelXbrl.createFact(conceptQn, attributes=attrs, text=text)

            del factRows[:]

        prevId = None
        for fact in factsTbl:
            id = fact[0]
            if id != prevId and prevId:
                storeFact()
            factRows.append(fact)
            prevId = id
        if prevId and factRows:
            storeFact()


        self.showStatus("saving XBRL instance")
        modelXbrl.saveInstance(overrideFilepath=loadDBsaveToFile, encoding="utf-8")
        self.showStatus(_("Saved extracted instance"), 5000)
        return modelXbrl.modelDocument
