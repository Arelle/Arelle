'''
XbrlSemanticSqlDB.py implements an SQL database interface for Arelle, based
on a concrete realization of the Abstract Model PWD 2.0 layer.  This is a semantic 
representation of XBRL information. 

This module may save directly to a Postgres, MySQL, MSSQL, or Oracle server.

This module provides the execution context for saving a dts and instances in 
XBRL JSON graph.  It may be loaded by Arelle's RSS feed, or by individual
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
from arelle.ModelValue import qname
from arelle.ValidateXbrlCalcs import roundValue
from arelle.XmlUtil import elementFragmentIdentifier
from arelle import XbrlConst
from arelle.UrlUtil import ensureUrl
from .SqlDb import XPDBException, isSqlConnection, SqlDbConnection
from collections import defaultdict


def insertIntoDB(modelXbrl, 
                 user=None, password=None, host=None, port=None, database=None, timeout=None,
                 product=None, rssItem=None):
    xpgdb = None
    try:
        xpgdb = XbrlSqlDatabaseConnection(modelXbrl, user, password, host, port, database, timeout, product)
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
    
def isDBPort(host, port, timeout=10, product="postgres"):
    return isSqlConnection(host, port, timeout)

XBRLDBTABLES = {
                "sequences",
                "filing", "report",
                "document", "referenced_documents",
                "aspect", "data_type", "role_type", "arcrole_type",
                "resource", "relationship_set", "relationship",
                "data_point", "entity", "period", "unit", "unit_measure", "aspect_value_selection",
                "message", "message_reference",
                "industry", "industry_level", "industry_structure",
                }



class XbrlSqlDatabaseConnection(SqlDbConnection):
    def verifyTables(self):
        missingTables = XBRLDBTABLES - self.tablesInDB()
        # if no tables, initialize database
        if missingTables == XBRLDBTABLES:
            self.create({"mssql": "xbrlSemanticMssqlDB.ddl",
                         "mysql": "xbrlSemanticMySqlDB.ddl",
                         "orcl": "xbrlSemanticOrclDB.ddl",
                         "postgres": "xbrlSemanticSqlDB.ddl"}[self.product])
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
                        
            # find pre-existing documents in server database
            self.identifyPreexistingDocuments()
            self.identifyAspectsUsed()
            
            startedAt = time.time()
            self.dropTemporaryTable()
            self.insertFiling(rssItem)
            self.insertDocuments()
            self.insertAspects()
            self.insertArcroleTypes()
            self.insertRoleTypes()
            self.insertResources()
            self.insertRelationships()
            self.modelXbrl.profileStat(_("XbrlSqlDB: DTS insertion"), time.time() - startedAt)
            startedAt = time.time()
            self.insertDataPoints()
            self.modelXbrl.profileStat(_("XbrlSqlDB: instance insertion"), time.time() - startedAt)
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
            
    def insertFiling(self, rssItem):
        self.showStatus("insert filing")
        if rssItem is None:
            now = datetime.datetime.now()
            table = self.getTable('filing', 'filing_id', 
                                  ('filing_number', 'accepted_timestamp', 'is_most_current', 'filing_date','entity_id', 
                                   'entity_name', 'creation_software', 'standard_industry_code', 
                                   'authority_html_url', 'entry_url', ), 
                                  ('filing_number',), 
                                  ((str(int(time.time())),  # NOT NULL
                                    now,
                                    True,
                                    now,  # NOT NULL
                                    0,  # NOT NULL
                                    '',
                                    self.modelXbrl.modelDocument.creationSoftwareComment,
                                    -1,  # NOT NULL
                                    None,
                                    None,
                                    ),),
                                  checkIfExisting=True,
                                  returnExistenceStatus=True)
        else:
            table = self.getTable('filing', 'filing_id', 
                                  ('filing_number', 'accepted_timestamp', 'is_most_current', 'filing_date','entity_id', 
                                   'entity_name', 'creation_software', 'standard_industry_code', 
                                   'authority_html_url', 'entry_url', ), 
                                  ('filing_number',), 
                                  ((rssItem.accessionNumber or str(int(time.time())),  # NOT NULL
                                    rssItem.acceptanceDatetime,
                                    True,
                                    rssItem.filingDate or datetime.datetime.min,  # NOT NULL
                                    rssItem.cikNumber or 0,  # NOT NULL
                                    rssItem.companyName,
                                    self.modelXbrl.modelDocument.creationSoftwareComment,
                                    rssItem.assignedSic or -1,  # NOT NULL
                                    rssItem.htmlUrl,
                                    rssItem.url
                                    ),),
                                  checkIfExisting=True,
                                  returnExistenceStatus=True)
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
        
    def identifyPreexistingDocuments(self):
        self.existingDocumentIds = {}
        docUris = set()
        for modelDocument in self.modelXbrl.urlDocs.values():
            docUris.add(self.dbStr(ensureUrl(modelDocument.uri)))
        if docUris:
            results = self.execute("SELECT document_id, document_url FROM {} WHERE document_url IN ({})"
                                   .format(self.dbTableName("document"),
                                           ', '.join(docUris)))
            self.existingDocumentIds = dict((docUri,docId) for docId, docUri in results)
        
    def identifyAspectsUsed(self):
        # relationshipSets are a dts property
        self.relationshipSets = [(arcrole, ELR, linkqname, arcqname)
                                 for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                 if ELR and (arcrole.startswith("XBRL-") or (linkqname and arcqname))]

        
        aspectsUsed = set(f.concept
                          for f in self.modelXbrl.factsInInstance)
        
        for cntx in self.modelXbrl.contexts.values():
            for dim in cntx.qnameDims.values():
                aspectsUsed.add(dim.dimension)
                if dim.isExplicit:
                    aspectsUsed.add(dim.member)
                else:
                    aspectsUsed.add(self.modelXbrl.qnameConcepts[dim.typedMember.qname])
        for defaultDimQn, defaultDimMemberQn in self.modelXbrl.qnameDimensionDefaults.items():
            aspectsUsed.add(self.modelXbrl.qnameConcepts[defaultDimQn])
            aspectsUsed.add(self.modelXbrl.qnameConcepts[defaultDimMemberQn])
        for relationshipSetKey in self.relationshipSets:
            relationshipSet = self.modelXbrl.relationshipSet(*relationshipSetKey)
            for rel in relationshipSet.modelRelationships:
                if isinstance(rel.fromModelObject, ModelConcept):
                    aspectsUsed.add(rel.fromModelObject)
                if isinstance(rel.toModelObject, ModelConcept):
                    aspectsUsed.add(rel.toModelObject)
        for qn in (XbrlConst.qnXbrliIdentifier, XbrlConst.qnXbrliPeriod, XbrlConst.qnXbrliUnit):
            aspectsUsed.add(self.modelXbrl.qnameConcepts[qn])

        for roleTypes in (self.modelXbrl.roleTypes.values(), self.modelXbrl.arcroleTypes.values()):
            for roleUriTypes in roleTypes:
                for roleType in roleUriTypes:
                    for qn in roleType.usedOns:
                        aspectsUsed.add(self.modelXbrl.qnameConcepts[qn])
        
        aspectsUsed -= {None}  # remove None if in conceptsUsed
        self.aspectsUsed = aspectsUsed
    
        typesUsed = set()
        def typeUsed(modelType):
            if modelType is not None:
                typesUsed.add(modelType)
                typesDerivedFrom = modelType.typeDerivedFrom
                if isinstance(typesDerivedFrom, list): # union derivation
                    for typeDerivedFrom in typesDerivedFrom:
                        if typeDerivedFrom not in typesUsed:
                            typeUsed(typeDerivedFrom)
                else: # single derivation
                    if typesDerivedFrom is not None and typesDerivedFrom not in typesUsed:
                        typeUsed(typesDerivedFrom)
                    
        for aspect in aspectsUsed:
            modelType = aspect.type
            if modelType is not None:
                if modelType not in typesUsed:
                    typeUsed(modelType)
        self.typesUsed = typesUsed
        
    def insertDocuments(self):
        self.showStatus("insert documents")
        table = self.getTable('document', 'document_id', 
                              ('document_url', 'document_type', 'namespace'), 
                              ('document_url',), 
                              set((uri,
                                   mdlDoc.type,
                                   mdlDoc.targetNamespace) 
                                  for docUri, mdlDoc in self.modelXbrl.urlDocs.items()
                                  for uri in (ensureUrl(docUri),)
                                  if uri not in self.existingDocumentIds),
                              checkIfExisting=True)
        self.documentIds = dict((uri, id)
                                for id, uri in table)
        self.documentIds.update(self.existingDocumentIds)

        referencedDocuments = set()
        # instance documents are filing references
        for mdlDoc in self.modelXbrl.urlDocs.values():
            uri = ensureUrl(mdlDoc.uri)
            if mdlDoc.type in (Type.INSTANCE, Type.INLINEXBRL):
                referencedDocuments.add( (self.reportId, self.documentIds[uri] ))
            if uri in self.documentIds and uri not in self.existingDocumentIds:
                for refDoc, ref in mdlDoc.referencesDocument.items():
                    if refDoc.inDTS and ref.referenceType in ("href", "import", "include") \
                       and ensureUrl(refDoc.uri) in self.documentIds:
                        referencedDocuments.add( (self.documentIds[uri], self.documentIds[ensureUrl(refDoc.uri)] ))
        
        table = self.getTable('referenced_documents', 
                              None, # no id column in this table 
                              ('object_id','document_id'), 
                              ('object_id','document_id'), 
                              referencedDocuments,
                              checkIfExisting=True)

        
    def insertAspects(self):
        self.showStatus("insert aspects")
        
        filingDocumentTypes = set()
        existingDocumentUsedTypes = set()
        for modelType in self.modelXbrl.qnameTypes.values():
            if ensureUrl(modelType.modelDocument.uri) not in self.existingDocumentIds:
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
                                  tuple((self.documentIds[ensureUrl(modelType.modelDocument.uri)],
                                         modelType.qname.clarkNotation)
                                        for modelType in existingDocumentUsedTypes),
                                  checkIfExisting=True,
                                  insertIfNotMatched=False)
            for typeId, docId, qn in table:
                self.typeQnameId[qname(qn)] = typeId
        
        table = self.getTable('data_type', 'data_type_id', 
                              ('document_id', 'xml_id',
                               'qname', 'name', 'base_type', 'derived_from_type_id'), 
                              ('document_id', 'qname',), 
                              tuple((self.documentIds[ensureUrl(modelType.modelDocument.uri)],
                                     elementFragmentIdentifier(modelType),
                                     modelType.qname.clarkNotation,
                                     modelType.name,
                                     modelType.baseXsdType,
                                     self.typeQnameId.get(modelType.typeDerivedFrom)
                                     if isinstance(modelType.typeDerivedFrom, ModelType) else None)
                                    for modelType in filingDocumentTypes)
                             )
        for typeId, docId, qn in table:
            self.typeQnameId[qname(qn)] = typeId
        
        updatesToDerivedFrom = set()
        for modelType in filingDocumentTypes:
            if isinstance(modelType.typeDerivedFrom, ModelType) and modelType.typeDerivedFrom in filingDocumentTypes:
                updatesToDerivedFrom.add( (self.typeQnameId[modelType.qname], 
                                           self.typeQnameId[modelType.typeDerivedFrom.qname]) )
        # update derivedFrom's of newly added types
        if updatesToDerivedFrom:
            self.updateTable('data_type', 
                             ('data_type_id', 'derived_from_type_id'),
                             updatesToDerivedFrom)
            
        existingDocumentUsedTypes.clear() # dereference
        filingDocumentTypes.clear() # dereference

        filingDocumentAspects = set()
        existingDocumentUsedAspects = set()
        for concept in self.modelXbrl.qnameConcepts.values():
            if ensureUrl(concept.modelDocument.uri) not in self.existingDocumentIds:
                filingDocumentAspects.add(concept)
            elif concept in self.aspectsUsed:
                existingDocumentUsedAspects.add(concept)
                
        self.aspectQnameId = {}
        
        # get existing element IDs
        if existingDocumentUsedAspects:
            table = self.getTable('aspect', 'aspect_id', 
                                  ('document_id', 'qname',), 
                                  ('document_id', 'qname',), 
                                  tuple((self.documentIds[ensureUrl(concept.modelDocument.uri)],
                                         concept.qname.clarkNotation)
                                        for concept in existingDocumentUsedAspects),
                                  checkIfExisting=True,
                                  insertIfNotMatched=False)
            for aspectId, docId, qn in table:
                self.aspectQnameId[qname(qn)] = aspectId
                
        table = self.getTable('aspect', 'aspect_id', 
                              ('document_id', 'xml_id',
                               'qname', 'name', 'datatype_id', 'base_type', 'substitution_group_aspect_id',  
                               'balance', 'period_type', 'abstract', 'nillable',
                               'is_numeric', 'is_monetary', 'is_text_block'), 
                              ('document_id', 'qname'), 
                              tuple((self.documentIds[ensureUrl(concept.modelDocument.uri)],
                                     elementFragmentIdentifier(concept),
                                     concept.qname.clarkNotation,
                                     concept.name,
                                     self.typeQnameId.get(concept.typeQname),
                                     concept.niceType,
                                     self.aspectQnameId.get(concept.substitutionGroupQname),
                                     concept.balance,
                                     concept.periodType,
                                     concept.isAbstract, 
                                     concept.isNillable,
                                     concept.isNumeric,
                                     concept.isMonetary,
                                     concept.isTextBlock)
                                    for concept in filingDocumentAspects)
                             )
        for aspectId, docId, qn in table:
            self.aspectQnameId[qname(qn)] = aspectId
            
        updatesToSubstitutionGroup = set()
        for concept in filingDocumentAspects:
            if concept.substitutionGroup in filingDocumentAspects:
                updatesToSubstitutionGroup.add( (self.aspectQnameId[concept.qname], 
                                                 self.aspectQnameId[concept.substitutionGroupQname]) )
        # update derivedFrom's of newly added types
        if updatesToSubstitutionGroup:
            self.updateTable('aspect', 
                             ('aspect_id', 'substitution_group_aspect_id'),
                             updatesToSubstitutionGroup)
            
        filingDocumentAspects.clear() # dereference
        existingDocumentUsedAspects.clear() # dereference
                   
    def insertArcroleTypes(self):
        self.showStatus("insert arcrole types")
        arcroleTypesByIds = dict(((self.documentIds[ensureUrl(arcroleType.modelDocument.uri)],
                                   arcroleType.arcroleURI), # key on docId, uriId
                                  arcroleType) # value is roleType object
                                 for arcroleTypes in self.modelXbrl.arcroleTypes.values()
                                 for arcroleType in arcroleTypes
                                 if ensureUrl(arcroleType.modelDocument.uri) not in self.existingDocumentIds)
        table = self.getTable('arcrole_type', 'arcrole_type_id', 
                              ('document_id', 'xml_id', 'arcrole_uri', 'cycles_allowed', 'definition'), 
                              ('document_id', 'arcrole_uri'), 
                              tuple((arcroleTypeIDs[0], # doc Id
                                     elementFragmentIdentifier(arcroleType),
                                     arcroleType.arcroleURI,
                                     arcroleType.cyclesAllowed,
                                     arcroleType.definition)
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()))
        
        self.arcroleTypeIds = {}
        for arcroleId, docId, uri in table:
            self.arcroleTypeIds[(docId, uri)] = arcroleId
            
        table = self.getTable('used_on', 
                              None, # no record id in this table  
                              ('object_id', 'aspect_id'), 
                              ('object_id', 'aspect_id'), 
                              tuple((self.arcroleTypeIds[(arcroleTypeIDs[0], arcroleType.arcroleURI)], 
                                     self.aspectQnameId[usedOnQn])
                                    for arcroleTypeIDs, arcroleType in arcroleTypesByIds.items()
                                    for usedOnQn in arcroleType.usedOns
                                    if usedOnQn in self.aspectQnameId),
                              checkIfExisting=True)
        
    def insertRoleTypes(self):
        self.showStatus("insert role types")
        roleTypesByIds = dict(((self.documentIds[ensureUrl(roleType.modelDocument.uri)],
                                roleType.roleURI), # key on docId, uriId
                               roleType) # value is roleType object
                              for roleTypes in self.modelXbrl.roleTypes.values()
                              for roleType in roleTypes
                              if ensureUrl(roleType.modelDocument.uri) not in self.existingDocumentIds)
        table = self.getTable('role_type', 'role_type_id', 
                              ('document_id', 'xml_id', 'role_uri', 'definition'), 
                              ('document_id', 'role_uri'), 
                              tuple((roleTypeIDs[0], # doc Id
                                     elementFragmentIdentifier(roleType),
                                     roleTypeIDs[1], # uri Id
                                     roleType.definition) 
                                    for roleTypeIDs, roleType in roleTypesByIds.items()))
        self.roleTypeIds = {}
        for roleId, docId, uri in table:
            self.roleTypeIds[(docId, uri)] = roleId
            
        table = self.getTable('used_on', 
                              None, # no record id in this table  
                              ('object_id', 'aspect_id'), 
                              ('object_id', 'aspect_id'), 
                              tuple((self.roleTypeIds[(roleTypeIDs[0], roleType.roleURI)], 
                                     self.aspectQnameId[usedOnQn])
                                    for roleTypeIDs, roleType in roleTypesByIds.items()
                                    for usedOnQn in roleType.usedOns
                                    if usedOnQn in self.aspectQnameId),
                              checkIfExisting=True)
        
    def insertResources(self):
        self.showStatus("insert resources")
        # deduplicate resources (may be on multiple arcs)
        # note that lxml has no column numbers, use objectIndex as pseudo-column number
        uniqueResources = dict(((self.documentIds[ensureUrl(resource.modelDocument.uri)],
                                 resource.objectIndex), resource)
                               for arcrole in (XbrlConst.conceptLabel, XbrlConst.conceptReference)
                               for rel in self.modelXbrl.relationshipSet(arcrole).modelRelationships
                               if rel.fromModelObject is not None and rel.toModelObject is not None
                               for resource in (rel.fromModelObject, rel.toModelObject)
                               if isinstance(resource, ModelResource))
        table = self.getTable('resource', 'resource_id', 
                              ('document_id', 'xml_id', 'qname', 'role', 'value', 'xml_lang'), 
                              ('document_id', 'xml_id'), 
                              tuple((self.documentIds[ensureUrl(resource.modelDocument.uri)],
                                     elementFragmentIdentifier(resource),
                                     resource.qname.clarkNotation,
                                     resource.role,
                                     resource.textValue,
                                     resource.xmlLang)
                                    for resource in uniqueResources.values()),
                              checkIfExisting=True)
        self.resourceId = dict(((docId, xml_id), id)
                               for id, docId, xml_id in table)
        uniqueResources.clear()
        
                
    def modelObjectId(self, modelObject):
        if isinstance(modelObject, ModelConcept):
            return self.aspectQnameId.get(modelObject.qname)
        elif isinstance(modelObject, ModelType):
            return self.aspectTypeIds.get(modelObject.qname)
        elif isinstance(modelObject, ModelResource):
            return self.resourceId.get((self.documentIds[ensureUrl(modelObject.modelDocument.uri)],
                                        elementFragmentIdentifier(modelObject)))
        else:
            return None 
    
    def insertRelationships(self):
        self.showStatus("insert relationship sets")
        table = self.getTable('relationship_set', 'relationship_set_id', 
                              ('report_id', 'arc_qname', 'link_qname', 'arc_role', 'link_role'), 
                              ('report_id', 'arc_qname', 'link_qname', 'arc_role', 'link_role'), 
                              tuple((self.reportId,
                                     arcqname.clarkNotation,
                                     linkqname.clarkNotation,
                                     arcrole,
                                     ELR)
                                    for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys()
                                    if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-")))
        self.relSetId = dict(((arcQn, lnkQn, arcRole, linkRole), id)
                             for id, reportId, arcQn, lnkQn, arcRole, linkRole in table)
        # do tree walk to build relationships with depth annotated, no targetRole navigation
        dbRels = []
        
        def walkTree(rels, seq, depth, relationshipSet, visited, dbRels, relSetId):
            for rel in rels:
                if rel not in visited and rel.toModelObject is not None:
                    visited.add(rel)
                    dbRels.append((rel, seq, depth, relSetId))
                    seq += 1
                    seq = walkTree(relationshipSet.fromModelObject(rel.toModelObject), seq, depth+1, relationshipSet, visited, dbRels, relSetId)
                    visited.remove(rel)
            return seq
        
        for arcrole, ELR, linkqname, arcqname in self.modelXbrl.baseSets.keys():
            if ELR and linkqname and arcqname and not arcrole.startswith("XBRL-"):
                relSetId = self.relSetId[(arcqname.clarkNotation,
                                          linkqname.clarkNotation,
                                          arcrole,
                                          ELR)]
                relationshipSet = self.modelXbrl.relationshipSet(arcrole, ELR, linkqname, arcqname)
                seq = 1               
                for rootConcept in relationshipSet.rootConcepts:
                    seq = walkTree(relationshipSet.fromModelObject(rootConcept), seq, 1, relationshipSet, set(), dbRels, relSetId)

        def resourceResourceId(resource):
            if isinstance(resource, ModelResource):
                return self.resourceId.get((self.documentIds[ensureUrl(resource.modelDocument.uri)],
                                            resource.sourceline, 
                                            resource.objectIndex))
            else:
                return None     
        
        table = self.getTable('relationship', 'relationship_id', 
                              ('report_id', 'document_id', 'xml_id', 
                               'relationship_set_id', 'reln_order', 
                               'from_id', 'to_id', 'calculation_weight', 
                               'tree_sequence', 'tree_depth', 'preferred_label_role'), 
                              ('relationship_set_id', 'document_id', 'xml_id'), 
                              tuple((self.reportId,
                                     self.documentIds[ensureUrl(rel.modelDocument.uri)],
                                     elementFragmentIdentifier(rel.arcElement),
                                     relSetId,
                                     self.dbNum(rel.order),
                                     self.modelObjectId(rel.fromModelObject),
                                     self.modelObjectId(rel.toModelObject),
                                     self.dbNum(rel.weight), # none if no weight
                                     sequence,
                                     depth,
                                     rel.preferredLabel)
                                    for rel, sequence, depth, relSetId in dbRels
                                    if rel.fromModelObject is not None and rel.toModelObject is not None))
        self.relationshipId = dict(((docId,xmlId), relationshipId)
                                   for relationshipId, relSetId, docId, xmlId in table)
        del dbRels[:]   # dererefence

    def insertDataPoints(self):
        reportId = self.reportId
        if self.filingPreviouslyInDB:
            self.showStatus("deleting prior data points of this report")
            # remove prior facts
            self.execute("DELETE FROM {0} WHERE {0}.report_id = {1}"
                         .format( self.dbTableName("data_point"), reportId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {0} WHERE {0}.report_id = {1}" 
                         .format( self.dbTableName("entity"), reportId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {0} WHERE {0}.report_id = {1}"
                         .format( self.dbTableName("period"), reportId), 
                         close=False, fetch=False)
            self.execute("DELETE from {0} "
                         "USING {1} "
                         "WHERE {1}.report_id = {2} AND {0}.aspect_value_selection_id = {1}.aspect_value_selection_id" 
                         .format( self.dbTableName("aspect_value_selection"), 
                                  self.dbTableName("aspect_value_selection_set"), 
                                  reportId), 
                         close=False, fetch=False)
            self.execute("DELETE FROM {0} WHERE {0}.report_id = {1};"
                         .format( self.dbTableName("aspect_value_selection_set"), reportId), 
                         close=False, fetch=False)
            self.execute("DELETE from {0} "
                         "USING {1} "
                         "WHERE {1}.report_id = {2} AND {0}.unit_id = {1}.unit_id"
                         .format( self.dbTableName("unit_measure"), 
                                  self.dbTableName("unit"), 
                                  reportId), 
                         close=False, fetch=False)
            self.execute("DELETE from {0} WHERE {0}.report_id = {1}"
                         .format( self.dbTableName("unit"), reportId), 
                         close=False, fetch=False)
        self.showStatus("insert data points")
        # units
        table = self.getTable('unit', 'unit_id', 
                              ('report_id', 'xml_id'), 
                              ('report_id', 'xml_id'), 
                              tuple((reportId,
                                     unitId)
                                    for unitId in self.modelXbrl.units.keys()))
        self.unitId = dict(((_reportId, xmlId), id)
                           for id, _reportId, xmlId in table)
        # measures
        table = self.getTable('unit_measure', 
                              None, 
                              ('unit_id', 'qname', 'is_multiplicand'), 
                              ('unit_id', 'qname', 'is_multiplicand'), 
                              tuple((self.unitId[(reportId,unit.id)],
                                     measure.clarkNotation,
                                     i == 0)
                                    for unit in self.modelXbrl.units.values()
                                    for i in range(2)
                                    for measure in unit.measures[i]))
        table = self.getTable('entity', 'entity_id', 
                              ('report_id', 'entity_scheme', 'entity_identifier'), 
                              ('report_id', 'entity_scheme', 'entity_identifier'), 
                              set((reportId,
                                   cntx.entityIdentifier[0],
                                   cntx.entityIdentifier[1])
                                for cntx in self.modelXbrl.contexts.values()))
        self.entityId = dict(((_reportId, entScheme, entIdent), id)
                             for id, _reportId, entScheme, entIdent in table)
        table = self.getTable('period', 'period_id', 
                              ('report_id', 'start_date', 'end_date', 'is_instant', 'is_forever'), 
                              ('report_id', 'start_date', 'end_date', 'is_instant', 'is_forever'), 
                              set((reportId,
                                   cntx.startDatetime if cntx.isStartEndPeriod else None,
                                   cntx.endDatetime if cntx.isStartEndPeriod else None,
                                   cntx.isInstantPeriod,
                                   cntx.isForeverPeriod)
                                for cntx in self.modelXbrl.contexts.values()))
        self.periodId = dict(((_reportId, start, end, isInstant, isForever), id)
                             for id, _reportId, start, end, isInstant, isForever in table)
        
        def cntxDimsSet(cntx):
            return frozenset((self.aspectQnameId[modelDimValue.dimensionQname],
                              self.aspectQnameId.get(modelDimValue.memberQname),
                              modelDimValue.isTyped,
                              modelDimValue.stringValue if modelDimValue.isTyped else None)
                             for modelDimValue in cntx.qnameDims.values())
        
        cntxAspectValueSelectionSet = dict((cntx, cntxDimsSet(cntx))
                                            for cntx in self.modelXbrl.contexts.values())
        
        aspectValueSelections = set(aspectValueSelectionSet
                                    for cntx, aspectValueSelectionSet in cntxAspectValueSelectionSet.items()
                                    if aspectValueSelectionSet)
        self.execute("DELETE FROM {0} WHERE report_id = {1}"
                     .format(self.dbTableName("aspect_value_selection_set"), reportId), 
                     close=False, fetch=False)
        table = self.getTable('aspect_value_selection_set', 'aspect_value_selection_id', 
                              ('report_id',), 
                              ('report_id',), 
                              tuple((reportId,)
                                    for aspectValueSelection in aspectValueSelections)
                              )
        # assure we only get single entry per result (above gives cross product)
        table = self.execute("SELECT aspect_value_selection_id, report_id from {0} "
                             "WHERE report_id = {1}"
                             .format(self.dbTableName("aspect_value_selection_set"), reportId))
        aspectValueSelectionSets = dict((aspectValueSelections.pop(), id)
                                        for id, _reportId in table)
        
        cntxAspectValueSelectionSetId = dict((cntx, aspectValueSelectionSets[_cntxDimsSet])
                                             for cntx, _cntxDimsSet in cntxAspectValueSelectionSet.items()
                                             if _cntxDimsSet)
                                    
        table = self.getTable('aspect_value_selection', 
                              None, 
                              ('aspect_value_selection_id', 'report_id', 'aspect_id', 'aspect_value_id', 'is_typed_value', 'typed_value'), 
                              ('aspect_value_selection_id', ), 
                              tuple((aspectValueSetId, reportId, dimId, dimMbrId, isTyped, typedValue)
                                    for aspectValueSelection, aspectValueSetId in aspectValueSelectionSets.items()
                                    for dimId, dimMbrId, isTyped, typedValue in aspectValueSelection)
                              )

        # facts
        def insertFactSet(modelFacts, parentDatapointId):
            table = self.getTable('data_point', 'datapoint_id', 
                                  ('report_id', 'document_id', 'xml_id', 'source_line', 
                                   'parent_datapoint_id',  # tuple
                                   'aspect_id',
                                   'context_xml_id', 'entity_id', 'period_id', 'aspect_value_selections_id', 'unit_id',
                                   'is_nil', 'precision_value', 'decimals_value', 'effective_value', 'value'), 
                                  ('document_id', 'xml_id'), 
                                  tuple((reportId,
                                         self.documentIds[ensureUrl(fact.modelDocument.uri)],
                                         elementFragmentIdentifier(fact),
                                         fact.sourceline,
                                         parentDatapointId, # parent ID
                                         self.aspectQnameId.get(fact.qname),
                                         fact.contextID,
                                         self.entityId.get((reportId, cntx.entityIdentifier[0], cntx.entityIdentifier[1]))
                                             if cntx is not None else None,
                                         self.periodId.get((reportId,
                                                            cntx.startDatetime if cntx.isStartEndPeriod else None,
                                                            cntx.endDatetime if cntx.isStartEndPeriod else None,
                                                            cntx.isInstantPeriod,
                                                            cntx.isForeverPeriod)) if cntx is not None else None,
                                         cntxAspectValueSelectionSetId.get(cntx) if cntx is not None else None,
                                         self.unitId.get((reportId,fact.unitID)),
                                         fact.isNil,
                                         fact.precision,
                                         fact.decimals,
                                         roundValue(fact.value, fact.precision, fact.decimals) if fact.isNumeric and not fact.isNil else None,
                                         fact.value
                                         )
                                        for fact in modelFacts
                                        for cntx in (fact.context,)))
            xmlIdDataPointId = dict(((docId, xmlId), datapointId)
                                    for datapointId, docId, xmlId in table)
            self.factDataPointId.update(xmlIdDataPointId)
            for fact in modelFacts:
                if fact.isTuple:
                    insertFactSet(fact.modelTupleFacts, 
                                  xmlIdDataPointId[(self.documentIds[ensureUrl(fact.modelDocument.uri)],
                                                    elementFragmentIdentifier(fact))])
        self.factDataPointId = {}
        insertFactSet(self.modelXbrl.facts, None)
        # hashes

    def insertValidationResults(self):
        reportId = self.reportId
        logEntries = []
        for handler in logging.getLogger("arelle").handlers:
            if hasattr(handler, "dbHandlerLogEntries"):
                logEntries = handler.dbHandlerLogEntries()
                break
        
        if self.filingPreviouslyInDB:
            self.showStatus("deleting prior messages of this report")
            # remove prior messages for this report
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
        for i, logEntry in enumerate(logEntries):
            sequenceInReport = i+1
            for ref in logEntry['refs']:
                modelObject = self.modelXbrl.modelObject(ref.get('objectId',''))
                # for now just find a concept
                objectId = None
                if isinstance(modelObject, ModelFact):
                    objectId = self.factPointId[(self.documentIds[ensureUrl(modelObject.modelDocument.uri)],
                                                 elementFragmentIdentifier(modelObject))]
                elif isinstance(modelObject, ModelRelationship):
                    objectId = self.factPointId[(self.documentIds[ensureUrl(modelObject.modelDocument.uri)],
                                                 elementFragmentIdentifier(modelObject.arcElement))]
                elif isinstance(modelObject, ModelConcept):
                    objectId = self.aspectQnameId[modelObject.qname]
                elif isinstance(modelObject, ModelXbrl):
                    objectId = reportId
                elif hasattr(modelObject, "modelDocument"):
                    objectId = self.documentIds[ensureUrl(modelObject.modelDocument.uri)]
                    
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
                        
